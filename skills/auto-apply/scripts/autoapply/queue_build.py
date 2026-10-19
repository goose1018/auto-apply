"""Hard-rule screening -> apply_queue.jsonl (BRIEF §3 "必跳过并记账", R1, R8, D7, D13). Business layer.

The script applies only deterministic rules and writes reason codes; match scoring and "is this a good
fit" stay with the Screening Agent. D7: nothing enters apply_queue.jsonl without user approval, so a
candidate is queued only when
  (a) its `screening.decision` is already "approved" in candidates.jsonl, or
  (b) the caller passes an explicit approval note (`--approve-all "<user's words>"`), optionally with
      `--exclude job_id,...`.
Everything else that passes the hard rules is listed as `pending_approval` for the shortlist.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from autoapply import enums
from autoapply.dedup import check_key, load_aliases, normalize_job_obj, read_jsonl, job_record_from_obj
from autoapply.errors import ProfileError, SchemaError, UsageError
from autoapply.ids import new_app_id, now_iso
from autoapply.ledger import ApplicationRecord, add_event, create_application, log_write, stats, upsert_job
from autoapply.normalize import make_dedup_key, normalize_company
from autoapply.paths import DataPaths
from autoapply.schema_validate import SchemaSet

DEGREE_RANK: dict[str, int] = {"diploma": 1, "bachelor": 2, "master": 3, "phd": 4}


@dataclass
class Screened:
    job_id: str
    company: str
    title: str
    decision: str  # skip | dedup_hit | dedup_review | recommend | approved | excluded_by_user
    reason_code: str | None
    reason: str
    dedup_match: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"job_id": self.job_id, "company": self.company, "title": self.title, "decision": self.decision,
                "reason_code": self.reason_code, "reason": self.reason, "dedup_match": self.dedup_match}


@dataclass
class QueueBuildResult:
    queued: list[dict[str, Any]] = field(default_factory=list)
    pending_approval: list[Screened] = field(default_factory=list)
    review: list[Screened] = field(default_factory=list)
    skipped: list[Screened] = field(default_factory=list)
    screened_path: Path | None = None
    queue_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": {"queued": len(self.queued), "pending_approval": len(self.pending_approval),
                       "review": len(self.review), "skipped": len(self.skipped)},
            "queued": self.queued,
            "pending_approval": [s.to_dict() for s in self.pending_approval],
            "review": [s.to_dict() for s in self.review],
            "skipped": [s.to_dict() for s in self.skipped],
            "screened_path": str(self.screened_path) if self.screened_path else None,
            "queue_path": str(self.queue_path) if self.queue_path else None,
        }


def load_profile(paths: DataPaths, schemas: SchemaSet) -> dict[str, Any]:
    p = paths.profile_json
    if not p.is_file():
        raise ProfileError("profile.json 不存在，请先完成问诊 / profile.json missing; run intake first", {"path": str(p)})
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ProfileError("profile.json 不是合法 JSON / corrupt profile.json") from e
    schemas.require("profile", data, "profile.json")
    return data


def _ym(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or len(value) < 7:
        return None
    try:
        return int(value[:4]), int(value[5:7])
    except ValueError:
        return None


def _months(ym: tuple[int, int]) -> int:
    return ym[0] * 12 + ym[1]


def _rule_names(rules: list[Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    today = date.today().isoformat()
    for r in rules or []:
        if not isinstance(r, dict) or not r.get("name"):
            continue
        until = r.get("until")
        if isinstance(until, str) and until < today:
            continue  # expired rule
        try:
            out.append((normalize_company(str(r["name"])), r))
        except UsageError as e:
            raise ProfileError("profile.rules 中的公司名无法规范化 / company rule name cannot be normalised", {"name": str(r["name"])}) from e
    return out


def _highest_degree(profile: dict[str, Any]) -> tuple[str | None, str | None]:
    """(highest degree in profile, degree of the is_current programme)."""
    best: str | None = None
    current: str | None = None
    for e in profile.get("education") or []:
        d = str(e.get("degree") or "")
        if d in DEGREE_RANK and (best is None or DEGREE_RANK[d] > DEGREE_RANK[best]):
            best = d
        if e.get("is_current"):
            current = d if d in DEGREE_RANK else current
    return best, current


def apply_hard_rules(job: dict[str, Any], profile: dict[str, Any], today: date) -> tuple[str | None, str]:
    """Return (skip_reason_code, reason) or (None, 'pass')."""
    rules = profile.get("rules") or {}
    intent = profile.get("intent") or {}
    salary = profile.get("salary") or {}
    status = profile.get("status") or {}
    materials = profile.get("materials") or {}
    hc = job.get("hard_conditions") or {}
    company_norm = str(job["company"]["normalized"])
    title_raw = str(job["title"]["raw"]).lower()

    for norm, rule in _rule_names(rules.get("company_blacklist") or []):
        if norm == company_norm:
            return "blacklist", "company on blacklist%s" % (": " + str(rule["reason"]) if rule.get("reason") else "")
    reserve = _rule_names(rules.get("reserve_for_referral") or [])
    for norm, rule in reserve:
        if norm == company_norm:
            return "reserve_for_referral", "company reserved for referral"
    for sub in rules.get("title_exclusions") or []:
        if str(sub).lower() in title_raw:
            return "title_excluded", "title contains excluded term '%s'" % sub
    for sub in intent.get("excluded_directions") or []:
        if str(sub).lower() in title_raw:
            return "title_excluded", "title matches excluded direction '%s'" % sub

    closes = job.get("closes_at")
    if isinstance(closes, str) and closes[:10] < today.isoformat():
        return "job_closed", "posting closed on %s" % closes[:10]

    if hc.get("requires_local_id") is True:
        return "id_number_required", "application requires NRIC/FIN (never filled)"

    gq = rules.get("global_quota_rule") or {}
    if hc.get("global_quota") is True:
        mode = gq.get("mode", "ignore")
        if mode == "skip_all_global_quota":
            return "global_quota", "global-quota posting (rule: skip all)"
        if mode == "skip_if_in_reserve_list" and any(n == company_norm for n, _ in reserve):
            return "global_quota", "global-quota posting at a reserve-list company"

    sal = hc.get("salary") or {}
    if sal.get("unpaid") is True and salary.get("allow_unpaid") is not True:
        return "unpaid", "unpaid posting and profile does not allow unpaid"
    floor = salary.get("hard_floor")
    if isinstance(floor, (int, float)) and sal.get("disclosed") is True:
        job_max = sal.get("max") if sal.get("max") is not None else sal.get("min")
        same_currency = not sal.get("currency") or not salary.get("currency") or str(sal["currency"]).upper() == str(salary["currency"]).upper()
        same_period = not sal.get("period") or not salary.get("period") or sal["period"] == salary["period"]
        if isinstance(job_max, (int, float)) and same_currency and same_period and job_max < floor:
            return "salary_below_floor", "disclosed max %s below hard floor %s" % (job_max, floor)
    if sal.get("disclosed") is False and salary.get("apply_if_undisclosed") is False:
        return "other", "salary undisclosed and profile says do not apply when undisclosed"

    best, current = _highest_degree(profile)
    req = hc.get("degree_required")
    if isinstance(req, str) and req in DEGREE_RANK and best in DEGREE_RANK and DEGREE_RANK[req] > DEGREE_RANK[best]:
        return "degree_mismatch", "requires %s, profile highest is %s" % (req, best)
    if hc.get("bachelor_only") is True and (current or best) != "bachelor" and intent.get("apply_to_bachelor_only_postings") is not True:
        return "degree_mismatch", "bachelor-only posting; profile does not opt in"
    if hc.get("accepts_master") is False and (current or best) == "master":
        return "degree_mismatch", "posting does not accept master's students"

    wpr = hc.get("work_pass_requirement")
    wp = status.get("work_pass")
    if wpr == "citizen_only" and wp not in (None, "citizen"):
        return "work_pass_mismatch", "citizens only"
    if wpr == "citizen_pr_only" and wp not in (None, "citizen", "permanent_resident"):
        return "work_pass_mismatch", "citizens / PR only"
    if wpr == "no_sponsorship" and status.get("requires_sponsorship_now") is True:
        return "work_pass_mismatch", "no sponsorship offered but sponsorship needed now"

    lang = hc.get("resume_language_required")
    if isinstance(lang, str):
        have = {str(r.get("language")) for r in materials.get("resumes") or []}
        if lang not in have:
            return "resume_language_missing", "needs a %s resume; profile has %s" % (lang, ", ".join(sorted(have)) or "none")

    window = intent.get("window") or {}
    istart, iend = _ym(window.get("start")), _ym(window.get("end"))
    tol = int(round(float(window.get("flexibility_weeks") or 0) / 4.33))
    jw = hc.get("work_window") or {}
    jstart, jend = _ym(jw.get("start")), _ym(jw.get("end"))
    if istart and jend and _months(jend) < _months(istart) - tol:
        return "date_window_mismatch", "posting ends %s before availability starts %s" % (jw.get("end"), window.get("start"))
    if iend and jstart and _months(jstart) > _months(iend) + tol:
        return "date_window_mismatch", "posting starts %s after availability ends %s" % (jw.get("start"), window.get("end"))
    if hc.get("start_immediately") is True and istart and _months(istart) > today.year * 12 + today.month + 1:
        return "start_immediately", "posting wants immediate start; availability starts %s" % window.get("start")
    return None, "pass"


def build_queue(
    conn: sqlite3.Connection,
    paths: DataPaths,
    schemas: SchemaSet,
    run_id: str,
    candidates: Path,
    *,
    out_path: Path | None = None,
    approve_all_note: str | None = None,
    exclude_job_ids: set[str] | None = None,
    today: date | None = None,
) -> QueueBuildResult:
    profile = load_profile(paths, schemas)
    aliases = load_aliases(paths)
    rules = profile.get("rules") or {}
    per_company_max = int(rules.get("per_company_max") or enums.DEFAULT_PER_COMPANY_MAX)
    per_round = int(rules.get("per_round") or enums.DEFAULT_PER_ROUND)
    per_day = int(rules.get("per_day") or enums.DEFAULT_PER_DAY)
    excluded = exclude_job_ids or set()
    the_day = today or date.today()
    run_dir = paths.run_dir(run_id)
    if not run_dir.is_dir():
        raise SchemaError("run 目录不存在，请先 `run new` / run directory missing", {"run_id": run_id})
    result = QueueBuildResult()
    result.screened_path = run_dir / "screened.jsonl"
    result.queue_path = out_path or (run_dir / "apply_queue.jsonl")

    st = stats(conn, today=the_day.isoformat())
    company_counts: dict[str, int] = dict(st["applied_by_company"])
    today_actions = int(st["today_submission_actions"])
    remaining_today = max(0, per_day - today_actions)

    rows = read_jsonl(candidates)
    latest: dict[str, tuple[int, dict[str, Any]]] = {}
    for n, obj in rows:
        fixed = normalize_job_obj(obj, aliases, n)
        fixed.setdefault("run_id", run_id)
        fixed.setdefault("discovered_at", now_iso())
        res = schemas.check("job", fixed)
        if not res.ok:
            raise SchemaError("candidates 第 %d 行不符合 job schema / line %d fails job schema" % (n, n), {"line": n, "errors": res.errors[:20]})
        latest[str(fixed["job_id"])] = (n, fixed)  # last line per job_id wins (§5.4)

    screened_lines: list[str] = []
    queued_lines: list[str] = []
    queued_count = 0
    ts = now_iso()
    for job_id, (_n, job) in latest.items():
        upsert_job(conn, job_record_from_obj(job))
        company = str(job["company"]["raw"])
        title = str(job["title"]["raw"])
        company_norm = str(job["company"]["normalized"])
        key = make_dedup_key(company, title, aliases)
        check = check_key(conn, key)
        decision_in_file = ((job.get("screening") or {}).get("decision")) or "pending"

        def _record(s: Screened) -> None:
            screened_lines.append(json.dumps(s.to_dict(), ensure_ascii=False, sort_keys=True))
            add_event(conn, "screened", "screening", {"job_id": s.job_id, "company": s.company, "title": s.title,
                                                       "decision": s.decision, "reason_code": s.reason_code},
                      run_id=run_id, job_id=s.job_id)

        if job_id in excluded or decision_in_file == "excluded_by_user":
            s = Screened(job_id, company, title, "excluded_by_user", "user_excluded", "excluded by user")
            _record(s)
            result.skipped.append(s)
            continue
        open_in_run = [a for a in check.applications
                       if a["run_id"] == run_id and a["status"] in ("queued", "in_progress", "draft_saved", "pending_user", "ready_to_submit")]
        if open_in_run:
            s = Screened(job_id, company, title, "approved", None, "already in this run's queue (%s)" % open_in_run[-1]["app_id"])
            _record(s)
            result.queued.append({"app_id": open_in_run[-1]["app_id"], "job_id": job_id, "company": company, "title": title,
                                  "channel": open_in_run[-1]["channel"], "platform": open_in_run[-1]["platform"], "already_queued": True})
            queued_count += 1
            continue
        if check.decision == "dedup_hit":
            s = Screened(job_id, company, title, "dedup_hit", "already_applied", check.reason,
                         {"job_id": job_id, "similarity": 1.0, "prior_status": check.reason})
            _record(s)
            result.skipped.append(s)
            continue
        code, reason = apply_hard_rules(job, profile, the_day)
        if code:
            s = Screened(job_id, company, title, "skip", code, reason)
            _record(s)
            result.skipped.append(s)
            continue
        if company_counts.get(company_norm, 0) >= per_company_max:
            s = Screened(job_id, company, title, "skip", "quota_reached",
                         "per_company_max %d reached for %s" % (per_company_max, company))
            _record(s)
            result.skipped.append(s)
            continue
        if check.decision == "dedup_review" and decision_in_file != "approved" and not approve_all_note:
            top = check.similar[0] if check.similar else None
            s = Screened(job_id, company, title, "dedup_review", None, check.reason,
                         {"job_id": top.job_id, "similarity": top.similarity, "prior_status": ",".join(top.statuses)} if top else None)
            _record(s)
            result.review.append(s)
            continue
        approved = decision_in_file == "approved" or bool(approve_all_note)
        if not approved:
            s = Screened(job_id, company, title, "recommend", None, "passes hard rules; awaiting user approval (D7)")
            _record(s)
            result.pending_approval.append(s)
            continue
        if queued_count >= per_round or queued_count >= remaining_today:
            s = Screened(job_id, company, title, "skip", "quota_reached",
                         "round cap %d / today's remaining %d reached" % (per_round, remaining_today))
            _record(s)
            result.skipped.append(s)
            continue
        note = approve_all_note or ((job.get("screening") or {}).get("reason")) or None
        if check.decision == "dedup_review" and not note:
            note = "user approved despite suspected duplicate"
        app = ApplicationRecord(
            app_id=new_app_id(), job_id=job_id, channel=str(job["channel"]), platform=str(job["platform"]),
            status="queued", run_id=run_id, profile_id=paths.profile_id, priority="normal",
            approval={"approved_by_user": True, "approved_at": ts, "approval_note": note},
            created_at=ts,
        )
        create_application(conn, app)
        company_counts[company_norm] = company_counts.get(company_norm, 0) + 1
        queued_count += 1
        line = {
            "app_id": app.app_id, "job_id": job_id, "run_id": run_id, "profile_id": paths.profile_id,
            "channel": app.channel, "platform": app.platform, "status": "queued", "priority": "normal",
            "approval": app.approval, "submission_action_count": 0, "created_at": ts, "updated_at": ts,
            "ledger_synced": True,
        }
        schemas.require("application", line, "apply_queue line")
        queued_lines.append(json.dumps(line, ensure_ascii=False, sort_keys=True))
        s = Screened(job_id, company, title, "approved", None, "queued")
        _record(s)
        result.queued.append({"app_id": app.app_id, "job_id": job_id, "company": company, "title": title,
                              "channel": app.channel, "platform": app.platform})

    with result.screened_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(screened_lines) + ("\n" if screened_lines else ""))
    with result.queue_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(queued_lines) + ("\n" if queued_lines else ""))
    log_write(paths, run_id, "queue_build", result.to_dict()["counts"])
    return result

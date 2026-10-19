"""Legacy four-section ledger (Markdown) -> jobs / applications / evidence (BRIEF D17). Business layer.

Section 1 (已确认投递)   -> job + application(applied) + evidence(legacy_import, qualifies=1).
                            Repeated mentions of the same dedup key add a submission action (R1).
Section 2 (中间状态)     -> job + application with a mapped intermediate status, no evidence (best effort).
Section 3 (规则)         -> skipped on purpose: it may contain contact details; rules come from profile.json.
Section 4 (状态追踪表)   -> tracking events; rows whose status says confirmed add legacy evidence.
Idempotent: every imported mention is keyed by "L<line>" in evidence.legacy_ref / events payload.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from autoapply.enums import LEGACY_UNKNOWN_TITLE
from autoapply.errors import MigrationError
from autoapply.ids import evidence_id_for, new_app_id, now_iso, now_local
from autoapply.ledger import (
    ApplicationRecord, EvidenceRow, JobRecord, add_event, applications_for_job, create_application, get_job,
    insert_evidence, next_evidence_seq, set_application_status, set_tracking_status, upsert_job,
)
from autoapply.normalize import make_dedup_key
from autoapply.redact import find_secret_hits

_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$")
_FW_PAREN_RE = re.compile(r"（[^（）]*）")
_ASCII_HASH_RE = re.compile(r"\s*\(#\s*\d+\)")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(.*)$")
_DATE_RANGE_RE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)\s*[~～–-]\s*(?:(20\d\d)-)?(\d\d)-(\d\d)")
_DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")

PLATFORM_HINTS: tuple[tuple[str, str, str], ...] = (
    ("jobstreet", "jobstreet", "jobstreet"), ("linkedin", "linkedin_easy_apply", "linkedin"),
    ("workable", "workable", "company_site"), ("ashby", "ashby", "company_site"),
    ("smartrecruiters", "smartrecruiters", "company_site"), ("greenhouse", "greenhouse", "company_site"),
    ("workday", "workday", "company_site"), ("successfactors", "successfactors", "company_site"),
    ("lever", "lever", "company_site"), ("mycareersfuture", "mycareersfuture", "mycareersfuture"),
    ("邮件", "email", "email"), ("email", "email", "email"), ("官网", "company_custom", "company_site"),
)


@dataclass
class LegacyEntry:
    section: str  # confirmed | intermediate | tracking
    line_no: int
    company: str
    title: str | None
    raw: str
    platform: str = "unknown"
    channel: str = "other"
    status: str = "applied"
    skip_reason_code: str | None = None
    tracking_status: str | None = None
    date: str | None = None
    note: str = ""


@dataclass
class LegacyParse:
    confirmed: list[LegacyEntry] = field(default_factory=list)
    intermediate: list[LegacyEntry] = field(default_factory=list)
    tracking: list[LegacyEntry] = field(default_factory=list)
    rules_lines: int = 0
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        keys: set[str] = set()
        for e in self.confirmed:
            keys.add(make_dedup_key(e.company, e.title or LEGACY_UNKNOWN_TITLE).key)
        return {"confirmed_mentions": len(self.confirmed),
                "confirmed_unique_keys": len(keys),
                "intermediate": len(self.intermediate), "tracking_rows": len(self.tracking),
                "rules_lines_skipped": self.rules_lines, "warnings": len(self.warnings)}


def _strip_md(s: str) -> str:
    return s.replace("**", "").replace("~~", "").strip()


def _hint(text: str) -> tuple[str, str] | None:
    low = text.lower()
    for word, platform, channel in PLATFORM_HINTS:
        if word in low:
            return platform, channel
    return None


def _clean_company(s: str) -> str:
    s = _strip_md(s)
    s = re.sub(r"\s*等\s*$", "", s)
    s = s.strip(" ：:；;、,，.")
    return s


def _clean_title(s: str) -> str:
    s = _strip_md(s)
    s = _ASCII_HASH_RE.sub("", s)
    return s.strip(" ：:；;、,，./")


def _split_titles(s: str, slash_split: bool) -> list[str]:
    parts = re.split(r"[；;、]", s)
    if slash_split:
        parts = [p for x in parts for p in re.split(r"\s+/\s+", x)]
    return [t for t in (_clean_title(p) for p in parts) if t]


def _section_of(heading: str) -> str | None:
    h = heading.strip()
    if h.startswith("一") or "已确认" in h:
        return "confirmed"
    if h.startswith("二") or "中间状态" in h:
        return "intermediate"
    if h.startswith("三") or "规则" in h:
        return "rules"
    if h.startswith("四") or "追踪" in h:
        return "tracking"
    return None


def _parse_confirmed_line(body: str, line_no: int, raw: str, batch_date: str | None, warnings: list[str]) -> list[LegacyEntry]:
    text = _strip_md(body)
    text = re.split(r"\s*——\s*", text)[0]
    hash_groups = len(re.findall(r"（#", text))
    notes = " ".join(_FW_PAREN_RE.findall(text))
    # "（#55）/ Title（#56）" style: the numbered marker doubles as a separator
    text = re.sub(r"（#\s*\d+）", "；", text)
    text = _FW_PAREN_RE.sub("", text).strip()
    hint = _hint(notes) or _hint(text.split("：", 1)[0] if "：" in text else "")
    default_company: str | None = None
    if "：" in text:
        pre, post = text.split("：", 1)
        if " — " not in pre:
            pre_c = _clean_company(pre)
            if not re.search(r"[㐀-鿿]", pre_c):
                default_company = pre_c
            else:
                hint = hint or _hint(pre_c)
            text = post.strip()
    entries: list[LegacyEntry] = []
    platform, channel = hint or ("unknown", "other")

    def make(company: str, title: str | None) -> None:
        c = _clean_company(company)
        if not c:
            return
        entries.append(LegacyEntry("confirmed", line_no, c, title, raw.strip(), platform, channel, "applied",
                                   None, None, batch_date, notes))

    dash_count = text.count(" — ")
    if default_company is not None:
        for t in _split_titles(text, hash_groups >= 2):
            make(default_company, t)
    elif dash_count >= 2:
        for piece in re.split(r"[；;]", text):
            piece = piece.strip()
            if not piece:
                continue
            if " — " in piece:
                company, titles = piece.split(" — ", 1)
                for t in _split_titles(titles, hash_groups >= 2):
                    make(company, t)
            else:
                make(piece, None)
    elif dash_count == 1:
        company, titles = text.split(" — ", 1)
        for t in _split_titles(titles, hash_groups >= 2):
            make(company, t)
    else:
        for piece in re.split(r"[；;、]", text):
            if piece.strip():
                make(piece, None)
    if not entries:
        warnings.append("L%d: no entry parsed" % line_no)
    return entries


def _map_intermediate_status(text: str) -> tuple[str, str | None, str | None]:
    low = text.lower()
    if "已投并在推进" in text or "简历筛选" in text:
        return "submitted_unverified", None, "under_review"
    if "草稿" in text:
        return "draft_saved", None, None
    if "nric" in low or "fin" in low or "证件" in text:
        return "skipped", "id_number_required", None
    if "立即到岗" in text:
        return "skipped", "start_immediately", None
    if "日期冲突" in text or "毕业" in text and "勿投" in text:
        return "skipped", "date_window_mismatch", None
    if "跳过" in text or "勿投" in text or "放弃" in text:
        return "skipped", "other", None
    if "待" in text or "验证码" in text or "验证" in text or "卡在" in text:
        return "pending_user", None, None
    if "失败" in text or "未提交" in text or "未计数" in text:
        return "failed", None, None
    return "abandoned", None, None


def _parse_intermediate_line(body: str, line_no: int, raw: str) -> list[LegacyEntry]:
    text = _strip_md(body)
    text = _FW_PAREN_RE.sub("", text)
    head, _, rest = text.partition("：")
    if not rest:
        head, _, rest = text.partition(":")
    head = re.sub(r"\s*→.*$", "", head).strip()
    status, code, tracking = _map_intermediate_status(text)
    hint = _hint(text) or ("unknown", "other")
    entries: list[LegacyEntry] = []
    if " — " in head:
        company, titles = head.split(" — ", 1)
        for t in _split_titles(titles, False):
            entries.append(LegacyEntry("intermediate", line_no, _clean_company(company), t, raw.strip(), hint[0], hint[1], status, code, tracking, None, rest.strip()))
    else:
        for c in re.split(r"\s+/\s+|[、；;]", head):
            c = _clean_company(c)
            if c:
                entries.append(LegacyEntry("intermediate", line_no, c, None, raw.strip(), hint[0], hint[1], status, code, tracking, None, rest.strip()))
    return entries


def _map_tracking_status(text: str) -> tuple[str, str | None]:
    """-> (application status, tracking_status)."""
    if "成功页" in text or "确认邮件" in text or re.search(r"(^|[^未])已投", text):
        return "applied", None
    if "草稿" in text:
        return "draft_saved", None
    if "拒" in text:
        return "submitted_unverified", "rejected"
    if "offer" in text.lower():
        return "submitted_unverified", "offer"
    if "面试" in text:
        return "submitted_unverified", "interview"
    if "测评" in text and "筛选" not in text:
        return "submitted_unverified", "assessment"
    if "筛选" in text or "审核" in text or "推进" in text:
        return "submitted_unverified", "under_review"
    if "回执" in text:
        return "submitted_unverified", "receipt"
    return "submitted_unverified", None


def _parse_tracking_row(line: str, line_no: int) -> LegacyEntry | None:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 5 or all(set(c) <= set("-: ") for c in cells):
        return None
    if cells[0] in ("日期", "Date") or "日期" in cells[0]:
        return None
    date = cells[0]
    company = _clean_company(cells[1])
    title = _clean_title(cells[2]) or None
    channel_text = cells[3]
    status_text = _strip_md(cells[4])
    note = cells[5] if len(cells) > 5 else ""
    if not company:
        return None
    status, tracking = _map_tracking_status(status_text)
    hint = _hint(channel_text) or _hint(status_text + " " + note) or ("company_custom" if "." in channel_text else "unknown", "company_site" if "." in channel_text else "other")
    d = date if _DATE_RE.match(date) else None
    return LegacyEntry("tracking", line_no, company, title, line.strip(), hint[0], hint[1], status, None, tracking, d,
                       "%s | %s | %s" % (channel_text, status_text, note))


def parse_legacy_markdown(text: str) -> LegacyParse:
    parse = LegacyParse()
    section: str | None = None
    batch_date: str | None = None
    for n, raw in enumerate(text.splitlines(), 1):
        m = _HEADING_RE.match(raw)
        if m:
            level = len(raw) - len(raw.lstrip()) + raw.lstrip().index(" ") if " " in raw.lstrip() else 1
            title = m.group(1)
            if raw.lstrip().startswith("## "):
                section = _section_of(title)
                batch_date = None
            elif raw.lstrip().startswith("### "):
                dm = _DATE_RANGE_RE.search(title)
                if dm:
                    y2 = dm.group(4) or dm.group(1)
                    batch_date = "%s-%s-%s" % (y2, dm.group(5), dm.group(6))
                else:
                    dm2 = _DATE_RE.search(title)
                    batch_date = dm2.group(0) if dm2 else batch_date
            _ = level
            continue
        if section is None or not raw.strip():
            continue
        if section == "rules":
            parse.rules_lines += 1
            continue
        if section == "tracking":
            if raw.lstrip().startswith("|"):
                row = _parse_tracking_row(raw, n)
                if row:
                    parse.tracking.append(row)
            continue
        bm = _BULLET_RE.match(raw)
        if not bm:
            continue
        body = bm.group(1)
        if find_secret_hits(body):
            parse.warnings.append("L%d: line contains a secret-like pattern; skipped" % n)
            continue
        if section == "confirmed":
            parse.confirmed.extend(_parse_confirmed_line(body, n, raw, batch_date, parse.warnings))
        elif section == "intermediate":
            parse.intermediate.extend(_parse_intermediate_line(body, n, raw))
    if not parse.confirmed and not parse.intermediate and not parse.tracking:
        raise MigrationError("未识别出任何台账条目（需要 '## 一、' 等四节标题）/ no ledger entries recognised")
    return parse


# ---- import --------------------------------------------------------------------------------------
def _legacy_ref(entry: LegacyEntry) -> str:
    return "L%d: %s" % (entry.line_no, entry.raw[:400])


def _find_legacy_app(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    for app in applications_for_job(conn, job_id):
        if app["run_id"] is None and (app["notes"] or "").startswith("legacy_import"):
            return app
    return None


def _has_ref(conn: sqlite3.Connection, ref_prefix: str) -> bool:
    row = conn.execute("SELECT 1 FROM evidence WHERE legacy_ref LIKE ? LIMIT 1", (ref_prefix + "%",)).fetchone()
    if row is not None:
        return True
    row = conn.execute("SELECT 1 FROM events WHERE kind='tracking_update' AND payload LIKE ? LIMIT 1",
                       ("%(legacy " + ref_prefix.strip(": ") + ")%",)).fetchone()
    if row is not None:
        return True
    row = conn.execute("SELECT 1 FROM events WHERE kind='tracking_update' AND payload LIKE ? LIMIT 1",
                       ('%"legacy_ref": "' + ref_prefix + '"%',)).fetchone()
    return row is not None


def _ensure_job(conn: sqlite3.Connection, entry: LegacyEntry, aliases: dict[str, str], at: str, source_name: str) -> dict[str, Any]:
    key = make_dedup_key(entry.company, entry.title or LEGACY_UNKNOWN_TITLE, aliases)
    existing = get_job(conn, key.job_id)
    if existing is None:
        upsert_job(conn, JobRecord(
            job_id=key.job_id, dedup_key=key.key, company_raw=key.company_raw, company_norm=key.company_norm,
            title_raw=key.title_raw, title_norm=key.title_norm, platform=entry.platform, source_type="legacy_import",
            channel=entry.channel, source_ref="%s:L%d" % (source_name, entry.line_no), notes=entry.note or None,
            seen_at=at,
        ))
    job = get_job(conn, key.job_id)
    if job is None:
        raise MigrationError("job 写入后读不到 / job missing after upsert")
    return job


def _local_midnight(date_str: str | None) -> str | None:
    if not date_str:
        return None
    tz = now_local().strftime("%z")
    tz = tz[:3] + ":" + tz[3:] if len(tz) == 5 else "+00:00"
    return "%sT00:00:00%s" % (date_str, tz)


def import_legacy(conn: sqlite3.Connection, parse: LegacyParse, aliases: dict[str, str], *, profile_id: str,
                  source_name: str = "投递台账.md", dry_run: bool = False) -> dict[str, Any]:
    at = now_iso()
    counts = {"jobs_created": 0, "applications_created": 0, "submission_actions_added": 0, "evidence_added": 0,
              "intermediate_created": 0, "tracking_events": 0, "skipped_already_imported": 0}
    if dry_run:
        return {"dry_run": True, "parse": parse.counts(), "counts": counts, "warnings": parse.warnings}
    jobs_before = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for entry in parse.confirmed:
            ref = _legacy_ref(entry)
            job = _ensure_job(conn, entry, aliases, at, source_name)
            app = _find_legacy_app(conn, job["job_id"])
            marker = "L%d|%s|%s" % (entry.line_no, entry.company[:60], (entry.title or LEGACY_UNKNOWN_TITLE)[:80])
            dup = conn.execute("SELECT 1 FROM evidence WHERE legacy_ref=? AND notes=? LIMIT 1", (ref, marker)).fetchone()
            if dup is not None:
                counts["skipped_already_imported"] += 1
                continue
            submitted_at = _local_midnight(entry.date) or at
            if app is None:
                rec = ApplicationRecord(
                    app_id=new_app_id(), job_id=job["job_id"], channel=entry.channel, platform=entry.platform,
                    status="queued", run_id=None, profile_id=profile_id,
                    approval={"approved_by_user": True, "approved_at": at,
                              "approval_note": "legacy_import: confirmed in %s L%d" % (source_name, entry.line_no)},
                    notes="legacy_import from %s L%d" % (source_name, entry.line_no), created_at=submitted_at,
                )
                app = create_application(conn, rec)
                counts["applications_created"] += 1
                first = True
            else:
                first = False
            seq = next_evidence_seq(conn, app["app_id"])
            insert_evidence(conn, EvidenceRow(
                evidence_id=evidence_id_for(app["app_id"], seq), app_id=app["app_id"], evidence_type="legacy_import",
                qualifies=True, captured_at=submitted_at, captured_by="migrate_legacy", legacy_ref=ref, notes=marker,
                matched_job_by="manual",
            ), actor="migrate_legacy")
            counts["evidence_added"] += 1
            if first:
                set_application_status(conn, app["app_id"], "applied", actor="migrate_legacy", at=submitted_at)
            else:
                set_application_status(conn, app["app_id"], "applied", count_submission=True, actor="migrate_legacy", at=submitted_at)
                counts["submission_actions_added"] += 1
        for entry in parse.intermediate:
            job = _ensure_job(conn, entry, aliases, at, source_name)
            note = "legacy_import from %s L%d: %s" % (source_name, entry.line_no, entry.note[:200])
            already = conn.execute("SELECT 1 FROM applications WHERE job_id=? AND notes LIKE ? LIMIT 1",
                                   (job["job_id"], "legacy_import from %s L%d%%" % (source_name, entry.line_no))).fetchone()
            if already is not None:
                counts["skipped_already_imported"] += 1
                continue
            rec = ApplicationRecord(app_id=new_app_id(), job_id=job["job_id"], channel=entry.channel, platform=entry.platform,
                                    status="queued", profile_id=profile_id, notes=note, created_at=at)
            app = create_application(conn, rec)
            set_application_status(conn, app["app_id"], entry.status, skip_reason_code=entry.skip_reason_code,
                                   tracking_status=entry.tracking_status, actor="migrate_legacy", at=at)
            counts["intermediate_created"] += 1
        for entry in parse.tracking:
            ref = _legacy_ref(entry)
            if _has_ref(conn, "L%d: " % entry.line_no):
                counts["skipped_already_imported"] += 1
                continue
            job = _ensure_job(conn, entry, aliases, at, source_name)
            apps = applications_for_job(conn, job["job_id"])
            ts = _local_midnight(entry.date) or at
            if apps:
                app = apps[-1]
            else:
                app = create_application(conn, ApplicationRecord(
                    app_id=new_app_id(), job_id=job["job_id"], channel=entry.channel, platform=entry.platform,
                    status="queued", profile_id=profile_id, notes="legacy_import from %s L%d" % (source_name, entry.line_no),
                    created_at=ts))
                counts["applications_created"] += 1
            if entry.status == "applied":
                if app["status"] != "applied":
                    seq = next_evidence_seq(conn, app["app_id"])
                    insert_evidence(conn, EvidenceRow(
                        evidence_id=evidence_id_for(app["app_id"], seq), app_id=app["app_id"], evidence_type="legacy_import",
                        qualifies=True, captured_at=ts, captured_by="migrate_legacy", legacy_ref=ref, matched_job_by="manual",
                        notes="tracking row"), actor="migrate_legacy")
                    counts["evidence_added"] += 1
                    set_application_status(conn, app["app_id"], "applied", actor="migrate_legacy", at=ts)
            elif app["status"] in ("queued", "in_progress") or app["status"] != entry.status and app["status"] not in ("applied",):
                set_application_status(conn, app["app_id"], entry.status, actor="migrate_legacy", at=ts)
            note = "%s (legacy L%d)" % (entry.note[:160], entry.line_no)
            if entry.tracking_status:
                set_tracking_status(conn, app["app_id"], entry.tracking_status, note, actor="migrate_legacy", at=ts)
            else:
                add_event(conn, "tracking_update", "migrate_legacy",
                          {"tracking_status": None, "company": job["company_raw"], "title": job["title_raw"],
                           "channel": entry.channel, "note": note, "legacy_ref": "L%d: " % entry.line_no},
                          app_id=app["app_id"], job_id=job["job_id"], at=ts)
            counts["tracking_events"] += 1
        counts["jobs_created"] = int(conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]) - int(jobs_before)
        add_event(conn, "legacy_imported", "migrate_legacy", {"source": source_name, "counts": counts, "parse": parse.counts()}, at=at)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"dry_run": False, "parse": parse.counts(), "counts": counts, "warnings": parse.warnings}

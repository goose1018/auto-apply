#!/usr/bin/env python3
"""auto-apply CLI — entry layer (argparse, printing, exit codes). Runnable directly or via `python3 -m autoapply`.

  python3 cli.py [--data-dir DIR] [--profile PROFILE_ID] [--json] <command> ...

Exit codes (CODE_STANDARDS §5): 0 ok · 1 business assertion failed · 2 usage/config/illegal transition ·
3 data integrity (schema, ledger, evidence). Failures print one JSON line on stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

PY_REQUIRED = (3, 9)


def _version_gate() -> None:
    if sys.version_info >= PY_REQUIRED:
        return
    sys.stderr.write(json.dumps({"error": "python_version", "detail": "auto-apply 需要 Python 3.9+，当前 %d.%d" % sys.version_info[:2]}) + "\n")
    sys.exit(2)


_version_gate()

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autoapply import dedup, enums, evidence, export_md, facts_render, gates, migrate_legacy, presubmit as presubmit_mod  # noqa: E402
from autoapply import normalize, profile_check, queue_build, report as report_mod, runstate, selfcheck as selfcheck_mod  # noqa: E402
from autoapply.errors import AutoApplyError, AssertionFailed, ConfigError, UsageError  # noqa: E402
from autoapply.ids import new_app_id, now_iso, parse_iso, sha256_file  # noqa: E402
from autoapply.ledger import (  # noqa: E402
    ApplicationRecord, applications_for_job, create_application, evidence_for_app, find_open_application, log_write,
    open_ledger, require_application, require_job, run_assertions, set_application_status, stats,
)
from autoapply.paths import DataPaths, resolve_data_root, resolve_profile_id, resolve_schema_dir  # noqa: E402
from autoapply.schema_validate import SchemaSet  # noqa: E402


# ---- context -------------------------------------------------------------------------------------
class Ctx:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.json = bool(args.json)
        self.data_root = resolve_data_root(args.data_dir)
        self._profile_override: str | None = args.profile
        self._paths: DataPaths | None = None
        self._schemas: SchemaSet | None = None
        self._conn: Any = None

    @property
    def schemas(self) -> SchemaSet:
        if self._schemas is None:
            self._schemas = SchemaSet(resolve_schema_dir())
        return self._schemas

    def profile_id_or_none(self) -> str | None:
        try:
            return resolve_profile_id(self._profile_override, self.data_root)
        except ConfigError:
            return None

    @property
    def paths(self) -> DataPaths:
        if self._paths is None:
            pid = resolve_profile_id(self._profile_override, self.data_root)
            self._paths = DataPaths(self.data_root, pid)
            self._paths.ensure_layout()
        return self._paths

    @property
    def conn(self) -> Any:
        if self._conn is None:
            self._conn = open_ledger(self.paths.ledger_sqlite, self.paths.profile_id)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _read_json_file(path: str, what: str) -> dict[str, Any]:
    return profile_check.read_json_object(Path(path).expanduser(), what)


def _load_profile_optional(ctx: Ctx) -> dict[str, Any] | None:
    p = ctx.paths.profile_json
    if not p.is_file():
        return None
    data = profile_check.read_json_object(p, "profile.json")
    ctx.schemas.require("profile", data, "profile.json")
    return data


def _per_company_max(profile: dict[str, Any] | None) -> int:
    rules = (profile or {}).get("rules") or {}
    return int(rules.get("per_company_max") or enums.DEFAULT_PER_COMPANY_MAX)


def _resolve_resume_meta(profile: dict[str, Any] | None, resume_path: str | None) -> tuple[str | None, str | None]:
    """(language, sha256) for a resume path used on `app start --resume`. language comes from the
    matching profile.materials.resumes[] entry (by path); sha256 is computed fresh from the file on
    disk when it exists (authoritative over any value recorded in the profile), so presubmit can
    detect a resume that changed after profile intake. Never raises: missing file/profile -> (None, None
    or whatever is resolvable)."""
    if not resume_path:
        return None, None
    p = Path(resume_path).expanduser()
    language: str | None = None
    for r in ((profile or {}).get("materials") or {}).get("resumes") or []:
        try:
            same = Path(str(r.get("path") or "")).expanduser().resolve() == p.resolve()
        except OSError:
            same = str(r.get("path") or "") == str(resume_path)
        if same:
            language = r.get("language")
            break
    digest: str | None = None
    if p.is_file():
        try:
            digest = sha256_file(p)
        except OSError:
            digest = None
    return language, digest


# ---- commands ------------------------------------------------------------------------------------
def cmd_selfcheck(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    schema_dir: Path | None
    try:
        schema_dir = resolve_schema_dir()
    except ConfigError:
        schema_dir = None
    items = selfcheck_mod.run_selfcheck(ctx.data_root, ctx.profile_id_or_none(), schema_dir)
    data = selfcheck_mod.summarize(items)
    lines = ["selfcheck — data root %s" % ctx.data_root]
    for i in items:
        lines.append("  [%-10s] %-26s %s" % (i.status.upper(), i.name, i.detail))
    c = data["counts"]
    lines.append("ok %d · warn %d · fail %d · unverified %d" % (c["ok"], c["warn"], c["fail"], c["unverified"]))
    return data, "\n".join(lines), (1 if data["failed"] else 0)


def cmd_profile_validate(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    profile = _read_json_file(ctx.args.file, "profile.json")
    errors, warnings = profile_check.validate_profile(ctx.schemas, profile, check_files=not ctx.args.no_file_check)
    data = {"file": ctx.args.file, "ok": not errors, "errors": errors, "warnings": warnings}
    lines = ["profile validate %s: %s" % (ctx.args.file, "PASS" if not errors else "FAIL (%d error(s))" % len(errors))]
    lines += ["  error: %s" % e for e in errors]
    lines += ["  warn:  %s" % w for w in warnings]
    return data, "\n".join(lines), (0 if not errors else 3)


def cmd_profile_consistency(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    profile = _read_json_file(ctx.args.file, "profile.json")
    ctx.schemas.require("profile", profile, "profile.json")
    rp_path = Path(ctx.args.resume_facts).expanduser()
    if not rp_path.is_file():
        raise UsageError("resume facts 文件不存在 / resume facts file not found", {"path": str(rp_path)})
    try:
        resume_parse = json.loads(rp_path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise UsageError("resume facts 不是合法 JSON / invalid JSON") from e
    rep = profile_check.consistency_report(profile, resume_parse)
    out: Path | None = None
    if ctx.args.output:
        out = Path(ctx.args.output).expanduser()
    else:
        pid = ctx.profile_id_or_none()
        if pid:
            out = ctx.paths.consistency_report_json
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rep["written_to"] = str(out) if out else None
    lines = ["consistency: overall=%s%s" % (rep["overall"], " -> %s" % out if out else "")]
    for r in rep["resumes"]:
        lines.append("  resume %s: %s" % (r["resume_path"], r["overall"]))
        for f in r["findings"]:
            if f["level"] != "pass":
                lines.append("    [%s] %s: %s (resume %s / profile %s)" % (f["level"], f["field"], f["hint"], f["resume_value_masked"], f["profile_value_masked"]))
    code = 1 if rep["overall"] == "block" else 0
    if code:
        lines.append("BLOCK: 需要用户处理 consistency_mismatch 关口 / user must resolve the consistency_mismatch gate")
    return rep, "\n".join(lines), code


def cmd_facts_render(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    card = _read_json_file(ctx.args.file, "facts_card.json")
    text = facts_render.render_facts_md(ctx.schemas, card)
    out = Path(ctx.args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return {"written_to": str(out), "facts": len(card.get("facts") or [])}, "facts render -> %s (%d facts)" % (out, len(card.get("facts") or [])), 0


def cmd_run_new(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    profile = _load_profile_optional(ctx)
    policy = (profile or {}).get("policy") or {}
    rules = (profile or {}).get("rules") or {}
    state = runstate.create_run(
        ctx.paths, ctx.schemas, ctx.conn, gate_mode=ctx.args.mode or policy.get("gate_mode") or "interactive",
        invocation=ctx.args.invocation, runtime=ctx.args.runtime, target=ctx.args.target or rules.get("per_round"),
        per_day_limit=rules.get("per_day"), report_every_n=policy.get("report_every_n"),
    )
    run_id = str(state["run_id"])
    return {"run_id": run_id, "run_dir": str(ctx.paths.run_dir(run_id)), "phase": state["phase"]}, "%s\n%s" % (run_id, ctx.paths.run_dir(run_id)), 0


def cmd_run_checkpoint(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    state = runstate.checkpoint(ctx.paths, ctx.schemas, ctx.conn, ctx.args.run_id, ctx.args.state,
                                resume_to=ctx.args.resume_to, gate_id=ctx.args.gate)
    return state, "%s: %s -> %s%s" % (ctx.args.run_id, state["previous_phase"], state["phase"],
                                      " (resume_to=%s)" % state["resume_to"] if state.get("resume_to") else ""), 0


def cmd_run_show(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    state = runstate.load_run_state(ctx.paths, ctx.args.run_id)
    opts = runstate.load_run_options(ctx.paths, ctx.args.run_id)
    pending = [a for a in gates.load_pending(ctx.paths, ctx.args.run_id).values() if a.get("status") == "open"]
    st = stats(ctx.conn, ctx.args.run_id)
    data = {"run_state": state, "options": opts, "open_pending": len(pending), "stats": st,
            "legal_next_states": sorted(runstate.legal_targets(state))}
    lines = ["run %s" % ctx.args.run_id,
             "  phase: %s (previous %s, resume_to %s)" % (state["phase"], state.get("previous_phase"), state.get("resume_to")),
             "  gate_mode: %s · started %s · updated %s" % (opts.get("gate_mode"), state["started_at"], state["updated_at"]),
             "  legal next states: %s" % ", ".join(data["legal_next_states"]),
             "  open pending actions: %d" % len(pending),
             "  applied (unique jobs) %d / submission actions %d / by status %s" % (st["unique_jobs_applied"], st["submission_actions"], json.dumps(st["by_status"], ensure_ascii=False))]
    return data, "\n".join(lines), 0


def cmd_run_pending(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    runstate.validate_run_id(ctx.args.run_id)
    if not ctx.paths.run_dir(ctx.args.run_id).is_dir():
        raise UsageError("run 目录不存在 / run not found", {"run_id": ctx.args.run_id})
    text = gates.render_and_write(ctx.paths, ctx.args.run_id)
    actions = gates.load_pending(ctx.paths, ctx.args.run_id)
    return {"run_id": ctx.args.run_id, "actions": list(actions.values()), "markdown": text,
            "path": str(ctx.paths.run_dir(ctx.args.run_id) / gates.PENDING_MD)}, text.rstrip(), 0


def cmd_run_resolve(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    obj = gates.resolve_action(ctx.conn, ctx.paths, ctx.schemas, ctx.args.run_id, ctx.args.action_id, ctx.args.resolution, ctx.args.note)
    state = runstate.load_run_state(ctx.paths, ctx.args.run_id)
    return {"action": obj, "phase": state["phase"]}, "%s -> %s · run phase now %s" % (ctx.args.action_id, obj["status"], state["phase"]), 0


def cmd_pending_expire(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    run_id = runstate.validate_run_id(ctx.args.run_id)
    if not ctx.paths.run_dir(run_id).is_dir():
        raise UsageError("run 目录不存在 / run not found", {"run_id": run_id})
    if ctx.args.dry_run:
        ref = parse_iso(now_iso())
        would = [action_id for action_id, obj in gates.load_pending(ctx.paths, run_id).items()
                if obj.get("status") == "open" and obj.get("expires_at") and parse_iso(str(obj["expires_at"])) <= ref]
        data = {"run_id": run_id, "dry_run": True, "would_expire": would, "count": len(would)}
        lines = ["pending expire %s (dry-run): %d 项逾期会被标过期 / %d item(s) would be marked expired" % (run_id, len(would), len(would))]
        lines += ["  %s" % a for a in would]
        return data, "\n".join(lines), 0
    expired = gates.expire_overdue(ctx.conn, ctx.paths, ctx.schemas, run_id)
    data = {"run_id": run_id, "dry_run": False, "expired": expired, "count": len(expired)}
    lines = ["pending expire %s: %d 项已标过期 / %d item(s) marked expired" % (run_id, len(expired), len(expired))]
    lines += ["  %s" % a for a in expired]
    return data, "\n".join(lines), 0


def _gate_request_from_args(args: argparse.Namespace, app_id: str | None, default_scope: str | None) -> gates.GateRequest:
    context: dict[str, Any] = {}
    if getattr(args, "url", None):
        context["url"] = args.url
    if getattr(args, "draft_url", None):
        context["draft_url"] = args.draft_url
        context["draft_saved"] = True
    if getattr(args, "field", None):
        context["field_label"] = args.field
    if getattr(args, "missing", None):
        context["missing_fields"] = [x.strip() for x in str(args.missing).split(",") if x.strip()]
    return gates.GateRequest(
        gate_type=args.type, message_zh=args.message, message_en=args.message_en, scope=args.scope or default_scope,
        mode=args.mode, app_id=app_id, priority=args.priority, playbook_step=args.step, context=context or None,
        instructions_zh=args.instructions, instructions_en=args.instructions_en,
        resume_instructions=args.resume_instructions, runtime=args.runtime, options=list(args.option or []),
    )


def cmd_run_gate(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    req = _gate_request_from_args(ctx.args, None, "run")
    obj = gates.open_gate(ctx.conn, ctx.paths, ctx.schemas, ctx.args.run_id, req)
    state = runstate.load_run_state(ctx.paths, ctx.args.run_id)
    return {"action": obj, "phase": state["phase"]}, "%s opened (%s, %s) · run phase %s" % (obj["action_id"], obj["gate_type"], obj["scope"], state["phase"]), 0


def cmd_run_list(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    runs = runstate.list_runs(ctx.paths)
    lines = ["%s  %-12s %s" % (r["run_id"], r["phase"], r["updated_at"]) for r in runs] or ["(no runs)"]
    return {"runs": runs, "latest_open": runstate.latest_open_run(ctx.paths)}, "\n".join(lines), 0


def cmd_jobs_add(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    rep = dedup.add_candidates(ctx.conn, ctx.paths, ctx.schemas, Path(ctx.args.file).expanduser(), run_id=ctx.args.run)
    data = rep.to_dict()
    lines = ["jobs add %s: %d line(s) · 新增 %d · 已存在/已投 %d · 疑似重复 %d" % (
        ctx.args.file, rep.lines_total, len(rep.added), len(rep.existing), len(rep.suspected))]
    for e in rep.existing:
        lines.append("  [%s] L%d %s — %s: %s" % (e["decision"], e["line"], e["company"], e["title"], e["reason"]))
    for e in rep.suspected:
        sim = e["similar"][0] if e["similar"] else None
        lines.append("  [dedup_review] L%d %s — %s: %s%s" % (e["line"], e["company"], e["title"], e["reason"],
                                                              " ~ '%s' (%.2f)" % (sim["title_raw"], sim["similarity"]) if sim else ""))
    return data, "\n".join(lines), 0


def cmd_jobs_check(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    res = dedup.check_company_title(ctx.conn, ctx.paths, ctx.args.company, ctx.args.title)
    data = res.to_dict()
    lines = ["company_norm: %s" % res.company_norm, "title_norm:   %s" % res.title_norm, "dedup_key:    %s" % res.dedup_key,
             "job_id:       %s" % res.job_id, "decision:     %s — %s" % (res.decision, res.reason)]
    for a in res.applications:
        lines.append("  application %s: %s via %s (%s), actions %d" % (a["app_id"], a["status"], a["channel"], a["platform"], a["submission_action_count"]))
    for m in res.similar:
        lines.append("  similar: %s — '%s' (%.2f) statuses %s" % (m.job_id, m.title_raw, m.similarity, ",".join(m.statuses) or "none"))
    return data, "\n".join(lines), 0


def cmd_jobs_normalize(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    n = dedup.write_normalized_jsonl(Path(ctx.args.file).expanduser(), Path(ctx.args.output).expanduser(), dedup.load_aliases(ctx.paths), ctx.args.run)
    return {"lines": n, "output": ctx.args.output}, "normalized %d line(s) -> %s" % (n, ctx.args.output), 0


def cmd_queue_build(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    excl = {x.strip() for x in str(ctx.args.exclude or "").split(",") if x.strip()}
    res = queue_build.build_queue(ctx.conn, ctx.paths, ctx.schemas, ctx.args.run_id, Path(ctx.args.source).expanduser(),
                                  out_path=Path(ctx.args.output).expanduser() if ctx.args.output else None,
                                  approve_all_note=ctx.args.approve_all, exclude_job_ids=excl, today=date.today())
    data = res.to_dict()
    c = data["counts"]
    lines = ["queue build %s: 入队 %d · 待批准 %d · 疑似重复待确认 %d · 跳过 %d -> %s" % (
        ctx.args.run_id, c["queued"], c["pending_approval"], c["review"], c["skipped"], res.queue_path)]
    for q in res.queued:
        lines.append("  [queued] %s %s — %s (%s)" % (q["app_id"], q["company"], q["title"], q["channel"]))
    for s in res.pending_approval:
        lines.append("  [pending_approval] %s — %s" % (s.company, s.title))
    for s in res.review:
        lines.append("  [dedup_review] %s — %s: %s" % (s.company, s.title, s.reason))
    for s in res.skipped:
        lines.append("  [skip:%s] %s — %s: %s" % (s.reason_code, s.company, s.title, s.reason))
    if c["pending_approval"] and not ctx.args.approve_all:
        lines.append("提示：未批准的候选不会入队（D7）。用户批准后用 --approve-all \"<用户原话>\" [--exclude job_id,...] 重跑。")
    return data, "\n".join(lines), 0


def cmd_app_start(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    run_id = runstate.validate_run_id(ctx.args.run_id)
    runstate.load_run_state(ctx.paths, run_id)
    job = require_job(ctx.conn, ctx.args.job_id)
    channel = ctx.args.channel
    if channel not in enums.CHANNELS:
        raise UsageError("channel 不合法 / invalid channel", {"channel": channel, "allowed": list(enums.CHANNELS)})
    platform = ctx.args.platform or str(job["platform"])
    existing = find_open_application(ctx.conn, run_id, str(job["job_id"]), channel)
    if existing is None:
        applied = [a for a in applications_for_job(ctx.conn, str(job["job_id"])) if a["status"] in enums.DEDUP_HIT_STATUSES]
        if applied and not ctx.args.force:
            raise AssertionFailed("该岗位已有 %s 状态的申请，重复投递需 --force 并在台账留说明 / job already applied; use --force to record a second submission" % ",".join(sorted({a["status"] for a in applied})),
                                  {"job_id": job["job_id"], "existing": [a["app_id"] for a in applied]})
        resume_language, resume_sha256 = _resolve_resume_meta(_load_profile_optional(ctx), ctx.args.resume)
        rec = ApplicationRecord(app_id=new_app_id(), job_id=str(job["job_id"]), channel=channel, platform=platform,
                                status="queued", run_id=run_id, profile_id=ctx.paths.profile_id,
                                approval={"approved_by_user": True, "approved_at": now_iso(), "approval_note": ctx.args.note or ("forced second submission" if applied else None)},
                                resume_path=ctx.args.resume, resume_language=resume_language, resume_sha256=resume_sha256,
                                created_at=now_iso())
        create_application(ctx.conn, rec)
        app_id = rec.app_id
    else:
        app_id = str(existing["app_id"])
    app = set_application_status(ctx.conn, app_id, "in_progress", actor="executor", note=ctx.args.note)
    state = runstate.load_run_state(ctx.paths, run_id)
    state["current_item"] = {"app_id": app_id, "step": "open", "playbook_step": None, "started_at": now_iso()}
    state["updated_at"] = now_iso()
    runstate.save_run_state(ctx.paths, ctx.schemas, state)
    item_dir = ctx.paths.run_dir(run_id) / "items" / app_id
    (item_dir / "content").mkdir(parents=True, exist_ok=True)
    log_write(ctx.paths, run_id, "app_start", {"app_id": app_id, "job_id": job["job_id"], "channel": channel})
    return {"app_id": app_id, "job_id": job["job_id"], "status": app["status"], "item_dir": str(item_dir)}, "%s\n%s" % (app_id, item_dir), 0


def cmd_app_status(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    status = ctx.args.status
    reason_code = None
    failure_reason = None
    note = ctx.args.note
    if status == "skipped":
        if ctx.args.reason in enums.SKIP_REASON_CODES:
            reason_code = ctx.args.reason
        elif ctx.args.reason:
            reason_code = "other"
            note = (note + "\n" if note else "") + str(ctx.args.reason)
    elif status == "failed":
        failure_reason = ctx.args.reason
    elif ctx.args.reason:
        note = (note + "\n" if note else "") + str(ctx.args.reason)
    app = set_application_status(ctx.conn, ctx.args.app_id, status, skip_reason_code=reason_code, note=note,
                                 failure_reason=failure_reason, count_submission=ctx.args.count_submission,
                                 actor=ctx.args.actor)
    log_write(ctx.paths, app["run_id"], "app_status", {"app_id": app["app_id"], "status": status, "skip_reason_code": reason_code})
    return app, "%s -> %s (actions %d)" % (app["app_id"], app["status"], app["submission_action_count"]), 0


def cmd_app_tracking(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    app = require_application(ctx.conn, ctx.args.app_id)
    updated = set_application_status(ctx.conn, ctx.args.app_id, str(app["status"]), note=ctx.args.note,
                                     tracking_status=ctx.args.tracking_status, actor=ctx.args.actor)
    log_write(ctx.paths, updated["run_id"], "app_tracking", {"app_id": updated["app_id"], "tracking_status": ctx.args.tracking_status})
    return updated, "%s tracking -> %s (status unchanged: %s)" % (updated["app_id"], updated["tracking_status"], updated["status"]), 0


def cmd_app_evidence(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    src = ctx.args.screenshot or ctx.args.file
    ev = evidence.EvidenceInput(
        evidence_type=ctx.args.type, captured_by=ctx.args.captured_by, url=ctx.args.url, page_title=ctx.args.page_title,
        source_file=Path(src).expanduser() if src else None, job_title_seen=ctx.args.job_title_seen,
        status_seen=ctx.args.status_seen, email_subject=ctx.args.subject, email_from=ctx.args.email_from,
        email_received_at=ctx.args.received_at, email_message_id=ctx.args.message_id, email_excerpt=ctx.args.excerpt,
        matched_job_by=ctx.args.matched_job_by, legacy_ref=ctx.args.legacy_ref, notes=ctx.args.note,
    )
    row = evidence.register_evidence(ctx.conn, ctx.paths, ctx.args.app_id, ev)
    lines = ["%s: %s qualifies=%s" % (row["evidence_id"], row["evidence_type"], "true" if row["qualifies"] else "false")]
    lines += ["  %s" % r for r in row["judge_reasons"]]
    code = 0
    if ctx.args.mark_applied:
        if row["qualifies"]:
            app = set_application_status(ctx.conn, ctx.args.app_id, "applied", actor=ctx.args.captured_by)
            row["application_status"] = app["status"]
            lines.append("  application -> applied")
        else:
            lines.append("  证据不合格，未标 applied / evidence does not qualify; status unchanged")
            code = 1
    return row, "\n".join(lines), code


def cmd_app_gate(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    app = require_application(ctx.conn, ctx.args.app_id)
    if not app["run_id"]:
        raise UsageError("该 application 没有 run_id，无法写 pending / application has no run_id")
    req = _gate_request_from_args(ctx.args, ctx.args.app_id, None)
    obj = gates.open_gate(ctx.conn, ctx.paths, ctx.schemas, str(app["run_id"]), req)
    return obj, "%s opened (%s, %s) -> %s" % (obj["action_id"], obj["gate_type"], obj["scope"], ctx.paths.run_dir(str(app["run_id"])) / gates.PENDING_MD), 0


def cmd_app_show(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    app = require_application(ctx.conn, ctx.args.app_id)
    job = require_job(ctx.conn, str(app["job_id"]))
    evs = evidence_for_app(ctx.conn, str(app["app_id"]))
    data = {"application": app, "job": job, "evidence": evs}
    lines = ["%s: %s — %s" % (app["app_id"], job["company_raw"], job["title_raw"]),
             "  status %s · channel %s · platform %s · actions %d · run %s" % (app["status"], app["channel"], app["platform"], app["submission_action_count"], app["run_id"])]
    for e in evs:
        lines.append("  evidence %s %s qualifies=%s" % (e["evidence_id"], e["evidence_type"], bool(e["qualifies"])))
    return data, "\n".join(lines), 0


def cmd_presubmit(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    profile = _load_profile_optional(ctx)
    rep = presubmit_mod.run_presubmit(ctx.conn, ctx.paths, ctx.args.app_id, profile)
    lines = ["presubmit %s: %s（%d 项不通过 / %d fail · %d 项需人工确认 / %d unverified）" % (
        ctx.args.app_id, "PASS" if rep["passed"] else "FAIL", rep["fail_count"], rep["fail_count"], rep["unverified_count"], rep["unverified_count"])]
    for i in rep["items"]:
        lines.append("  [%-10s] %-10s %s" % (i["status"].upper(), i["name"], i["note"]))
    if not rep["passed"]:
        lines.append("不通过：先修上面标 FAIL 的项，或按 gates.md 挂对应关口；presubmit 不通过不得进入 final_submit / fix the FAIL items above (or open the matching gate) before final_submit")
    return rep, "\n".join(lines), (0 if rep["passed"] else 1)


def cmd_quota(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    run_id = ctx.args.run or runstate.latest_open_run(ctx.paths)
    profile = _load_profile_optional(ctx)
    rules = (profile or {}).get("rules") or {}
    per_day = int(rules.get("per_day") or enums.DEFAULT_PER_DAY)
    per_round = int(rules.get("per_round") or enums.DEFAULT_PER_ROUND)
    per_company_max = _per_company_max(profile)
    # 公司名必须走 R1 规范化，否则 profile 里写 "P Co" 而台账键是 "p"，上限永远匹配不上。
    caps = {normalize.normalize_company(str(c.get("company"))): int(c["max_applications"])
            for c in (rules.get("company_caps") or []) if isinstance(c, dict) and c.get("company") and c.get("max_applications") is not None}
    total = stats(ctx.conn)
    run_stats = stats(ctx.conn, run_id) if run_id else None
    run_state = runstate.load_run_state(ctx.paths, run_id) if run_id else None
    quotas = (run_state or {}).get("quotas") or {}
    blocked = set(quotas.get("platform_blocked") or [])
    li_remaining = quotas.get("linkedin_daily_remaining")
    companies = []
    for norm, n in total["applied_by_company"].items():
        cap = caps.get(norm, per_company_max)
        companies.append({"company": norm, "applied": n, "cap": cap, "over": n >= cap})
    companies.sort(key=lambda x: (-x["applied"], x["company"]))
    platforms = []
    for plat, n in total["applied_by_platform"].items():
        entry: dict[str, Any] = {"platform": plat, "applied": n, "blocked_this_run": plat in blocked}
        if plat == "linkedin_easy_apply":
            entry["linkedin_daily_remaining"] = li_remaining
            entry["over"] = bool(plat in blocked or (isinstance(li_remaining, int) and li_remaining <= 0))
        else:
            entry["over"] = plat in blocked
        platforms.append(entry)
    platforms.sort(key=lambda x: (-x["applied"], x["platform"]))
    today_over = total["today_submission_actions"] >= per_day
    round_over = bool(run_stats and run_stats["unique_jobs_applied"] >= per_round)
    data = {
        "run_id": run_id,
        "today": {"date": total["today"], "submission_actions": total["today_submission_actions"],
                  "unique_applied": total["today_unique_applied"], "per_day_limit": per_day, "over": today_over},
        "this_round": None if run_stats is None else {
            "submission_actions": run_stats["submission_actions"], "unique_applied": run_stats["unique_jobs_applied"],
            "per_round_target": per_round, "over": round_over,
        },
        "by_company": companies,
        "by_platform": platforms,
        "per_company_max_default": per_company_max,
    }
    lines = ["quota%s" % (" (run %s)" % run_id if run_id else " (no open run)"),
             "  今日 / today %s：提交动作 / submission actions %d/%d%s · 新确认 / newly applied %d" % (
                 total["today"], total["today_submission_actions"], per_day, "  OVER" if today_over else "",
                 total["today_unique_applied"])]
    if run_stats is not None:
        lines.append("  本轮 / this round：提交动作 / submission actions %d · 去重岗 / unique applied %d/%d%s" % (
            run_stats["submission_actions"], run_stats["unique_jobs_applied"], per_round, "  TARGET REACHED" if round_over else ""))
    lines.append("  各公司 / by company（cap 取 rules.company_caps 覆盖，否则 per_company_max=%d）：" % per_company_max)
    for c in companies[:50]:
        lines.append("    %-40s %d/%d%s" % (c["company"], c["applied"], c["cap"], "  OVER" if c["over"] else ""))
    lines.append("  各平台 / by platform（除 LinkedIn 外无固定数字上限，按 run_state.quotas.platform_blocked 标记）：")
    for p in platforms:
        extra = " remaining=%s" % p.get("linkedin_daily_remaining") if "linkedin_daily_remaining" in p else ""
        lines.append("    %-22s %d%s%s" % (p["platform"], p["applied"], extra, "  OVER/BLOCKED" if p["over"] else ""))
    return data, "\n".join(lines), 0


def cmd_ledger_stats(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    st = stats(ctx.conn, ctx.args.run)
    lines = ["ledger stats%s" % (" (run %s)" % ctx.args.run if ctx.args.run else ""),
             "  去重 %d 岗 / 提交 %d 次（其中重复 %d）" % (st["unique_jobs_applied"], st["submission_actions"], st["duplicates"]),
             "  今日 %s：提交动作 %d · 新确认 %d" % (st["today"], st["today_submission_actions"], st["today_unique_applied"]),
             "  by status: %s" % json.dumps(st["by_status"], ensure_ascii=False),
             "  applied by platform: %s" % json.dumps(st["applied_by_platform"], ensure_ascii=False),
             "  open gates: %d · jobs known: %d" % (st["open_gates"], st["jobs_total"]),
             "  applied by company (unique jobs):"]
    for c, n in list(st["applied_by_company"].items())[:50]:
        lines.append("    %-40s %d" % (c, n))
    return st, "\n".join(lines), 0


def cmd_ledger_export(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    profile = _load_profile_optional(ctx)
    text = export_md.build_export(ctx.conn, profile, now_iso(), _per_company_max(profile))
    out = Path(ctx.args.output).expanduser() if ctx.args.output else ctx.paths.exports_dir / "投递台账.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return {"written_to": str(out), "bytes": len(text.encode("utf-8"))}, "ledger export -> %s" % out, 0


def cmd_ledger_migrate(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    src = Path(ctx.args.file).expanduser()
    if not src.is_file():
        raise UsageError("旧台账文件不存在 / legacy ledger file not found", {"path": str(src)})
    parse = migrate_legacy.parse_legacy_markdown(src.read_text(encoding="utf-8"))
    res = migrate_legacy.import_legacy(ctx.conn, parse, dedup.load_aliases(ctx.paths), profile_id=ctx.paths.profile_id,
                                       source_name=src.name, dry_run=ctx.args.dry_run)
    p = res["parse"]
    c = res["counts"]
    lines = ["migrate-legacy %s%s" % (src.name, " (dry-run)" if ctx.args.dry_run else ""),
             "  解析：已确认 %d 条（去重键 %d）· 中间状态 %d · 追踪表 %d 行 · 规则节跳过 %d 行 · 警告 %d" % (
                 p["confirmed_mentions"], p["confirmed_unique_keys"], p["intermediate"], p["tracking_rows"], p["rules_lines_skipped"], p["warnings"])]
    if not ctx.args.dry_run:
        lines.append("  写入：jobs +%d · applications +%d · 追加提交动作 %d · 证据 %d · 中间状态 %d · 追踪事件 %d · 已导入跳过 %d" % (
            c["jobs_created"], c["applications_created"], c["submission_actions_added"], c["evidence_added"],
            c["intermediate_created"], c["tracking_events"], c["skipped_already_imported"]))
        st = stats(ctx.conn)
        lines.append("  台账现在：去重 %d 岗 / 提交 %d 次（其中重复 %d）" % (st["unique_jobs_applied"], st["submission_actions"], st["duplicates"]))
    for w in res["warnings"][:20]:
        lines.append("  warn: %s" % w)
    return res, "\n".join(lines), 0


def cmd_ledger_assert(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    failures = run_assertions(ctx.conn, _per_company_max(_load_profile_optional(ctx)))
    data = {"ok": not failures, "failures": failures}
    if failures:
        return data, "ledger assert FAIL:\n" + "\n".join("  " + f for f in failures), 3
    return data, "ledger assert PASS (applied-has-evidence, unique-vs-actions, no-secrets, per-company-cap)", 0


def cmd_report(ctx: Ctx) -> tuple[dict[str, Any], str, int]:
    data = report_mod.build_report(ctx.conn, ctx.paths, ctx.args.run_id)
    text = report_mod.render_report_md(data)
    if ctx.args.output:
        out = Path(ctx.args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        data["written_to"] = str(out)
    data["markdown"] = text
    return data, text.rstrip(), 0


# ---- parser --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autoapply", description="auto-apply deterministic scripts (stdlib only)")
    p.add_argument("--data-dir", help="数据根目录 / data root (default $AUTO_APPLY_DATA_DIR or ~/auto-apply-data)")
    p.add_argument("--profile", help="profile_id -> <data-dir>/<profile_id>/ (default $AUTO_APPLY_PROFILE or the only profile)")
    p.add_argument("--json", action="store_true", help="机器可读输出 / machine-readable JSON on stdout")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selfcheck", help="环境自检 / environment self-check").set_defaults(fn=cmd_selfcheck)

    prof = sub.add_parser("profile", help="档案校验与一致性门 / profile validation, R3 gate").add_subparsers(dest="sub", required=True)
    v = prof.add_parser("validate")
    v.add_argument("file")
    v.add_argument("--no-file-check", action="store_true", help="不检查简历文件是否存在 / skip resume path existence check")
    v.set_defaults(fn=cmd_profile_validate)
    c = prof.add_parser("consistency")
    c.add_argument("file")
    c.add_argument("--resume-facts", required=True, help="resume_parse.json")
    c.add_argument("-o", "--output", help="consistency_report.json path (default <profile>/consistency_report.json)")
    c.set_defaults(fn=cmd_profile_consistency)

    facts = sub.add_parser("facts").add_subparsers(dest="sub", required=True)
    fr = facts.add_parser("render")
    fr.add_argument("file")
    fr.add_argument("-o", "--output", required=True)
    fr.set_defaults(fn=cmd_facts_render)

    run = sub.add_parser("run", help="run 检查点与关口 / run checkpoints and gates").add_subparsers(dest="sub", required=True)
    rn = run.add_parser("new")
    rn.add_argument("--mode", choices=list(enums.GATE_MODE_POLICIES), help="关口模式 / gate handling (default profile.policy.gate_mode or interactive)")
    rn.add_argument("--invocation", choices=list(enums.RUN_INVOCATIONS), default="apply", help="run_state.mode")
    rn.add_argument("--runtime", choices=list(enums.RUNTIMES))
    rn.add_argument("--target", type=int, help="本轮目标份数 / round target")
    rn.set_defaults(fn=cmd_run_new)
    rc = run.add_parser("checkpoint")
    rc.add_argument("run_id")
    rc.add_argument("--state", required=True, choices=list(enums.PHASES))
    rc.add_argument("--resume-to", choices=list(enums.PHASES), help="pending_user 时恢复目标 / phase to resume to")
    rc.add_argument("--gate", help="gate_id that suspends the run")
    rc.set_defaults(fn=cmd_run_checkpoint)
    rs = run.add_parser("show")
    rs.add_argument("run_id")
    rs.set_defaults(fn=cmd_run_show)
    rp = run.add_parser("pending")
    rp.add_argument("run_id")
    rp.set_defaults(fn=cmd_run_pending)
    rr = run.add_parser("resolve")
    rr.add_argument("run_id")
    rr.add_argument("action_id")
    rr.add_argument("--resolution", choices=list(enums.GATE_RESOLUTIONS), default="resolved")
    rr.add_argument("--note")
    rr.set_defaults(fn=cmd_run_resolve)
    rg = run.add_parser("gate", help="run 级关口（无 application）/ run-scoped gate without an application")
    rg.add_argument("run_id")
    _add_gate_args(rg, scope_choices=["run"])
    rg.set_defaults(fn=cmd_run_gate)
    run.add_parser("list").set_defaults(fn=cmd_run_list)

    pending = sub.add_parser("pending", help="待办动作维护 / pending-action maintenance").add_subparsers(dest="sub", required=True)
    pe = pending.add_parser("expire", help="把逾期 pending_action 标过期 / mark overdue pending_actions expired")
    pe.add_argument("run_id")
    pe.add_argument("--dry-run", action="store_true", help="只列出会过期的项，不写入 / list what would expire, write nothing")
    pe.set_defaults(fn=cmd_pending_expire)

    jobs = sub.add_parser("jobs", help="候选岗位与去重 / candidates and dedup").add_subparsers(dest="sub", required=True)
    ja = jobs.add_parser("add")
    ja.add_argument("file", help="candidates.jsonl")
    ja.add_argument("--run", help="run_id to fill into lines that lack one")
    ja.set_defaults(fn=cmd_jobs_add)
    jc = jobs.add_parser("check")
    jc.add_argument("company")
    jc.add_argument("title")
    jc.set_defaults(fn=cmd_jobs_check)
    jn = jobs.add_parser("normalize", help="填充 normalized/dedup_key/job_id / fill derived fields")
    jn.add_argument("file")
    jn.add_argument("-o", "--output", required=True)
    jn.add_argument("--run")
    jn.set_defaults(fn=cmd_jobs_normalize)

    queue = sub.add_parser("queue").add_subparsers(dest="sub", required=True)
    qb = queue.add_parser("build")
    qb.add_argument("run_id")
    qb.add_argument("--from", dest="source", required=True, help="candidates.jsonl")
    qb.add_argument("-o", "--output", help="apply_queue.jsonl (default runs/<run_id>/apply_queue.jsonl)")
    qb.add_argument("--approve-all", help="用户批准原话；给出后所有通过硬规则的候选入队 / user's approval note (D7)")
    qb.add_argument("--exclude", help="逗号分隔 job_id / comma-separated job_ids the user excluded")
    qb.set_defaults(fn=cmd_queue_build)

    app = sub.add_parser("app", help="申请项 / application items").add_subparsers(dest="sub", required=True)
    ast = app.add_parser("start")
    ast.add_argument("run_id")
    ast.add_argument("job_id")
    ast.add_argument("--channel", required=True, choices=list(enums.CHANNELS))
    ast.add_argument("--platform", choices=list(enums.PLATFORMS))
    ast.add_argument("--resume", help="resume path used")
    ast.add_argument("--note")
    ast.add_argument("--force", action="store_true", help="允许对已投岗位再次提交（需说明）/ allow a second submission")
    ast.set_defaults(fn=cmd_app_start)
    asu = app.add_parser("status")
    asu.add_argument("app_id")
    asu.add_argument("status", choices=list(enums.APP_STATUSES))
    asu.add_argument("--reason", help="skipped: skip_reason_code; failed: failure text; else appended to notes")
    asu.add_argument("--note")
    asu.add_argument("--count-submission", action="store_true", help="记一次提交动作 / count one submission action")
    asu.add_argument("--actor", default="executor")
    asu.set_defaults(fn=cmd_app_status)
    atr = app.add_parser("tracking", help="投后追踪状态；不改 applications.status / post-application tracking status only, never touches applications.status")
    atr.add_argument("app_id")
    atr.add_argument("tracking_status", choices=list(enums.TRACKING_STATUSES))
    atr.add_argument("--note")
    atr.add_argument("--actor", default="tracker")
    atr.set_defaults(fn=cmd_app_tracking)
    aev = app.add_parser("evidence")
    aev.add_argument("app_id")
    aev.add_argument("--type", required=True, choices=list(enums.EVIDENCE_TYPES))
    aev.add_argument("--url")
    aev.add_argument("--screenshot", help="screenshot / page text file to copy into evidence/<app_id>/")
    aev.add_argument("--file", help="alias of --screenshot")
    aev.add_argument("--page-title")
    aev.add_argument("--job-title-seen", help="岗位名/需求编号（success_page 必填）/ job title or req id seen on the page")
    aev.add_argument("--status-seen", help="ats_portal_status: 门户显示的状态文本 / status text shown in the portal")
    aev.add_argument("--subject", help="email subject")
    aev.add_argument("--from", "--email-from", dest="email_from", help="email sender / 邮件发件人")
    aev.add_argument("--received-at", help="email received time (ISO-8601)")
    aev.add_argument("--message-id")
    aev.add_argument("--excerpt", help="email excerpt (<=300 chars after redaction)")
    aev.add_argument("--matched-job-by", choices=list(enums.EVIDENCE_MATCHED_BY),
                     help="人工指定该证据如何对上这个岗位（不填则由脚本按 §7.1 规则判定）/ override how the evidence was matched to the job (auto-judged by §7.1 when omitted)")
    aev.add_argument("--legacy-ref")
    aev.add_argument("--captured-by", default="qa")
    aev.add_argument("--note")
    aev.add_argument("--mark-applied", action="store_true", help="合格则同时标 applied / set applied when it qualifies")
    aev.set_defaults(fn=cmd_app_evidence)
    ag = app.add_parser("gate")
    ag.add_argument("app_id")
    _add_gate_args(ag, scope_choices=list(enums.GATE_SCOPES))
    ag.set_defaults(fn=cmd_app_gate)
    ash = app.add_parser("show")
    ash.add_argument("app_id")
    ash.set_defaults(fn=cmd_app_show)

    ledger = sub.add_parser("ledger", help="台账 / ledger").add_subparsers(dest="sub", required=True)
    ls = ledger.add_parser("stats")
    ls.add_argument("--run")
    ls.set_defaults(fn=cmd_ledger_stats)
    le = ledger.add_parser("export")
    le.add_argument("-o", "--output", help="default <profile>/exports/投递台账.md")
    le.set_defaults(fn=cmd_ledger_export)
    lm = ledger.add_parser("migrate-legacy")
    lm.add_argument("file")
    lm.add_argument("--dry-run", action="store_true")
    lm.set_defaults(fn=cmd_ledger_migrate)
    ledger.add_parser("assert").set_defaults(fn=cmd_ledger_assert)

    rep = sub.add_parser("report", help="三栏汇报（只读台账）/ three-column report")
    rep.add_argument("run_id")
    rep.add_argument("-o", "--output", help="also write report.md")
    rep.set_defaults(fn=cmd_report)

    ps = sub.add_parser("presubmit", help="R10 提交前复核（checklists/pre_submit.md 里可机器判定的项）/ pre-submit review, machine-checkable subset only")
    ps.add_argument("app_id")
    ps.set_defaults(fn=cmd_presubmit)

    qt = sub.add_parser("quota", help="今日/本轮/各公司/各平台节流现状（供 SKILL.md 节流用）/ today's, this round's, per-company and per-platform throttling status")
    qt.add_argument("--run", help="run_id (default: the latest open run)")
    qt.set_defaults(fn=cmd_quota)
    return p


def _add_gate_args(sp: argparse.ArgumentParser, scope_choices: list[str]) -> None:
    sp.add_argument("--type", required=True, choices=list(enums.GATE_TYPES))
    sp.add_argument("--message", required=True, help="中文一句话（脱敏）/ one redacted sentence")
    sp.add_argument("--message-en")
    sp.add_argument("--scope", choices=scope_choices)
    sp.add_argument("--mode", choices=list(enums.GATE_MODES))
    sp.add_argument("--priority", choices=list(enums.PRIORITIES))
    sp.add_argument("--step", help="playbook step id, e.g. login.otp")
    sp.add_argument("--url")
    sp.add_argument("--draft-url")
    sp.add_argument("--field", help="triggering field label (redacted)")
    sp.add_argument("--missing", help="comma-separated missing field names")
    sp.add_argument("--option", action="append", help="user option text (repeatable)")
    sp.add_argument("--instructions", help="override zh instructions")
    sp.add_argument("--instructions-en")
    sp.add_argument("--resume-instructions")
    sp.add_argument("--runtime", choices=list(enums.RUNTIMES))


# ---- main ----------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx: Ctx | None = None
    try:
        ctx = Ctx(args)
        data, human, code = args.fn(ctx)
        if ctx.json:
            data = dict(data)
            data.setdefault("exit_code", code)
            sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
        else:
            sys.stdout.write(human + "\n")
        return code
    except AutoApplyError as e:
        sys.stderr.write(json.dumps(e.to_json(), ensure_ascii=False, default=str) + "\n")
        if not (ctx and ctx.json):
            sys.stderr.write("错误 / error [%s]: %s\n" % (e.code, e.message))
        return e.exit_code
    except Exception as e:  # noqa: BLE001 — last resort: never a silent crash, never a stack trace by default
        sys.stderr.write(json.dumps({"error": "internal_error", "detail": type(e).__name__}) + "\n")
        if os.environ.get("AUTO_APPLY_DEBUG") == "1":
            raise
        sys.stderr.write("内部错误 / internal error: %s（设 AUTO_APPLY_DEBUG=1 查看堆栈）\n" % type(e).__name__)
        return 1
    finally:
        if ctx is not None:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())

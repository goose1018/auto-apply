"""Gate protocol (ARCHITECTURE §3): pending_actions.jsonl (canonical) + pending_actions.md (rendered).

open_gate    -> append pending_action, insert gates row, suspend item (status pending_user) or run.
resolve      -> append updated line, update gates row, re-queue / skip / hand over to verify, resume run.
render       -> fixed bilingual markdown (§3.2). Text fields pass through redact() first.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from autoapply import enums, runstate
from autoapply.errors import GateError, UsageError
from autoapply.i18n import PRIORITY_LABEL, gate_instructions
from autoapply.ids import iso_plus_days, new_action_id, now_iso, parse_iso
from autoapply.ledger import (
    GateRow, get_application, insert_gate, log_write, open_gates, require_job, resolve_gate,
    set_application_status,
)
from autoapply.paths import DataPaths
from autoapply.redact import redact
from autoapply.schema_validate import SchemaSet

PENDING_JSONL = "pending_actions.jsonl"
PENDING_MD = "pending_actions.md"
_PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}
_RESOLUTION_TO_STATUS = {"resolved": "resolved", "skipped": "skipped", "user_completed": "user_completed",
                         "expired": "expired", "abandoned": "abandoned"}


@dataclass(frozen=True)
class GateRequest:
    gate_type: str
    message_zh: str
    message_en: str | None = None
    scope: str | None = None
    mode: str | None = None
    app_id: str | None = None
    priority: str | None = None
    playbook_step: str | None = None
    context: dict[str, Any] | None = None
    instructions_zh: str | None = None
    instructions_en: str | None = None
    resume_instructions: str | None = None
    runtime: str | None = None
    expires_days: int | None = None
    options: list[str] = field(default_factory=list)


def pending_path(paths: DataPaths, run_id: str) -> Path:
    return paths.run_dir(run_id) / PENDING_JSONL


def load_pending(paths: DataPaths, run_id: str) -> dict[str, dict[str, Any]]:
    """Last line per action_id wins (ARCHITECTURE §5.3)."""
    p = pending_path(paths, run_id)
    out: dict[str, dict[str, Any]] = {}
    if not p.is_file():
        return out
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            raise GateError("pending_actions.jsonl 第 %d 行不是合法 JSON / corrupt line" % n) from e
        if not isinstance(obj, dict) or "action_id" not in obj:
            raise GateError("pending_actions.jsonl 第 %d 行缺 action_id / missing action_id" % n)
        out[str(obj["action_id"])] = obj
    return out


def _append(paths: DataPaths, run_id: str, schemas: SchemaSet, obj: dict[str, Any]) -> None:
    schemas.require("pending_action", obj, "pending_action")
    run_dir = paths.run_dir(run_id)
    if not run_dir.is_dir():
        raise GateError("run 目录不存在 / run directory missing", {"run_id": run_id})
    with pending_path(paths, run_id).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def _gate_mode_for(run_opts: dict[str, Any], req: GateRequest) -> str:
    if req.mode:
        if req.mode not in enums.GATE_MODES:
            raise UsageError("mode 只能是 sync|async", {"mode": req.mode})
        return req.mode
    forced_sync = {"final_submit", "queue_approval", "consistency_mismatch", "browser_disconnected"}
    if req.gate_type in forced_sync:
        return "sync"
    return "sync" if run_opts.get("gate_mode", "interactive") == "interactive" else "async"


def open_gate(conn: sqlite3.Connection, paths: DataPaths, schemas: SchemaSet, run_id: str, req: GateRequest) -> dict[str, Any]:
    runstate.validate_run_id(run_id)
    if req.gate_type not in enums.GATE_TYPES:
        raise UsageError("gate_type 不合法 / invalid gate_type", {"gate_type": req.gate_type, "allowed": list(enums.GATE_TYPES)})
    scope = req.scope or ("run" if req.gate_type in enums.RUN_SCOPED_GATE_TYPES else "item")
    if scope not in enums.GATE_SCOPES:
        raise UsageError("scope 只能是 item|run", {"scope": scope})
    if scope == "item" and not req.app_id:
        raise UsageError("item 级关口必须带 application_id / item-scoped gate needs an app_id")
    app = get_application(conn, req.app_id) if req.app_id else None
    if req.app_id and app is None:
        raise GateError("台账中不存在该 application_id / application not in ledger", {"app_id": req.app_id})
    if app is not None and app["run_id"] and app["run_id"] != run_id:
        raise GateError("application 属于另一个 run / application belongs to a different run",
                        {"app_run_id": app["run_id"], "run_id": run_id})
    run_opts = runstate.load_run_options(paths, run_id)
    mode = _gate_mode_for(run_opts, req)
    priority = req.priority or ("high" if scope == "run" or req.gate_type in ("final_submit", "otp", "captcha") else "normal")
    if priority not in enums.PRIORITIES:
        raise UsageError("priority 只能是 high|normal|low", {"priority": priority})
    zh_default, en_default = gate_instructions(req.gate_type)
    ts = now_iso()
    action_id = new_action_id()
    expires_at = None if scope == "run" else iso_plus_days(req.expires_days or enums.DEFAULT_PENDING_EXPIRY_DAYS)
    job_ref = None
    if app is not None:
        job = require_job(conn, app["job_id"])
        job_ref = {"company": job["company_raw"], "title": job["title_raw"], "url": job["url"], "platform": app["platform"]}
    context: dict[str, Any] = dict(req.context or {})
    if req.options:
        context["options"] = list(req.options)
    obj: dict[str, Any] = {
        "action_id": action_id,
        "run_id": run_id,
        "app_id": req.app_id,
        "job_ref": job_ref,
        "gate_type": req.gate_type,
        "scope": scope,
        "mode": mode,
        "priority": priority,
        "status": "open",
        "opened_at": ts,
        "expires_at": expires_at,
        "resolved_at": None,
        "resolution_note": None,
        "playbook_step": req.playbook_step,
        "context": context or None,
        "agent_message": {"zh": redact(req.message_zh), "en": redact(req.message_en) if req.message_en else None},
        "user_instructions": {"zh": redact(req.instructions_zh or zh_default), "en": redact(req.instructions_en or en_default)},
        "resume_instructions": redact(req.resume_instructions) if req.resume_instructions else None,
        "runtime": req.runtime,
    }
    _append(paths, run_id, schemas, obj)
    insert_gate(conn, GateRow(
        gate_id=action_id, run_id=run_id, app_id=req.app_id, gate_type=req.gate_type, scope=scope, mode=mode,
        opened_at=ts, playbook_step=req.playbook_step, expires_at=expires_at,
        summary=redact(req.message_zh)[:300], runtime=req.runtime,
    ))
    # only in-flight items move to pending_user; submitted / terminal items keep their status
    if scope == "item" and app is not None and app["status"] in ("queued", "in_progress", "draft_saved", "ready_to_submit"):
        set_application_status(conn, str(req.app_id), "pending_user", actor="orchestrator")
    if scope == "run":
        runstate.suspend(paths, schemas, conn, run_id, action_id)
    render_and_write(paths, run_id)
    log_write(paths, run_id, "gate_open", {"action_id": action_id, "gate_type": req.gate_type, "scope": scope, "app_id": req.app_id})
    return obj


def resolve_action(conn: sqlite3.Connection, paths: DataPaths, schemas: SchemaSet, run_id: str, action_id: str,
                   resolution: str, note: str | None = None) -> dict[str, Any]:
    if resolution not in enums.GATE_RESOLUTIONS:
        raise UsageError("resolution 不合法 / invalid resolution", {"resolution": resolution, "allowed": list(enums.GATE_RESOLUTIONS)})
    actions = load_pending(paths, run_id)
    cur = actions.get(action_id)
    if cur is None:
        raise GateError("该 run 没有此 action_id / action not found in this run", {"action_id": action_id, "run_id": run_id})
    if cur.get("status") != "open":
        raise GateError("该项已处理 / action already closed", {"action_id": action_id, "status": cur.get("status")})
    ts = now_iso()
    updated = dict(cur)
    updated["status"] = _RESOLUTION_TO_STATUS[resolution]
    updated["resolved_at"] = ts
    updated["resolution_note"] = redact(note)[:500] if note else None
    _append(paths, run_id, schemas, updated)
    resolve_gate(conn, action_id, resolution, ts)
    app_id = cur.get("app_id")
    if cur.get("scope") == "item" and app_id:
        app = get_application(conn, str(app_id))
        if app is not None and app["status"] == "pending_user":
            if resolution == "resolved":
                set_application_status(conn, str(app_id), "queued", priority="high", actor="orchestrator", note=note)
            elif resolution == "skipped":
                set_application_status(conn, str(app_id), "skipped", skip_reason_code="user_excluded", actor="user", note=note)
            elif resolution == "user_completed":
                # user submitted it themselves -> counts as a submission action, still needs evidence (verify)
                set_application_status(conn, str(app_id), "submitted_unverified", actor="user", note=note)
            elif resolution == "expired":
                set_application_status(conn, str(app_id), "abandoned", actor="orchestrator", note=note)
            elif resolution == "abandoned":
                set_application_status(conn, str(app_id), "abandoned", actor="user", note=note)
    if cur.get("scope") == "run":
        state = runstate.load_run_state(paths, run_id)
        still_open = [g for g in open_gates(conn, run_id, "run")]
        if state.get("phase") == "pending_user" and not still_open and resolution in ("resolved", "user_completed", "skipped"):
            runstate.resume(paths, schemas, conn, run_id)
    render_and_write(paths, run_id)
    log_write(paths, run_id, "gate_resolve", {"action_id": action_id, "resolution": resolution})
    return updated


def expire_overdue(conn: sqlite3.Connection, paths: DataPaths, schemas: SchemaSet, run_id: str,
                   now: datetime | None = None) -> list[str]:
    expired: list[str] = []
    ref = now or parse_iso(now_iso())
    for action_id, obj in load_pending(paths, run_id).items():
        if obj.get("status") != "open" or not obj.get("expires_at"):
            continue
        if parse_iso(str(obj["expires_at"])) <= ref:
            resolve_action(conn, paths, schemas, run_id, action_id, "expired", "expired automatically")
            expired.append(action_id)
    return expired


# ---- rendering (ARCHITECTURE §3.2) ---------------------------------------------------------------
def _fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return parse_iso(value).strftime("%Y-%m-%d %H:%M")
    except UsageError:
        return value


def _fmt_date(value: str | None) -> str:
    if not value:
        return "不过期 / no expiry"
    try:
        return parse_iso(value).strftime("%Y-%m-%d")
    except UsageError:
        return value


def _sort_key(obj: dict[str, Any]) -> tuple[int, int, str]:
    return (0 if obj.get("scope") == "run" else 1, _PRIORITY_ORDER.get(str(obj.get("priority") or "normal"), 1), str(obj.get("opened_at") or ""))


def render_pending_md(run_id: str, actions: dict[str, dict[str, Any]], generated_at: str | None = None) -> str:
    items = sorted(actions.values(), key=_sort_key)
    open_items = [a for a in items if a.get("status") == "open"]
    expired_items = [a for a in items if a.get("status") == "expired"]
    handled_items = [a for a in items if a.get("status") not in ("open", "expired")]
    lines: list[str] = []
    lines.append("# 待用户动作 / Pending actions — %s" % run_id)
    lines.append("> 生成 %s · 打开 %d · 已处理 %d · 过期 %d" % (_fmt_dt(generated_at or now_iso()), len(open_items), len(handled_items), len(expired_items)))
    lines.append("> 处理完后回到会话说「继续」或 \"continue\"；只处理部分也可以，说明哪几项即可。")
    lines.append("")
    if not open_items:
        lines.append("（当前没有待处理项 / Nothing pending）")
        lines.append("")
    for i, a in enumerate(open_items, 1):
        lines.extend(_render_item(i, a))
        lines.append("")
    if handled_items or expired_items:
        lines.append("## 已处理 / Handled")
        for a in handled_items + expired_items:
            ref = a.get("job_ref") or {}
            label = "%s — %s" % (ref.get("company"), ref.get("title")) if ref else "(run)"
            lines.append("- [%s] %s · %s · %s · id: %s" % (a.get("gate_type"), label, a.get("status"), _fmt_dt(a.get("resolved_at")), a.get("action_id")))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_item(index: int, a: dict[str, Any]) -> list[str]:
    ref = a.get("job_ref") or {}
    scope_label = "（整轮挂起 / run）" if a.get("scope") == "run" else ""
    head = "%s — %s" % (ref.get("company"), ref.get("title")) if ref else "整轮 / Run-level"
    pr = PRIORITY_LABEL.get(str(a.get("priority") or "normal"), ("中", "normal"))[0]
    out = ["## %d. [%s] %s%s　　优先级 %s · 到期 %s" % (index, a.get("gate_type"), head, scope_label, pr, _fmt_date(a.get("expires_at")))]
    ctx = a.get("context") or {}
    url = ctx.get("url") or ref.get("url")
    if url:
        out.append("- 页面 / Page: %s" % url)
    step = a.get("playbook_step")
    msg = a.get("agent_message") or {}
    stuck = msg.get("zh") or ""
    if step:
        stuck = "%s（playbook step `%s`）" % (stuck, step)
    out.append("- 卡在 / Stuck at: %s" % stuck)
    if msg.get("en"):
        out.append("  %s" % msg["en"])
    if ctx.get("draft_saved") is not None:
        draft = "已保存" if ctx.get("draft_saved") else "未保存"
        if ctx.get("draft_url"):
            draft += "（%s）" % ctx["draft_url"]
        out.append("- 草稿 / Draft: %s" % draft)
    if ctx.get("field_label"):
        out.append("- 字段 / Field: %s" % ctx["field_label"])
    if ctx.get("missing_fields"):
        out.append("- 缺失字段 / Missing fields: %s" % ", ".join(str(x) for x in ctx["missing_fields"]))
    if ctx.get("options"):
        out.append("- 可选 / Options: %s" % " ".join(str(x) for x in ctx["options"]))
    ui = a.get("user_instructions") or {}
    out.append("- 你需要做 / What you do: %s" % (ui.get("zh") or ""))
    if ui.get("en"):
        out.append("  %s" % ui["en"])
    if a.get("resume_instructions"):
        out.append("- 恢复后 Agent 会 / After resume: %s" % a["resume_instructions"])
    out.append("- id: %s" % a.get("action_id"))
    return out


def render_and_write(paths: DataPaths, run_id: str) -> str:
    text = render_pending_md(run_id, load_pending(paths, run_id))
    (paths.run_dir(run_id) / PENDING_MD).write_text(text, encoding="utf-8")
    return text

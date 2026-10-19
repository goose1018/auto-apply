"""Three-column report data (ARCHITECTURE §1.3 report). Read-only over ledger + run files. Business layer."""

from __future__ import annotations

import sqlite3
from typing import Any

from autoapply import gates, runstate
from autoapply.ledger import applications_for_run, evidence_for_app, require_job, stats
from autoapply.paths import DataPaths

STUCK_STATUSES: tuple[str, ...] = ("failed", "skipped", "abandoned", "submitted_unverified", "pending_user", "draft_saved", "withdrawn")


def build_report(conn: sqlite3.Connection, paths: DataPaths, run_id: str) -> dict[str, Any]:
    state = runstate.load_run_state(paths, run_id)
    apps = applications_for_run(conn, run_id)
    applied: list[dict[str, Any]] = []
    stuck: list[dict[str, Any]] = []
    for a in apps:
        job = require_job(conn, str(a["job_id"]))
        base = {"app_id": a["app_id"], "company": job["company_raw"], "title": job["title_raw"], "channel": a["channel"],
                "platform": a["platform"], "status": a["status"]}
        if a["status"] == "applied":
            ev = [e["evidence_type"] for e in evidence_for_app(conn, str(a["app_id"])) if e["qualifies"]]
            applied.append({**base, "applied_confirmed_at": a["applied_confirmed_at"], "evidence": ev,
                            "submission_action_count": a["submission_action_count"]})
        elif a["status"] in STUCK_STATUSES:
            gate = conn.execute("SELECT gate_type, summary, resolved_at FROM gates WHERE app_id=? ORDER BY opened_at DESC LIMIT 1",
                                (a["app_id"],)).fetchone()
            stuck.append({**base, "skip_reason_code": a["skip_reason_code"], "failure_reason": a["failure_reason"],
                          "gate_type": gate["gate_type"] if gate else None, "gate_summary": gate["summary"] if gate else None,
                          "gate_open": bool(gate and gate["resolved_at"] is None),
                          "note": (a["notes"] or "").splitlines()[-1] if a["notes"] else None})
    pending = [a for a in gates.load_pending(paths, run_id).values() if a.get("status") == "open"]
    pending.sort(key=lambda x: (0 if x.get("scope") == "run" else 1, str(x.get("opened_at"))))
    run_stats = stats(conn, run_id)
    total_stats = stats(conn)
    return {
        "run_id": run_id,
        "phase": state.get("phase"),
        "resume_to": state.get("resume_to"),
        "started_at": state.get("started_at"),
        "updated_at": state.get("updated_at"),
        "run": {"unique_jobs_applied": run_stats["unique_jobs_applied"], "submission_actions": run_stats["submission_actions"],
                "duplicates": run_stats["duplicates"], "by_status": run_stats["by_status"]},
        "total": {"unique_jobs_applied": total_stats["unique_jobs_applied"], "submission_actions": total_stats["submission_actions"],
                  "duplicates": total_stats["duplicates"], "today_submission_actions": total_stats["today_submission_actions"]},
        "applied": applied,
        "pending": [{"action_id": p.get("action_id"), "gate_type": p.get("gate_type"), "scope": p.get("scope"),
                     "priority": p.get("priority"), "job_ref": p.get("job_ref"), "message": (p.get("agent_message") or {}).get("zh"),
                     "expires_at": p.get("expires_at")} for p in pending],
        "stuck": stuck,
    }


def render_report_md(data: dict[str, Any]) -> str:
    run = data["run"]
    total = data["total"]
    lines: list[str] = []
    lines.append("# 投递汇报 / Report — %s" % data["run_id"])
    lines.append("> 状态 %s · 本轮去重 %d 岗 / 提交 %d 次（其中重复 %d） · 累计去重 %d 岗 / 提交 %d 次（其中重复 %d） · 今日提交 %d 次"
                 % (data["phase"], run["unique_jobs_applied"], run["submission_actions"], run["duplicates"],
                    total["unique_jobs_applied"], total["submission_actions"], total["duplicates"], total["today_submission_actions"]))
    lines.append("> 数字只来自台账 ledger.sqlite / All numbers come from the ledger.")
    lines.append("")
    lines.append("## 1. 已确认投递 / Confirmed applications（%d）" % len(data["applied"]))
    if data["applied"]:
        lines.append("| 公司 | 岗位 | 渠道 | 证据 | 确认时间 |")
        lines.append("|---|---|---|---|---|")
        for a in data["applied"]:
            lines.append("| %s | %s | %s | %s | %s |" % (a["company"], a["title"], a["channel"], "+".join(a["evidence"]) or "—", str(a.get("applied_confirmed_at") or "")[:16]))
    else:
        lines.append("（本轮暂无 / none this run）")
    lines.append("")
    lines.append("## 2. 待用户动作 / Pending user actions（%d）" % len(data["pending"]))
    if data["pending"]:
        for i, p in enumerate(data["pending"], 1):
            ref = p.get("job_ref") or {}
            label = "%s — %s" % (ref.get("company"), ref.get("title")) if ref else "整轮 / run-level"
            lines.append("%d. [%s] %s：%s（id %s）" % (i, p["gate_type"], label, p.get("message") or "", p["action_id"]))
        lines.append("详见 runs/%s/pending_actions.md" % data["run_id"])
    else:
        lines.append("（无 / none）")
    lines.append("")
    lines.append("## 3. 卡壳原因 / Blocked or skipped（%d）" % len(data["stuck"]))
    if data["stuck"]:
        lines.append("| 公司 | 岗位 | 状态 | 原因 |")
        lines.append("|---|---|---|---|")
        for s in data["stuck"]:
            reason = s.get("skip_reason_code") or s.get("failure_reason") or (("关口 %s" % s["gate_type"]) if s.get("gate_type") else "") or s.get("note") or ""
            if s.get("gate_summary") and s.get("gate_type"):
                reason = "%s：%s" % (reason, s["gate_summary"]) if reason else s["gate_summary"]
            lines.append("| %s | %s | %s | %s |" % (s["company"], s["title"], s["status"], reason))
    else:
        lines.append("（无 / none）")
    lines.append("")
    return "\n".join(lines) + "\n"

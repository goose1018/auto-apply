"""Ledger -> exports/投递台账.md in the legacy "four sections" format (BRIEF D11, ARCHITECTURE §5.6).

Idempotent: the body depends only on ledger + profile content; only the header carries the export time.
Section 3 renders rules from profile.json and never includes contact details or secrets.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from autoapply import enums
from autoapply.ledger import events, evidence_for_app, open_gates, row_to_dict
from autoapply.redact import redact

STATUS_ZH: dict[str, str] = {
    "queued": "已入队", "in_progress": "填表中", "draft_saved": "草稿已保存", "pending_user": "待用户动作",
    "ready_to_submit": "待提交", "submitted_unverified": "已提交待核实", "applied": "已投", "skipped": "已跳过",
    "failed": "失败", "withdrawn": "已撤回", "abandoned": "已放弃",
}
TRACKING_ZH: dict[str, str] = {
    "none": "", "receipt": "已收回执", "under_review": "审核中", "assessment": "测评", "interview": "面试",
    "offer": "Offer", "rejected": "拒信", "closed": "已关闭",
}
EVIDENCE_SHORT: dict[str, str] = {
    "success_page": "成功页", "ats_confirmation_email": "ATS确认邮件", "employer_confirmation_email": "雇主确认邮件",
    "ats_portal_status": "门户状态", "legacy_import": "旧台账", "review_page_screenshot": "确认页截图",
    "form_completed_screenshot": "填表截图", "draft_saved": "草稿", "account_verification_email": "账号验证邮件",
    "external_redirect": "外跳", "open_tab": "打开页面", "generic_ack_email": "泛回执",
}
CHANNEL_ZH: dict[str, str] = {
    "company_site": "官网", "linkedin": "LinkedIn", "jobstreet": "Jobstreet", "mycareersfuture": "MyCareersFuture",
    "email": "邮件", "other": "其他",
}


def _fmt_list(values: list[Any]) -> str:
    return "、".join(str(v) for v in values) if values else "（无）"


def _company_groups(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """company_norm -> {label, jobs: {job_id: {title, channels, evidence_types}}} for applied applications."""
    groups: dict[str, dict[str, Any]] = {}
    rows = conn.execute(
        """SELECT a.app_id, a.job_id, a.channel, j.company_norm, j.company_raw, j.title_raw, j.first_seen_at
           FROM applications a JOIN jobs j ON j.job_id = a.job_id WHERE a.status='applied'
           ORDER BY j.company_norm, j.first_seen_at, j.title_raw, a.created_at"""
    ).fetchall()
    for r in rows:
        g = groups.setdefault(r["company_norm"], {"label": r["company_raw"], "jobs": {}})
        job = g["jobs"].setdefault(r["job_id"], {"title": r["title_raw"], "channels": [], "evidence": []})
        if r["channel"] not in job["channels"]:
            job["channels"].append(r["channel"])
        for ev in evidence_for_app(conn, r["app_id"]):
            if ev["qualifies"] and ev["evidence_type"] not in job["evidence"]:
                job["evidence"].append(ev["evidence_type"])
    return groups


def _section_confirmed(conn: sqlite3.Connection, per_company_max: int) -> list[str]:
    lines = ["## 一、已确认投递（禁止重复）", ""]
    groups = _company_groups(conn)
    if not groups:
        lines.append("（暂无 / none yet）")
        lines.append("")
        return lines
    for company_norm in sorted(groups, key=lambda k: (groups[k]["label"].lower(), k)):
        g = groups[company_norm]
        parts: list[str] = []
        for job in g["jobs"].values():
            ch = "/".join(CHANNEL_ZH.get(c, c) for c in job["channels"])
            ev = "+".join(EVIDENCE_SHORT.get(e, e) for e in job["evidence"]) or "无合格证据"
            parts.append("%s（%s，%s）" % (job["title"], ch, ev))
        line = "- %s — %s" % (g["label"], "；".join(parts))
        n = len(g["jobs"])
        if n >= per_company_max:
            line += " —— **已投 %d 份，不再新投**" % n
        lines.append(line)
    lines.append("")
    return lines


def _section_intermediate(conn: sqlite3.Connection) -> list[str]:
    lines = ["## 二、未投但有中间状态（重投前需先查状态）", ""]
    rows = conn.execute(
        """SELECT a.*, j.company_raw, j.title_raw FROM applications a JOIN jobs j ON j.job_id=a.job_id
           WHERE a.status IN (%s) OR (a.status='skipped' AND a.skip_reason_code IN (%s))
           ORDER BY j.company_raw, j.title_raw, a.created_at"""
        % (",".join("'%s'" % s for s in sorted(enums.EXPORT_INTERMEDIATE_STATUSES)),
           ",".join("'%s'" % s for s in sorted(enums.EXPORT_INTERMEDIATE_SKIP_REASONS)))
    ).fetchall()
    if not rows:
        lines.append("（暂无 / none）")
        lines.append("")
        return lines
    for r in rows:
        gate = conn.execute(
            "SELECT gate_type, summary, resolution FROM gates WHERE app_id=? ORDER BY opened_at DESC LIMIT 1", (r["app_id"],)
        ).fetchone()
        detail: list[str] = []
        if r["skip_reason_code"]:
            detail.append(str(r["skip_reason_code"]))
        if r["failure_reason"]:
            detail.append(str(r["failure_reason"]))
        if gate is not None:
            detail.append("关口 %s%s" % (gate["gate_type"], "：" + str(gate["summary"]) if gate["summary"] else ""))
        if r["tracking_status"] and r["tracking_status"] != "none":
            detail.append(TRACKING_ZH.get(str(r["tracking_status"]), str(r["tracking_status"])))
        if r["notes"]:
            detail.append(str(r["notes"]).splitlines()[-1][:120])
        lines.append("- %s — %s：%s%s" % (
            r["company_raw"], r["title_raw"], STATUS_ZH.get(str(r["status"]), str(r["status"])),
            "（%s）" % "；".join(detail) if detail else "",
        ))
    lines.append("")
    return lines


def _section_rules(profile: dict[str, Any] | None, per_company_max: int) -> list[str]:
    lines = ["## 三、既定投递规则", ""]
    if profile:
        intent = profile.get("intent") or {}
        salary = profile.get("salary") or {}
        rules = profile.get("rules") or {}
        policy = profile.get("policy") or {}
        window = intent.get("window") or {}
        lines.append("- 目标：%s；类型 %s；方向 %s；窗口 %s ~ %s" % (
            _fmt_list(intent.get("locations") or []), _fmt_list(intent.get("types") or []),
            _fmt_list(intent.get("keywords") or []), window.get("start") or "?", window.get("end") or "?"))
        if intent.get("excluded_directions"):
            lines.append("- 排除方向：%s" % _fmt_list(intent["excluded_directions"]))
        if salary:
            floor = salary.get("hard_floor")
            lines.append("- 薪资：硬下限 %s%s；未披露%s；无薪%s" % (
                salary.get("currency") or "", floor if floor is not None else "未设",
                "照投" if salary.get("apply_if_undisclosed") in (None, True) else "不投",
                "可投" if salary.get("allow_unpaid") else "不投"))
        bl = [r.get("name") for r in rules.get("company_blacklist") or [] if isinstance(r, dict)]
        rf = [r.get("name") for r in rules.get("reserve_for_referral") or [] if isinstance(r, dict)]
        lines.append("- 黑名单：%s；保留内推：%s" % (_fmt_list(bl), _fmt_list(rf)))
        if rules.get("title_exclusions") or rules.get("industry_exclusions"):
            lines.append("- 岗位名排除：%s；行业排除：%s" % (_fmt_list(rules.get("title_exclusions") or []), _fmt_list(rules.get("industry_exclusions") or [])))
        lines.append("- 节奏：每轮 %s、每日 ≤%s、同公司 ≤%s、每 %s 份汇报（BRIEF D13）" % (
            rules.get("per_round") or enums.DEFAULT_PER_ROUND, rules.get("per_day") or enums.DEFAULT_PER_DAY,
            per_company_max, policy.get("report_every_n") or 5))
        lines.append("- 提交模式：%s；关口模式：%s；开放题：%s；求职信：%s；EEO 默认：%s" % (
            policy.get("submit_mode"), policy.get("gate_mode") or "interactive", policy.get("open_question_policy") or "approve",
            policy.get("cover_letter_policy") or "approve", policy.get("eeo_default") or "prefer_not_to_say"))
        if rules.get("channel_priority"):
            lines.append("- 渠道优先级：%s" % " > ".join(str(c) for c in rules["channel_priority"]))
    else:
        lines.append("- （profile.json 不存在，仅列固定规则）")
    lines.append("- 计数规则：只有职位级成功页或雇主/ATS 确认邮件才算已投；填完表、最终确认页、账号验证邮件、打开的标签页均不算（BRIEF §3）")
    lines.append("- 去重规则：公司 + 岗位名规范化后为去重键，渠道是属性；汇报写「去重 N 岗 / 提交 M 次（其中重复 K）」（R1）")
    lines.append("- 必停关口：密码/新建账号、验证码、邮箱/短信 OTP、证件号、支付、本人声明题、最终提交（confirm 模式）")
    lines.append("- 必跳过并记账：日期窗不符、学历门槛不符、薪资低于下限、已投、黑名单/保留内推名单")
    lines.append("- 事实底线：不编造任何经历、日期、签证与声明题答案；缺失字段跳过并记账")
    lines.append("")
    return lines


def _section_tracking(conn: sqlite3.Connection) -> list[str]:
    lines = ["## 四、状态追踪表（新投递与状态变化只在这里追加）", "",
             "| 日期 | 公司 | 岗位 | 渠道 | 状态 | 证据/备注 |", "|---|---|---|---|---|---|"]
    job_cache: dict[str, dict[str, Any]] = {}
    app_cache: dict[str, dict[str, Any]] = {}

    def job_of(job_id: str | None) -> dict[str, Any]:
        if not job_id:
            return {}
        if job_id not in job_cache:
            job_cache[job_id] = row_to_dict(conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()) or {}
        return job_cache[job_id]

    def app_of(app_id: str | None) -> dict[str, Any]:
        if not app_id:
            return {}
        if app_id not in app_cache:
            app_cache[app_id] = row_to_dict(conn.execute("SELECT * FROM applications WHERE app_id=?", (app_id,)).fetchone()) or {}
        return app_cache[app_id]

    for ev in events(conn, enums.EXPORT_TRACKING_EVENT_KINDS):
        payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
        job = job_of(ev.get("job_id"))
        app = app_of(ev.get("app_id"))
        company = payload.get("company") or job.get("company_raw") or ""
        title = payload.get("title") or job.get("title_raw") or ""
        channel = payload.get("channel") or app.get("channel") or ""
        kind = str(ev["kind"])
        if kind == "applied":
            status = "已投"
        elif kind == "skipped":
            status = "已跳过"
        elif kind == "gate_opened":
            status = "关口 %s" % payload.get("gate_type")
        elif kind == "tracking_update":
            ts_val = payload.get("tracking_status")
            status = TRACKING_ZH.get(str(ts_val), str(ts_val)) if ts_val else "状态更新"
        else:
            status = STATUS_ZH.get(str(payload.get("to")), str(payload.get("to") or kind))
        note_parts: list[str] = []
        if payload.get("skip_reason_code"):
            note_parts.append(str(payload["skip_reason_code"]))
        if payload.get("note"):
            note_parts.append(str(payload["note"]))
        if payload.get("summary"):
            note_parts.append(str(payload["summary"]))
        if kind == "applied" and ev.get("app_id"):
            types = [EVIDENCE_SHORT.get(e["evidence_type"], e["evidence_type"]) for e in evidence_for_app(conn, str(ev["app_id"])) if e["qualifies"]]
            if types:
                note_parts.append("+".join(types))
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            str(ev["at"])[:10], _cell(company), _cell(title), _cell(CHANNEL_ZH.get(str(channel), str(channel))),
            _cell(status), _cell("；".join(note_parts)),
        ))
    lines.append("")
    return lines


def _cell(text: str) -> str:
    return redact(str(text)).replace("|", "\\|").replace("\n", " ")


def build_export(conn: sqlite3.Connection, profile: dict[str, Any] | None, exported_at: str,
                 per_company_max: int = enums.DEFAULT_PER_COMPANY_MAX) -> str:
    lines: list[str] = ["# 求职投递台账（防重复主清单）", "",
                        "> 由 auto-apply 导出于 %s，来源 ledger.sqlite；手改会被覆盖。" % exported_at,
                        "> 口径：只有「明确成功页 / 雇主确认邮件」才算已投。投递前必须先查本文件，已投的公司+岗位组合一律不重投。", ""]
    lines += _section_confirmed(conn, per_company_max)
    lines += _section_intermediate(conn)
    lines += _section_rules(profile, per_company_max)
    lines += _section_tracking(conn)
    open_run_gates = len([g for g in conn.execute("SELECT 1 FROM gates WHERE resolved_at IS NULL")])
    if open_run_gates:
        lines.append("> 当前有 %d 个未处理关口，见对应 run 的 pending_actions.md。" % open_run_gates)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def export_body(text: str) -> str:
    """Everything except the export-time header line (for idempotence checks)."""
    return "\n".join(l for l in text.splitlines() if not l.startswith("> 由 auto-apply 导出于"))


__all__ = ["build_export", "export_body", "open_gates"]

"""facts_card.json (canonical) -> facts_card.md (rendered, the object the user signs). Business layer."""

from __future__ import annotations

from typing import Any

from autoapply.schema_validate import SchemaSet

CATEGORY_LABELS: dict[str, str] = {
    "identity": "身份 / Identity", "education": "教育 / Education", "experience": "经历 / Experience",
    "skill": "技能 / Skills", "achievement": "成果 / Achievements", "availability": "可到岗 / Availability",
    "work_permit": "工作许可 / Work permit", "salary": "薪资 / Salary", "declaration": "声明 / Declarations",
    "motivation": "动机 / Motivation", "other": "其他 / Other",
}
STATUS_LABELS: dict[str, str] = {"draft": "草稿 / draft", "confirmed": "已确认 / confirmed",
                                 "edited": "已修改待确认 / edited", "rejected": "已否决 / rejected"}


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_facts_md(schemas: SchemaSet, card: dict[str, Any]) -> str:
    schemas.require("facts_card", card, "facts_card.json")
    meta = card["meta"]
    facts: list[dict[str, Any]] = list(card.get("facts") or [])
    confirmed = sum(1 for f in facts if f.get("status") == "confirmed")
    lines: list[str] = []
    lines.append("# 事实红线卡 / Facts card — %s" % meta["profile_id"])
    lines.append("> 生成 / generated: %s · 版本 / version: %s · 事实 %d 条，已确认 %d 条 / %d facts, %d confirmed"
                 % (meta["generated_at"], meta["version"], len(facts), confirmed, len(facts), confirmed))
    signed = "已签字 / signed at %s" % meta.get("signed_at") if meta.get("signed_by_user") else "未签字 / not signed"
    lines.append("> 签字状态 / sign-off: %s" % signed)
    lines.append("> 规则：Content Agent 只能引用状态为「已确认」的事实；本文件由 facts_card.json 渲染，手改会被覆盖。")
    lines.append("> Rule: only facts marked confirmed may be cited. Rendered from facts_card.json; manual edits are overwritten.")
    lines.append("")
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for f in facts:
        by_cat.setdefault(str(f.get("category")), []).append(f)
    for cat in CATEGORY_LABELS:
        items = by_cat.get(cat)
        if not items:
            continue
        lines.append("## %s" % CATEGORY_LABELS[cat])
        lines.append("")
        lines.append("| id | 事实 / Statement | 来源 / Source | 状态 / Status | 可用于开放题 | 敏感度 |")
        lines.append("|---|---|---|---|---|---|")
        for f in items:
            src = f.get("source") or {}
            src_text = str(src.get("type", ""))
            if src.get("ref"):
                src_text += " (%s)" % src["ref"]
            stmt = _esc(str(f.get("statement", "")))
            if f.get("statement_en"):
                stmt += "<br>" + _esc(str(f["statement_en"]))
            usable = f.get("usable_in_open_answers")
            usable_text = "是 / yes" if usable in (None, True) else "否 / no"
            lines.append("| %s | %s | %s | %s | %s | %s |" % (
                f.get("fact_id"), stmt, _esc(src_text), STATUS_LABELS.get(str(f.get("status")), str(f.get("status"))),
                usable_text, str(f.get("sensitivity") or "standard"),
            ))
        lines.append("")
    forbidden = card.get("forbidden_claims") or []
    lines.append("## 禁止说法 / Forbidden claims")
    lines.append("")
    if forbidden:
        for c in forbidden:
            lines.append("- %s" % c)
    else:
        lines.append("（无 / none）")
    lines.append("")
    lines.append("## 签字 / Sign-off")
    lines.append("")
    lines.append("- 我确认以上标为「已确认」的事实属实，可用于填写申请表与开放题。")
    lines.append("- I confirm the facts marked confirmed are true and may be used in application forms and open answers.")
    lines.append("- 签字 / Signed: %s" % (meta.get("signed_at") or "________"))
    return "\n".join(lines) + "\n"

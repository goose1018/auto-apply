"""Pre-submit review (R10; checklists/pre_submit.md §1). Business layer.

Judges the subset of the pre-submit checklist that a deterministic script can decide from
profile.json, the application/job ledger rows, and files already on disk (the resume file's own
digest, and the run item's content/ files). The remaining checklist items need a live page read
(email field, work-pass/sponsorship answer text, JD location, attachments, required-field
readback, forbidden-field readback) — those are never judged here; they stay `status="unverified"`
and remain the QA Agent's job per checklists/pre_submit.md (this module changes nothing about
that document or that Agent's responsibility).

`items[].name` follows schemas/application.schema.json `pre_submit_check.items[].name` where a
direct match exists (name_order, phone_country_code, graduation_year, internship_window, salary,
resume_version); the remaining checks reuse `name="other"` with the same `note` labels the
checklist itself already uses (dedup_not_applied, declarations_preset, open_answers_approved) so a
human reading both documents sees the same vocabulary.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from autoapply.ids import now_iso, sha256_file
from autoapply.ledger import applications_for_job, require_application, require_job
from autoapply.paths import DataPaths
from autoapply.redact import mask_name, mask_phone

# checklists/pre_submit.md items that need a live page read; always reported as unverified.
NEEDS_MANUAL_CHECK: tuple[tuple[str, str], ...] = (
    ("email", "邮箱字段与页面所填是否一致需现场回读，不得凭记忆判断（I-03）/ compare against the value actually seen on the page"),
    ("location", "岗位地点是否落在 intent.locations / remote_ok 需要打开官网 JD 核对，台账字段不够 / needs the live JD, the ledger row is not enough"),
    ("work_pass_answer", "表单里工作授权/准证答案需现场回读并与档案比对 / needs the live form"),
    ("sponsorship_answer", "表单里现在/未来是否需要赞助两题需现场回读 / needs the live form"),
    ("other", "所有标必填字段需逐个现场回读非空，自动完成控件需确认已选中而非仅有输入文字（required_fields_readback，I-09）/ needs the live form"),
    ("other", "岗位要求的成绩单/证书是否已上传、不要求的是否留空，需现场核对（attachments）/ needs the live form"),
    ("other", "证件号/银行/支付字段是否留空需现场核对，不读取内容（no_forbidden_fields_filled）/ needs the live form, content itself is never read"),
)

REQUIRED_DECLARATIONS: tuple[str, ...] = (
    "criminal_record", "bankruptcy", "vaccination_status", "relatives_in_company",
    "previously_applied_or_employed", "non_compete", "background_check_consent", "data_processing_consent",
)


def _item(name: str, status: str, note: str) -> dict[str, Any]:
    return {"name": name, "status": status, "ok": status == "pass", "note": note}


def _ym(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or len(value) < 7:
        return None
    try:
        return int(value[:4]), int(value[5:7])
    except ValueError:
        return None


def _months(ym: tuple[int, int]) -> int:
    return ym[0] * 12 + ym[1]


def _hard_conditions(job: dict[str, Any]) -> dict[str, Any]:
    raw = job.get("hard_conditions")
    if not raw:
        return {}
    try:
        return json.loads(str(raw)) or {}
    except ValueError:
        return {}


def _check_name_order(profile: dict[str, Any]) -> dict[str, Any]:
    name = (profile.get("identity") or {}).get("name") or {}
    given, family, order = name.get("given"), name.get("family"), name.get("name_order")
    missing = [k for k, v in (("given", given), ("family", family), ("name_order", order)) if not v]
    if missing:
        return _item("name_order", "fail", "profile.identity.name 缺 %s，无法确定表单姓名字段拆分 / missing %s" % (",".join(missing), ",".join(missing)))
    return _item("name_order", "pass", "given=%s family=%s order=%s" % (mask_name(str(given)), mask_name(str(family)), order))


def _check_phone(profile: dict[str, Any]) -> dict[str, Any]:
    phones = (profile.get("identity") or {}).get("phones") or []
    if not phones:
        return _item("phone_country_code", "fail", "profile.identity.phones 为空 / no phone on file")
    default = next((p for p in phones if isinstance(p, dict) and p.get("is_default")), phones[0])
    cc, num = default.get("country_code"), default.get("number")
    if not cc or not num:
        return _item("phone_country_code", "fail", "默认手机缺区号或号码 / default phone missing country_code or number")
    return _item("phone_country_code", "pass", mask_phone("%s %s" % (cc, num)))


def _check_graduation(profile: dict[str, Any]) -> dict[str, Any]:
    edu = profile.get("education") or []
    current = [e for e in edu if isinstance(e, dict) and e.get("is_current")]
    if not current:
        return _item("graduation_year", "fail", "education[] 没有 is_current=true 的条目，无法确定要填的毕业年月 / no education entry marked is_current")
    end = current[0].get("end_expected")
    if not end:
        return _item("graduation_year", "fail", "is_current 教育条目缺 end_expected / the current education entry has no end_expected")
    text = str(end)
    masked = (text[:5] + "*") if len(text) >= 6 else text
    return _item("graduation_year", "pass", "end_expected=%s" % masked)


def _check_resume(app: dict[str, Any], job: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    path = app.get("resume_path")
    if not path:
        items.append(_item("resume_version", "fail", "application.resume_path 未设置（app start 未带 --resume）/ no resume recorded on this application"))
        return items
    p = Path(str(path)).expanduser()
    if not p.is_file():
        items.append(_item("resume_version", "fail", "简历文件在本机不存在 / resume file not found on this machine"))
    else:
        recorded = app.get("resume_sha256")
        actual = sha256_file(p)
        if not recorded:
            items.append(_item("resume_version", "fail", "application.resume_sha256 未记录，无法核实是不是当时用的那份 / resume_sha256 not recorded"))
        elif actual != recorded:
            items.append(_item("resume_version", "fail", "文件已变化：当前 sha256 与记录不符 / file changed since it was recorded (sha256 mismatch)"))
        else:
            items.append(_item("resume_version", "pass", "简历文件存在且 sha256 与记录一致 / file exists, sha256 matches the recorded value"))
    hc = _hard_conditions(job)
    required_lang = hc.get("resume_language_required")
    resume_lang = app.get("resume_language")
    if not required_lang:
        items.append(_item("resume_version", "pass", "岗位未指定简历语言要求 / posting states no resume-language requirement"))
    elif not resume_lang:
        items.append(_item("resume_version", "fail", "application.resume_language 未记录，岗位要求 %s / resume_language not recorded; posting requires %s" % (required_lang, required_lang)))
    elif resume_lang != required_lang:
        items.append(_item("resume_version", "fail", "简历语言 %s 与岗位要求 %s 不符 / resume language %s does not match required %s" % (resume_lang, required_lang, resume_lang, required_lang)))
    else:
        items.append(_item("resume_version", "pass", "简历语言 %s 符合岗位要求 / resume language matches the posting" % resume_lang))
    return items


def _check_window(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    intent = profile.get("intent") or {}
    window = intent.get("window") or {}
    istart, iend = _ym(window.get("start")), _ym(window.get("end"))
    if not istart and not iend and not intent.get("earliest_start"):
        return _item("internship_window", "fail", "intent.window 与 intent.earliest_start 均未设置 / profile has no availability window at all")
    hc = _hard_conditions(job)
    jw = hc.get("work_window") or {}
    jstart, jend = _ym(jw.get("start")), _ym(jw.get("end"))
    if not jstart and not jend:
        return _item("internship_window", "pass", "岗位未声明窗口，无冲突可判 / posting states no work window; nothing to conflict with")
    tol = int(round(float(window.get("flexibility_weeks") or 0) / 4.33))
    if istart and jend and _months(jend) < _months(istart) - tol:
        return _item("internship_window", "fail", "岗位窗口结束于 %s，早于可到岗 %s / posting ends %s before availability starts %s" % (jw.get("end"), window.get("start"), jw.get("end"), window.get("start")))
    if iend and jstart and _months(jstart) > _months(iend) + tol:
        return _item("internship_window", "fail", "岗位窗口始于 %s，晚于可到岗结束 %s / posting starts %s after availability ends %s" % (jw.get("start"), window.get("end"), jw.get("start"), window.get("end")))
    return _item("internship_window", "pass", "窗口无冲突（容差 ±%d 周）/ no conflict (tolerance +/- %d weeks)" % (tol, tol))


def _check_salary(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    salary = profile.get("salary") or {}
    floor = salary.get("hard_floor")
    if not isinstance(floor, (int, float)):
        return _item("salary", "pass", "profile.salary.hard_floor 未设置，无下限可比 / no hard_floor set")
    hc = _hard_conditions(job)
    sal = hc.get("salary") or {}
    if sal.get("disclosed") is not True:
        return _item("salary", "pass", "岗位未披露薪资，硬下限无法比对 / posting salary undisclosed; nothing to compare against the floor")
    job_max = sal.get("max") if sal.get("max") is not None else sal.get("min")
    if not isinstance(job_max, (int, float)):
        return _item("salary", "pass", "岗位披露区间但无具体数值 / posting discloses a range with no usable figure")
    same_currency = not sal.get("currency") or not salary.get("currency") or str(sal["currency"]).upper() == str(salary["currency"]).upper()
    same_period = not sal.get("period") or not salary.get("period") or sal["period"] == salary["period"]
    if not (same_currency and same_period):
        return _item("salary", "pass", "币种或周期不一致，脚本不换算，需人工核对 / currency or period differs; not auto-converted, needs a human check")
    if job_max < floor:
        return _item("salary", "fail", "岗位披露上限 %s 低于硬下限 %s / disclosed max %s is below hard floor %s" % (job_max, floor, job_max, floor))
    return _item("salary", "pass", "岗位披露上限 %s ≥ 硬下限 %s / disclosed max %s is at or above hard floor %s" % (job_max, floor, job_max, floor))


def _check_dedup(conn: sqlite3.Connection, app: dict[str, Any]) -> dict[str, Any]:
    others = [a for a in applications_for_job(conn, str(app["job_id"])) if a["app_id"] != app["app_id"]]
    hit = [a for a in others if a["status"] in ("applied", "submitted_unverified")]
    if hit:
        statuses = ",".join(sorted({str(a["status"]) for a in hit}))
        return _item("other", "fail", "同岗位已有其它申请处于 %s（%s）/ another application for this job is already %s (dedup_not_applied)" % (statuses, ",".join(str(a["app_id"]) for a in hit), statuses))
    return _item("other", "pass", "同岗位无其它已投申请（dedup_not_applied）/ no other applied record exists for this job (dedup_not_applied)")


def _check_declarations(profile: dict[str, Any]) -> dict[str, Any]:
    decl = (profile.get("policy") or {}).get("declarations") or {}
    missing = [k for k in REQUIRED_DECLARATIONS if decl.get(k) is None]
    if missing:
        return _item("other", "fail", "以下声明题未预设，遇到会触发 personal_declaration 关口：%s（declarations_preset）/ not preset, will trigger a gate: %s (declarations_preset)" % (",".join(missing), ",".join(missing)))
    return _item("other", "pass", "8 项固定声明题均已预设（declarations_preset）/ all 8 fixed declarations are preset (declarations_preset)")


def _check_open_answers(paths: DataPaths, app: dict[str, Any]) -> dict[str, Any]:
    run_id = app.get("run_id")
    if not run_id:
        return _item("other", "pass", "该申请无 run_id，无开放题目录（open_answers_approved）/ no run_id, so no content directory (open_answers_approved)")
    content_dir = paths.run_dir(str(run_id)) / "items" / str(app["app_id"]) / "content"
    if not content_dir.is_dir():
        return _item("other", "pass", "无开放题 / cover letter 草稿目录，视为无需批准（open_answers_approved）/ no content directory, nothing pending (open_answers_approved)")
    bad: list[str] = []
    for f in sorted(content_dir.glob("*.md")):
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        status = None
        if lines:
            try:
                status = json.loads(lines[0]).get("status")
            except ValueError:
                status = None
        if status not in ("approved", "filled", "skipped"):
            bad.append("%s(status=%s)" % (f.name, status or "unreadable"))
    if bad:
        return _item("other", "fail", "以下开放题草稿未批准：%s（open_answers_approved）/ not approved yet: %s (open_answers_approved)" % (", ".join(bad), ", ".join(bad)))
    return _item("other", "pass", "开放题 / cover letter 均已批准或跳过（open_answers_approved）/ all open answers are approved or skipped (open_answers_approved)")


def run_presubmit(conn: sqlite3.Connection, paths: DataPaths, app_id: str, profile: dict[str, Any] | None) -> dict[str, Any]:
    app = require_application(conn, app_id)
    job = require_job(conn, str(app["job_id"]))
    items: list[dict[str, Any]] = []
    if profile is None:
        items.append(_item("other", "fail", "profile.json 不存在，机器可判定项全部无法核实 / profile.json not found, none of the machine-checkable items can be verified"))
    else:
        items.append(_check_name_order(profile))
        items.append(_check_phone(profile))
        items.append(_check_graduation(profile))
        items.extend(_check_resume(app, job))
        items.append(_check_window(profile, job))
        items.append(_check_salary(profile, job))
        items.append(_check_dedup(conn, app))
        items.append(_check_declarations(profile))
        items.append(_check_open_answers(paths, app))
    for name, note in NEEDS_MANUAL_CHECK:
        items.append(_item(name, "unverified", note))
    failed = [i for i in items if i["status"] == "fail"]
    unverified = [i for i in items if i["status"] == "unverified"]
    return {
        "app_id": app_id,
        "job_id": app["job_id"],
        "run_id": app.get("run_id"),
        "checked_at": now_iso(),
        "items": items,
        "passed": not failed,
        "fail_count": len(failed),
        "unverified_count": len(unverified),
    }

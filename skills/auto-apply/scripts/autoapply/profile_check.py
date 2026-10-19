"""Profile validation and the R3 consistency gate (ARCHITECTURE §8). Business layer.

validate_profile   -> schema + hard-coded forbidden keys + semantic rules (autopilot consent, resume files).
consistency_report -> compares resume_parse.json with profile.json; all values masked; overall pass|warn|block.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from autoapply.errors import ProfileError
from autoapply.ids import now_iso
from autoapply.redact import mask_email, mask_name, mask_phone
from autoapply.schema_validate import SchemaSet

INSTITUTION_ALIASES: dict[str, str] = {
    "ntu": "nanyang technological university",
    "nus": "national university of singapore",
    "smu": "singapore management university",
    "sutd": "singapore university of technology and design",
    "sit": "singapore institute of technology",
    "suss": "singapore university of social sciences",
    "nyp": "nanyang polytechnic",
    "sp": "singapore polytechnic",
    "np": "ngee ann polytechnic",
    "tp": "temasek polytechnic",
    "rp": "republic polytechnic",
}


def read_json_object(path: Path, what: str) -> dict[str, Any]:
    if not path.is_file():
        raise ProfileError("%s 不存在 / %s not found" % (what, what), {"path": str(path)})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ProfileError("%s 不是合法 JSON / %s is not valid JSON" % (what, what), {"path": str(path)}) from e
    if not isinstance(data, dict):
        raise ProfileError("%s 顶层必须是对象 / %s must be a JSON object" % (what, what))
    return data


def validate_profile(schemas: SchemaSet, profile: dict[str, Any], *, check_files: bool = True) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors include schema errors and forbidden keys."""
    res = schemas.check("profile", profile)
    errors = list(res.errors)
    warnings = list(res.warnings)
    policy = profile.get("policy") or {}
    if policy.get("submit_mode") == "autopilot" and not policy.get("autopilot_consent"):
        errors.append("$.policy: submit_mode=autopilot requires policy.autopilot_consent (BRIEF D8)")
    resumes = (profile.get("materials") or {}).get("resumes") or []
    defaults = [r for r in resumes if r.get("is_default")]
    if len(defaults) > 1:
        errors.append("$.materials.resumes: more than one is_default resume")
    if check_files:
        for i, r in enumerate(resumes):
            p = Path(str(r.get("path", ""))).expanduser()
            if not p.is_file():
                errors.append("$.materials.resumes[%d].path: file not found on this machine" % i)
    edu = profile.get("education") or []
    current = [e for e in edu if e.get("is_current")]
    if len(current) > 1:
        warnings.append("$.education: more than one is_current entry; consistency gate compares the first")
    if current and not current[0].get("end_expected"):
        warnings.append("$.education[current].end_expected missing; graduation year cannot be checked (R3/R10)")
    if not profile.get("policy", {}).get("platform_tos_acknowledged"):
        warnings.append("$.policy.platform_tos_acknowledged is not true; onboarding must show the ToS notice (D13)")
    return errors, warnings


# ---- consistency (R3) ----------------------------------------------------------------------------
def _norm_email(v: Any) -> str | None:
    return str(v).strip().lower() if isinstance(v, str) and "@" in v else None


def _norm_phone(cc: Any, number: Any) -> str | None:
    if not isinstance(number, str):
        return None
    digits = re.sub(r"\D", "", number)
    if not digits:
        return None
    ccd = re.sub(r"\D", "", str(cc)) if isinstance(cc, str) else ""
    return "+%s %s" % (ccd, digits) if ccd else digits


def _phone_matches(resume_phone: str, profile_phones: set[str]) -> bool:
    """简历上的手机常常不带区号（中文简历尤其如此）：无区号时只比对号码本体。
    Resumes (Chinese ones especially) often omit the country code: compare the bare number when no code was parsed."""
    if resume_phone in profile_phones:
        return True
    if resume_phone.startswith("+"):
        return False
    return any(p.split(" ", 1)[-1] == resume_phone for p in profile_phones)


def _name_tokens(v: Any) -> list[str]:
    if not isinstance(v, str):
        return []
    return [t for t in re.sub(r"[^\w\s]", " ", v.lower()).split() if t]


DEGREE_WORDS: dict[str, str] = {
    "phd": "phd", "dphil": "phd", "doctor": "phd", "doctorate": "phd",
    "master": "master", "masters": "master", "msc": "master", "ms": "master", "meng": "master", "mba": "master",
    "ma": "master", "mtech": "master", "mphil": "master", "硕士": "master",
    "bachelor": "bachelor", "bachelors": "bachelor", "bsc": "bachelor", "bs": "bachelor", "beng": "bachelor",
    "ba": "bachelor", "btech": "bachelor", "bba": "bachelor", "学士": "bachelor", "本科": "bachelor",
    "diploma": "diploma", "大专": "diploma",
}


def _degree_level(v: Any) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return None
    for tok in re.sub(r"[^\w\s]", " ", v.lower()).split():
        if tok in DEGREE_WORDS:
            return DEGREE_WORDS[tok]
    for word, level in DEGREE_WORDS.items():
        if word in v.lower():
            return level
    return None


def _inst_norm(v: Any) -> str:
    s = re.sub(r"[^\w\s]", " ", str(v or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    return INSTITUTION_ALIASES.get(s, s)


def _resume_entries(resume_parse: Any) -> list[dict[str, Any]]:
    if isinstance(resume_parse, list):
        return [x for x in resume_parse if isinstance(x, dict)]
    if isinstance(resume_parse, dict):
        if isinstance(resume_parse.get("resumes"), list):
            return [x for x in resume_parse["resumes"] if isinstance(x, dict)]
        return [resume_parse]
    raise ProfileError("resume_parse.json 必须是对象或数组 / resume_parse must be an object or list")


def consistency_report(profile: dict[str, Any], resume_parse: Any) -> dict[str, Any]:
    identity = profile.get("identity") or {}
    emails = identity.get("emails") or {}
    profile_emails = {e for e in (_norm_email(emails.get("primary")), _norm_email(emails.get("signup"))) if e}
    profile_emails.update(e for e in (_norm_email(x) for x in emails.get("others") or []) if e)
    profile_phones = {p for p in (_norm_phone(x.get("country_code"), x.get("number")) for x in identity.get("phones") or []) if p}
    edu = profile.get("education") or []
    current = next((e for e in edu if e.get("is_current")), None)
    resumes_meta = {str(r.get("path")): r for r in (profile.get("materials") or {}).get("resumes") or []}

    report_resumes: list[dict[str, Any]] = []
    overall = "pass"
    levels = {"pass": 0, "info": 0, "warn": 1, "block": 2}

    for entry in _resume_entries(resume_parse):
        path = str(entry.get("resume_path") or entry.get("path") or "")
        parsed = entry.get("parsed") if isinstance(entry.get("parsed"), dict) else entry
        known = set(str(x) for x in (resumes_meta.get(path) or {}).get("known_mismatches") or [])
        findings: list[dict[str, Any]] = []

        def add(fieldname: str, level: str, rv: str | None, pv: str | None, hint: str) -> None:
            lv = "info" if fieldname in known and level != "info" else level
            findings.append({"field": fieldname, "level": lv, "resume_value_masked": rv, "profile_value_masked": pv,
                             "hint": hint + ("（已在 known_mismatches 中接受 / accepted）" if lv != level else "")})

        r_emails = [e for e in (_norm_email(x) for x in parsed.get("emails") or []) if e]
        if not r_emails:
            add("email", "info", None, None, "简历未解析出邮箱 / no email parsed from resume")
        elif not any(e in profile_emails for e in r_emails):
            add("email", "block", ", ".join(mask_email(e) for e in r_emails),
                ", ".join(sorted(mask_email(e) for e in profile_emails)) or None,
                "简历邮箱不在档案邮箱集合内 / resume email not in profile emails")
        else:
            add("email", "pass", None, None, "ok")

        r_phones = [p for p in (_norm_phone(x.get("country_code"), x.get("number")) for x in parsed.get("phones") or [] if isinstance(x, dict)) if p]
        if not r_phones:
            add("phone", "info", None, None, "简历未解析出手机 / no phone parsed from resume")
        elif not profile_phones:
            add("phone", "warn", ", ".join(mask_phone(p) for p in r_phones), None, "档案无手机 / profile has no phone")
        elif not any(_phone_matches(p, profile_phones) for p in r_phones):
            add("phone", "block", ", ".join(mask_phone(p) for p in r_phones), ", ".join(sorted(mask_phone(p) for p in profile_phones)),
                "简历手机不在档案手机集合内 / resume phone not in profile phones")
        else:
            add("phone", "pass", None, None, "ok")

        grad = parsed.get("graduation") if isinstance(parsed.get("graduation"), dict) else {}
        r_exp = str(grad.get("expected") or "")
        p_exp = str((current or {}).get("end_expected") or "")
        if r_exp and p_exp:
            if r_exp[:4] != p_exp[:4]:
                add("graduation", "block", r_exp[:7], p_exp[:7], "毕业年份不同 / graduation year differs")
            elif len(r_exp) >= 7 and r_exp[:7] != p_exp[:7]:
                add("graduation", "warn", r_exp[:7], p_exp[:7], "毕业年份相同、月份不同 / same year, different month")
            else:
                add("graduation", "pass", None, None, "ok")
        else:
            add("graduation", "info", r_exp[:7] or None, p_exp[:7] or None, "一方缺毕业时间 / graduation date missing on one side")

        r_name = _name_tokens(parsed.get("full_name"))
        p_name = _name_tokens((identity.get("name") or {}).get("full"))
        p_native = _name_tokens((identity.get("name") or {}).get("native"))
        if r_name and p_name:
            if r_name == p_name or (p_native and r_name == p_native):
                add("name", "pass", None, None, "ok")
            elif set(r_name) == set(p_name):
                add("name", "warn", mask_name(" ".join(r_name)), mask_name(" ".join(p_name)), "姓名顺序不同 / name order differs")
            else:
                add("name", "warn", mask_name(" ".join(r_name)), mask_name(" ".join(p_name)), "姓名 token 不同 / name tokens differ")
        else:
            add("name", "info", None, None, "一方缺姓名 / name missing on one side")

        r_inst = _inst_norm(grad.get("institution"))
        p_inst = _inst_norm((current or {}).get("institution"))
        if r_inst and p_inst:
            add("institution", "pass" if r_inst == p_inst else "warn", None if r_inst == p_inst else r_inst,
                None if r_inst == p_inst else p_inst, "ok" if r_inst == p_inst else "学校名不同（别名表后）/ institution differs after aliasing")
        r_deg = _degree_level(grad.get("degree"))
        p_deg = _degree_level((current or {}).get("degree"))
        if r_deg and p_deg and r_deg != p_deg:
            add("degree", "warn", r_deg, p_deg, "学位层级不同 / degree level differs")

        r_li = str(parsed.get("linkedin_url") or "").lower().rstrip("/")
        p_li = str((profile.get("materials") or {}).get("linkedin_url") or "").lower().rstrip("/")
        if r_li and p_li:
            rp = re.sub(r"^https?://(www\.)?", "", r_li)
            pp = re.sub(r"^https?://(www\.)?", "", p_li)
            add("linkedin_url", "pass" if rp == pp else "info", None if rp == pp else rp, None if rp == pp else pp,
                "ok" if rp == pp else "LinkedIn 链接不同 / LinkedIn URL differs")

        worst = "pass"
        for f in findings:
            if levels.get(str(f["level"]), 0) > levels.get(worst, 0):
                worst = str(f["level"])
        if levels.get(worst, 0) > levels.get(overall, 0):
            overall = worst
        report_resumes.append({"resume_path": path, "overall": worst, "findings": findings})

    return {"checked_at": now_iso(), "resumes": report_resumes, "overall": overall if overall != "info" else "pass"}

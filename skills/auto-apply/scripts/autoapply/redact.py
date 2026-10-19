"""Redaction (CODE_STANDARDS §6.3, SECURITY §5). The project's single implementation.

mask_email / mask_phone / mask_name  -> partial masks for user-facing reports.
redact(text)                         -> replaces emails / phones with [REDACTED:<kind>];
                                        NRIC/FIN or password-key hits raise RedactionError
                                        (their presence is a bug, never a warning).
find_secret_hits(text)               -> list of kinds found, without raising (for scanners).
"""

from __future__ import annotations

import re

from autoapply.errors import RedactionError

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# international: +CC then 7-13 digits with optional separators
PHONE_INTL_RE = re.compile(r"(?<![\w./])\+\d{1,4}[\s\-]?\d(?:[\d\s\-]{5,12})\d(?![\w/])(?!\.\d)")
# Singapore local 8-digit numbers starting with 3/6/8/9 (not inside URLs / identifiers)
PHONE_SG_RE = re.compile(r"(?<![\w./#])[3689]\d{3}[\s\-]?\d{4}(?![\w/])(?!\.\d)")
NRIC_RE = re.compile(r"(?<![A-Za-z0-9])[STFGM]\d{7}[A-Z](?![A-Za-z0-9])")
PASSWORD_KEY_RE = re.compile(
    r"(?i)(?:^|[\s,;{\"'])(?:JOB_ACCOUNT_PASSWORD|JOB_APPLY_PASSWORD|password|passwd|pwd)\s*[=:]\s*\S+"
)
# 6-digit OTP right after an "otp"/"code" word — only used by scanners (too noisy for auto-redact)
OTP_HINT_RE = re.compile(r"(?i)\b(?:otp|verification code|one[- ]time (?:code|password))\b\s*[:=]?\s*\d{4,8}\b")

CJK_RE = re.compile(r"[㐀-鿿]")


def mask_email(value: str) -> str:
    v = value.strip()
    if "@" not in v:
        return "***"
    local, _, domain = v.partition("@")
    head = local[:1] if local else ""
    return "%s***@%s" % (head, domain)


def mask_phone(value: str) -> str:
    v = value.strip()
    m = re.match(r"^(\+\d{1,4})?[\s\-]*(.*)$", v)
    cc = (m.group(1) if m else "") or ""
    digits = re.sub(r"\D", "", (m.group(2) if m else v) or "")
    tail = digits[-4:] if len(digits) >= 4 else "*" * len(digits)
    return ("%s ****%s" % (cc, tail)).strip()


def mask_name(value: str) -> str:
    words = value.strip().split()
    out: list[str] = []
    for w in words:
        if CJK_RE.search(w):
            out.append(w[:1] + "*" * max(1, len(w) - 1))
        else:
            out.append(w[:1] + "**" if len(w) > 1 else w)
    return " ".join(out) if out else "***"


def find_secret_hits(text: str) -> list[str]:
    """Return kinds of secret-like content found (nric, password_key). Does not raise."""
    kinds: list[str] = []
    if NRIC_RE.search(text):
        kinds.append("nric")
    if PASSWORD_KEY_RE.search(text):
        kinds.append("password_key")
    return kinds


def redact(text: str, *, phones: bool = True) -> str:
    """Redact emails/phones; raise on NRIC/FIN or password keys (CODE_STANDARDS §6.3)."""
    hits = find_secret_hits(text)
    if hits:
        # Message carries only the kind, never the value.
        raise RedactionError("redaction hit kind=%s" % ",".join(hits), {"kinds": hits})
    out = EMAIL_RE.sub("[REDACTED:email]", text)
    if phones:
        out = PHONE_INTL_RE.sub("[REDACTED:phone]", out)
        out = PHONE_SG_RE.sub("[REDACTED:phone]", out)
    return out


def contains_personal_pattern(text: str) -> bool:
    return bool(EMAIL_RE.search(text) or PHONE_INTL_RE.search(text) or NRIC_RE.search(text))

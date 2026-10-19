"""Identifiers and timestamps (ARCHITECTURE §5.1). Pure tool layer."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from autoapply.errors import UsageError

RUN_ID_RE = re.compile(r"^run_[0-9]{8}_[0-9]{6}$")
APP_ID_RE = re.compile(r"^app_[0-9]{8}_[a-f0-9]{6}$")
JOB_ID_RE = re.compile(r"^job_[a-f0-9]{12}$")
ACTION_ID_RE = re.compile(r"^pa_[0-9]{8}_[a-f0-9]{6}$")
ISO_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?([+-][0-9]{2}:[0-9]{2}|Z)?$")


def now_local() -> datetime:
    return datetime.now().astimezone()


def now_iso() -> str:
    return now_local().isoformat(timespec="seconds")


def today_compact(dt: datetime | None = None) -> str:
    return (dt or now_local()).strftime("%Y%m%d")


def local_date(dt: datetime | None = None) -> date:
    return (dt or now_local()).date()


def parse_iso(value: str) -> datetime:
    """Parse ISO-8601 (accepts trailing Z). Naive values are treated as local time."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as e:
        raise UsageError("时间格式不合法（需 ISO-8601）/ invalid ISO-8601 timestamp") from e
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def iso_plus_days(days: int, base: datetime | None = None) -> str:
    return ((base or now_local()) + timedelta(days=days)).isoformat(timespec="seconds")


def new_run_id(dt: datetime | None = None) -> str:
    return (dt or now_local()).strftime("run_%Y%m%d_%H%M%S")


def new_app_id(dt: datetime | None = None) -> str:
    return "app_%s_%s" % (today_compact(dt), secrets.token_hex(3))


def new_action_id(dt: datetime | None = None) -> str:
    return "pa_%s_%s" % (today_compact(dt), secrets.token_hex(3))


def job_id_from_key(dedup_key: str) -> str:
    return "job_" + hashlib.sha256(dedup_key.encode("utf-8")).hexdigest()[:12]


def evidence_id_for(app_id: str, seq: int) -> str:
    if not APP_ID_RE.match(app_id):
        raise UsageError("app_id 格式不合法 / invalid app_id format")
    return "ev_%s_%02d" % (app_id[len("app_"):], seq)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

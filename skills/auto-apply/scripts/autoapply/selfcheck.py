"""Environment self-check for onboarding (ARCHITECTURE §1.3 selfcheck). Business layer.

Statuses: ok | warn | fail | unverified. "unverified" items cannot be probed from Python (browser
extension, mail connector, Chrome login) and are printed as "未验证，请手动确认".
"""

from __future__ import annotations

import json
import sqlite3
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoapply.errors import AutoApplyError
from autoapply.ledger import open_ledger, run_assertions
from autoapply.paths import SCHEMA_FILES, DataPaths
from autoapply.schema_validate import SchemaSet, scan_forbidden

REQUIRED_PY = (3, 9)


@dataclass(frozen=True)
class CheckItem:
    name: str
    status: str  # ok | warn | fail | unverified
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(d), prefix=".selfcheck-", delete=True):
            pass
        return True
    except OSError:
        return False


def run_selfcheck(data_root: Path, profile_id: str | None, schema_dir: Path | None) -> list[CheckItem]:
    items: list[CheckItem] = []
    v = sys.version_info
    if v >= REQUIRED_PY:
        items.append(CheckItem("python_version", "ok", "Python %d.%d.%d" % (v.major, v.minor, v.micro)))
    else:
        items.append(CheckItem("python_version", "fail", "Python %d.%d.%d，需要 3.9+ / need Python 3.9+" % (v.major, v.minor, v.micro)))
    items.append(CheckItem("sqlite3", "ok", "sqlite %s" % sqlite3.sqlite_version))

    if _writable(data_root):
        items.append(CheckItem("data_root_writable", "ok", str(data_root)))
    else:
        items.append(CheckItem("data_root_writable", "fail", "数据目录不可写 / not writable: %s" % data_root))
    try:
        mode = stat.S_IMODE(data_root.stat().st_mode)
        if mode & 0o077:
            items.append(CheckItem("data_root_permissions", "warn", "建议 chmod 700（当前 %o）/ recommend mode 700" % mode))
        else:
            items.append(CheckItem("data_root_permissions", "ok", "%o" % mode))
    except OSError:
        items.append(CheckItem("data_root_permissions", "warn", "无法读取权限位 / cannot stat"))

    if schema_dir is None:
        items.append(CheckItem("schemas", "fail", "找不到 schemas/ 目录 / schema directory not found"))
    else:
        missing = [f for f in SCHEMA_FILES if not (schema_dir / f).is_file()]
        if missing:
            items.append(CheckItem("schemas", "fail", "缺少 / missing: %s" % ", ".join(missing)))
        else:
            try:
                ss = SchemaSet(schema_dir)
                warnings: list[str] = []
                for kind in ss.KINDS:
                    warnings.extend(ss.get(kind).load_warnings)
                items.append(CheckItem("schemas", "ok" if not warnings else "warn",
                                       "6 份 schema 可加载 / all six schemas load%s" % ("; %d unsupported keyword(s) ignored" % len(warnings) if warnings else "")))
            except AutoApplyError as e:
                items.append(CheckItem("schemas", "fail", e.message))

    if profile_id:
        paths = DataPaths(data_root, profile_id)
        if paths.profile_dir.is_dir():
            items.append(CheckItem("profile_dir", "ok", str(paths.profile_dir)))
        else:
            items.append(CheckItem("profile_dir", "warn", "profile 目录不存在（首次 onboarding 会创建）/ not created yet"))
        if paths.profile_json.is_file():
            try:
                data = json.loads(paths.profile_json.read_text(encoding="utf-8"))
                problems = scan_forbidden(data)
                if schema_dir is not None and not problems:
                    res = SchemaSet(schema_dir).check("profile", data)
                    problems = res.errors
                if problems:
                    items.append(CheckItem("profile_json", "fail", "profile.json 校验失败 %d 项 / %d validation error(s)" % (len(problems), len(problems))))
                else:
                    signed = bool((data.get("meta") or {}).get("intake_signed_at"))
                    items.append(CheckItem("profile_json", "ok" if signed else "warn", "有效 / valid%s" % ("" if signed else "；尚未签字 / not signed yet")))
            except ValueError:
                items.append(CheckItem("profile_json", "fail", "profile.json 不是合法 JSON / invalid JSON"))
        else:
            items.append(CheckItem("profile_json", "warn", "profile.json 不存在，需先问诊 / missing; run intake"))
        if paths.facts_card_json.is_file():
            try:
                card = json.loads(paths.facts_card_json.read_text(encoding="utf-8"))
                signed = bool((card.get("meta") or {}).get("signed_by_user"))
                items.append(CheckItem("facts_card", "ok" if signed else "warn", "存在 / present%s" % ("" if signed else "；未签字 / not signed")))
            except ValueError:
                items.append(CheckItem("facts_card", "fail", "facts_card.json 不是合法 JSON / invalid JSON"))
        else:
            items.append(CheckItem("facts_card", "warn", "facts_card.json 不存在 / missing"))
        if paths.ledger_sqlite.is_file():
            try:
                conn = open_ledger(paths.ledger_sqlite, profile_id)
                failures = run_assertions(conn)
                conn.close()
                items.append(CheckItem("ledger", "ok" if not failures else "fail",
                                       "台账断言通过 / assertions pass" if not failures else "; ".join(failures)[:300]))
            except AutoApplyError as e:
                items.append(CheckItem("ledger", "fail", e.message))
        else:
            items.append(CheckItem("ledger", "warn", "ledger.sqlite 尚未创建 / not created yet"))
        sec = paths.secrets_env
        if sec.exists():
            mode = stat.S_IMODE(sec.stat().st_mode)
            if mode & 0o077:
                items.append(CheckItem("secrets_env_permissions", "fail", "secrets.env 权限应为 600（当前 %o）/ must be mode 600" % mode))
            else:
                items.append(CheckItem("secrets_env_permissions", "ok", "存在且为 600（内容未读取）/ present, mode 600, content not read"))
        else:
            items.append(CheckItem("secrets_env_permissions", "ok", "不存在（Claude Code 运行时不需要）/ absent (not needed on Claude Code)"))
    else:
        items.append(CheckItem("profile", "warn", "未指定 profile（--profile 或 AUTO_APPLY_PROFILE）/ no profile selected"))

    for name in ("browser_extension", "chrome_logged_in", "mail_connector"):
        items.append(CheckItem(name, "unverified", "未验证，请手动确认 / not verifiable from Python; confirm manually"))
    return items


def selfcheck_failed(items: list[CheckItem]) -> bool:
    return any(i.status == "fail" for i in items)


def summarize(items: list[CheckItem]) -> dict[str, Any]:
    return {"items": [i.to_dict() for i in items], "failed": selfcheck_failed(items),
            "counts": {s: sum(1 for i in items if i.status == s) for s in ("ok", "warn", "fail", "unverified")}}

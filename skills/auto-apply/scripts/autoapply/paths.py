"""Data directory resolution. The only tool-layer module allowed to read os.environ.

Data root:   --data-dir > $AUTO_APPLY_DATA_DIR > ~/auto-apply-data
Profile:     --profile  > $AUTO_APPLY_PROFILE  > the single existing profile dir (if exactly one)
Schemas:     $AUTO_APPLY_SCHEMA_DIR > <repo>/schemas (resolved through the skill symlink)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from autoapply.errors import ConfigError

ENV_DATA_DIR = "AUTO_APPLY_DATA_DIR"
ENV_PROFILE = "AUTO_APPLY_PROFILE"
ENV_SCHEMA_DIR = "AUTO_APPLY_SCHEMA_DIR"
DEFAULT_DATA_DIR_NAME = "auto-apply-data"
PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
SCHEMA_FILES: tuple[str, ...] = (
    "profile.schema.json", "facts_card.schema.json", "job.schema.json",
    "application.schema.json", "run_state.schema.json", "pending_action.schema.json",
)


def resolve_data_root(override: str | None) -> Path:
    raw = override or os.environ.get(ENV_DATA_DIR) or ""
    if raw.strip():
        return Path(raw).expanduser().resolve()
    return (Path.home() / DEFAULT_DATA_DIR_NAME).resolve()


def resolve_profile_id(override: str | None, data_root: Path) -> str:
    candidate = override or os.environ.get(ENV_PROFILE) or ""
    if candidate.strip():
        pid = candidate.strip()
        if not PROFILE_ID_RE.match(pid):
            raise ConfigError("profile_id 不合法（^[a-z0-9][a-z0-9_-]{1,31}$）/ invalid profile_id", {"profile_id": pid})
        return pid
    if data_root.is_dir():
        found = sorted(
            p.name for p in data_root.iterdir()
            if p.is_dir() and PROFILE_ID_RE.match(p.name)
            and ((p / "profile.json").exists() or (p / "ledger.sqlite").exists())
        )
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise ConfigError(
                "数据目录下有多个 profile，请用 --profile 指定 / multiple profiles found, pass --profile",
                {"profiles": found},
            )
    raise ConfigError(
        "未指定 profile：用 --profile <id> 或设置 AUTO_APPLY_PROFILE / no profile given",
        {"data_root": str(data_root)},
    )


def resolve_schema_dir() -> Path:
    env = os.environ.get(ENV_SCHEMA_DIR, "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser().resolve())
    here = Path(__file__).resolve()
    # <repo>/skills/auto-apply/scripts/autoapply/paths.py -> parents[4] == <repo>
    if len(here.parents) >= 5:
        candidates.append(here.parents[4] / "schemas")
    # fallback: a schemas/ copy shipped next to the skill
    if len(here.parents) >= 3:
        candidates.append(here.parents[2] / "schemas")
    for c in candidates:
        if all((c / f).is_file() for f in SCHEMA_FILES):
            return c
    raise ConfigError(
        "找不到 schemas/ 目录（六份 schema 必须齐全）/ schemas directory not found",
        {"looked_in": [str(c) for c in candidates], "required": list(SCHEMA_FILES)},
    )


@dataclass(frozen=True)
class DataPaths:
    root: Path
    profile_id: str

    @property
    def profile_dir(self) -> Path:
        return self.root / self.profile_id

    @property
    def profile_json(self) -> Path:
        return self.profile_dir / "profile.json"

    @property
    def facts_card_json(self) -> Path:
        return self.profile_dir / "facts_card.json"

    @property
    def facts_card_md(self) -> Path:
        return self.profile_dir / "facts_card.md"

    @property
    def resume_parse_json(self) -> Path:
        return self.profile_dir / "resume_parse.json"

    @property
    def consistency_report_json(self) -> Path:
        return self.profile_dir / "consistency_report.json"

    @property
    def dedup_aliases_json(self) -> Path:
        return self.profile_dir / "dedup_aliases.json"

    @property
    def secrets_env(self) -> Path:
        # Existence / permission bits only. The package never reads this file (SECURITY §1.2).
        return self.profile_dir / "secrets.env"

    @property
    def ledger_sqlite(self) -> Path:
        return self.profile_dir / "ledger.sqlite"

    @property
    def evidence_dir(self) -> Path:
        return self.profile_dir / "evidence"

    @property
    def runs_dir(self) -> Path:
        return self.profile_dir / "runs"

    @property
    def exports_dir(self) -> Path:
        return self.profile_dir / "exports"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def ensure_layout(self) -> None:
        for d in (self.profile_dir, self.evidence_dir, self.runs_dir, self.exports_dir):
            d.mkdir(parents=True, exist_ok=True)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False

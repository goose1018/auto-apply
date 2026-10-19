"""Shared helpers for verify scripts (not a verify script itself: underscore prefix, skipped by all.py).

Every verify script:
- forces AUTO_APPLY_DATA_DIR to a temporary directory (never the user's ~/auto-apply-data),
- runs the real CLI in a subprocess with the current interpreter,
- ends with exactly one `PASS <name>: ...` or `FAIL <name>: ...` line.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "skills" / "auto-apply" / "scripts"
CLI = SCRIPTS_DIR / "autoapply" / "cli.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def version_gate() -> None:
    """CODE_STANDARDS §1: explicit version gate."""
    if sys.version_info < (3, 9):
        sys.exit("需要 Python 3.9+（当前 %d.%d）/ need Python 3.9+" % (sys.version_info[0], sys.version_info[1]))


class Checker:
    def __init__(self, name: str) -> None:
        self.name = name

    def check(self, cond: bool, msg: str) -> None:
        if not cond:
            print("FAIL %s: %s" % (self.name, msg))
            sys.exit(1)

    def done(self, msg: str) -> int:
        print("PASS %s: %s" % (self.name, msg))
        return 0


class TempData:
    """Temporary data root + fixed profile id; guards against touching the real data dir."""

    def __init__(self, profile_id: str = "verify_user") -> None:
        self._td = tempfile.TemporaryDirectory(prefix="auto-apply-verify-")
        self.root = Path(self._td.name).resolve()
        self.profile_id = profile_id
        os.environ["AUTO_APPLY_DATA_DIR"] = str(self.root)
        os.environ["AUTO_APPLY_PROFILE"] = profile_id
        home_data = (Path.home() / "auto-apply-data").resolve()
        if self.root == home_data or str(self.root).startswith(str(home_data) + os.sep):
            raise SystemExit("FAIL: temp data dir resolves into ~/auto-apply-data")
        self.profile_dir = self.root / profile_id
        self.profile_dir.mkdir(parents=True)

    def cleanup(self) -> None:
        self._td.cleanup()

    def __enter__(self) -> "TempData":
        return self

    def __exit__(self, *exc: object) -> None:
        self.cleanup()


def run_cli(*args: str, data: TempData | None = None, expect: int | None = 0, json_out: bool = False,
            timeout: int = 60) -> tuple[int, str, str, Any]:
    """Run the CLI; returns (code, stdout, stderr, parsed_json_or_None). Fails loudly on unexpected code."""
    cmd = [sys.executable, str(CLI)]
    if data is not None:
        cmd += ["--data-dir", str(data.root), "--profile", data.profile_id]
    if json_out:
        cmd.append("--json")
    cmd += list(args)
    env = dict(os.environ)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    parsed: Any = None
    if json_out and proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout)
        except ValueError:
            parsed = None
    if expect is not None and proc.returncode != expect:
        print("FAIL: command %s exited %d (expected %d)\nstdout:\n%s\nstderr:\n%s" % (
            " ".join(args), proc.returncode, expect, proc.stdout[-2000:], proc.stderr[-2000:]))
        sys.exit(1)
    return proc.returncode, proc.stdout, proc.stderr, parsed


def stderr_json(stderr: str) -> dict[str, Any] | None:
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                continue
    return None


def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path

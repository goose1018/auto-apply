#!/usr/bin/env python3
"""verify: cli_contract — every command in the task contract exists with the agreed name and arguments
(so agents/*.md written by H can call them verbatim). Also: `python3 -m autoapply` works; global flags exist;
failures emit one JSON line on stderr; Python version gate exits 2 on an interpreter below 3.9.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CLI, SCRIPTS_DIR, Checker, TempData, run_cli, stderr_json, version_gate  # noqa: E402

version_gate()

NAME = "cli_contract"
c = Checker(NAME)

CONTRACT: list[tuple[list[str], list[str]]] = [
    (["selfcheck"], []),
    (["profile", "validate"], ["file"]),
    (["profile", "consistency"], ["file", "--resume-facts"]),
    (["facts", "render"], ["file", "-o"]),
    (["run", "new"], ["--mode", "interactive", "batch"]),
    (["run", "checkpoint"], ["run_id", "--state"]),
    (["run", "show"], ["run_id"]),
    (["run", "pending"], ["run_id"]),
    (["run", "resolve"], ["run_id", "action_id", "--note"]),
    (["jobs", "add"], ["file"]),
    (["jobs", "check"], ["company", "title"]),
    (["queue", "build"], ["run_id", "--from", "-o"]),
    (["app", "start"], ["run_id", "job_id", "--channel"]),
    (["app", "status"], ["app_id", "status", "--reason"]),
    (["app", "evidence"], ["app_id", "--type", "--url", "--screenshot", "--subject", "--note"]),
    (["app", "gate"], ["app_id", "--type", "--message", "--scope", "item", "run"]),
    (["ledger", "stats"], ["--run"]),
    (["ledger", "export"], ["-o"]),
    (["ledger", "migrate-legacy"], ["file", "--dry-run"]),
    (["report"], ["run_id"]),
]


def main() -> int:
    for path, needles in CONTRACT:
        code, out, err, _ = run_cli(*path, "--help", expect=None)
        c.check(code == 0, "`%s --help` exited %d: %s" % (" ".join(path), code, err[-300:]))
        for n in needles:
            c.check(n in out, "`%s --help` lacks %r" % (" ".join(path), n))
    code, out, _e, _ = run_cli("--help", expect=None)
    for n in ("--data-dir", "--profile", "--json"):
        c.check(n in out, "global flag %s missing" % n)
    proc = subprocess.run([sys.executable, "-m", "autoapply", "--help"], cwd=str(SCRIPTS_DIR), capture_output=True, text=True, env=dict(os.environ))
    c.check(proc.returncode == 0 and "selfcheck" in proc.stdout, "python3 -m autoapply failed: %s" % proc.stderr[-300:])
    with TempData() as d:
        code, out, err, _ = run_cli("run", "show", "run_20260101_000000", data=d, expect=None)
        j = stderr_json(err)
        c.check(code == 2 and j is not None and "error" in j and "detail" in j, "failure must print one JSON line on stderr (got %r)" % err[-200:])
        code, out, err, _ = run_cli("run", "show", "run_20260101_000000", data=d, json_out=True, expect=None)
        c.check(code == 2 and stderr_json(err) is not None, "--json failure path")
        # no profile & several profiles -> config error exit 2
        (d.root / "second_user").mkdir()
        (d.root / "second_user" / "profile.json").write_text("{}", encoding="utf-8")
        (d.profile_dir / "profile.json").write_text("{}", encoding="utf-8")
        env2 = dict(os.environ)
        env2.pop("AUTO_APPLY_PROFILE", None)
        proc = subprocess.run([sys.executable, str(CLI), "--data-dir", str(d.root), "run", "list"], capture_output=True, text=True, env=env2)
        c.check(proc.returncode == 2 and (stderr_json(proc.stderr) or {}).get("error") == "config_error", "ambiguous profile must be config_error")
    # version gate: simulate an interpreter below 3.9 by faking sys.version_info before running cli.py.
    fake_code = (
        "import sys, runpy\n"
        "sys.version_info = (3, 8, 0, 'final', 0)\n"
        "sys.argv = [%r, '--help']\n"
        "runpy.run_path(%r, run_name='__main__')\n"
    ) % (str(CLI), str(CLI))
    proc = subprocess.run([sys.executable, "-c", fake_code], capture_output=True, text=True, env=dict(os.environ))
    c.check(proc.returncode == 2 and (stderr_json(proc.stderr) or {}).get("error") == "python_version", "version gate must exit 2 below 3.9 (no override exists)")
    return c.done("all contract commands/arguments present; -m entry works; stderr JSON on failure; version gate")


if __name__ == "__main__":
    sys.exit(main())

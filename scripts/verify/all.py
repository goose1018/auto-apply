#!/usr/bin/env python3
"""Run every scripts/verify/*.py (except all.py and _*.py) with the current interpreter (CODE_STANDARDS §8.3).

Prints a table (script / verdict / seconds / last line) and ends with
    SUMMARY passed=<n> failed=<m> total=<t>
Exit code 1 if any script is not PASS. No skip switch exists on purpose.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT = 120

if sys.version_info < (3, 9):
    sys.exit("需要 Python 3.9+（当前 %d.%d）/ need Python 3.9+" % (sys.version_info[0], sys.version_info[1]))


def main() -> int:
    scripts = sorted(p for p in HERE.glob("*.py") if p.name != "all.py" and not p.name.startswith("_"))
    rows: list[tuple[str, str, float, str]] = []
    failed: list[str] = []
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    for script in scripts:
        t0 = time.time()
        try:
            proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=TIMEOUT, env=env)
            out_lines = [l for l in (proc.stdout or "").splitlines() if l.strip()]
            last = out_lines[-1] if out_lines else ""
            if last.startswith("PASS ") and proc.returncode == 0:
                verdict = "PASS"
            elif last.startswith("FAIL "):
                verdict = "FAIL"
            else:
                verdict = "NO-VERDICT"
                err_lines = [l for l in (proc.stderr or "").splitlines() if l.strip() and not l.startswith("[未验证]")]
                if err_lines:
                    last = (last + " | " if last else "") + err_lines[-1]
                if proc.returncode != 0 and not last:
                    last = "exit %d" % proc.returncode
        except subprocess.TimeoutExpired:
            verdict, last = "TIMEOUT", "exceeded %ds" % TIMEOUT
        dt = time.time() - t0
        rows.append((script.name, verdict, dt, last))
        if verdict != "PASS":
            failed.append(script.name)
    width = max((len(r[0]) for r in rows), default=10)
    print("%-*s  %-10s  %6s  %s" % (width, "script", "verdict", "sec", "last line"))
    for name, verdict, dt, last in rows:
        print("%-*s  %-10s  %6.1f  %s" % (width, name, verdict, dt, last[:160]))
    if failed:
        print("failed scripts: " + ", ".join(failed))
    print("SUMMARY passed=%d failed=%d total=%d" % (len(rows) - len(failed), len(failed), len(rows)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

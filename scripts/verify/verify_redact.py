#!/usr/bin/env python3
"""verify: redact — CODE_STANDARDS §6.3 / SECURITY §5 masking and secret detection (R7).
Main path: mask_email / mask_phone / mask_name; redact() replaces e-mails and phones; job ids / req ids untouched.
Failure paths: NRIC/FIN and password keys raise RedactionError; ledger events / notes pass through redact().
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.errors import RedactionError  # noqa: E402
from autoapply.redact import find_secret_hits, mask_email, mask_name, mask_phone, redact  # noqa: E402

NAME = "redact"
c = Checker(NAME)


def main() -> int:
    c.check(mask_email("alex.tan@example.com") == "a***@example.com", "mask_email")
    c.check(mask_phone("+65 0000 1234") == "+65 ****1234", "mask_phone: %r" % mask_phone("+65 0000 1234"))
    c.check(mask_phone("+65-0000-5678") == "+65 ****5678", "mask_phone dashes")
    c.check(mask_name("Alex Tan") == "A** T**" and mask_name("李明") == "李*", "mask_name: %r %r" % (mask_name("Alex Tan"), mask_name("李明")))
    text = "Contact alex.tan@example.com or +65 0000 1234 / 91234567; req JR106776, id 26978591, url /job/93624878/apply"
    out = redact(text)
    c.check("alex.tan@" not in out and "[REDACTED:email]" in out, "email not redacted: %s" % out)
    c.check("0000 1234" not in out and "91234567" not in out, "phones not redacted: %s" % out)
    c.check("JR106776" in out and "26978591" in out and "/job/93624878/apply" in out, "identifiers wrongly redacted: %s" % out)
    for bad in ("nric S1234567A", "fin G7654321X", "password=abc", "JOB_ACCOUNT_PASSWORD=x", "Password: hunter2"):
        try:
            redact(bad)
            c.check(False, "redact must raise on %r" % bad)
        except RedactionError as e:
            c.check("S1234567A" not in str(e) and "hunter2" not in str(e) and "abc" not in str(e), "exception message leaks the value")
    c.check(find_secret_hits("HRC1666025 UNI4651") == [], "req ids flagged as secrets")
    c.check(find_secret_hits("S1234567A") == ["nric"], "find_secret_hits")

    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        for st in ("source", "screen", "apply"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)
        cf = write_jsonl(d.root / "c.jsonl", [fx.candidate("R Co", "Intern", run_id=run_id)])
        _c, _o, _e, rep = run_cli("jobs", "add", str(cf), data=d, json_out=True)
        _c, _o, _e, a = run_cli("app", "start", run_id, rep["added"][0]["job_id"], "--channel", "company_site", data=d, json_out=True)
        run_cli("app", "status", a["app_id"], "failed", "--reason", "form rejected for alex.tan@example.com", data=d)
        run_cli("app", "gate", a["app_id"], "--type", "captcha", "--message", "验证码页面 联系 +65 0000 1234", data=d)
        conn = sqlite3.connect(str(d.profile_dir / "ledger.sqlite"))
        for table in ("applications", "events", "gates"):
            cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
            for row in conn.execute("SELECT * FROM %s" % table):
                for col, val in zip(cols, row):
                    if isinstance(val, str):
                        c.check("alex.tan@" not in val and "0000 1234" not in val, "%s.%s stored unredacted text" % (table, col))
        conn.close()
        md = (d.profile_dir / "runs" / run_id / "pending_actions.md").read_text(encoding="utf-8")
        c.check("0000 1234" not in md and "[REDACTED:phone]" in md, "pending md not redacted")
        writes = (d.profile_dir / "runs" / run_id / "ledger_writes.jsonl").read_text(encoding="utf-8")
        c.check("alex.tan@" not in writes, "ledger_writes.jsonl leaks")
        run_cli("app", "status", a["app_id"], "failed", "--reason", "nric S1234567A required", data=d, expect=3)
    return c.done("masks match spec; e-mail/phone redacted, ids kept; NRIC/password raise; ledger/pending/writes redacted")


if __name__ == "__main__":
    sys.exit(main())

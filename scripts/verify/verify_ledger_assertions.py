#!/usr/bin/env python3
"""verify: ledger_assertions — ARCHITECTURE §9 assertions and the "已投" hard rule (BRIEF §3; INCIDENTS I-18).
Main path: qualifying evidence -> applied; `ledger assert` PASS.
Failure paths: applied without evidence -> exit 3; non-qualifying types never qualify; unique-vs-actions,
no-secrets and per-company-cap violations make `ledger assert` exit 3.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, stderr_json, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "ledger_assertions"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume, per_company_max=2))
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        for st in ("source", "screen", "apply"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)
        cands = [fx.candidate("Same Co", "Intern %d" % i, run_id=run_id) for i in range(1, 5)]
        cf = write_jsonl(d.root / "c.jsonl", cands)
        _c, _o, _e, rep = run_cli("jobs", "add", str(cf), data=d, json_out=True)
        job_ids = [e["job_id"] for e in rep["added"]]
        c.check(len(job_ids) == 4, "expected 4 jobs")

        _c, _o, _e, a = run_cli("app", "start", run_id, job_ids[0], "--channel", "company_site", data=d, json_out=True)
        app1 = a["app_id"]
        code, _o, err, _ = run_cli("app", "status", app1, "applied", data=d, expect=3)
        j = stderr_json(err)
        c.check(j is not None and j.get("error") == "evidence_error", "expected evidence_error JSON on stderr, got %r" % (j,))
        shot = d.root / "form.txt"
        shot.write_text("form completed for Intern 1", encoding="utf-8")
        for t in ("form_completed_screenshot", "review_page_screenshot", "draft_saved", "external_redirect", "open_tab",
                  "account_verification_email", "generic_ack_email"):
            _c, _o, _e, ev = run_cli("app", "evidence", app1, "--type", t, "--url", "https://x", "--screenshot", str(shot),
                                     "--job-title-seen", "Intern 1", "--subject", "Intern 1 received", "--from", "jobs@example.com",
                                     "--received-at", "2026-09-05T10:00:00+08:00", data=d, json_out=True)
            c.check(ev["qualifies"] == 0, "%s must never qualify" % t)
        run_cli("app", "status", app1, "applied", data=d, expect=3)
        _c, _o, _e, ev = run_cli("app", "evidence", app1, "--type", "success_page", "--url", "https://x/ok", "--screenshot", str(shot),
                                 data=d, json_out=True)
        c.check(ev["qualifies"] == 0, "success_page without job_title_seen must not qualify")
        _c, _o, _e, ev = run_cli("app", "evidence", app1, "--type", "success_page", "--url", "https://x/ok", "--screenshot", str(shot),
                                 "--job-title-seen", "Intern 1", data=d, json_out=True)
        c.check(ev["qualifies"] == 1, "success_page with matching title should qualify: %s" % ev["judge_reasons"])
        _c, _o, _e, app = run_cli("app", "status", app1, "applied", data=d, json_out=True)
        c.check(app["status"] == "applied" and app["submission_action_count"] == 1 and app["applied_confirmed_at"], "applied bookkeeping")
        run_cli("ledger", "assert", data=d, expect=0)

        # per-company-cap: 3 applied at per_company_max=2 without override notes -> FAIL; with note -> PASS
        for jid in job_ids[1:3]:
            _c, _o, _e, a = run_cli("app", "start", run_id, jid, "--channel", "company_site", data=d, json_out=True)
            title = [x for x in cands if x["job_id"] == jid] if False else None
            run_cli("app", "evidence", a["app_id"], "--type", "success_page", "--url", "https://x/ok", "--screenshot", str(shot),
                    "--job-title-seen", "Intern", "--mark-applied", data=d)
        _c, out, _e, _ = run_cli("ledger", "assert", data=d, expect=3)
        c.check("per-company-cap" in out, "per-company-cap violation not reported: %s" % out)
        db = d.profile_dir / "ledger.sqlite"
        conn = sqlite3.connect(str(db))
        conn.execute("UPDATE applications SET approval_json='{\"approval_note\": \"user override\", \"approved_at\": \"x\", \"approved_by_user\": true}' WHERE app_id != ?", (app1,))
        conn.commit()
        run_cli("ledger", "assert", data=d, expect=0)
        # unique-vs-actions: force actions below unique
        conn.execute("UPDATE applications SET submission_action_count=0 WHERE status='applied'")
        conn.commit()
        _c, out, _e, _ = run_cli("ledger", "assert", data=d, expect=3)
        c.check("unique-vs-actions" in out, "unique-vs-actions not reported")
        conn.execute("UPDATE applications SET submission_action_count=1 WHERE status='applied'")
        # no-secrets: inject a NRIC-like value directly (the API refuses it, so bypass via SQL)
        conn.execute("UPDATE applications SET notes='id S1234567A' WHERE app_id=?", (app1,))
        conn.commit()
        _c, out, _e, _ = run_cli("ledger", "assert", data=d, expect=3)
        c.check("no-secrets" in out, "no-secrets not reported")
        conn.execute("UPDATE applications SET notes=NULL WHERE app_id=?", (app1,))
        # applied-has-evidence: delete evidence behind an applied row
        conn.execute("DELETE FROM evidence WHERE app_id=?", (app1,))
        conn.commit()
        _c, out, _e, _ = run_cli("ledger", "assert", data=d, expect=3)
        c.check("applied-has-evidence" in out, "applied-has-evidence not reported")
        conn.close()
        # API refuses secret-like notes
        run_cli("app", "status", app1, "applied", "--note", "password=hunter2", data=d, expect=3)
    return c.done("applied requires qualifying evidence (exit 3 otherwise); 4 ledger assertions have pass + fail paths")


if __name__ == "__main__":
    sys.exit(main())

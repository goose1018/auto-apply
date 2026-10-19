#!/usr/bin/env python3
"""verify: evidence — §7 qualification rules; only evidence.py sets qualifies; text evidence is redacted.
Main path: success_page (url+file+matching title), ATS-domain email, portal Submitted, legacy_import qualify.
Failure paths: missing title / mismatched title / unknown sender + no title / portal "under review" / non-qualifying
types never qualify; NRIC in a text evidence file is refused (exit 3); missing file exit 3.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.evidence import EvidenceInput, JobContext, judge  # noqa: E402

NAME = "evidence"
c = Checker(NAME)
JOB = JobContext(company_raw="Example Robotics", company_norm="example robotics", title_raw="AI Engineer Intern (Edge)",
                 title_norm="ai engineer intern edge", req_id="JR12345", company_domain="example.com")


def main() -> int:
    ok = judge(EvidenceInput("success_page", url="https://x", job_title_seen="AI Engineer Intern"), JOB, has_file=True)
    c.check(ok.qualifies, "success_page with matching title should qualify: %s" % (ok.reasons,))
    c.check(judge(EvidenceInput("success_page", url="https://x", job_title_seen="JR12345 received"), JOB, True).qualifies, "req_id match")
    c.check(not judge(EvidenceInput("success_page", url="https://x"), JOB, True).qualifies, "missing job_title_seen must fail")
    c.check(not judge(EvidenceInput("success_page", url="https://x", job_title_seen="Marketing Manager"), JOB, True).qualifies, "mismatched title must fail")
    c.check(not judge(EvidenceInput("success_page", url="https://x", job_title_seen="AI Engineer Intern"), JOB, False).qualifies, "missing file must fail")
    c.check(not judge(EvidenceInput("success_page", job_title_seen="AI Engineer Intern"), JOB, True).qualifies, "missing url must fail")
    em = EvidenceInput("ats_confirmation_email", email_subject="Thanks for your application", email_from="no-reply@myworkday.com",
                       email_received_at="2026-09-05T10:00:00+08:00")
    c.check(judge(em, JOB, False).qualifies, "known ATS domain should qualify")
    em2 = EvidenceInput("ats_confirmation_email", email_subject="Application received: AI Engineer Intern", email_from="hr@unknown.test",
                        email_received_at="2026-09-05T10:00:00+08:00")
    c.check(judge(em2, JOB, False).qualifies, "subject naming the job should qualify")
    em3 = EvidenceInput("ats_confirmation_email", email_subject="Newsletter", email_from="hr@unknown.test", email_received_at="2026-09-05T10:00:00+08:00")
    c.check(not judge(em3, JOB, False).qualifies, "unknown sender + generic subject must fail")
    em4 = EvidenceInput("employer_confirmation_email", email_subject="We got it", email_from="talent@example.com", email_received_at="x")
    c.check(judge(em4, JOB, False).qualifies, "company domain should qualify")
    c.check(not judge(EvidenceInput("employer_confirmation_email", email_subject="x", email_from="talent@example.com"), JOB, False).qualifies, "missing received_at must fail")
    portal = EvidenceInput("ats_portal_status", url="https://x/my-applications", job_title_seen="AI Engineer Intern", status_seen="Submitted")
    c.check(judge(portal, JOB, True).qualifies, "portal Submitted should qualify")
    c.check(not judge(EvidenceInput("ats_portal_status", url="https://x", job_title_seen="AI Engineer Intern", status_seen="Under review"), JOB, True).qualifies,
            "portal 'under review' must not qualify (HISTORY decision)")
    c.check(judge(EvidenceInput("legacy_import", legacy_ref="L1: x"), JOB, False).qualifies, "legacy_import with ref qualifies")
    c.check(not judge(EvidenceInput("legacy_import"), JOB, False).qualifies, "legacy_import without ref must fail")
    for t in ("review_page_screenshot", "form_completed_screenshot", "draft_saved", "account_verification_email", "external_redirect", "open_tab", "generic_ack_email"):
        c.check(not judge(EvidenceInput(t, url="https://x", job_title_seen="AI Engineer Intern", email_subject="AI Engineer Intern",
                                        email_from="a@example.com", email_received_at="x"), JOB, True).qualifies, "%s must never qualify" % t)

    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        for st in ("source", "screen", "apply"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)
        cf = write_jsonl(d.root / "c.jsonl", [fx.candidate("Example Robotics", "AI Engineer Intern", run_id=run_id, domain="example.com")])
        _c, _o, _e, rep = run_cli("jobs", "add", str(cf), data=d, json_out=True)
        job_id = rep["added"][0]["job_id"]
        _c, _o, _e, a = run_cli("app", "start", run_id, job_id, "--channel", "company_site", data=d, json_out=True)
        app_id = a["app_id"]
        page = d.root / "page.txt"
        page.write_text("Thank you Alex Tan <alex.tan@example.com>, call +65 0000 1234. Application submitted for AI Engineer Intern.", encoding="utf-8")
        _c, _o, _e, ev = run_cli("app", "evidence", app_id, "--type", "success_page", "--url", "https://x/ok", "--screenshot", str(page),
                                 "--job-title-seen", "AI Engineer Intern", "--captured-by", "qa", data=d, json_out=True)
        c.check(ev["qualifies"] == 1 and ev["evidence_id"] == "ev_%s_01" % app_id[4:], "evidence id / qualifies: %s" % ev)
        stored = d.profile_dir / "evidence" / app_id / "01_success_page.txt"
        c.check(stored.is_file(), "evidence file not stored at %s" % stored)
        text = stored.read_text(encoding="utf-8")
        c.check("[REDACTED:email]" in text and "[REDACTED:phone]" in text and "alex.tan@" not in text, "text evidence not redacted: %s" % text)
        c.check(ev["file"] == "%s/01_success_page.txt" % app_id and len(ev["sha256"]) == 64, "file/sha256 columns")
        bad = d.root / "bad.txt"
        bad.write_text("NRIC S1234567A shown on page", encoding="utf-8")
        run_cli("app", "evidence", app_id, "--type", "success_page", "--url", "https://x", "--screenshot", str(bad), "--job-title-seen", "AI Engineer Intern", data=d, expect=3)
        run_cli("app", "evidence", app_id, "--type", "success_page", "--url", "https://x", "--screenshot", str(d.root / "missing.png"), "--job-title-seen", "x", data=d, expect=3)
        run_cli("app", "evidence", app_id, "--type", "success_page", "--url", "https://x", "--screenshot", str(resume.with_suffix(".exe")), data=d, expect=3)
        # email evidence via CLI with excerpt redaction
        _c, _o, _e, ev2 = run_cli("app", "evidence", app_id, "--type", "ats_confirmation_email", "--subject", "Application received",
                                  "--from", "noreply@greenhouse.io", "--received-at", "2026-09-05T10:00:00+08:00",
                                  "--excerpt", "Dear Alex (alex.tan@example.com), we received your application.", data=d, json_out=True)
        c.check(ev2["qualifies"] == 1 and "[REDACTED:email]" in ev2["email_excerpt"], "email evidence / excerpt redaction: %s" % ev2)
        _c, _o, _e, ev3 = run_cli("app", "evidence", app_id, "--type", "open_tab", "--url", "https://x", "--mark-applied", data=d, json_out=True, expect=None)
        c.check(ev3["qualifies"] == 0, "open_tab must not qualify even with --mark-applied")
    return c.done("§7.1 table enforced; title/domain/portal rules; text evidence redacted; secrets refused")


if __name__ == "__main__":
    sys.exit(main())

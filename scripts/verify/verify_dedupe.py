#!/usr/bin/env python3
"""verify: dedupe — R1 dedup key and counting (ARCHITECTURE §6; INCIDENTS I-01).
Main path: normalisation examples from §6.2/§6.3; same job via two channels -> unique 1 / actions 2 / duplicates 1.
Failure paths: second channel without --force is refused (exit 1); suspected duplicate -> dedup_review; aliases apply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.normalize import is_suspected_duplicate, make_dedup_key, normalize_company, normalize_title  # noqa: E402

NAME = "dedupe"
c = Checker(NAME)

COMPANY_CASES = {
    "NCS Pte. Ltd.": "ncs", "Panasonic Asia Pacific": "panasonic", "Sea Limited": "sea",
    "Fraser & Neave (Singapore)": "fraser and neave", "华为技术有限公司": "华为技术", "The Example Group": "example",
    "Example Robotics Pte Ltd": "example robotics", "EXAMPLE ROBOTICS": "example robotics",
}
TITLE_CASES = {
    "AI Solutions & Analytics (HRC1666025)": "ai solutions analytics",
    "SWE Intern (Edge AI Toolchain)": "software engineer intern edge ai toolchain",
    "Technology Consulting - AI & Cybersecurity Intern Jan-Jun 2027": "technology consulting ai cybersecurity intern",
    "Data Analyst Intern Spring 2027": "data analyst intern",
    "[Uni – Jan till Jun 2027] Agentic AI Intern": "agentic ai intern",
    "AI Engineer Internship (Singapore)": "ai engineer intern",
    "2027 APAC Summer Internship": "intern",
}


def main() -> int:
    for raw, want in COMPANY_CASES.items():
        got = normalize_company(raw)
        c.check(got == want, "normalize_company(%r) = %r, want %r" % (raw, got, want))
    for raw, want in TITLE_CASES.items():
        got = normalize_title(raw)
        c.check(got == want, "normalize_title(%r) = %r, want %r" % (raw, got, want))
    k1 = make_dedup_key("Example Robotics Pte Ltd", "AI Engineer Intern")
    k2 = make_dedup_key("EXAMPLE ROBOTICS", "AI Engineer Internship (Singapore)")
    c.check(k1.key == k2.key and k1.job_id == k2.job_id, "same job different spelling -> different job_id")
    c.check(k1.job_id.startswith("job_") and len(k1.job_id) == 16, "job_id format")
    c.check(is_suspected_duplicate("agentic ai intern", "agentic ai"), "contiguous subsequence not flagged")
    c.check(not is_suspected_duplicate("software engineer intern", "data analyst intern"), "unrelated titles flagged")

    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        cands = write_jsonl(d.root / "c.jsonl", [
            fx.candidate("Example Robotics Pte Ltd", "AI Engineer Intern", run_id=run_id, platform="greenhouse", channel="company_site"),
            fx.candidate("EXAMPLE ROBOTICS", "AI Engineer Internship (Singapore)", run_id=run_id, platform="linkedin_easy_apply", channel="linkedin"),
            fx.candidate("Other Co", "Data Intern", run_id=run_id),
        ])
        _c, _o, _e, rep = run_cli("jobs", "add", str(cands), data=d, json_out=True)
        c.check(rep["counts"]["added"] == 2 and rep["counts"]["existing"] == 1, "dedup report counts: %s" % rep["counts"])
        c.check(rep["existing"][0]["line"] == 2 and "same dedup_key" in rep["existing"][0]["reason"], "second channel not detected as same job")
        _c, _o, _e, st = run_cli("ledger", "stats", data=d, json_out=True)
        c.check(st["jobs_total"] == 2, "jobs table should hold 2 unique jobs, has %s" % st["jobs_total"])

        job_id = k1.job_id
        run_cli("run", "checkpoint", run_id, "--state", "source", data=d)
        run_cli("run", "checkpoint", run_id, "--state", "screen", data=d)
        run_cli("run", "checkpoint", run_id, "--state", "apply", data=d)
        _c, _o, _e, a1 = run_cli("app", "start", run_id, job_id, "--channel", "company_site", data=d, json_out=True)
        shot = d.root / "success.txt"
        shot.write_text("Application submitted: AI Engineer Intern", encoding="utf-8")
        run_cli("app", "evidence", a1["app_id"], "--type", "success_page", "--url", "https://jobs.example.com/ok",
                "--screenshot", str(shot), "--job-title-seen", "AI Engineer Intern", "--mark-applied", data=d)
        # second channel: refused without --force (already applied)
        run_cli("app", "start", run_id, job_id, "--channel", "linkedin", data=d, expect=1)
        _c, _o, _e, a2 = run_cli("app", "start", run_id, job_id, "--channel", "linkedin", "--force", "--note", "user insisted", data=d, json_out=True)
        run_cli("app", "status", a2["app_id"], "submitted_unverified", data=d)
        _c, _o, _e, st = run_cli("ledger", "stats", data=d, json_out=True)
        c.check(st["unique_jobs_applied"] == 1 and st["submission_actions"] == 2 and st["duplicates"] == 1,
                "R1 counting wrong: %s" % {k: st[k] for k in ("unique_jobs_applied", "submission_actions", "duplicates")})
        # jobs check: exact hit and suspected duplicate
        _c, _o, _e, chk = run_cli("jobs", "check", "Example Robotics Pte. Ltd.", "AI Engineer Intern Spring 2027", data=d, json_out=True)
        c.check(chk["decision"] == "dedup_hit", "exact hit expected, got %s" % chk["decision"])
        _c, _o, _e, chk = run_cli("jobs", "check", "Example Robotics", "AI Engineer", data=d, json_out=True)
        c.check(chk["decision"] == "dedup_review" and chk["similar"], "suspected duplicate expected, got %s" % chk["decision"])
        _c, _o, _e, chk = run_cli("jobs", "check", "Example Robotics", "Marketing Manager", data=d, json_out=True)
        c.check(chk["decision"] == "new", "unrelated title at same company should be new, got %s" % chk["decision"])
        # aliases
        write_json(d.profile_dir / "dedup_aliases.json", {"ex robotics": "example robotics"})
        _c, _o, _e, chk = run_cli("jobs", "check", "Ex Robotics", "AI Engineer Intern", data=d, json_out=True)
        c.check(chk["decision"] == "dedup_hit" and chk["company_norm"] == "example robotics", "alias not applied: %s" % chk["company_norm"])
        # mismatching precomputed job_id in candidates must be refused (script is the authority)
        bad = fx.candidate("Other Co", "QA Intern", run_id=run_id)
        bad["job_id"] = "job_000000000000"
        badf = write_jsonl(d.root / "bad.jsonl", [bad])
        run_cli("jobs", "add", str(badf), data=d, expect=3)
        _ = json.dumps(rep)
    return c.done("normalisation matches §6 examples; 1 job via 2 channels counts 1/2/1; review + aliases + refusal paths")


if __name__ == "__main__":
    sys.exit(main())

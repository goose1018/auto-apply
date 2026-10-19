#!/usr/bin/env python3
"""verify: presubmit — R10 CLI review (autoapply/presubmit.py), the machine-checkable subset of
checklists/pre_submit.md §1. Main path: a fully-consistent profile + resume + job -> all 10
machine-checked items pass, the 7 live-page items stay unverified, overall passed=true, exit 0.
Failure path: no --resume on app start, a missing declaration, and a job requiring a different
resume language all make their items fail -> passed=false, exit 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "presubmit"
c = Checker(NAME)

FULL_DECLARATIONS = {
    "criminal_record": "No", "bankruptcy": "No", "vaccination_status": "Not applicable",
    "relatives_in_company": "No", "previously_applied_or_employed": "No", "non_compete": "No",
    "background_check_consent": "Yes", "data_processing_consent": "Yes", "other": [],
}


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume_en.txt"
        resume.write_text("Fictional resume content for verify_presubmit.", encoding="utf-8")
        profile = fx.profile(resume)
        profile["policy"]["declarations"] = dict(FULL_DECLARATIONS)
        write_json(d.profile_dir / "profile.json", profile)

        _c, _o, _e, r = run_cli("run", "new", data=d, json_out=True)
        run_id = r["run_id"]
        for st in ("source", "screen", "apply"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)

        cand = fx.candidate("Example Robotics Pte Ltd", "AI Engineer Intern", run_id=run_id, hard={
            "resume_language_required": "en",
            "work_window": {"start": "2027-01", "end": "2027-06", "raw": None},
            "salary": {"disclosed": True, "min": 2000, "max": 2500, "currency": "SGD", "period": "month", "unpaid": False},
        })
        cf = write_jsonl(d.root / "c.jsonl", [cand])
        _c, _o, _e, rep = run_cli("jobs", "add", str(cf), data=d, json_out=True)
        job_id = rep["added"][0]["job_id"]

        # --- main path: --resume given, everything lines up -> passed
        _c, _o, _e, a = run_cli("app", "start", run_id, job_id, "--channel", "company_site", "--resume", str(resume), data=d, json_out=True)
        app_id = a["app_id"]
        code, out, err, pres = run_cli("presubmit", app_id, data=d, json_out=True, expect=None)
        c.check(code == 0 and pres["passed"] is True, "fully-consistent application should pass: code=%s items=%s" % (code, [(i["name"], i["status"]) for i in pres.get("items", [])]))
        by_name: dict[str, list[str]] = {}
        for i in pres["items"]:
            by_name.setdefault(i["name"], []).append(i["status"])
        c.check(by_name.get("name_order") == ["pass"], "name_order should pass: %s" % by_name.get("name_order"))
        c.check(by_name.get("phone_country_code") == ["pass"], "phone_country_code should pass: %s" % by_name.get("phone_country_code"))
        c.check(by_name.get("graduation_year") == ["pass"], "graduation_year should pass: %s" % by_name.get("graduation_year"))
        c.check(by_name.get("resume_version") == ["pass", "pass"], "both resume_version checks should pass: %s" % by_name.get("resume_version"))
        c.check(by_name.get("internship_window") == ["pass"], "internship_window should pass: %s" % by_name.get("internship_window"))
        c.check(by_name.get("salary") == ["pass"], "salary should pass: %s" % by_name.get("salary"))
        others = by_name.get("other") or []
        c.check(others.count("pass") == 3 and others.count("unverified") == 3, "3 'other' machine checks (dedup/declarations/open_answers) pass, 3 stay unverified: %s" % others)
        c.check(pres["unverified_count"] == 7, "7 checklist items always need a live page read: %s" % pres["unverified_count"])
        unverified_names = {i["name"] for i in pres["items"] if i["status"] == "unverified"}
        c.check({"email", "location", "work_pass_answer", "sponsorship_answer"} <= unverified_names, "manual-only checklist items must be reported, not silently dropped: %s" % unverified_names)
        c.check(pres.get("fail_count") == 0, "no FAIL expected on the main path: %s" % pres)

        # --- human output: FAIL/PASS lines rendered, one line per item
        _c, human, _e, _ = run_cli("presubmit", app_id, data=d)
        c.check("presubmit %s: PASS" % app_id in human and "[PASS      ] name_order" in human, "human-readable presubmit output: %r" % human[:200])

        # --- failure path: no --resume on app start (second app, second channel to skip the dedup gate) ---
        cand2 = fx.candidate("Sample Analytics Ltd", "Data Intern", run_id=run_id, hard={
            "resume_language_required": "zh",  # profile only has an "en" resume -> resume_version language check fails
            "salary": {"disclosed": True, "min": 100, "max": 200, "currency": "SGD", "period": "month", "unpaid": False},  # below hard_floor 1500
        })
        cf2 = write_jsonl(d.root / "c2.jsonl", [cand2])
        _c, _o, _e, rep2 = run_cli("jobs", "add", str(cf2), data=d, json_out=True)
        job_id2 = rep2["added"][0]["job_id"]
        _c, _o, _e, a2 = run_cli("app", "start", run_id, job_id2, "--channel", "company_site", data=d, json_out=True)
        app_id2 = a2["app_id"]
        bad_profile = fx.profile(resume)
        bad_profile["policy"]["declarations"] = dict(FULL_DECLARATIONS)
        bad_profile["policy"]["declarations"]["bankruptcy"] = None  # not preset -> declarations_preset should fail
        write_json(d.profile_dir / "profile.json", bad_profile)
        code2, _o, _e, pres2 = run_cli("presubmit", app_id2, data=d, json_out=True, expect=None)
        c.check(code2 == 1 and pres2["passed"] is False, "inconsistent application must fail with exit 1: code=%s passed=%s" % (code2, pres2.get("passed")))
        by_name2: dict[str, list[str]] = {}
        for i in pres2["items"]:
            by_name2.setdefault(i["name"], []).append(i["status"])
        c.check("fail" in by_name2.get("resume_version", []), "no --resume + wrong language -> resume_version must fail: %s" % by_name2.get("resume_version"))
        c.check("fail" in by_name2.get("salary", []), "job below hard_floor -> salary must fail: %s" % by_name2.get("salary"))
        fail_others = [i for i in pres2["items"] if i["name"] == "other" and i["status"] == "fail"]
        c.check(any("declarations_preset" in i["note"] for i in fail_others), "unset declaration must fail with the declarations_preset label: %s" % fail_others)
        c.check(pres2["fail_count"] >= 3, "at least 3 fail items expected: %s" % pres2)

        # unknown app_id -> ledger_error, not a silent pass
        run_cli("presubmit", "app_20260101_ffffff", data=d, expect=3)
    return c.done("R10 machine-checkable subset judged pass/fail; unverifiable checklist items always reported as unverified, never counted as pass")


if __name__ == "__main__":
    sys.exit(main())

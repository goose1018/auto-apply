#!/usr/bin/env python3
"""verify: consistency — R3 resume/profile gate (ARCHITECTURE §8; INCIDENTS I-03; P2 DoD).
Main path: matching resume facts -> overall pass, exit 0, report written with masked values.
Failure paths: e-mail mismatch -> block + exit 1; graduation year mismatch -> block; name order -> warn;
known_mismatches downgrade to info; missing files exit 2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "consistency"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        prof = fx.profile(resume)
        pf = write_json(d.profile_dir / "profile.json", prof)
        good = write_json(d.root / "rp_good.json", fx.resume_parse(resume))
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(good), data=d, json_out=True)
        c.check(rep["overall"] == "pass", "matching facts should pass: %s" % json.dumps(rep, ensure_ascii=False)[:400])
        c.check(Path(rep["written_to"]).name == "consistency_report.json" and (d.profile_dir / "consistency_report.json").is_file(), "report file")
        bad_email = write_json(d.root / "rp_email.json", fx.resume_parse(resume, email="alex.tan@other.example"))
        code, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(bad_email), data=d, json_out=True, expect=1)
        c.check(rep["overall"] == "block", "e-mail mismatch must block")
        f = [x for x in rep["resumes"][0]["findings"] if x["field"] == "email"][0]
        c.check(f["level"] == "block" and f["resume_value_masked"] == "a***@other.example" and "alex.tan" not in json.dumps(rep), "masked values: %s" % f)
        bad_year = write_json(d.root / "rp_year.json", fx.resume_parse(resume, expected="2028-06"))
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(bad_year), data=d, json_out=True, expect=1)
        c.check(any(x["field"] == "graduation" and x["level"] == "block" for x in rep["resumes"][0]["findings"]), "graduation year mismatch must block")
        bad_month = write_json(d.root / "rp_month.json", fx.resume_parse(resume, expected="2027-05"))
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(bad_month), data=d, json_out=True, expect=0)
        c.check(rep["overall"] == "warn", "same year different month should warn")
        bad_name = write_json(d.root / "rp_name.json", fx.resume_parse(resume, name="Tan Alex"))
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(bad_name), data=d, json_out=True, expect=0)
        c.check(any(x["field"] == "name" and x["level"] == "warn" and "顺序" in x["hint"] for x in rep["resumes"][0]["findings"]), "name order warn")
        bad_phone = write_json(d.root / "rp_phone.json", fx.resume_parse(resume, phone="0000 9999"))
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(bad_phone), data=d, json_out=True, expect=1)
        c.check(any(x["field"] == "phone" and x["level"] == "block" and x["resume_value_masked"] == "+65 ****9999" for x in rep["resumes"][0]["findings"]), "phone block + mask")
        # code-less resume phone (typical for Chinese resumes) must match the same bare number in the profile
        nocc = fx.resume_parse(resume); nocc["parsed"]["phones"] = [{"country_code": None, "number": "0000-1234"}]
        nocc_p = write_json(d.root / "rp_nocc.json", nocc)
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(nocc_p), data=d, json_out=True, expect=None)
        c.check(not any(x["field"] == "phone" and x["level"] == "block" for x in rep["resumes"][0]["findings"]),
                "resume phone without country code must not block when the bare number matches")
        # native-script name on the resume must pass when it equals identity.name.native
        prof_native = json.loads(json.dumps(prof)); prof_native["identity"]["name"]["native"] = "陈家明"
        pf_native = write_json(d.root / "profile_native.json", prof_native)
        native = write_json(d.root / "rp_native.json", fx.resume_parse(resume, name="陈家明"))
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf_native), "--resume-facts", str(native), data=d, json_out=True, expect=None)
        c.check(any(x["field"] == "name" and x["level"] == "pass" for x in rep["resumes"][0]["findings"]),
                "native-script resume name matching identity.name.native must pass")
        # known_mismatches accepted -> no longer blocks
        prof2 = json.loads(json.dumps(prof))
        prof2["materials"]["resumes"][0]["known_mismatches"] = ["email"]
        pf2 = write_json(d.root / "profile2.json", prof2)
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf2), "--resume-facts", str(bad_email), "-o", str(d.root / "r2.json"), data=d, json_out=True, expect=0)
        c.check(rep["overall"] == "pass" and (d.root / "r2.json").is_file(), "known_mismatches should downgrade to info")
        # list form of resume_parse with two resumes -> worst wins
        both = write_json(d.root / "rp_both.json", [fx.resume_parse(resume), fx.resume_parse(d.root / "zh.pdf", email="x@other.example")])
        _c, _o, _e, rep = run_cli("profile", "consistency", str(pf), "--resume-facts", str(both), data=d, json_out=True, expect=1)
        c.check(len(rep["resumes"]) == 2 and rep["overall"] == "block", "multi-resume aggregation")
        run_cli("profile", "consistency", str(pf), "--resume-facts", str(d.root / "missing.json"), data=d, expect=2)
    return c.done("R3 gate blocks on e-mail/phone/graduation-year, warns on month/name order, honours known_mismatches, masks values")


if __name__ == "__main__":
    sys.exit(main())

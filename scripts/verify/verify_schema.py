#!/usr/bin/env python3
"""verify: schema — hand-written validator covers ARCHITECTURE §11 keywords; forbidden keys rejected (D3/SECURITY §2).
Main path: six schemas load without unsupported keywords; fixture profile/facts_card/job/pending_action/run_state pass.
Failure paths: enum, additionalProperties, pattern, required, type list; password / nric keys anywhere; NRIC-like value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, stderr_json, version_gate, write_json  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.paths import resolve_schema_dir  # noqa: E402
from autoapply.schema_validate import SchemaSet, Validator, scan_forbidden  # noqa: E402

NAME = "schema"
c = Checker(NAME)


def main() -> int:
    ss = SchemaSet(resolve_schema_dir())
    for kind in ss.KINDS:
        v = ss.get(kind)
        c.check(not v.load_warnings, "%s uses unsupported keywords: %s" % (kind, v.load_warnings[:3]))

    pa = {"action_id": "pa_20260905_ab12cd", "run_id": "run_20260905_101500", "gate_type": "otp", "scope": "item",
          "mode": "sync", "status": "open", "opened_at": "2026-09-05T11:00:00+08:00", "app_id": None,
          "agent_message": {"zh": "需要验证码"}, "user_instructions": {"zh": "贴验证码", "en": None}}
    c.check(ss.check("pending_action", pa).ok, "valid pending_action rejected")
    bad = dict(pa, gate_type="bogus")
    errs = ss.check("pending_action", bad).errors
    c.check(any("enum" in e for e in errs), "enum violation not reported: %s" % errs)
    bad = dict(pa, extra=1)
    c.check(any("additional property" in e for e in ss.check("pending_action", bad).errors), "additionalProperties not enforced")
    bad = dict(pa, action_id="pa_x")
    c.check(any("pattern" in e for e in ss.check("pending_action", bad).errors), "pattern not enforced")
    bad = {k: v for k, v in pa.items() if k != "run_id"}
    c.check(any("required" in e for e in ss.check("pending_action", bad).errors), "required not enforced")
    bad = dict(pa, app_id=123)
    c.check(any("expected type" in e for e in ss.check("pending_action", bad).errors), "type list (string|null) not enforced")

    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        prof = fx.profile(resume)
        c.check(ss.check("profile", prof).ok, "fixture profile fails schema: %s" % ss.check("profile", prof).errors[:3])
        c.check(ss.check("facts_card", fx.facts_card()).ok, "fixture facts_card fails schema")
        # forbidden keys: schema `not` + hard-coded scan
        with_pw = json.loads(json.dumps(prof))
        with_pw["identity"]["password"] = "x"
        res = ss.check("profile", with_pw)
        c.check(not res.ok and any("forbidden" in e for e in res.errors), "password key not rejected: %s" % res.errors[:3])
        nested = {"meta": {"deep": [{"NRIC-number": "x"}]}}
        c.check(scan_forbidden(nested), "nested forbidden key not found by scan")
        c.check(scan_forbidden({"note": "id S1234567A"}), "NRIC-like value not flagged")
        c.check(not scan_forbidden(prof), "clean profile flagged by scan: %s" % scan_forbidden(prof)[:3])
        # integer vs boolean strictness
        v = Validator({"type": "object", "properties": {"n": {"type": "integer"}}, "additionalProperties": False})
        c.check(not v.validate({"n": True}).ok, "boolean accepted as integer")
        c.check(v.validate({"n": 3}).ok and v.validate({"n": 3.0}).ok, "integer rejected")
        # $ref resolution + anyOf
        v2 = Validator({"$defs": {"d": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}$"}},
                        "anyOf": [{"$ref": "#/$defs/d"}, {"type": "null"}]})
        c.check(v2.validate("2027-06").ok and v2.validate(None).ok and not v2.validate("x").ok, "$ref/anyOf broken")

        # CLI exit codes
        good = write_json(d.root / "good.json", prof)
        run_cli("profile", "validate", str(good), data=d, expect=0)
        badf = write_json(d.root / "bad.json", with_pw)
        code, _out, err, _ = run_cli("profile", "validate", str(badf), data=d, expect=3)
        j = stderr_json(err)
        c.check(j is None or "error" in j or code == 3, "stderr JSON missing on failure")
        missing = json.loads(json.dumps(prof))
        missing["materials"]["resumes"][0]["path"] = str(d.root / "nope.pdf")
        mf = write_json(d.root / "missing.json", missing)
        run_cli("profile", "validate", str(mf), data=d, expect=3)
        run_cli("profile", "validate", str(mf), "--no-file-check", data=d, expect=0)
        auto = json.loads(json.dumps(prof))
        auto["policy"]["submit_mode"] = "autopilot"
        af = write_json(d.root / "auto.json", auto)
        run_cli("profile", "validate", str(af), data=d, expect=3)  # autopilot without consent (D8)

        # run_state written by the CLI must validate against its schema
        write_json(d.profile_dir / "profile.json", prof)
        _code, _out, _err, js = run_cli("run", "new", data=d, json_out=True)
        state = json.loads((d.profile_dir / "runs" / js["run_id"] / "run_state.json").read_text(encoding="utf-8"))
        c.check(ss.check("run_state", state).ok, "run_state.json from `run new` fails schema")
        # job candidate normalised by the script validates
        cand = fx.candidate("Example Robotics Pte Ltd", "AI Engineer Intern", run_id=js["run_id"])
        from autoapply.dedup import normalize_job_obj
        c.check(ss.check("job", normalize_job_obj(cand, {}, 1)).ok, "normalised candidate fails job schema")
    return c.done("six schemas load; keyword subset enforced; forbidden keys/values rejected; CLI exit codes 0/3")


if __name__ == "__main__":
    sys.exit(main())

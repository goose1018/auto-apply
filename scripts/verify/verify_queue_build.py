#!/usr/bin/env python3
"""verify: queue_build — hard-rule screening (BRIEF §3 必跳过, R8, D13) and D7 approval gating.
Main path: each hard rule yields its skip_reason_code; approved candidates become queued applications.
Failure paths: unapproved candidates never enter apply_queue; per_company_max / per_round caps; already applied
-> dedup_hit; suspected duplicate -> review; missing profile -> exit 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "queue_build"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        # profile missing -> exit 3
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        cf0 = write_jsonl(d.root / "c0.jsonl", [fx.candidate("Any Co", "Intern", run_id=run_id)])
        run_cli("queue", "build", run_id, "--from", str(cf0), data=d, expect=3)
        write_json(d.profile_dir / "profile.json", fx.profile(resume, per_company_max=2, per_round=4))
        for st in ("source", "screen"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)
        cands = [
            fx.candidate("Blocked Corp", "Data Intern", run_id=run_id),
            fx.candidate("Referral Labs", "Data Intern", run_id=run_id),
            fx.candidate("A Co", "Sales Executive Intern", run_id=run_id),
            fx.candidate("A Co", "Enterprise Sales Intern", run_id=run_id),
            fx.candidate("A Co", "Closed Intern", run_id=run_id, closes_at="2026-01-01"),
            fx.candidate("A Co", "ID Intern", run_id=run_id, hard={"requires_local_id": True}),
            fx.candidate("Referral Labs", "Quota Intern", run_id=run_id, hard={"global_quota": True}),
            fx.candidate("A Co", "Unpaid Intern", run_id=run_id, hard={"salary": {"unpaid": True}}),
            fx.candidate("A Co", "Cheap Intern", run_id=run_id, hard={"salary": {"disclosed": True, "max": 1000, "currency": "SGD", "period": "month"}}),
            # NB: titles must not collapse to the same dedup key ("PhD Intern" and "Summer Intern" both normalise
            # to "intern" per ARCHITECTURE §6.3 edge stripping; the last line per job_id would win, §5.4)
            fx.candidate("A Co", "PhD Research Intern", run_id=run_id, hard={"degree_required": "phd"}),
            fx.candidate("A Co", "Bachelor Intern", run_id=run_id, hard={"bachelor_only": True}),
            fx.candidate("A Co", "Citizen Intern", run_id=run_id, hard={"work_pass_requirement": "citizen_only"}),
            fx.candidate("A Co", "Chinese Resume Intern", run_id=run_id, hard={"resume_language_required": "zh"}),
            fx.candidate("A Co", "Late Window Intern", run_id=run_id, hard={"work_window": {"start": "2027-08", "end": "2027-12"}}),
            fx.candidate("A Co", "Immediate Intern", run_id=run_id, hard={"start_immediately": True}),
            fx.candidate("B Co", "Good Intern", run_id=run_id),
            fx.candidate("B Co", "Approved Intern", run_id=run_id, screening={"decision": "approved"}),
        ]
        cf = write_jsonl(d.root / "c.jsonl", cands)
        _c, _o, _e, q = run_cli("queue", "build", run_id, "--from", str(cf), data=d, json_out=True)
        codes = {s["title"]: s["reason_code"] for s in q["skipped"]}
        expected = {
            "Sales Executive Intern": "title_excluded", "Enterprise Sales Intern": "title_excluded",
            "Closed Intern": "job_closed", "ID Intern": "id_number_required", "Quota Intern": "reserve_for_referral",
            "Unpaid Intern": "unpaid", "Cheap Intern": "salary_below_floor", "PhD Research Intern": "degree_mismatch",
            "Bachelor Intern": "degree_mismatch", "Citizen Intern": "work_pass_mismatch", "Chinese Resume Intern": "resume_language_missing",
            "Late Window Intern": "date_window_mismatch", "Immediate Intern": "start_immediately",
        }
        for title, code in expected.items():
            c.check(codes.get(title) == code, "%s: expected %s got %s" % (title, code, codes.get(title)))
        blocked = [s for s in q["skipped"] if s["company"] == "Blocked Corp"]
        referral = [s for s in q["skipped"] if s["company"] == "Referral Labs" and s["title"] == "Data Intern"]
        c.check(blocked and blocked[0]["reason_code"] == "blacklist", "blacklist")
        c.check(referral and referral[0]["reason_code"] == "reserve_for_referral", "reserve_for_referral")
        c.check(q["counts"]["queued"] == 1 and q["queued"][0]["title"] == "Approved Intern", "only pre-approved candidate queued: %s" % q["counts"])
        c.check([s["title"] for s in q["pending_approval"]] == ["Good Intern"], "Good Intern must wait for approval (D7)")
        queue_file = d.profile_dir / "runs" / run_id / "apply_queue.jsonl"
        rows = [json.loads(l) for l in queue_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        c.check(len(rows) == 1 and rows[0]["approval"]["approved_by_user"] is True and rows[0]["status"] == "queued", "apply_queue line")
        screened = d.profile_dir / "runs" / run_id / "screened.jsonl"
        c.check(screened.is_file() and len(screened.read_text(encoding="utf-8").splitlines()) == len(cands), "screened.jsonl must have one line per candidate")
        # approve all: Good Intern joins; Approved Intern already queued (no duplicate application)
        _c, _o, _e, q2 = run_cli("queue", "build", run_id, "--from", str(cf), "--approve-all", "全部批准", data=d, json_out=True)
        c.check(q2["counts"]["queued"] == 2 and q2["counts"]["pending_approval"] == 0, "approve-all counts: %s" % q2["counts"])
        _c, _o, _e, st = run_cli("ledger", "stats", data=d, json_out=True)
        c.check(st["by_status"].get("queued") == 2, "queued applications should be 2, got %s" % st["by_status"])
        # exclude
        good_id = [s["job_id"] for s in q["pending_approval"]][0]
        _c, _o, _e, q3 = run_cli("queue", "build", run_id, "--from", str(cf), "--approve-all", "批准", "--exclude", good_id, data=d, json_out=True)
        c.check(any(s["job_id"] == good_id and s["reason_code"] == "user_excluded" for s in q3["skipped"]), "exclude must mark user_excluded")
        # per_company_max (=2): B Co has 2 queued already -> third B Co candidate is quota_reached
        _c, _o, _e, r2 = run_cli("run", "new", data=d, json_out=True)
        run2 = r2["run_id"]
        for st_ in ("source", "screen"):
            run_cli("run", "checkpoint", run2, "--state", st_, data=d)
        # make the two B Co applications applied so the cap counts them
        run_cli("run", "checkpoint", run_id, "--state", "apply", data=d)
        shot = d.root / "ok.txt"
        shot.write_text("submitted", encoding="utf-8")
        for row in [json.loads(l) for l in queue_file.read_text(encoding="utf-8").splitlines() if l.strip()][:2]:
            _c, _o, _e, a = run_cli("app", "start", run_id, row["job_id"], "--channel", "company_site", data=d, json_out=True)
            run_cli("app", "evidence", a["app_id"], "--type", "success_page", "--url", "https://x", "--screenshot", str(shot),
                    "--job-title-seen", "Intern", "--mark-applied", data=d)
        cf2 = write_jsonl(d.root / "c2.jsonl", [
            fx.candidate("B Co", "Third Intern", run_id=run2), fx.candidate("B Co", "Approved Intern", run_id=run2),
            fx.candidate("B Co", "Approved Internship 2027", run_id=run2), fx.candidate("C Co", "X1", run_id=run2),
            fx.candidate("C Co", "X2", run_id=run2), fx.candidate("C Co", "X3", run_id=run2), fx.candidate("D Co", "X4", run_id=run2),
            fx.candidate("D Co", "X5", run_id=run2), fx.candidate("E Co", "X6", run_id=run2),
        ])
        _c, _o, _e, q4 = run_cli("queue", "build", run2, "--from", str(cf2), "--approve-all", "批准", data=d, json_out=True)
        by_title = {s["title"]: s for s in q4["skipped"]}
        c.check(by_title.get("Third Intern", {}).get("reason_code") == "quota_reached", "per_company_max not enforced: %s" % by_title.get("Third Intern"))
        # "Approved Intern" and "Approved Internship 2027" share one dedup key: the last line wins (§5.4) and is a dedup_hit
        c.check(by_title.get("Approved Internship 2027", {}).get("reason_code") == "already_applied" and by_title["Approved Internship 2027"]["decision"] == "dedup_hit",
                "normalised duplicate of an applied job must be dedup_hit: %s" % by_title.get("Approved Internship 2027"))
        c.check("Approved Intern" not in by_title and not any(x["title"] == "Approved Intern" for x in q4["queued"]), "collapsed duplicate line must not be screened twice")
        c.check(q4["counts"]["queued"] == 4, "per_round=4 cap: queued %s" % q4["counts"])
        # dedup_review: same company + similar title applied, not pre-approved -> review list
        # (raise per_company_max above the 2 already-applied B Co jobs first: the company cap is
        # checked before the similarity review; schema caps per_company_max at 3, so use the max)
        write_json(d.profile_dir / "profile.json", fx.profile(resume, per_company_max=3, per_round=4))
        _c, _o, _e, r3 = run_cli("run", "new", data=d, json_out=True)
        run3 = r3["run_id"]
        for st_ in ("source", "screen"):
            run_cli("run", "checkpoint", run3, "--state", st_, data=d)
        cf3 = write_jsonl(d.root / "c3.jsonl", [fx.candidate("B Co", "Approved", run_id=run3)])
        _c, _o, _e, q5 = run_cli("queue", "build", run3, "--from", str(cf3), data=d, json_out=True)
        c.check(q5["counts"]["review"] == 1, "suspected duplicate should go to review: %s" % q5["counts"])
        # global_quota with mode skip_all_global_quota (reserve-list companies are caught earlier by reserve_for_referral)
        prof = fx.profile(resume)
        prof["rules"]["global_quota_rule"] = {"mode": "skip_all_global_quota", "notes": None}
        write_json(d.profile_dir / "profile.json", prof)
        _c, _o, _e, r4 = run_cli("run", "new", data=d, json_out=True)
        run4 = r4["run_id"]
        for st_ in ("source", "screen"):
            run_cli("run", "checkpoint", run4, "--state", st_, data=d)
        cf4 = write_jsonl(d.root / "c4.jsonl", [fx.candidate("G Co", "Global Quota Intern", run_id=run4, hard={"global_quota": True})])
        _c, _o, _e, q6 = run_cli("queue", "build", run4, "--from", str(cf4), data=d, json_out=True)
        c.check(q6["skipped"] and q6["skipped"][0]["reason_code"] == "global_quota", "skip_all_global_quota: %s" % q6["skipped"])
    return c.done("14 hard rules produce the right skip_reason_code; D7 gating; caps; dedup_hit/review")


if __name__ == "__main__":
    sys.exit(main())

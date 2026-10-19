#!/usr/bin/env python3
"""verify: quota — today's/this-round/per-company/per-platform throttling status (D13/R6, feeds
SKILL.md's pre-`app start` checks). Main path: applied counts and profile caps (incl. a
`rules.company_caps` override) line up; a platform marked blocked in run_state.quotas shows as
`over`; today's submission actions past `per_day` shows `over`; `--run` defaults to the latest open
run. Read-only: the ledger fingerprint must not change.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.ledger import ledger_fingerprint  # noqa: E402

NAME = "quota"
c = Checker(NAME)


def _mark_applied(d: TempData, run_id: str, job_id: str, channel: str = "company_site") -> None:
    shot = d.root / ("ok_%s.txt" % job_id[-6:])
    if not shot.is_file():
        shot.write_text("submitted", encoding="utf-8")
    _c, _o, _e, a = run_cli("app", "start", run_id, job_id, "--channel", channel, data=d, json_out=True)
    run_cli("app", "evidence", a["app_id"], "--type", "success_page", "--url", "https://x", "--screenshot", str(shot),
           "--job-title-seen", "Intern", "--mark-applied", data=d)
    return a["app_id"]


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        profile = fx.profile(resume, per_day=5, per_company_max=2)
        profile["rules"]["company_caps"] = [{"company": "P Co", "max_applications": 1}]
        write_json(d.profile_dir / "profile.json", profile)

        _c, _o, _e, r = run_cli("run", "new", data=d, json_out=True)
        run_id = r["run_id"]
        for st in ("source", "screen", "apply"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)

        cf = write_jsonl(d.root / "c.jsonl", [
            fx.candidate("P Co", "P Intern", run_id=run_id, platform="greenhouse"),
            fx.candidate("Q Co", "Q Intern 1", run_id=run_id, platform="linkedin_easy_apply"),
            fx.candidate("Q Co", "Q Intern 2", run_id=run_id, platform="linkedin_easy_apply"),
        ])
        _c, _o, _e, jrep = run_cli("jobs", "add", str(cf), data=d, json_out=True)
        by_title = {e["title"]: e for e in jrep["added"]}

        _mark_applied(d, run_id, by_title["P Intern"]["job_id"])
        _mark_applied(d, run_id, by_title["Q Intern 1"]["job_id"])
        _mark_applied(d, run_id, by_title["Q Intern 2"]["job_id"])

        # mark a platform as blocked this run, directly in run_state.json (no CLI writes this yet)
        state_path = d.profile_dir / "runs" / run_id / "run_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["quotas"]["platform_blocked"] = ["linkedin_easy_apply"]
        state["quotas"]["linkedin_daily_remaining"] = 0
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        db = d.profile_dir / "ledger.sqlite"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        before = ledger_fingerprint(conn)
        conn.close()

        # no --run given -> auto-picks the one open run
        code, human, _e, q = run_cli("quota", data=d, json_out=True, expect=None)
        c.check(code == 0 and q["run_id"] == run_id, "quota without --run should default to the latest open run: %s" % q.get("run_id"))
        c.check(q["today"]["submission_actions"] == 3 and q["today"]["per_day_limit"] == 5 and q["today"]["over"] is False,
                "today's submission actions/limit: %s" % q["today"])
        c.check(q["this_round"]["unique_applied"] == 3, "this round's unique applied: %s" % q["this_round"])
        by_company = {x["company"]: x for x in q["by_company"]}
        c.check(by_company["p"]["cap"] == 1 and by_company["p"]["over"] is True, "company_caps override must win over per_company_max: %s" % by_company.get("p"))
        c.check(by_company["q"]["cap"] == 2 and by_company["q"]["applied"] == 2 and by_company["q"]["over"] is True, "per_company_max default + at-cap flag: %s" % by_company.get("q"))
        by_platform = {x["platform"]: x for x in q["by_platform"]}
        c.check(by_platform["linkedin_easy_apply"]["blocked_this_run"] is True and by_platform["linkedin_easy_apply"]["over"] is True,
                "platform_blocked in run_state.quotas must surface as over: %s" % by_platform.get("linkedin_easy_apply"))
        c.check(by_platform["linkedin_easy_apply"].get("linkedin_daily_remaining") == 0, "linkedin_daily_remaining passthrough: %s" % by_platform.get("linkedin_easy_apply"))
        c.check("greenhouse" in by_platform and by_platform["greenhouse"]["blocked_this_run"] is False, "unblocked platform must not be flagged: %s" % by_platform.get("greenhouse"))
        # 人类可读输出必须单独跑一次（--json 时 stdout 是 JSON，不含表格）
        _hc, human_txt, _he, _hj = run_cli("quota", data=d, expect=None)
        c.check("quota" in human_txt and "OVER" in human_txt, "human-readable output should mark over-cap items: %r" % human_txt[:200])

        # explicit --run must match
        _c, _o, _e, q2 = run_cli("quota", "--run", run_id, data=d, json_out=True)
        c.check(q2["run_id"] == run_id and q2["this_round"] == q["this_round"], "explicit --run should match the auto-picked run")

        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        c.check(ledger_fingerprint(conn) == before, "quota must never write to the ledger")
        conn.close()

        # per_day exhausted -> today.over must flip
        profile2 = fx.profile(resume, per_day=2, per_company_max=2)
        write_json(d.profile_dir / "profile.json", profile2)
        _c, _o, _e, q3 = run_cli("quota", data=d, json_out=True)
        c.check(q3["today"]["over"] is True, "3 submission actions past a per_day of 2 must be over: %s" % q3["today"])
    return c.done("today/this-round/per-company (incl. company_caps override)/per-platform (incl. run_state.quotas.platform_blocked) throttling status; read-only")


if __name__ == "__main__":
    sys.exit(main())

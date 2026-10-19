#!/usr/bin/env python3
"""verify: report — three-column report reads only the ledger (BRIEF §3 汇报只引用台账; D16 口径).
Main path: applied / pending / stuck sections populated; numbers equal `ledger stats --run`; markdown written with -o.
Failure path: report must not modify the ledger (fingerprint unchanged); unknown run exits 2.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.ledger import ledger_fingerprint  # noqa: E402

NAME = "report"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        for st in ("source", "screen"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)
        cf = write_jsonl(d.root / "c.jsonl", [
            fx.candidate("P Co", "Applied Intern", run_id=run_id, screening={"decision": "approved"}),
            fx.candidate("Q Co", "Pending Intern", run_id=run_id, screening={"decision": "approved"}),
            fx.candidate("R Co", "Skipped Intern", run_id=run_id, screening={"decision": "approved"}),
            fx.candidate("Blocked Corp", "Rule Intern", run_id=run_id, screening={"decision": "approved"}),
        ])
        _c, _o, _e, q = run_cli("queue", "build", run_id, "--from", str(cf), data=d, json_out=True)
        run_cli("run", "checkpoint", run_id, "--state", "apply", data=d)
        by_title = {x["title"]: x for x in q["queued"]}
        shot = d.root / "ok.txt"
        shot.write_text("submitted", encoding="utf-8")
        _c, _o, _e, a = run_cli("app", "start", run_id, by_title["Applied Intern"]["job_id"], "--channel", "company_site", data=d, json_out=True)
        run_cli("app", "evidence", a["app_id"], "--type", "success_page", "--url", "https://x", "--screenshot", str(shot),
                "--job-title-seen", "Applied Intern", "--mark-applied", data=d)
        _c, _o, _e, b = run_cli("app", "start", run_id, by_title["Pending Intern"]["job_id"], "--channel", "company_site", data=d, json_out=True)
        run_cli("app", "gate", b["app_id"], "--type", "otp", "--message", "需要验证码", data=d)
        _c, _o, _e, s = run_cli("app", "start", run_id, by_title["Skipped Intern"]["job_id"], "--channel", "company_site", data=d, json_out=True)
        run_cli("app", "status", s["app_id"], "skipped", "--reason", "unknown_required_field", data=d)
        db = d.profile_dir / "ledger.sqlite"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        before = ledger_fingerprint(conn)
        conn.close()
        out_md = d.root / "report.md"
        _c, human, _e, rep = run_cli("report", run_id, "-o", str(out_md), data=d, json_out=True)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        c.check(ledger_fingerprint(conn) == before, "report modified the ledger")
        conn.close()
        c.check(len(rep["applied"]) == 1 and rep["applied"][0]["company"] == "P Co", "applied column")
        c.check(len(rep["pending"]) == 1 and rep["pending"][0]["gate_type"] == "otp", "pending column")
        stuck = {s["company"]: s for s in rep["stuck"]}
        c.check("R Co" in stuck and stuck["R Co"]["skip_reason_code"] == "unknown_required_field", "stuck column skipped reason")
        c.check("Q Co" in stuck and stuck["Q Co"]["gate_type"] == "otp", "stuck column shows pending item gate")
        c.check("Blocked Corp" not in stuck, "screen-time skips (no application) belong to screened.jsonl, not the report")
        _c, _o, _e, st = run_cli("ledger", "stats", "--run", run_id, data=d, json_out=True)
        c.check(rep["run"]["unique_jobs_applied"] == st["unique_jobs_applied"] == 1 and rep["run"]["submission_actions"] == st["submission_actions"], "numbers differ from ledger stats")
        md = out_md.read_text(encoding="utf-8")
        for needle in ("# 投递汇报 / Report — %s" % run_id, "本轮去重 1 岗 / 提交 1 次（其中重复 0）", "## 1. 已确认投递", "## 2. 待用户动作", "## 3. 卡壳原因", "| P Co | Applied Intern |"):
            c.check(needle in md, "report.md missing %r" % needle)
        _c, human, _e, _ = run_cli("report", run_id, data=d)
        c.check(human.startswith("# 投递汇报"), "human output should be the markdown")
        run_cli("report", "run_20260101_000000", data=d, expect=2)
    return c.done("three columns match ledger; read-only; markdown format")


if __name__ == "__main__":
    sys.exit(main())

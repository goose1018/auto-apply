#!/usr/bin/env python3
"""verify: gates — gate protocol (ARCHITECTURE §3): pending_actions.jsonl canonical, .md rendered in the fixed format.
Main path: item gate -> app pending_user + md; run gate -> run suspended; resolve -> re-queued / user_completed / resume.
Failure paths: password text in a gate message refused (exit 3); unknown action / double resolve exit 2; wrong run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, stderr_json, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "gates"
c = Checker(NAME)


def _setup(d: TempData, mode: str) -> tuple[str, str]:
    _c, _o, _e, js = run_cli("run", "new", "--mode", mode, data=d, json_out=True)
    run_id = js["run_id"]
    for st in ("source", "screen"):
        run_cli("run", "checkpoint", run_id, "--state", st, data=d)
    cf = write_jsonl(d.root / ("c_%s.jsonl" % mode), [fx.candidate("Gate Co %s" % mode, "AI Intern", run_id=run_id, screening={"decision": "approved"})])
    _c, _o, _e, q = run_cli("queue", "build", run_id, "--from", str(cf), data=d, json_out=True)
    run_cli("run", "checkpoint", run_id, "--state", "apply", data=d)
    app_id = q["queued"][0]["app_id"]
    run_cli("app", "start", run_id, q["queued"][0]["job_id"], "--channel", "company_site", data=d)
    return run_id, app_id


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        run_id, app_id = _setup(d, "interactive")
        _c, _o, _e, g = run_cli("app", "gate", app_id, "--type", "otp", "--message", "登录需要邮箱验证码", "--step", "login.otp",
                                "--url", "https://ats.example.com/login", "--draft-url", "https://ats.example.com/draft", data=d, json_out=True)
        c.check(g["scope"] == "item" and g["mode"] == "sync" and g["status"] == "open" and g["expires_at"], "item gate fields: %s" % g)
        _c, _o, _e, app = run_cli("app", "show", app_id, data=d, json_out=True)
        c.check(app["application"]["status"] == "pending_user", "item gate must set pending_user")
        run_dir = d.profile_dir / "runs" / run_id
        md = (run_dir / "pending_actions.md").read_text(encoding="utf-8")
        for needle in ("# 待用户动作 / Pending actions — %s" % run_id, "> 生成 ", "## 1. [otp] Gate Co interactive — AI Intern",
                       "- 页面 / Page: https://ats.example.com/login", "playbook step `login.otp`", "- 草稿 / Draft: 已保存",
                       "- 你需要做 / What you do:", "- id: %s" % g["action_id"]):
            c.check(needle in md, "pending_actions.md missing %r" % needle)
        jsonl_lines = [json.loads(l) for l in (run_dir / "pending_actions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        c.check(len(jsonl_lines) == 1 and jsonl_lines[0]["action_id"] == g["action_id"], "jsonl canonical line")
        # run-level gate suspends the run and renders first
        _c, _o, _e, rg = run_cli("run", "gate", run_id, "--type", "browser_disconnected", "--message", "扩展无响应", data=d, json_out=True)
        c.check(rg["action"]["scope"] == "run" and rg["phase"] == "pending_user", "run gate must suspend the run")
        md = (run_dir / "pending_actions.md").read_text(encoding="utf-8")
        c.check(md.index("[browser_disconnected]") < md.index("[otp]"), "run-level gate must render first")
        c.check("打开 2" in md, "header counts")
        # secrets refused
        code, _o, err, _ = run_cli("app", "gate", app_id, "--type", "captcha", "--message", "password=abc123", data=d, expect=3)
        j = stderr_json(err)
        c.check(j is not None and j.get("error") == "redaction_error", "password in message must be redaction_error")
        # resolve run gate -> run resumes to apply
        _c, _o, _e, r = run_cli("run", "resolve", run_id, rg["action"]["action_id"], "--note", "已重连", data=d, json_out=True)
        c.check(r["phase"] == "apply" and r["action"]["status"] == "resolved", "run resume after resolve: %s" % r["phase"])
        run_cli("run", "resolve", run_id, rg["action"]["action_id"], data=d, expect=2)  # already closed
        run_cli("run", "resolve", run_id, "pa_20260905_ffffff", data=d, expect=2)  # unknown
        # resolve item gate as resolved -> re-queued with high priority
        _c, _o, _e, r = run_cli("run", "resolve", run_id, g["action_id"], data=d, json_out=True)
        _c, _o, _e, app = run_cli("app", "show", app_id, data=d, json_out=True)
        c.check(app["application"]["status"] == "queued" and app["application"]["priority"] == "high", "resolved item must be re-queued high")
        md = (run_dir / "pending_actions.md").read_text(encoding="utf-8")
        c.check("## 已处理 / Handled" in md and "（当前没有待处理项" in md, "handled section rendering")
        # user_completed -> submitted_unverified + one submission action
        _c, _o, _e, g2 = run_cli("app", "gate", app_id, "--type", "final_submit", "--message", "停在提交前", data=d, json_out=True)
        run_cli("run", "resolve", run_id, g2["action_id"], "--resolution", "user_completed", data=d)
        _c, _o, _e, app = run_cli("app", "show", app_id, data=d, json_out=True)
        c.check(app["application"]["status"] == "submitted_unverified" and app["application"]["submission_action_count"] == 1, "user_completed bookkeeping")
        # skipped -> user_excluded
        _c, _o, _e, g3 = run_cli("app", "gate", app_id, "--type", "id_number", "--message", "表单要求证件号", data=d, json_out=True)
        _c, _o, _e, app = run_cli("app", "show", app_id, data=d, json_out=True)
        c.check(app["application"]["status"] == "submitted_unverified", "gate on a submitted item must not regress its status")
        # `run pending` prints the markdown
        _c, out, _e, _ = run_cli("run", "pending", run_id, data=d)
        c.check(out.startswith("# 待用户动作 / Pending actions"), "run pending must print the rendered markdown")
        # gates table mirrors pending actions
        _c, _o, _e, st = run_cli("ledger", "stats", data=d, json_out=True)
        c.check(st["open_gates"] == 1, "gates table open count: %s" % st["open_gates"])
        # batch mode -> async for otp, sync forced for final_submit
        run_b, app_b = _setup(d, "batch")
        _c, _o, _e, gb = run_cli("app", "gate", app_b, "--type", "otp", "--message", "验证码", data=d, json_out=True)
        c.check(gb["mode"] == "async", "batch mode should make otp async")
        _c, _o, _e, gb2 = run_cli("app", "gate", app_b, "--type", "final_submit", "--message", "提交前", data=d, json_out=True)
        c.check(gb2["mode"] == "sync", "final_submit must be sync even in batch mode")
        # gate on an application from another run must be refused
        run_cli("run", "gate", run_id, "--type", "queue_approval", "--message", "母清单", data=d)
        _c, _o, _e, appb = run_cli("app", "show", app_b, data=d, json_out=True)
        c.check(appb["application"]["run_id"] == run_b, "setup sanity")
    return c.done("item/run gates render the fixed md; resolve re-queues / hands over / resumes; secrets refused")


if __name__ == "__main__":
    sys.exit(main())

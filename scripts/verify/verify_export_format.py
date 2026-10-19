#!/usr/bin/env python3
"""verify: export_format — exports/投递台账.md keeps the legacy four-section layout (BRIEF D11, ARCHITECTURE §5.6).
Main path: four headings in order; section 1 groups by company with per_company_max marker; section 4 table;
export is idempotent (body identical across two exports); imported legacy entries all appear in section 1.
Failure path: section 3 contains no e-mail / phone even though profile.json has them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json, write_jsonl  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.export_md import export_body  # noqa: E402
from autoapply.migrate_legacy import parse_legacy_markdown  # noqa: E402
from autoapply.normalize import normalize_title  # noqa: E402

NAME = "export_format"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume, per_company_max=3))
        legacy = d.root / "legacy.md"
        legacy.write_text(fx.LEGACY_MD, encoding="utf-8")
        run_cli("ledger", "migrate-legacy", str(legacy), data=d)
        # one fresh application with a gate, so section 2 and 4 have live rows
        _c, _o, _e, js = run_cli("run", "new", data=d, json_out=True)
        run_id = js["run_id"]
        for st in ("source", "screen"):
            run_cli("run", "checkpoint", run_id, "--state", st, data=d)
        cf = write_jsonl(d.root / "c.jsonl", [fx.candidate("Fresh Co", "Data Intern", run_id=run_id, screening={"decision": "approved"})])
        _c, _o, _e, q = run_cli("queue", "build", run_id, "--from", str(cf), data=d, json_out=True)
        run_cli("run", "checkpoint", run_id, "--state", "apply", data=d)
        _c, _o, _e, a = run_cli("app", "start", run_id, q["queued"][0]["job_id"], "--channel", "company_site", data=d, json_out=True)
        run_cli("app", "gate", a["app_id"], "--type", "captcha", "--message", "出现验证码", data=d)

        out1 = d.root / "export1.md"
        run_cli("ledger", "export", "-o", str(out1), data=d)
        text = out1.read_text(encoding="utf-8")
        heads = ["## 一、已确认投递（禁止重复）", "## 二、未投但有中间状态（重投前需先查状态）", "## 三、既定投递规则", "## 四、状态追踪表（新投递与状态变化只在这里追加）"]
        pos = [text.find(h) for h in heads]
        c.check(all(p >= 0 for p in pos) and pos == sorted(pos), "four section headings missing or out of order: %s" % pos)
        c.check(text.splitlines()[0] == "# 求职投递台账（防重复主清单）", "title line")
        c.check("> 由 auto-apply 导出于 " in text, "export header line")
        sec1 = text[pos[0]:pos[1]]
        sec2 = text[pos[1]:pos[2]]
        sec3 = text[pos[2]:pos[3]]
        sec4 = text[pos[3]:]
        parse = parse_legacy_markdown(fx.LEGACY_MD)
        # every "title（channel，evidence）" segment in section 1, normalised (one job may carry several raw titles)
        sec1_titles = {normalize_title(t) for t in re.findall(r"(?:— |；)([^；（\n]+?)（[^（）]*，[^（）]*）", sec1)}
        for e in parse.confirmed:
            c.check(("- %s — " % e.company) in sec1, "legacy confirmed company %r missing from section 1" % e.company)
            if e.title:
                c.check(e.title in sec1 or normalize_title(e.title) in sec1_titles, "legacy title %r missing from section 1" % e.title)
        c.check(re.search(r"^- Sample Systems — .+ —— \*\*已投 5 份，不再新投\*\*$", sec1, re.M), "per-company cap marker missing for Sample Systems")
        c.check(re.search(r"^- Omega Retail — .+（.+，旧台账）；.+（.+，旧台账）$", sec1, re.M), "multi-title company line format")
        c.check("Fresh Co — Data Intern：待用户动作（关口 captcha：出现验证码）" in sec2, "section 2 line format: %s" % sec2)
        c.check("Mu Fintech" in sec2 and "id_number_required" in sec2, "legacy intermediate entries in section 2")
        c.check("@" not in sec3 and "+65" not in sec3 and "0000 1234" not in sec3 and "Alex" not in sec3, "section 3 leaks contact data")
        c.check("硬下限 SGD1500" in sec3 and "黑名单：Blocked Corp" in sec3 and "同公司 ≤3" in sec3, "section 3 rule rendering")
        c.check("| 日期 | 公司 | 岗位 | 渠道 | 状态 | 证据/备注 |" in sec4 and "|---|---|---|---|---|---|" in sec4, "section 4 table header")
        c.check("| 关口 captcha |" in sec4 and "| 已投 |" in sec4, "section 4 rows")
        c.check("@" not in text, "export must not contain any e-mail address")
        out2 = d.root / "export2.md"
        run_cli("ledger", "export", "-o", str(out2), data=d)
        c.check(export_body(text) == export_body(out2.read_text(encoding="utf-8")), "export is not idempotent")
        # default output path
        _c, _o, _e, r = run_cli("ledger", "export", data=d, json_out=True)
        c.check(r["written_to"].endswith("exports/投递台账.md"), "default export path: %s" % r["written_to"])
    return c.done("four sections in order; legacy entries all in section 1; cap marker; no contact data; idempotent")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify: facts_render — facts_card.json (canonical) -> facts_card.md (D9/R9 fact source for the Content Agent).
Main path: rendered md lists every fact with id / status, forbidden claims, sign-off block.
Failure paths: invalid card (bad fact_id / extra key) exits 3; unsigned card renders "未签字".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "facts_render"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        card = fx.facts_card()
        cf = write_json(d.root / "facts_card.json", card)
        out = d.root / "facts_card.md"
        run_cli("facts", "render", str(cf), "-o", str(out), data=d)
        md = out.read_text(encoding="utf-8")
        for needle in ("# 事实红线卡 / Facts card — verify_user", "已确认 2 条", "已签字 / signed at 2026-09-01T11:00:00+08:00",
                       "| f_001 |", "| f_002 |", "| f_003 |", "已确认 / confirmed", "草稿 / draft", "## 禁止说法 / Forbidden claims",
                       "不得声称有全职工作经验", "## 签字 / Sign-off", "## 教育 / Education", "## 工作许可 / Work permit"):
            c.check(needle in md, "facts_card.md missing %r" % needle)
        c.check(md.index("## 教育 / Education") < md.index("## 经历 / Experience") < md.index("## 工作许可 / Work permit"), "category order")
        unsigned = fx.facts_card(signed=False)
        uf = write_json(d.root / "unsigned.json", unsigned)
        run_cli("facts", "render", str(uf), "-o", str(d.root / "u.md"), data=d)
        c.check("未签字 / not signed" in (d.root / "u.md").read_text(encoding="utf-8"), "unsigned rendering")
        bad = json.loads(json.dumps(card))
        bad["facts"][0]["fact_id"] = "fact-1"
        bf = write_json(d.root / "bad.json", bad)
        run_cli("facts", "render", str(bf), "-o", str(d.root / "b.md"), data=d, expect=3)
        bad2 = json.loads(json.dumps(card))
        bad2["facts"][0]["password"] = "x"
        bf2 = write_json(d.root / "bad2.json", bad2)
        run_cli("facts", "render", str(bf2), "-o", str(d.root / "b2.md"), data=d, expect=3)
        c.check(not (d.root / "b.md").exists(), "invalid card must not produce output")
    return c.done("facts_card.md rendered from JSON with ids/status/forbidden claims/sign-off; invalid cards exit 3")


if __name__ == "__main__":
    sys.exit(main())

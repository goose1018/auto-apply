#!/usr/bin/env python3
"""verify: dedup generic-title-stub guard — 防止去重误拦（R1 的反向风险）。

背景：边缘剥离会把 season/degree 类限定词去掉（EDGE_STRIP_TOKENS 含 summer / phd），
于是 "Summer Intern" 与 "PhD Intern" 在同一家公司会得到同一个 dedup_key，本质不同的岗位
被当成已投而硬拦（误拦比漏拦更危险：用户永远看不到那个岗位）。

主路径：同键但原始标题不同 + 标题只剩通用残根 -> dedup_review（交人确认，不自动跳过）。
失败路径：原始标题相同的真重复仍然是 dedup_hit；标题不是通用残根时不受影响，仍硬拦。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, version_gate  # noqa: E402

version_gate()
from autoapply import dedup, ledger  # noqa: E402
from autoapply.normalize import is_generic_title, make_dedup_key  # noqa: E402

NAME = "dedup_generic_stub"
c = Checker(NAME)


def _seed(conn, company: str, title: str, status: str = "applied"):
    k = make_dedup_key(company, title)
    ledger.upsert_job(conn, dedup.JobRecord(
        job_id=k.job_id, dedup_key=k.key, company_raw=k.company_raw, company_norm=k.company_norm,
        title_raw=k.title_raw, title_norm=k.title_norm, platform="greenhouse", source_type="user_list"))
    ledger.create_application(conn, ledger.ApplicationRecord(
        app_id="app_%012d" % (abs(hash(k.key)) % 10 ** 12), job_id=k.job_id, run_id="run_20260905_000000",
        profile_id="test", channel="company_site", platform="greenhouse", status=status))
    return k


def main() -> int:
    c.check(is_generic_title("intern") and not is_generic_title("ai intern"),
            "is_generic_title: bare stub yes, qualified title no")
    with TempData() as d:
        conn = ledger.open_ledger(d.profile_dir / "ledger.sqlite", profile_id="test")

        k_seed = _seed(conn, "Acme Tech", "Summer Intern")
        k_other = make_dedup_key("Acme Tech", "PhD Intern")
        c.check(k_seed.key == k_other.key,
                "precondition: both intern titles must still collide on the dedup key (%s vs %s)" % (k_seed.key, k_other.key))

        r_other = dedup.check_key(conn, k_other)
        c.check(r_other.decision == "dedup_review",
                "different role sharing a generic stub must be reviewed, not blocked: %s / %s" % (r_other.decision, r_other.reason))
        c.check("PhD Intern" in r_other.reason and "Summer Intern" in r_other.reason,
                "review reason must name both raw titles so the user can judge: %s" % r_other.reason)

        r_repeat = dedup.check_key(conn, make_dedup_key("Acme Tech", "summer intern"))
        c.check(r_repeat.decision == "dedup_hit",
                "a true repeat (same raw title, case-insensitive) must still be blocked: %s" % r_repeat.decision)

        # 非通用残根的标题不受影响：括号批次差异仍应硬拦
        _seed(conn, "Beta Corp", "Data Analyst Intern (Summer 2027)")
        r_variant = dedup.check_key(conn, make_dedup_key("Beta Corp", "Data Analyst Intern"))
        c.check(r_variant.decision == "dedup_hit",
                "non-stub titles keep hard dedup (batch/year variants are the same job): %s" % r_variant.decision)
    return c.done("generic title stubs downgrade an exact-key hit to dedup_review; true repeats and non-stub variants stay dedup_hit")


if __name__ == "__main__":
    sys.exit(main())

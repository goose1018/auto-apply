#!/usr/bin/env python3
"""verify: migrate_legacy — legacy four-section Markdown -> ledger (BRIEF D17; P3 DoD replay).
Main path (fixture): parse counts; import creates applied rows with legacy_import evidence; repeated mention adds a
submission action; re-import is a no-op; every confirmed entry is a dedup_hit afterwards; section 3 never imported.
Real ledger (~/Documents/Codex/投递台账.md): if present it is parsed READ-ONLY into a temp database: >=100 confirmed
entries, section 4 rows parsed, replay 100% dedup_hit, no e-mail leaks into the temp ledger. Nothing is copied.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, Checker, TempData, run_cli, version_gate, write_json  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.enums import LEGACY_UNKNOWN_TITLE  # noqa: E402
from autoapply.migrate_legacy import parse_legacy_markdown  # noqa: E402

NAME = "migrate_legacy"
c = Checker(NAME)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _replay(d: TempData, entries: list, label: str) -> tuple[int, int]:
    hits = 0
    total = 0
    misses: list[str] = []
    for e in entries:
        total += 1
        _c, _o, _e, chk = run_cli("jobs", "check", e.company, e.title or LEGACY_UNKNOWN_TITLE, data=d, json_out=True)
        if chk["decision"] == "dedup_hit":
            hits += 1
        elif len(misses) < 5:
            misses.append("%s — %s -> %s" % (e.company, e.title, chk["decision"]))
    c.check(hits == total, "%s replay: %d/%d dedup_hit; misses: %s" % (label, hits, total, misses))
    return hits, total


def _no_email_in_db(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    for table in ("jobs", "applications", "evidence", "gates", "events"):
        cols = [r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)]
        for row in conn.execute("SELECT * FROM %s" % table):
            for col, val in zip(cols, row):
                if isinstance(val, str) and EMAIL_RE.search(val):
                    conn.close()
                    c.check(False, "e-mail leaked into %s.%s" % (table, col))
    conn.close()


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        parse = parse_legacy_markdown(fx.LEGACY_MD)
        pc = parse.counts()
        c.check(pc["confirmed_mentions"] == 22, "fixture confirmed mentions: %s" % pc)
        c.check(pc["confirmed_unique_keys"] == 21, "fixture unique keys (one repeated Demo Semiconductor title): %s" % pc)
        c.check(pc["intermediate"] == 6 and pc["tracking_rows"] == 3 and pc["rules_lines_skipped"] == 2, "fixture section counts: %s" % pc)
        titles = {e.title for e in parse.confirmed}
        for t in ("AI, Automation & Database", "Data Scientist & Automation", "AI Solutions & Analytics", "GenAI SWE", "SWE (Low Code)",
                  "Quantitative Developer Intern (Python)", "AI-Powered BD Intern"):
            c.check(t in titles, "title %r not parsed" % t)
        companies = {e.company for e in parse.confirmed}
        for co in ("Alpha Logistics", "Beta Transit", "Gamma Capital", "Epsilon Media", "Sample Systems", "Kappa Insurance"):
            c.check(co in companies, "company %r not parsed" % co)
        plat = {(e.company, e.title): (e.platform, e.channel) for e in parse.confirmed}
        c.check(plat[("Example Robotics Pte Ltd", "AI Engineer Intern")] == ("jobstreet", "jobstreet"), "platform hint from note")
        c.check(plat[("Delta AI", "AI Application Engineer Intern")] == ("email", "email"), "platform hint from label")
        inter = {e.company: e for e in parse.intermediate}
        c.check(inter["Mu Fintech"].status == "skipped" and inter["Mu Fintech"].skip_reason_code == "id_number_required", "NRIC line mapping")
        c.check(inter["Nu Consulting"].status == "draft_saved" and inter["Nu Consulting"].title == "Strategy Analyst Intern", "draft mapping")
        c.check(inter["Rho Corp"].skip_reason_code == "start_immediately" and inter["Xi Tech"].skip_reason_code == "date_window_mismatch", "skip mappings")
        tr = {e.company: e for e in parse.tracking}
        c.check(tr["Lambda Holdings"].status == "draft_saved" and tr["Sigma Games"].status == "applied" and tr["Omega Retail"].tracking_status == "under_review", "tracking rows")

        legacy = d.root / "legacy.md"
        legacy.write_text(fx.LEGACY_MD, encoding="utf-8")
        _c, _o, _e, dry = run_cli("ledger", "migrate-legacy", str(legacy), "--dry-run", data=d, json_out=True)
        c.check(dry["dry_run"] and not (d.profile_dir / "ledger.sqlite").exists() or dry["counts"]["applications_created"] == 0, "dry-run must not write")
        _c, _o, _e, res = run_cli("ledger", "migrate-legacy", str(legacy), data=d, json_out=True)
        cnt = res["counts"]
        # 21 unique confirmed keys + 2 applications created from tracking rows (Lambda draft, Sigma applied)
        c.check(cnt["applications_created"] == 23 and cnt["submission_actions_added"] == 1 and cnt["evidence_added"] == 23
                and cnt["intermediate_created"] == 6 and cnt["tracking_events"] == 3 and cnt["jobs_created"] == 29, "import counts: %s" % cnt)
        _c, _o, _e, st = run_cli("ledger", "stats", data=d, json_out=True)
        c.check(st["unique_jobs_applied"] == 22 and st["submission_actions"] == 23 and st["duplicates"] == 1, "R1 counts after import: %s" % st)
        run_cli("ledger", "assert", data=d, expect=0)
        _c, _o, _e, res2 = run_cli("ledger", "migrate-legacy", str(legacy), data=d, json_out=True)
        c.check(res2["counts"]["applications_created"] == 0 and res2["counts"]["evidence_added"] == 0 and res2["counts"]["tracking_events"] == 0,
                "re-import must be a no-op: %s" % res2["counts"])
        _c, _o, _e, st2 = run_cli("ledger", "stats", data=d, json_out=True)
        c.check(st2["submission_actions"] == 23, "re-import changed counts")
        _replay(d, parse.confirmed, "fixture")
        _c, _o, _e, chk = run_cli("jobs", "check", "Alpha Logistics", "Any New Title", data=d, json_out=True)
        c.check(chk["decision"] == "dedup_review", "company with unrecorded legacy title must trigger review, got %s" % chk["decision"])
        _no_email_in_db(d.profile_dir / "ledger.sqlite")
        run_cli("ledger", "migrate-legacy", str(d.root / "nope.md"), data=d, expect=2)
        bad = d.root / "bad.md"
        bad.write_text("# nothing here\n\nplain text\n", encoding="utf-8")
        run_cli("ledger", "migrate-legacy", str(bad), data=d, expect=3)

    # ---- real ledger, read-only -------------------------------------------------------------------
    real = Path.home() / "Documents" / "Codex" / "投递台账.md"
    if not real.is_file():
        print("SKIP real ledger: %s not present" % real)
        return c.done("fixture parse/import/replay/idempotence verified; real ledger absent (SKIP)")
    text = real.read_text(encoding="utf-8")
    rparse = parse_legacy_markdown(text)
    rc = rparse.counts()
    print("real ledger: confirmed %d (unique keys %d), intermediate %d, tracking rows %d, rules lines skipped %d, warnings %d"
          % (rc["confirmed_mentions"], rc["confirmed_unique_keys"], rc["intermediate"], rc["tracking_rows"], rc["rules_lines_skipped"], rc["warnings"]))
    for w in rparse.warnings[:10]:
        print("  warn: %s" % w)
    c.check(rc["confirmed_mentions"] >= 100, "real ledger section 1 parsed %d < 100" % rc["confirmed_mentions"])
    c.check(rc["tracking_rows"] >= 1, "real ledger section 4 table not parsed")
    c.check(rc["rules_lines_skipped"] >= 1, "real ledger section 3 must be skipped, not imported")
    with TempData(profile_id="replay_user") as d2:
        write_json(d2.profile_dir / "profile.json", fx.profile(d2.root / "r.txt"))
        (d2.root / "r.txt").write_text("x", encoding="utf-8")
        _c, _o, _e, res = run_cli("ledger", "migrate-legacy", str(real), data=d2, json_out=True)
        _c, _o, _e, st = run_cli("ledger", "stats", data=d2, json_out=True)
        print("real ledger import: applications %d, evidence %d, extra submission actions %d -> 去重 %d 岗 / 提交 %d 次（其中重复 %d）"
              % (res["counts"]["applications_created"], res["counts"]["evidence_added"], res["counts"]["submission_actions_added"],
                 st["unique_jobs_applied"], st["submission_actions"], st["duplicates"]))
        run_cli("ledger", "assert", data=d2, expect=0)
        hits, total = _replay(d2, rparse.confirmed, "real ledger")
        print("real ledger replay: %d/%d confirmed entries blocked as dedup_hit" % (hits, total))
        _no_email_in_db(d2.profile_dir / "ledger.sqlite")
        for p in (ROOT / "tests", ROOT / "scripts", ROOT / "skills", ROOT / "examples"):
            for f in p.rglob("*.md"):
                c.check(f.resolve() != real.resolve() and f.read_bytes() != real.read_bytes(), "real ledger copied into repo: %s" % f)
    return c.done("fixture + real ledger (read-only): >=100 confirmed parsed, section 4 parsed, replay 100%% dedup_hit, no e-mail in ledger")


if __name__ == "__main__":
    sys.exit(main())

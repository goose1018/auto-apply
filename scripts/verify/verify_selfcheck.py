#!/usr/bin/env python3
"""verify: selfcheck — onboarding environment check (ARCHITECTURE §1.3 selfcheck; SECURITY §1.2 secrets.env mode).
Main path: temp data dir -> exit 0; three items reported as "unverified" (browser / Chrome login / mail connector).
Failure paths: secrets.env with loose permissions -> fail (exit 1) without reading it; profile.json with a
forbidden key -> fail; unwritable data dir -> fail.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, version_gate, write_json  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402

NAME = "selfcheck"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        _c, out, _e, js = run_cli("selfcheck", data=d, json_out=True)
        names = {i["name"]: i for i in js["items"]}
        c.check(js["counts"]["unverified"] == 3 and all(names[n]["status"] == "unverified" for n in ("browser_extension", "chrome_logged_in", "mail_connector")),
                "browser/mail items must be reported as unverified")
        c.check(all("未验证" in names[n]["detail"] for n in ("browser_extension", "chrome_logged_in", "mail_connector")), "unverified wording")
        c.check(names["schemas"]["status"] == "ok" and names["data_root_writable"]["status"] == "ok" and names["profile_json"]["status"] == "ok", "basic items: %s" % names)
        c.check(names["python_version"]["status"] == "ok", "python item (cli.py's own gate guarantees >=3.9 by the time selfcheck runs)")
        c.check(names["secrets_env_permissions"]["status"] == "ok", "absent secrets.env should be ok")
        _c, human, _e, _ = run_cli("selfcheck", data=d)
        c.check("[UNVERIFIED]" in human and "未验证，请手动确认" in human, "human output must show unverified items")
        # secrets.env 644 -> fail ; 600 -> ok ; content never printed
        sec = d.profile_dir / "secrets.env"
        sec.write_text("JOB_ACCOUNT_PASSWORD=verify-only-placeholder\n", encoding="utf-8")
        os.chmod(sec, 0o644)
        code, out, err, js = run_cli("selfcheck", data=d, json_out=True, expect=1)
        c.check({i["name"]: i for i in js["items"]}["secrets_env_permissions"]["status"] == "fail", "loose secrets.env must fail")
        c.check("verify-only-placeholder" not in out + err, "selfcheck must never print secrets.env content")
        os.chmod(sec, 0o600)
        run_cli("selfcheck", data=d, json_out=True, expect=0)
        # ledger assertions surface through selfcheck
        _c, _o, _e, r = run_cli("run", "new", data=d, json_out=True)
        _c, _o, _e, js = run_cli("selfcheck", data=d, json_out=True)
        c.check({i["name"]: i for i in js["items"]}["ledger"]["status"] == "ok", "ledger item after run new")
        # forbidden key in profile -> fail
        bad = fx.profile(resume)
        bad["identity"]["nric"] = "x"
        write_json(d.profile_dir / "profile.json", bad)
        run_cli("selfcheck", data=d, expect=1)
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        # no profile selected (no flag, no env, empty data dir) -> warn, still exit 0
        saved = os.environ.pop("AUTO_APPLY_PROFILE", None)
        try:
            _c, _o, _e, js = run_cli("--data-dir", str(d.root / "empty"), "selfcheck", json_out=True)
        finally:
            if saved is not None:
                os.environ["AUTO_APPLY_PROFILE"] = saved
        c.check(any(i["name"] == "profile" and i["status"] == "warn" for i in js["items"]), "no-profile warning")
        # unwritable data dir -> fail
        ro = d.root / "ro"
        ro.mkdir()
        os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
        try:
            code, _o, _e, js = run_cli("--data-dir", str(ro), "--profile", "x_user", "selfcheck", json_out=True, expect=None)
            c.check(code == 1 and any(i["name"] == "data_root_writable" and i["status"] == "fail" for i in js["items"]), "unwritable data dir must fail")
        finally:
            os.chmod(ro, stat.S_IRWXU)
    return c.done("selfcheck reports ok/warn/fail/unverified; secrets.env mode checked without reading; failures exit 1")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify: runstate — run checkpoints and the §2.3 transition table.
Main path: run new -> onboard; legal chain onboard→source→screen→apply→verify→ledger→apply→ledger→track→report→done.
Failure paths: illegal transition exit 2; pending_user requires resume_to and only resumes there; terminal states frozen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, TempData, run_cli, stderr_json, version_gate, write_json  # noqa: E402

version_gate()
import _fixtures as fx  # noqa: E402
from autoapply.ids import RUN_ID_RE  # noqa: E402

NAME = "runstate"
c = Checker(NAME)


def main() -> int:
    with TempData() as d:
        resume = d.root / "resume.txt"
        resume.write_text("fictional resume", encoding="utf-8")
        write_json(d.profile_dir / "profile.json", fx.profile(resume))
        code, out, _e, js = run_cli("run", "new", "--mode", "batch", "--runtime", "claude_code", data=d, json_out=True)
        run_id = js["run_id"]
        c.check(RUN_ID_RE.match(run_id) is not None, "run_id format: %s" % run_id)
        run_dir = d.profile_dir / "runs" / run_id
        for name in ("run_state.json", "run_options.json", "pending_actions.jsonl", "candidates.jsonl", "apply_queue.jsonl", "ledger_writes.jsonl"):
            c.check((run_dir / name).exists(), "missing %s" % name)
        state = json.loads((run_dir / "run_state.json").read_text(encoding="utf-8"))
        c.check(state["phase"] == "onboard" and state["runtime"] == "claude_code" and state["mode"] == "apply", "initial state")
        c.check(json.loads((run_dir / "run_options.json").read_text())["gate_mode"] == "batch", "gate_mode option")
        # human output: first line is the run_id
        _c, out, _e, _ = run_cli("run", "new", data=d)
        c.check(RUN_ID_RE.match(out.splitlines()[0]) is not None, "human `run new` must print run_id first")

        # illegal: onboard -> apply
        code, _o, err, _ = run_cli("run", "checkpoint", run_id, "--state", "apply", data=d, expect=2)
        j = stderr_json(err)
        c.check(j is not None and j.get("error") == "runstate_error", "illegal transition should be runstate_error")
        for st in ("source", "screen", "apply", "verify", "ledger", "apply", "ledger", "track", "report", "done"):
            _c, _o, _e, s = run_cli("run", "checkpoint", run_id, "--state", st, data=d, json_out=True)
            c.check(s["phase"] == st, "phase not updated to %s" % st)
        c.check(s["ended_at"], "done must set ended_at")
        run_cli("run", "checkpoint", run_id, "--state", "report", data=d, expect=2)  # terminal
        # same-phase transition is illegal too
        _c, _o, _e, js2 = run_cli("run", "new", data=d, json_out=True)
        r2 = js2["run_id"]
        run_cli("run", "checkpoint", r2, "--state", "onboard", data=d, expect=2)
        run_cli("run", "checkpoint", r2, "--state", "source", data=d)
        run_cli("run", "checkpoint", r2, "--state", "screen", data=d)
        _c, _o, _e, s = run_cli("run", "checkpoint", r2, "--state", "pending_user", data=d, json_out=True)
        c.check(s["phase"] == "pending_user" and s["resume_to"] == "screen", "pending_user must record resume_to (default current)")
        run_cli("run", "checkpoint", r2, "--state", "apply", data=d, expect=2)  # not resume_to
        _c, _o, _e, s = run_cli("run", "checkpoint", r2, "--state", "screen", data=d, json_out=True)
        c.check(s["phase"] == "screen" and s["resume_to"] is None, "resume must clear resume_to")
        _c, _o, _e, s = run_cli("run", "checkpoint", r2, "--state", "pending_user", "--resume-to", "apply", "--gate", "pa_20260905_aaaaaa", data=d, json_out=True)
        c.check(s["resume_to"] == "apply" and s["suspended_by_gate"] == "pa_20260905_aaaaaa", "explicit resume_to / gate not stored")
        run_cli("run", "checkpoint", r2, "--state", "report", data=d)  # pending_user -> report allowed
        run_cli("run", "checkpoint", r2, "--state", "aborted", data=d)
        # bad ids
        run_cli("run", "show", "run_bad", data=d, expect=2)
        run_cli("run", "show", "run_20260101_000000", data=d, expect=2)
        _c, _o, _e, lst = run_cli("run", "list", data=d, json_out=True)
        c.check(len(lst["runs"]) == 3, "run list should show 3 runs")
        _c, _o, _e, show = run_cli("run", "show", run_id, data=d, json_out=True)
        c.check(show["legal_next_states"] == [], "done has no legal next states")
    return c.done("legal chain accepted; illegal / same-phase / terminal transitions exit 2; pending_user resume_to honoured")


if __name__ == "__main__":
    sys.exit(main())

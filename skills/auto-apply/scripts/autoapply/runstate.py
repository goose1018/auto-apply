"""Run checkpoints and the run-level state machine (ARCHITECTURE §2). Business layer.

runs/<run_id>/run_state.json is the single source of progress; every write is schema-validated and
every phase change is checked against enums.TRANSITIONS (illegal -> RunStateError, exit 2).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

from autoapply import enums
from autoapply.errors import RunStateError, UsageError
from autoapply.ids import RUN_ID_RE, new_run_id, now_iso, now_local
from autoapply.ledger import add_event
from autoapply.paths import DataPaths
from autoapply.schema_validate import SchemaSet

RUN_STATE_FILE = "run_state.json"
RUN_OPTIONS_FILE = "run_options.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RunStateError("找不到 run_state.json / run not found", {"path": str(path)}) from e
    except ValueError as e:
        raise RunStateError("run_state.json 不是合法 JSON / corrupt run_state.json", {"path": str(path)}) from e
    if not isinstance(data, dict):
        raise RunStateError("run_state.json 顶层必须是对象 / run_state.json must be an object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.match(run_id):
        raise UsageError("run_id 格式不合法（run_<YYYYMMDD>_<HHMMSS>）/ invalid run_id", {"run_id": run_id})
    return run_id


def load_run_state(paths: DataPaths, run_id: str) -> dict[str, Any]:
    validate_run_id(run_id)
    return _read_json(paths.run_dir(run_id) / RUN_STATE_FILE)


def save_run_state(paths: DataPaths, schemas: SchemaSet, state: dict[str, Any]) -> None:
    schemas.require("run_state", state, "run_state")
    _write_json(paths.run_dir(str(state["run_id"])) / RUN_STATE_FILE, state)


def load_run_options(paths: DataPaths, run_id: str) -> dict[str, Any]:
    p = paths.run_dir(run_id) / RUN_OPTIONS_FILE
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def create_run(
    paths: DataPaths,
    schemas: SchemaSet,
    conn: sqlite3.Connection,
    *,
    gate_mode: str = "interactive",
    invocation: str = "apply",
    runtime: str | None = None,
    target: int | None = None,
    per_day_limit: int | None = None,
    report_every_n: int | None = None,
) -> dict[str, Any]:
    if gate_mode not in enums.GATE_MODE_POLICIES:
        raise UsageError("--mode 只能是 interactive|batch / invalid --mode", {"mode": gate_mode})
    if invocation not in enums.RUN_INVOCATIONS:
        raise UsageError("invocation 只能是 apply|status|report", {"invocation": invocation})
    if runtime is not None and runtime not in enums.RUNTIMES:
        raise UsageError("runtime 只能是 claude_code|codex", {"runtime": runtime})
    dt = now_local()
    run_id = new_run_id(dt)
    run_dir = paths.run_dir(run_id)
    for bump in range(1, 30):  # run_id has second granularity; step forward instead of failing
        if not run_dir.exists():
            break
        dt = now_local() + timedelta(seconds=bump)
        run_id = new_run_id(dt)
        run_dir = paths.run_dir(run_id)
    if run_dir.exists():
        raise RunStateError("无法分配唯一 run_id / cannot allocate a unique run_id", {"run_id": run_id})
    run_dir.mkdir(parents=True)
    (run_dir / "items").mkdir()
    ts = dt.isoformat(timespec="seconds")
    state: dict[str, Any] = {
        "run_id": run_id,
        "profile_id": paths.profile_id,
        "runtime": runtime,
        "mode": invocation,
        "phase": "onboard",
        "previous_phase": None,
        "resume_to": None,
        "suspended_by_gate": None,
        "started_at": ts,
        "updated_at": ts,
        "ended_at": None,
        "round": {
            "target": target,
            "per_day_limit": per_day_limit,
            "per_day_used": 0,
            "submission_actions": 0,
            "unique_applied": 0,
            "per_company_counts": {},
        },
        "quotas": {"linkedin_daily_remaining": None, "linkedin_limit_hit_at": None, "platform_blocked": []},
        "browser": {"channel": None, "status": "unknown", "last_ok_at": None, "lease_holder": None},
        "current_item": None,
        "queue_cursor": 0,
        "counters": {"candidates": 0, "screened": 0, "queued": 0, "applied": 0, "submitted_unverified": 0,
                     "pending_user": 0, "skipped": 0, "failed": 0},
        "reporting": {"every_n": report_every_n, "last_report_at": None, "last_report_applied_count": None},
        "checkpoints": {"onboard": ts},
        "errors": [],
        "version": "1",
    }
    save_run_state(paths, schemas, state)
    _write_json(run_dir / RUN_OPTIONS_FILE, {"gate_mode": gate_mode, "created_at": ts})
    for name in ("candidates.jsonl", "apply_queue.jsonl", "pending_actions.jsonl", "ledger_writes.jsonl", "log.jsonl"):
        (run_dir / name).touch()
    add_event(conn, "run_started", "orchestrator", {"gate_mode": gate_mode, "invocation": invocation, "runtime": runtime},
              run_id=run_id, at=ts)
    return state


def legal_targets(state: dict[str, Any]) -> set[str]:
    phase = str(state["phase"])
    targets = set(enums.TRANSITIONS.get(phase, frozenset()))
    if phase == "pending_user" and state.get("resume_to"):
        targets.add(str(state["resume_to"]))
    return targets


def checkpoint(
    paths: DataPaths,
    schemas: SchemaSet,
    conn: sqlite3.Connection,
    run_id: str,
    new_phase: str,
    *,
    resume_to: str | None = None,
    gate_id: str | None = None,
    actor: str = "orchestrator",
) -> dict[str, Any]:
    if new_phase not in enums.PHASES:
        raise UsageError("state 不合法 / invalid state", {"state": new_phase, "allowed": list(enums.PHASES)})
    state = load_run_state(paths, run_id)
    current = str(state["phase"])
    allowed = legal_targets(state)
    if new_phase not in allowed:
        raise RunStateError(
            "非法状态转移 %s -> %s（ARCHITECTURE §2.3）/ illegal transition" % (current, new_phase),
            {"from": current, "to": new_phase, "allowed": sorted(allowed)},
        )
    if new_phase == "pending_user":
        target = resume_to or current
        if target not in enums.PHASES or target in ("pending_user", "done", "aborted"):
            raise UsageError("resume_to 不合法 / invalid resume_to", {"resume_to": target})
        state["resume_to"] = target
        state["suspended_by_gate"] = gate_id
    elif current == "pending_user":
        state["resume_to"] = None
        state["suspended_by_gate"] = None
    ts = now_iso()
    state["previous_phase"] = current
    state["phase"] = new_phase
    state["updated_at"] = ts
    if new_phase in enums.TERMINAL_PHASES:
        state["ended_at"] = ts
    cps = state.setdefault("checkpoints", {})
    if isinstance(cps, dict):
        cps[new_phase] = ts
    save_run_state(paths, schemas, state)
    add_event(conn, "phase_change", actor, {"from": current, "to": new_phase, "resume_to": state.get("resume_to"), "gate_id": gate_id},
              run_id=run_id, at=ts)
    return state


def suspend(paths: DataPaths, schemas: SchemaSet, conn: sqlite3.Connection, run_id: str, gate_id: str,
            resume_to: str | None = None) -> dict[str, Any]:
    state = load_run_state(paths, run_id)
    if state["phase"] == "pending_user":
        state["suspended_by_gate"] = gate_id
        state["updated_at"] = now_iso()
        save_run_state(paths, schemas, state)
        return state
    return checkpoint(paths, schemas, conn, run_id, "pending_user", resume_to=resume_to, gate_id=gate_id)


def resume(paths: DataPaths, schemas: SchemaSet, conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    state = load_run_state(paths, run_id)
    if state["phase"] != "pending_user":
        raise RunStateError("run 不在 pending_user，无需恢复 / run is not suspended", {"phase": state["phase"]})
    target = state.get("resume_to")
    if not target:
        raise RunStateError("run_state.resume_to 为空 / resume_to missing")
    return checkpoint(paths, schemas, conn, run_id, str(target))


def list_runs(paths: DataPaths) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not paths.runs_dir.is_dir():
        return out
    for d in sorted(paths.runs_dir.iterdir()):
        if d.is_dir() and RUN_ID_RE.match(d.name) and (d / RUN_STATE_FILE).is_file():
            try:
                st = _read_json(d / RUN_STATE_FILE)
            except RunStateError:
                continue
            out.append({"run_id": d.name, "phase": st.get("phase"), "updated_at": st.get("updated_at")})
    return out


def latest_open_run(paths: DataPaths) -> str | None:
    open_runs = [r for r in list_runs(paths) if r.get("phase") not in enums.TERMINAL_PHASES]
    return str(open_runs[-1]["run_id"]) if open_runs else None


def update_counters(paths: DataPaths, schemas: SchemaSet, run_id: str, counters: dict[str, int],
                    round_fields: dict[str, Any] | None = None) -> dict[str, Any]:
    state = load_run_state(paths, run_id)
    c = state.setdefault("counters", {})
    if isinstance(c, dict):
        for k, v in counters.items():
            c[k] = int(v)
    if round_fields:
        r = state.setdefault("round", {})
        if isinstance(r, dict):
            r.update(round_fields)
    state["updated_at"] = now_iso()
    save_run_state(paths, schemas, state)
    return state

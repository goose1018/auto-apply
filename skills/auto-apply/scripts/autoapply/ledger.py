"""SQLite ledger (ARCHITECTURE §9 DDL + BRIEF D11). Business layer; the only writer of ledger.sqlite.

Columns are a superset of ARCHITECTURE §9: fields that exist in schemas/*.json but not in the DDL
were added (schema wins, see README "schema vs DDL"). Every ARCHITECTURE column is present verbatim.

Hard rule enforced here: an application can only become `applied` when at least one evidence row
with qualifies=1 exists (EvidenceError, exit code 3). `qualifies` values come only from evidence.py.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoapply import enums
from autoapply.errors import EvidenceError, LedgerError, UsageError
from autoapply.ids import now_iso, sha256_text
from autoapply.paths import DataPaths
from autoapply.redact import find_secret_hits, redact

SCHEMA_VERSION = "1"


def _check(name: str, values: tuple[str, ...]) -> str:
    return "%s IN (%s)" % (name, ",".join("'%s'" % v for v in values))


DDL: str = """
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id            TEXT PRIMARY KEY,
  dedup_key         TEXT NOT NULL UNIQUE,
  company_raw       TEXT NOT NULL,
  company_norm      TEXT NOT NULL,
  title_raw         TEXT NOT NULL,
  title_norm        TEXT NOT NULL,
  platform          TEXT NOT NULL CHECK (%(platform)s),
  channel           TEXT CHECK (channel IS NULL OR %(channel)s),
  url               TEXT,
  apply_url         TEXT,
  req_id            TEXT,
  location          TEXT,
  company_domain    TEXT,
  source_type       TEXT NOT NULL CHECK (%(source_type)s),
  source_ref        TEXT,
  source_added_by   TEXT,
  posted_at         TEXT,
  closes_at         TEXT,
  jd_summary        TEXT,
  jd_hash           TEXT,
  hard_conditions   TEXT,
  match_score       INTEGER,
  match_json        TEXT,
  risks_json        TEXT,
  screening_json    TEXT,
  notes             TEXT,
  first_seen_at     TEXT NOT NULL,
  last_seen_at      TEXT NOT NULL,
  closed_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_company_norm ON jobs(company_norm);
CREATE INDEX IF NOT EXISTS idx_jobs_platform     ON jobs(platform);

CREATE TABLE IF NOT EXISTS applications (
  app_id                  TEXT PRIMARY KEY,
  job_id                  TEXT NOT NULL REFERENCES jobs(job_id),
  run_id                  TEXT,
  profile_id              TEXT,
  channel                 TEXT NOT NULL CHECK (%(channel)s),
  platform                TEXT NOT NULL CHECK (%(platform)s),
  status                  TEXT NOT NULL CHECK (%(status)s),
  tracking_status         TEXT NOT NULL DEFAULT 'none' CHECK (%(tracking)s),
  skip_reason_code        TEXT CHECK (skip_reason_code IS NULL OR %(skip)s),
  priority                TEXT CHECK (priority IS NULL OR %(priority)s),
  submission_action_count INTEGER NOT NULL DEFAULT 0,
  submitted_at            TEXT,
  applied_confirmed_at    TEXT,
  resume_path             TEXT,
  resume_language         TEXT,
  resume_sha256           TEXT,
  pre_submit_passed       INTEGER,
  approval_json           TEXT,
  content_json            TEXT,
  failure_reason          TEXT,
  form_state_ref          TEXT,
  notes                   TEXT,
  created_at              TEXT NOT NULL,
  updated_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_app_job     ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_app_status  ON applications(status);
CREATE INDEX IF NOT EXISTS idx_app_run     ON applications(run_id);
CREATE INDEX IF NOT EXISTS idx_app_submitted ON applications(submitted_at);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id      TEXT PRIMARY KEY,
  app_id           TEXT NOT NULL REFERENCES applications(app_id),
  evidence_type    TEXT NOT NULL CHECK (%(evidence_type)s),
  qualifies        INTEGER NOT NULL DEFAULT 0,
  captured_at      TEXT NOT NULL,
  captured_by      TEXT NOT NULL,
  url              TEXT,
  page_title       TEXT,
  file             TEXT,
  sha256           TEXT,
  job_title_seen   TEXT,
  email_subject    TEXT,
  email_from       TEXT,
  email_received_at TEXT,
  email_message_id TEXT,
  email_excerpt    TEXT,
  matched_job_by   TEXT,
  legacy_ref       TEXT,
  notes            TEXT
);
CREATE INDEX IF NOT EXISTS idx_ev_app ON evidence(app_id);
CREATE INDEX IF NOT EXISTS idx_ev_qual ON evidence(app_id, qualifies);

CREATE TABLE IF NOT EXISTS gates (
  gate_id       TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL,
  app_id        TEXT REFERENCES applications(app_id),
  gate_type     TEXT NOT NULL CHECK (%(gate_type)s),
  scope         TEXT NOT NULL CHECK (%(scope)s),
  mode          TEXT NOT NULL CHECK (%(mode)s),
  playbook_step TEXT,
  opened_at     TEXT NOT NULL,
  expires_at    TEXT,
  resolved_at   TEXT,
  resolution    TEXT CHECK (resolution IS NULL OR %(resolution)s),
  summary       TEXT,
  runtime       TEXT CHECK (runtime IS NULL OR %(runtime)s)
);
CREATE INDEX IF NOT EXISTS idx_gates_open ON gates(run_id, resolved_at);

CREATE TABLE IF NOT EXISTS events (
  event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  run_id     TEXT,
  app_id     TEXT REFERENCES applications(app_id),
  job_id     TEXT REFERENCES jobs(job_id),
  kind       TEXT NOT NULL CHECK (%(kind)s),
  actor      TEXT NOT NULL,
  payload    TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_at   ON events(at);
CREATE INDEX IF NOT EXISTS idx_events_app  ON events(app_id);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
""" % {
    "platform": _check("platform", enums.PLATFORMS),
    "channel": _check("channel", enums.CHANNELS),
    "source_type": _check("source_type", enums.SOURCE_TYPES),
    "status": _check("status", enums.APP_STATUSES),
    "tracking": _check("tracking_status", enums.TRACKING_STATUSES),
    "skip": _check("skip_reason_code", enums.SKIP_REASON_CODES),
    "priority": _check("priority", enums.PRIORITIES),
    "evidence_type": _check("evidence_type", enums.EVIDENCE_TYPES),
    "gate_type": _check("gate_type", enums.GATE_TYPES),
    "scope": _check("scope", enums.GATE_SCOPES),
    "mode": _check("mode", enums.GATE_MODES),
    "resolution": _check("resolution", enums.GATE_RESOLUTIONS),
    "runtime": _check("runtime", enums.RUNTIMES),
    "kind": _check("kind", enums.EVENT_KINDS),
}

# status -> event kind (ARCHITECTURE §9 events.kind)
_STATUS_EVENT_KIND: dict[str, str] = {
    "applied": "applied",
    "submitted_unverified": "submitted_unverified",
    "skipped": "skipped",
    "failed": "failed",
    "draft_saved": "draft_saved",
    "in_progress": "apply_started",
    "queued": "queued",
}


# ---- records -------------------------------------------------------------------------------------
@dataclass(frozen=True)
class JobRecord:
    job_id: str
    dedup_key: str
    company_raw: str
    company_norm: str
    title_raw: str
    title_norm: str
    platform: str
    source_type: str
    channel: str | None = None
    url: str | None = None
    apply_url: str | None = None
    req_id: str | None = None
    location: str | None = None
    company_domain: str | None = None
    source_ref: str | None = None
    source_added_by: str | None = None
    posted_at: str | None = None
    closes_at: str | None = None
    jd_summary: str | None = None
    jd_hash: str | None = None
    hard_conditions: dict[str, Any] | None = None
    match_score: int | None = None
    match_json: dict[str, Any] | None = None
    risks: list[str] = field(default_factory=list)
    screening: dict[str, Any] | None = None
    notes: str | None = None
    seen_at: str | None = None


@dataclass(frozen=True)
class ApplicationRecord:
    app_id: str
    job_id: str
    channel: str
    platform: str
    status: str = "queued"
    run_id: str | None = None
    profile_id: str | None = None
    priority: str | None = None
    approval: dict[str, Any] | None = None
    resume_path: str | None = None
    resume_language: str | None = None
    resume_sha256: str | None = None
    notes: str | None = None
    submission_action_count: int = 0
    submitted_at: str | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class EvidenceRow:
    """Built only by evidence.py (qualifies is a judged value, never user input)."""

    evidence_id: str
    app_id: str
    evidence_type: str
    qualifies: bool
    captured_at: str
    captured_by: str
    url: str | None = None
    page_title: str | None = None
    file: str | None = None
    sha256: str | None = None
    job_title_seen: str | None = None
    email_subject: str | None = None
    email_from: str | None = None
    email_received_at: str | None = None
    email_message_id: str | None = None
    email_excerpt: str | None = None
    matched_job_by: str | None = None
    legacy_ref: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class GateRow:
    gate_id: str
    run_id: str
    gate_type: str
    scope: str
    mode: str
    opened_at: str
    app_id: str | None = None
    playbook_step: str | None = None
    expires_at: str | None = None
    summary: str | None = None
    runtime: str | None = None


# ---- connection ----------------------------------------------------------------------------------
def open_ledger(path: Path, profile_id: str) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path), isolation_level=None)
    except sqlite3.Error as e:
        raise LedgerError("无法打开台账 / cannot open ledger", {"path": str(path)}) from e
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(DDL)  # idempotent; executescript commits on its own
        with transaction(conn):
            existing = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if existing is None:
                conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
                conn.execute("INSERT INTO meta(key, value) VALUES ('profile_id', ?)", (profile_id,))
                conn.execute("INSERT INTO meta(key, value) VALUES ('created_at', ?)", (now_iso(),))
            elif existing["value"] != SCHEMA_VERSION:
                raise LedgerError(
                    "台账 schema 版本不匹配 / ledger schema version mismatch",
                    {"found": existing["value"], "expected": SCHEMA_VERSION},
                )
    except sqlite3.Error as e:
        raise LedgerError("台账初始化失败 / ledger init failed", {"path": str(path)}) from e
    return conn


class transaction:
    """with transaction(conn): ... — BEGIN IMMEDIATE / COMMIT / ROLLBACK."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is None:
            self.conn.execute("COMMIT")
        else:
            self.conn.execute("ROLLBACK")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else {k: row[k] for k in row.keys()}


def _dump(obj: Any) -> str | None:
    return None if obj is None else json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _load(text: str | None) -> Any:
    return None if text in (None, "") else json.loads(str(text))


# ---- jobs ----------------------------------------------------------------------------------------
def upsert_job(conn: sqlite3.Connection, job: JobRecord) -> str:
    at = job.seen_at or now_iso()
    existing = conn.execute("SELECT * FROM jobs WHERE dedup_key = ?", (job.dedup_key,)).fetchone()
    if existing is not None and existing["job_id"] != job.job_id:
        raise LedgerError("job_id 与 dedup_key 不一致 / job_id does not match dedup_key", {"dedup_key": job.dedup_key})
    if existing is None:
        conn.execute(
            """INSERT INTO jobs(job_id, dedup_key, company_raw, company_norm, title_raw, title_norm, platform, channel,
               url, apply_url, req_id, location, company_domain, source_type, source_ref, source_added_by, posted_at,
               closes_at, jd_summary, jd_hash, hard_conditions, match_score, match_json, risks_json, screening_json,
               notes, first_seen_at, last_seen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job.job_id, job.dedup_key, job.company_raw, job.company_norm, job.title_raw, job.title_norm,
                job.platform, job.channel, job.url, job.apply_url, job.req_id, job.location, job.company_domain,
                job.source_type, job.source_ref, job.source_added_by, job.posted_at, job.closes_at, job.jd_summary,
                job.jd_hash, _dump(job.hard_conditions), job.match_score, _dump(job.match_json), _dump(job.risks),
                _dump(job.screening), job.notes, at, at,
            ),
        )
    else:
        # keep first-seen provenance; refresh mutable fields when the new record has a value
        conn.execute(
            """UPDATE jobs SET last_seen_at=?, platform=COALESCE(?, platform), channel=COALESCE(?, channel),
               url=COALESCE(?, url), apply_url=COALESCE(?, apply_url), req_id=COALESCE(?, req_id),
               location=COALESCE(?, location), company_domain=COALESCE(?, company_domain),
               posted_at=COALESCE(?, posted_at), closes_at=COALESCE(?, closes_at),
               jd_summary=COALESCE(?, jd_summary), jd_hash=COALESCE(?, jd_hash),
               hard_conditions=COALESCE(?, hard_conditions), match_score=COALESCE(?, match_score),
               match_json=COALESCE(?, match_json), risks_json=COALESCE(?, risks_json),
               screening_json=COALESCE(?, screening_json), notes=COALESCE(?, notes)
               WHERE job_id=?""",
            (
                at, job.platform, job.channel, job.url, job.apply_url, job.req_id, job.location, job.company_domain,
                job.posted_at, job.closes_at, job.jd_summary, job.jd_hash, _dump(job.hard_conditions),
                job.match_score, _dump(job.match_json), _dump(job.risks) if job.risks else None,
                _dump(job.screening), job.notes, job.job_id,
            ),
        )
    return job.job_id


def get_job(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone())


def require_job(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    job = get_job(conn, job_id)
    if job is None:
        raise LedgerError("台账中不存在该 job_id / job not in ledger", {"job_id": job_id})
    return job


def get_job_by_key(conn: sqlite3.Connection, dedup_key: str) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM jobs WHERE dedup_key=?", (dedup_key,)).fetchone())


def jobs_by_company_norm(conn: sqlite3.Connection, company_norm: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM jobs WHERE company_norm=? ORDER BY first_seen_at", (company_norm,)).fetchall()
    return [r for r in (row_to_dict(x) for x in rows) if r is not None]


# ---- applications --------------------------------------------------------------------------------
def create_application(conn: sqlite3.Connection, app: ApplicationRecord) -> dict[str, Any]:
    if app.status not in enums.APP_STATUSES:
        raise UsageError("status 不合法 / invalid status", {"status": app.status})
    if app.channel not in enums.CHANNELS or app.platform not in enums.PLATFORMS:
        raise UsageError("channel/platform 不合法 / invalid channel or platform")
    require_job(conn, app.job_id)
    at = app.created_at or now_iso()
    conn.execute(
        """INSERT INTO applications(app_id, job_id, run_id, profile_id, channel, platform, status, priority,
           submission_action_count, submitted_at, resume_path, resume_language, resume_sha256, approval_json, notes,
           created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            app.app_id, app.job_id, app.run_id, app.profile_id, app.channel, app.platform, app.status, app.priority,
            app.submission_action_count, app.submitted_at, app.resume_path, app.resume_language, app.resume_sha256,
            _dump(app.approval), app.notes, at, at,
        ),
    )
    add_event(conn, _STATUS_EVENT_KIND.get(app.status, "status_change"), "script",
              {"to": app.status, "channel": app.channel, "platform": app.platform},
              run_id=app.run_id, app_id=app.app_id, job_id=app.job_id, at=at)
    return require_application(conn, app.app_id)


def get_application(conn: sqlite3.Connection, app_id: str) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM applications WHERE app_id=?", (app_id,)).fetchone())


def require_application(conn: sqlite3.Connection, app_id: str) -> dict[str, Any]:
    app = get_application(conn, app_id)
    if app is None:
        raise LedgerError("台账中不存在该 application_id / application not in ledger", {"app_id": app_id})
    return app


def applications_for_job(conn: sqlite3.Connection, job_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM applications WHERE job_id=? ORDER BY created_at", (job_id,)).fetchall()
    return [r for r in (row_to_dict(x) for x in rows) if r is not None]


def applications_for_run(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM applications WHERE run_id=? ORDER BY created_at", (run_id,)).fetchall()
    return [r for r in (row_to_dict(x) for x in rows) if r is not None]


def find_open_application(conn: sqlite3.Connection, run_id: str, job_id: str, channel: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT * FROM applications WHERE run_id=? AND job_id=? AND channel=?
           AND status IN ('queued','in_progress','draft_saved','pending_user','ready_to_submit')
           ORDER BY created_at DESC LIMIT 1""",
        (run_id, job_id, channel),
    ).fetchone()
    return row_to_dict(row)


def has_qualifying_evidence(conn: sqlite3.Connection, app_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM evidence WHERE app_id=? AND qualifies=1 LIMIT 1", (app_id,)).fetchone()
    return row is not None


def first_qualifying_evidence_at(conn: sqlite3.Connection, app_id: str) -> str | None:
    row = conn.execute(
        "SELECT MIN(captured_at) AS at FROM evidence WHERE app_id=? AND qualifies=1", (app_id,)
    ).fetchone()
    return None if row is None else row["at"]


def set_application_status(
    conn: sqlite3.Connection,
    app_id: str,
    status: str,
    *,
    skip_reason_code: str | None = None,
    note: str | None = None,
    failure_reason: str | None = None,
    count_submission: bool = False,
    priority: str | None = None,
    tracking_status: str | None = None,
    actor: str = "script",
    at: str | None = None,
) -> dict[str, Any]:
    if status not in enums.APP_STATUSES:
        raise UsageError("status 不合法 / invalid status", {"status": status, "allowed": list(enums.APP_STATUSES)})
    if skip_reason_code is not None and skip_reason_code not in enums.SKIP_REASON_CODES:
        raise UsageError("skip_reason_code 不合法 / invalid skip_reason_code", {"code": skip_reason_code})
    if status == "skipped" and skip_reason_code is None:
        raise UsageError("status=skipped 必须给 skip_reason_code（--reason）/ skipped requires a reason code")
    if tracking_status is not None and tracking_status not in enums.TRACKING_STATUSES:
        raise UsageError("tracking_status 不合法 / invalid tracking_status", {"tracking_status": tracking_status})
    app = require_application(conn, app_id)
    ts = at or now_iso()
    if status == "applied" and not has_qualifying_evidence(conn, app_id):
        raise EvidenceError(
            "无合格证据不得标 applied：先用 `app evidence` 登记职位级成功页或确认邮件 / "
            "applied requires qualifying evidence (success page or confirmation email)",
            {"app_id": app_id, "assertion": "applied-has-evidence"},
        )
    for text in (note, failure_reason):
        if text and find_secret_hits(text):
            raise EvidenceError("备注中含密码/证件号模式，拒绝写入 / note contains secret-like content")
    count = int(app["submission_action_count"])
    submitted_at = app["submitted_at"]
    if status == "submitted_unverified" or count_submission:
        count += 1
        submitted_at = submitted_at or ts
    applied_at = app["applied_confirmed_at"]
    if status == "applied":
        if count == 0:
            count = 1
        submitted_at = submitted_at or ts
        applied_at = applied_at or first_qualifying_evidence_at(conn, app_id) or ts
    new_notes = app["notes"]
    if note:
        new_notes = (new_notes + "\n" if new_notes else "") + redact(note)
    conn.execute(
        """UPDATE applications SET status=?, skip_reason_code=COALESCE(?, skip_reason_code),
           failure_reason=COALESCE(?, failure_reason), submission_action_count=?, submitted_at=?,
           applied_confirmed_at=?, priority=COALESCE(?, priority), tracking_status=COALESCE(?, tracking_status),
           notes=?, updated_at=? WHERE app_id=?""",
        (status, skip_reason_code, redact(failure_reason) if failure_reason else None, count, submitted_at,
         applied_at, priority, tracking_status, new_notes, ts, app_id),
    )
    job = require_job(conn, app["job_id"])
    add_event(
        conn, _STATUS_EVENT_KIND.get(status, "status_change"), actor,
        {"from": app["status"], "to": status, "company": job["company_raw"], "title": job["title_raw"],
         "platform": app["platform"], "channel": app["channel"], "skip_reason_code": skip_reason_code,
         "submission_action_count": count},
        run_id=app["run_id"], app_id=app_id, job_id=app["job_id"], at=ts,
    )
    return require_application(conn, app_id)


def set_tracking_status(conn: sqlite3.Connection, app_id: str, tracking_status: str, note: str | None,
                        actor: str = "tracker", at: str | None = None) -> dict[str, Any]:
    if tracking_status not in enums.TRACKING_STATUSES:
        raise UsageError("tracking_status 不合法 / invalid tracking_status")
    app = require_application(conn, app_id)
    ts = at or now_iso()
    conn.execute("UPDATE applications SET tracking_status=?, updated_at=? WHERE app_id=?", (tracking_status, ts, app_id))
    job = require_job(conn, app["job_id"])
    add_event(conn, "tracking_update", actor,
              {"tracking_status": tracking_status, "company": job["company_raw"], "title": job["title_raw"],
               "channel": app["channel"], "note": redact(note) if note else None},
              run_id=app["run_id"], app_id=app_id, job_id=app["job_id"], at=ts)
    return require_application(conn, app_id)


# ---- evidence ------------------------------------------------------------------------------------
def next_evidence_seq(conn: sqlite3.Connection, app_id: str) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM evidence WHERE app_id=?", (app_id,)).fetchone()
    return int(row["n"]) + 1


def insert_evidence(conn: sqlite3.Connection, ev: EvidenceRow, actor: str = "script") -> dict[str, Any]:
    if ev.evidence_type not in enums.EVIDENCE_TYPES:
        raise UsageError("evidence_type 不合法 / invalid evidence_type", {"evidence_type": ev.evidence_type})
    if ev.qualifies and ev.evidence_type not in enums.QUALIFYING_EVIDENCE_TYPES:
        raise EvidenceError("不合格类型不能 qualifies=1 / non-qualifying type cannot qualify", {"evidence_type": ev.evidence_type})
    app = require_application(conn, ev.app_id)
    conn.execute(
        """INSERT INTO evidence(evidence_id, app_id, evidence_type, qualifies, captured_at, captured_by, url,
           page_title, file, sha256, job_title_seen, email_subject, email_from, email_received_at,
           email_message_id, email_excerpt, matched_job_by, legacy_ref, notes)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ev.evidence_id, ev.app_id, ev.evidence_type, 1 if ev.qualifies else 0, ev.captured_at, ev.captured_by,
         ev.url, ev.page_title, ev.file, ev.sha256, ev.job_title_seen, ev.email_subject, ev.email_from,
         ev.email_received_at, ev.email_message_id, ev.email_excerpt, ev.matched_job_by, ev.legacy_ref, ev.notes),
    )
    add_event(conn, "evidence_added", actor,
              {"evidence_id": ev.evidence_id, "evidence_type": ev.evidence_type, "qualifies": bool(ev.qualifies)},
              run_id=app["run_id"], app_id=ev.app_id, job_id=app["job_id"], at=ev.captured_at)
    row = row_to_dict(conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (ev.evidence_id,)).fetchone())
    if row is None:
        raise LedgerError("证据写入后读不到 / evidence row missing after insert")
    return row


def evidence_for_app(conn: sqlite3.Connection, app_id: str) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM evidence WHERE app_id=? ORDER BY captured_at", (app_id,)).fetchall()
    return [r for r in (row_to_dict(x) for x in rows) if r is not None]


# ---- gates ---------------------------------------------------------------------------------------
def insert_gate(conn: sqlite3.Connection, gate: GateRow, actor: str = "script") -> None:
    conn.execute(
        """INSERT INTO gates(gate_id, run_id, app_id, gate_type, scope, mode, playbook_step, opened_at, expires_at,
           summary, runtime) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (gate.gate_id, gate.run_id, gate.app_id, gate.gate_type, gate.scope, gate.mode, gate.playbook_step,
         gate.opened_at, gate.expires_at, gate.summary, gate.runtime),
    )
    job_id = None
    if gate.app_id:
        job_id = require_application(conn, gate.app_id)["job_id"]
    add_event(conn, "gate_opened", actor,
              {"gate_id": gate.gate_id, "gate_type": gate.gate_type, "scope": gate.scope, "summary": gate.summary},
              run_id=gate.run_id, app_id=gate.app_id, job_id=job_id, at=gate.opened_at)


def resolve_gate(conn: sqlite3.Connection, gate_id: str, resolution: str, at: str, actor: str = "user") -> dict[str, Any]:
    if resolution not in enums.GATE_RESOLUTIONS:
        raise UsageError("resolution 不合法 / invalid resolution", {"resolution": resolution})
    row = row_to_dict(conn.execute("SELECT * FROM gates WHERE gate_id=?", (gate_id,)).fetchone())
    if row is None:
        raise LedgerError("gates 表中不存在该 gate_id / gate not in ledger", {"gate_id": gate_id})
    conn.execute("UPDATE gates SET resolved_at=?, resolution=? WHERE gate_id=?", (at, resolution, gate_id))
    add_event(conn, "gate_resolved", actor, {"gate_id": gate_id, "gate_type": row["gate_type"], "resolution": resolution},
              run_id=row["run_id"], app_id=row["app_id"], at=at)
    out = row_to_dict(conn.execute("SELECT * FROM gates WHERE gate_id=?", (gate_id,)).fetchone())
    if out is None:
        raise LedgerError("gate 更新后读不到 / gate missing after update")
    return out


def open_gates(conn: sqlite3.Connection, run_id: str, scope: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM gates WHERE run_id=? AND resolved_at IS NULL"
    params: list[Any] = [run_id]
    if scope:
        sql += " AND scope=?"
        params.append(scope)
    rows = conn.execute(sql + " ORDER BY opened_at", params).fetchall()
    return [r for r in (row_to_dict(x) for x in rows) if r is not None]


# ---- events --------------------------------------------------------------------------------------
def add_event(
    conn: sqlite3.Connection,
    kind: str,
    actor: str,
    payload: dict[str, Any] | None = None,
    *,
    run_id: str | None = None,
    app_id: str | None = None,
    job_id: str | None = None,
    at: str | None = None,
) -> int:
    if kind not in enums.EVENT_KINDS:
        raise UsageError("event kind 不合法 / invalid event kind", {"kind": kind})
    text = _dump(payload)
    if text is not None:
        text = redact(text)
    cur = conn.execute(
        "INSERT INTO events(at, run_id, app_id, job_id, kind, actor, payload) VALUES (?,?,?,?,?,?,?)",
        (at or now_iso(), run_id, app_id, job_id, kind, actor, text),
    )
    return int(cur.lastrowid or 0)


def events(conn: sqlite3.Connection, kinds: tuple[str, ...] | None = None, run_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM events"
    clauses: list[str] = []
    params: list[Any] = []
    if kinds:
        clauses.append("kind IN (%s)" % ",".join("?" * len(kinds)))
        params.extend(kinds)
    if run_id:
        clauses.append("run_id=?")
        params.append(run_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    rows = conn.execute(sql + " ORDER BY at, event_id", params).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = row_to_dict(r)
        if d is not None:
            d["payload"] = _load(d.get("payload"))
            out.append(d)
    return out


# ---- stats & assertions --------------------------------------------------------------------------
def stats(conn: sqlite3.Connection, run_id: str | None = None, today: str | None = None) -> dict[str, Any]:
    where = " WHERE run_id=?" if run_id else ""
    params: tuple[Any, ...] = (run_id,) if run_id else ()
    unique_applied = conn.execute(
        "SELECT COUNT(DISTINCT job_id) AS n FROM applications%s%s status='applied'" % (where, " AND" if where else " WHERE"),
        params,
    ).fetchone()["n"]
    actions = conn.execute("SELECT COALESCE(SUM(submission_action_count),0) AS n FROM applications%s" % where, params).fetchone()["n"]
    by_status = {
        r["status"]: r["n"]
        for r in conn.execute("SELECT status, COUNT(*) AS n FROM applications%s GROUP BY status" % where, params)
    }
    by_platform = {
        r["platform"]: r["n"]
        for r in conn.execute(
            "SELECT platform, COUNT(*) AS n FROM applications%s%s status='applied' GROUP BY platform" % (where, " AND" if where else " WHERE"),
            params,
        )
    }
    by_company = {
        r["company_norm"]: r["n"]
        for r in conn.execute(
            """SELECT j.company_norm, COUNT(DISTINCT a.job_id) AS n FROM applications a JOIN jobs j ON j.job_id=a.job_id
               WHERE a.status='applied'%s GROUP BY j.company_norm ORDER BY n DESC, j.company_norm""" % (" AND a.run_id=?" if run_id else ""),
            params,
        )
    }
    today_str = today or now_iso()[:10]
    today_actions = conn.execute(
        "SELECT COALESCE(SUM(submission_action_count),0) AS n FROM applications WHERE substr(submitted_at,1,10)=?",
        (today_str,),
    ).fetchone()["n"]
    today_applied = conn.execute(
        "SELECT COUNT(DISTINCT job_id) AS n FROM applications WHERE status='applied' AND substr(COALESCE(applied_confirmed_at, submitted_at),1,10)=?",
        (today_str,),
    ).fetchone()["n"]
    open_gates_n = conn.execute(
        "SELECT COUNT(*) AS n FROM gates WHERE resolved_at IS NULL%s" % (" AND run_id=?" if run_id else ""), params
    ).fetchone()["n"]
    jobs_n = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
    return {
        "run_id": run_id,
        "unique_jobs_applied": int(unique_applied),
        "submission_actions": int(actions),
        "duplicates": int(actions) - int(unique_applied),
        "by_status": by_status,
        "applied_by_platform": by_platform,
        "applied_by_company": by_company,
        "today": today_str,
        "today_submission_actions": int(today_actions),
        "today_unique_applied": int(today_applied),
        "open_gates": int(open_gates_n),
        "jobs_total": int(jobs_n),
    }


def run_assertions(conn: sqlite3.Connection, per_company_max: int = enums.DEFAULT_PER_COMPANY_MAX) -> list[str]:
    """ARCHITECTURE §9 assertions. Returns failure descriptions (empty == all pass)."""
    failures: list[str] = []
    n = conn.execute(
        """SELECT COUNT(*) AS n FROM applications a WHERE a.status='applied'
           AND NOT EXISTS (SELECT 1 FROM evidence e WHERE e.app_id=a.app_id AND e.qualifies=1)"""
    ).fetchone()["n"]
    if n:
        failures.append("applied-has-evidence: %d applied application(s) without qualifying evidence" % n)
    bad_q = conn.execute(
        "SELECT COUNT(*) AS n FROM evidence WHERE qualifies=1 AND evidence_type NOT IN (%s)"
        % ",".join("'%s'" % t for t in sorted(enums.QUALIFYING_EVIDENCE_TYPES))
    ).fetchone()["n"]
    if bad_q:
        failures.append("qualifies-only-qualifying-types: %d evidence row(s) qualify with a non-qualifying type" % bad_q)
    s = stats(conn)
    if s["unique_jobs_applied"] > s["submission_actions"]:
        failures.append("unique-vs-actions: unique_jobs_applied %d > submission_actions %d" % (s["unique_jobs_applied"], s["submission_actions"]))
    # no-secrets: scan every text cell
    for table in ("jobs", "applications", "evidence", "gates", "events", "meta"):
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)]
        for row in conn.execute("SELECT * FROM %s" % table):
            for c in cols:
                v = row[c]
                if isinstance(v, str) and find_secret_hits(v):
                    failures.append("no-secrets: %s.%s contains a secret-like pattern" % (table, c))
                    break
    # per-company-cap
    rows = conn.execute(
        """SELECT j.company_norm, COUNT(*) AS n,
                  SUM(CASE WHEN a.approval_json IS NOT NULL AND a.approval_json LIKE '%approval_note%'
                            AND a.approval_json NOT LIKE '%"approval_note": null%' THEN 1 ELSE 0 END) AS noted
           FROM applications a JOIN jobs j ON j.job_id=a.job_id WHERE a.status='applied' GROUP BY j.company_norm"""
    ).fetchall()
    for r in rows:
        if int(r["n"]) > per_company_max and int(r["noted"]) < int(r["n"]) - per_company_max:
            failures.append(
                "per-company-cap: company_norm=%s applied %d > %d without enough approval_note overrides"
                % (r["company_norm"], r["n"], per_company_max)
            )
    return failures


# ---- write audit log (runs/<run_id>/ledger_writes.jsonl) ---------------------------------------
def log_write(paths: DataPaths, run_id: str | None, verb: str, payload: dict[str, Any]) -> None:
    if not run_id:
        return
    run_dir = paths.run_dir(run_id)
    if not run_dir.is_dir():
        return
    line = json.dumps({"at": now_iso(), "verb": verb, "payload": payload}, ensure_ascii=False, sort_keys=True)
    with (run_dir / "ledger_writes.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(redact(line) + "\n")


def ledger_fingerprint(conn: sqlite3.Connection) -> str:
    """Stable hash of ledger content (used by verify to prove export idempotence)."""
    parts: list[str] = []
    for table in ("jobs", "applications", "evidence", "gates", "events"):
        for row in conn.execute("SELECT * FROM %s ORDER BY 1" % table):
            parts.append(json.dumps([row[k] for k in row.keys()], ensure_ascii=False, sort_keys=True))
    return sha256_text("\n".join(parts))

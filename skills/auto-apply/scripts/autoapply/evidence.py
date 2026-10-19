"""Evidence registration and qualification (ARCHITECTURE §7). The ONLY place that sets qualifies=True.

Qualifying types (§7.1): success_page, ats_confirmation_email, employer_confirmation_email,
ats_portal_status (HISTORY decision: portal must show a job-level "Submitted / Application received"
state with URL + screenshot; "under review" alone does not count), legacy_import.
All other types are recorded with qualifies=0 regardless of their content.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autoapply import enums
from autoapply.errors import EvidenceError, UsageError
from autoapply.ids import evidence_id_for, now_iso, sha256_file
from autoapply.ledger import (
    EvidenceRow, add_event, insert_evidence, log_write, next_evidence_seq, require_application, require_job,
)
from autoapply.normalize import fuzzy_ratio, normalize_title
from autoapply.paths import DataPaths
from autoapply.redact import redact

KNOWN_ATS_DOMAINS: tuple[str, ...] = (
    "myworkday.com", "myworkdayjobs.com", "workday.com", "successfactors.com", "successfactors.eu", "sap.com",
    "greenhouse.io", "greenhouse-mail.io", "ashbyhq.com", "smartrecruiters.com", "lever.co", "hire.lever.co",
    "workable.com", "workablemail.com", "jobstreet.com", "jobstreet.com.sg", "seek.com", "seek.com.au",
    "linkedin.com", "mycareersfuture.gov.sg", "icims.com", "taleo.net", "oraclecloud.com", "jobvite.com",
    "bamboohr.com", "recruitee.com", "teamtailor.com", "breezy.hr", "applytojob.com",
)
TEXT_SUFFIXES: frozenset[str] = frozenset({".txt", ".html", ".htm", ".json", ".md", ".eml"})
ALLOWED_SUFFIXES: frozenset[str] = TEXT_SUFFIXES | frozenset({".png", ".jpg", ".jpeg", ".webp", ".pdf"})
PORTAL_SUBMITTED_WORDS: tuple[str, ...] = ("submitted", "application received", "application complete", "applied")
PORTAL_NOT_SUBMITTED_WORDS: tuple[str, ...] = ("draft", "incomplete", "in progress", "not submitted")


@dataclass(frozen=True)
class EvidenceInput:
    evidence_type: str
    captured_by: str = "qa"
    url: str | None = None
    page_title: str | None = None
    source_file: Path | None = None
    job_title_seen: str | None = None
    status_seen: str | None = None
    email_subject: str | None = None
    email_from: str | None = None
    email_received_at: str | None = None
    email_message_id: str | None = None
    email_excerpt: str | None = None
    matched_job_by: str | None = None
    legacy_ref: str | None = None
    notes: str | None = None
    captured_at: str | None = None


@dataclass(frozen=True)
class JobContext:
    company_raw: str
    company_norm: str
    title_raw: str
    title_norm: str
    req_id: str | None = None
    company_domain: str | None = None


@dataclass(frozen=True)
class Decision:
    qualifies: bool
    reasons: tuple[str, ...]
    matched_job_by: str | None = None


def _title_matches(seen: str | None, job: JobContext) -> tuple[bool, str | None]:
    if not seen or not seen.strip():
        return False, None
    if job.req_id and job.req_id.strip() and job.req_id.strip().lower() in seen.lower():
        return True, "req_id"
    try:
        seen_norm = normalize_title(seen)
    except UsageError:
        seen_norm = seen.lower()
    score = max(fuzzy_ratio(seen, job.title_raw), fuzzy_ratio(seen_norm, job.title_norm), _containment(seen, job))
    return score >= enums.EVIDENCE_TITLE_MATCH_THRESHOLD, ("title" if score >= enums.EVIDENCE_TITLE_MATCH_THRESHOLD else None)


def _from_domain_ok(email_from: str | None, job: JobContext) -> bool:
    if not email_from or "@" not in email_from:
        return False
    domain = email_from.rsplit("@", 1)[1].strip().lower().rstrip(">")
    if job.company_domain and (domain == job.company_domain.lower() or domain.endswith("." + job.company_domain.lower())):
        return True
    return any(domain == d or domain.endswith("." + d) for d in KNOWN_ATS_DOMAINS)


def _containment(text: str, job: JobContext) -> float:
    """Share of the job's normalised title tokens that appear in the text (0..1)."""
    try:
        text_tokens = set(normalize_title(text).split())
    except UsageError:
        text_tokens = set(text.lower().split())
    title_tokens = set(job.title_norm.split())
    if not title_tokens:
        return 0.0
    return len(title_tokens & text_tokens) / float(len(title_tokens))


def _subject_mentions_job(subject: str | None, job: JobContext) -> bool:
    if not subject:
        return False
    s = subject.lower()
    if job.req_id and job.req_id.lower() in s:
        return True
    if fuzzy_ratio(subject, job.title_raw) >= enums.EVIDENCE_TITLE_MATCH_THRESHOLD or job.title_norm in s:
        return True
    return _containment(subject, job) >= enums.EVIDENCE_TITLE_MATCH_THRESHOLD


def judge(ev: EvidenceInput, job: JobContext, has_file: bool) -> Decision:
    t = ev.evidence_type
    if t not in enums.EVIDENCE_TYPES:
        raise UsageError("evidence_type 不合法 / invalid evidence_type", {"evidence_type": t, "allowed": list(enums.EVIDENCE_TYPES)})
    if t not in enums.QUALIFYING_EVIDENCE_TYPES:
        return Decision(False, ("type '%s' is not a qualifying evidence type (ARCHITECTURE §7.1)" % t,))
    reasons: list[str] = []
    if t == "success_page":
        if not ev.url:
            reasons.append("success_page requires url")
        if not has_file:
            reasons.append("success_page requires a screenshot or page-text file")
        ok, how = _title_matches(ev.job_title_seen, job)
        if not ok:
            reasons.append("job_title_seen missing or does not match the job title / req_id (>= %.1f)" % enums.EVIDENCE_TITLE_MATCH_THRESHOLD)
        return Decision(not reasons, tuple(reasons) or ("success page with matching job title",), ev.matched_job_by or how)
    if t == "ats_portal_status":
        if not ev.url:
            reasons.append("ats_portal_status requires url")
        if not has_file:
            reasons.append("ats_portal_status requires a screenshot")
        ok, how = _title_matches(ev.job_title_seen, job)
        if not ok:
            reasons.append("job_title_seen missing or does not match the job title / req_id")
        status_text = " ".join(x for x in (ev.status_seen, ev.page_title, ev.notes) if x).lower()
        if not any(w in status_text for w in PORTAL_SUBMITTED_WORDS) or any(w in status_text for w in PORTAL_NOT_SUBMITTED_WORDS):
            reasons.append("portal status must show a job-level Submitted / Application received state (--status-seen)")
        return Decision(not reasons, tuple(reasons) or ("candidate portal lists the job as submitted",), ev.matched_job_by or how)
    if t in ("ats_confirmation_email", "employer_confirmation_email"):
        for name, val in (("email_subject", ev.email_subject), ("email_from", ev.email_from), ("email_received_at", ev.email_received_at)):
            if not val:
                reasons.append("%s requires %s" % (t, name))
        domain_ok = _from_domain_ok(ev.email_from, job)
        subject_ok = _subject_mentions_job(ev.email_subject, job)
        if not domain_ok and not subject_ok:
            reasons.append("sender domain must match the company / a known ATS domain, or the subject must name the job")
        how = ev.matched_job_by or ("company_domain" if domain_ok and not subject_ok else "title")
        return Decision(not reasons, tuple(reasons) or ("job-level confirmation email",), how)
    if t == "legacy_import":
        if not ev.legacy_ref:
            reasons.append("legacy_import requires legacy_ref")
        return Decision(not reasons, tuple(reasons) or ("imported from the legacy ledger (already confirmed there)",), ev.matched_job_by or "manual")
    return Decision(False, ("unhandled type",))


def register_evidence(conn: sqlite3.Connection, paths: DataPaths, app_id: str, ev: EvidenceInput) -> dict[str, Any]:
    app = require_application(conn, app_id)
    job_row = require_job(conn, app["job_id"])
    job = JobContext(
        company_raw=job_row["company_raw"], company_norm=job_row["company_norm"], title_raw=job_row["title_raw"],
        title_norm=job_row["title_norm"], req_id=job_row["req_id"], company_domain=job_row["company_domain"],
    )
    seq = next_evidence_seq(conn, app_id)
    evidence_id = evidence_id_for(app_id, seq)
    stored_rel: str | None = None
    digest: str | None = None
    if ev.source_file is not None:
        src = ev.source_file
        if not src.is_file():
            raise EvidenceError("证据文件不存在 / evidence file not found", {"file": str(src)})
        suffix = src.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise EvidenceError("证据文件类型不支持 / unsupported evidence file type", {"suffix": suffix, "allowed": sorted(ALLOWED_SUFFIXES)})
        dest_dir = paths.evidence_dir / app_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / ("%02d_%s%s" % (seq, ev.evidence_type, suffix))
        if suffix in TEXT_SUFFIXES:
            text = src.read_text(encoding="utf-8", errors="replace")
            dest.write_text(redact(text), encoding="utf-8")  # raises on secrets (ARCHITECTURE §7.3)
        else:
            shutil.copyfile(str(src), str(dest))
        stored_rel = "%s/%s" % (app_id, dest.name)
        digest = sha256_file(dest)
    decision = judge(ev, job, has_file=stored_rel is not None)
    excerpt = redact(ev.email_excerpt)[:300] if ev.email_excerpt else None
    notes = ev.notes or ""
    if ev.status_seen:
        notes = ("status_seen: %s" % ev.status_seen) + ("\n" + notes if notes else "")
    notes = redact(notes) if notes else ""
    notes = (notes + ("\n" if notes else "") + "judge: " + "; ".join(decision.reasons)).strip()
    row = EvidenceRow(
        evidence_id=evidence_id, app_id=app_id, evidence_type=ev.evidence_type, qualifies=decision.qualifies,
        captured_at=ev.captured_at or now_iso(), captured_by=ev.captured_by, url=ev.url, page_title=ev.page_title,
        file=stored_rel, sha256=digest, job_title_seen=ev.job_title_seen, email_subject=ev.email_subject,
        email_from=ev.email_from, email_received_at=ev.email_received_at, email_message_id=ev.email_message_id,
        email_excerpt=excerpt, matched_job_by=decision.matched_job_by if decision.qualifies else ev.matched_job_by,
        legacy_ref=ev.legacy_ref, notes=notes,
    )
    stored = insert_evidence(conn, row, actor=ev.captured_by)
    stored["judge_reasons"] = list(decision.reasons)
    log_write(paths, app["run_id"], "evidence", {"app_id": app_id, "evidence_id": evidence_id,
                                                 "evidence_type": ev.evidence_type, "qualifies": decision.qualifies})
    return stored


def refuse_password_in_chat(conn: sqlite3.Connection, run_id: str | None, actor: str = "orchestrator") -> int:
    """SECURITY §3: record that a password was refused. Never stores content."""
    return add_event(conn, "password_in_chat_refused", actor, {"note": "content not recorded"}, run_id=run_id)

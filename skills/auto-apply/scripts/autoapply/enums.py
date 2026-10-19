"""Central enum definitions. Values are copied verbatim from schemas/*.json and ARCHITECTURE §2.3 / §9.

No other module may spell these literals. Keep in sync with the schemas (schema wins on conflict).
"""

from __future__ import annotations

PLATFORMS: tuple[str, ...] = (
    "jobstreet", "linkedin_easy_apply", "linkedin_external", "mycareersfuture", "workday",
    "successfactors", "greenhouse", "ashby", "smartrecruiters", "lever", "workable",
    "company_custom", "email", "other", "unknown",
)

CHANNELS: tuple[str, ...] = ("company_site", "linkedin", "jobstreet", "mycareersfuture", "email", "other")

SOURCE_TYPES: tuple[str, ...] = (
    "user_list", "user_link", "site_search", "recommendation", "referral", "legacy_import", "other",
)

APP_STATUSES: tuple[str, ...] = (
    "queued", "in_progress", "draft_saved", "pending_user", "ready_to_submit",
    "submitted_unverified", "applied", "skipped", "failed", "withdrawn", "abandoned",
)

TRACKING_STATUSES: tuple[str, ...] = (
    "none", "receipt", "under_review", "assessment", "interview", "offer", "rejected", "closed",
)

SKIP_REASON_CODES: tuple[str, ...] = (
    "date_window_mismatch", "degree_mismatch", "salary_below_floor", "unpaid", "already_applied",
    "blacklist", "reserve_for_referral", "global_quota", "industry_excluded", "title_excluded",
    "id_number_required", "payment_required", "resume_language_missing", "unknown_required_field",
    "quota_reached", "job_closed", "user_excluded", "work_pass_mismatch", "start_immediately", "other",
)

EVIDENCE_TYPES: tuple[str, ...] = (
    "success_page", "ats_confirmation_email", "employer_confirmation_email", "ats_portal_status",
    "legacy_import", "review_page_screenshot", "form_completed_screenshot", "draft_saved",
    "account_verification_email", "external_redirect", "open_tab", "generic_ack_email",
)

# ARCHITECTURE §7.1 — the only evidence types that can make an application `applied`.
QUALIFYING_EVIDENCE_TYPES: frozenset[str] = frozenset({
    "success_page", "ats_confirmation_email", "employer_confirmation_email", "ats_portal_status",
    "legacy_import",
})

# schemas/application.schema.json evidence.matched_job_by — how the evidence was tied to the job.
EVIDENCE_MATCHED_BY: tuple[str, ...] = ("title", "req_id", "company_domain", "manual")

GATE_TYPES: tuple[str, ...] = (
    "password_or_signup", "captcha", "otp", "email_verification_link", "id_number", "payment",
    "personal_declaration", "final_submit", "content_approval", "resume_missing_language",
    "unknown_required_field", "file_upload_blocked", "session_expired", "dedup_review",
    "queue_approval", "consistency_mismatch", "browser_disconnected", "quota_exhausted",
)

# ARCHITECTURE §3.1 — default scope per gate type; run-scoped gates suspend the whole run.
RUN_SCOPED_GATE_TYPES: frozenset[str] = frozenset({
    "queue_approval", "consistency_mismatch", "browser_disconnected", "quota_exhausted",
})

GATE_SCOPES: tuple[str, ...] = ("item", "run")
GATE_MODES: tuple[str, ...] = ("sync", "async")
GATE_RESOLUTIONS: tuple[str, ...] = ("resolved", "skipped", "user_completed", "expired", "abandoned")
PENDING_STATUSES: tuple[str, ...] = ("open", "resolved", "skipped", "user_completed", "expired", "abandoned")
PRIORITIES: tuple[str, ...] = ("high", "normal", "low")
RUNTIMES: tuple[str, ...] = ("claude_code", "codex")
GATE_MODE_POLICIES: tuple[str, ...] = ("interactive", "batch")
RUN_INVOCATIONS: tuple[str, ...] = ("apply", "status", "report")

EVENT_KINDS: tuple[str, ...] = (
    "run_started", "phase_change", "candidate_added", "screened", "queued", "apply_started",
    "draft_saved", "submit_clicked", "applied", "submitted_unverified", "skipped", "failed",
    "gate_opened", "gate_resolved", "evidence_added", "tracking_update", "status_change",
    "quota_switch", "browser_disconnected", "browser_recovered", "password_in_chat_refused",
    "legacy_imported", "export", "report", "note",
)

PHASES: tuple[str, ...] = (
    "onboard", "intake", "source", "screen", "apply", "verify", "ledger", "track", "report",
    "done", "pending_user", "aborted",
)

TERMINAL_PHASES: frozenset[str] = frozenset({"done", "aborted"})

# ARCHITECTURE §2.3 — legal transitions. pending_user additionally allows <resume_to>.
TRANSITIONS: dict[str, frozenset[str]] = {
    "onboard": frozenset({"intake", "source", "aborted"}),
    "intake": frozenset({"source", "pending_user", "aborted"}),
    "source": frozenset({"screen", "report", "pending_user", "aborted"}),
    "screen": frozenset({"pending_user", "apply", "report", "aborted"}),
    "apply": frozenset({"verify", "ledger", "pending_user", "aborted"}),
    "verify": frozenset({"ledger", "pending_user", "aborted"}),
    "ledger": frozenset({"apply", "track", "report", "pending_user", "aborted"}),
    "track": frozenset({"report", "pending_user", "aborted"}),
    "report": frozenset({"done", "aborted"}),
    "pending_user": frozenset({"report", "aborted"}),
    "done": frozenset(),
    "aborted": frozenset(),
}

# ARCHITECTURE §6.4 — application statuses that make a job count as "already applied" for dedup.
DEDUP_HIT_STATUSES: frozenset[str] = frozenset({"applied", "submitted_unverified", "pending_user", "draft_saved"})

# ARCHITECTURE §5.6 — section 2 of the export.
EXPORT_INTERMEDIATE_STATUSES: frozenset[str] = frozenset({
    "pending_user", "draft_saved", "submitted_unverified", "failed", "abandoned",
})
EXPORT_INTERMEDIATE_SKIP_REASONS: frozenset[str] = frozenset({
    "id_number_required", "resume_language_missing", "unknown_required_field", "date_window_mismatch",
})
EXPORT_TRACKING_EVENT_KINDS: tuple[str, ...] = ("applied", "status_change", "tracking_update", "gate_opened", "skipped")

# Title placeholder for legacy entries that only recorded the company (migrate_legacy); dedup treats a
# company with such an entry as "review" for any new title at that company.
LEGACY_UNKNOWN_TITLE = "[legacy: title not recorded]"

DEFAULT_PER_COMPANY_MAX = 3
DEFAULT_PER_ROUND = 10
DEFAULT_PER_DAY = 20
DEFAULT_PENDING_EXPIRY_DAYS = 7
DEDUP_JACCARD_THRESHOLD = 0.8
EVIDENCE_TITLE_MATCH_THRESHOLD = 0.6

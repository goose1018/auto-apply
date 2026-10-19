"""Exception hierarchy (CODE_STANDARDS §5). Messages must never contain personal data."""

from __future__ import annotations

from typing import Any


class AutoApplyError(Exception):
    """Base class. `code` is machine readable, `exit_code` follows CODE_STANDARDS §5."""

    code: str = "autoapply_error"
    exit_code: int = 1

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail: dict[str, Any] = detail or {}

    def to_json(self) -> dict[str, Any]:
        return {"error": self.code, "detail": self.message, **({"data": self.detail} if self.detail else {})}


class ConfigError(AutoApplyError):
    code = "config_error"
    exit_code = 2


class UsageError(AutoApplyError):
    code = "usage_error"
    exit_code = 2


class SchemaError(AutoApplyError):
    code = "schema_error"
    exit_code = 3


class ProfileError(AutoApplyError):
    code = "profile_error"
    exit_code = 3


class LedgerError(AutoApplyError):
    code = "ledger_error"
    exit_code = 3


class EvidenceError(AutoApplyError):
    code = "evidence_error"
    exit_code = 3


class GateError(AutoApplyError):
    code = "gate_error"
    exit_code = 2


class RunStateError(AutoApplyError):
    code = "runstate_error"
    exit_code = 2


class RedactionError(AutoApplyError):
    code = "redaction_error"
    exit_code = 3


class MigrationError(AutoApplyError):
    code = "migration_error"
    exit_code = 3


class AssertionFailed(AutoApplyError):
    """A business assertion (ledger assert, consistency block) failed."""

    code = "assertion_failed"
    exit_code = 1

"""Candidate ingestion and dedup checks (R1, ARCHITECTURE §6.4). Business layer.

- normalize_job_obj: fill company.normalized / title.normalized / dedup_key / job_id from raw values;
  values already present must agree with the computed ones (fail loud otherwise).
- check_job: decision for one (company, title) against the ledger: new | dedup_hit | dedup_review | seen.
- add_candidates: validate every line of candidates.jsonl, upsert jobs, return a dedup report.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoapply import enums
from autoapply.errors import LedgerError, SchemaError, UsageError
from autoapply.ids import now_iso
from autoapply.ledger import (
    JobRecord, add_event, applications_for_job, get_job, jobs_by_company_norm, log_write, upsert_job,
)
from autoapply.normalize import DedupKey, is_generic_title, make_dedup_key, normalize_title, title_similarity
from autoapply.paths import DataPaths
from autoapply.schema_validate import SchemaSet


@dataclass(frozen=True)
class DedupMatch:
    job_id: str
    company_raw: str
    title_raw: str
    title_norm: str
    similarity: float
    statuses: tuple[str, ...]


@dataclass
class CheckResult:
    company_norm: str
    title_norm: str
    dedup_key: str
    job_id: str
    decision: str  # new | dedup_hit | dedup_review | seen
    reason: str
    existing_job: dict[str, Any] | None = None
    applications: list[dict[str, Any]] = field(default_factory=list)
    similar: list[DedupMatch] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_norm": self.company_norm, "title_norm": self.title_norm, "dedup_key": self.dedup_key,
            "job_id": self.job_id, "decision": self.decision, "reason": self.reason,
            "existing_job": {k: self.existing_job[k] for k in ("job_id", "company_raw", "title_raw", "platform", "first_seen_at")} if self.existing_job else None,
            "applications": [{k: a[k] for k in ("app_id", "status", "channel", "platform", "submission_action_count", "run_id")} for a in self.applications],
            "similar": [m.__dict__ for m in self.similar],
        }


@dataclass
class DedupReport:
    added: list[dict[str, Any]] = field(default_factory=list)
    existing: list[dict[str, Any]] = field(default_factory=list)
    suspected: list[dict[str, Any]] = field(default_factory=list)
    lines_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"lines_total": self.lines_total, "added": self.added, "existing": self.existing, "suspected": self.suspected,
                "counts": {"added": len(self.added), "existing": len(self.existing), "suspected": len(self.suspected)}}


def load_aliases(paths: DataPaths) -> dict[str, str]:
    p = paths.dedup_aliases_json
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise UsageError("dedup_aliases.json 不是合法 JSON / corrupt aliases file") from e
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise UsageError("dedup_aliases.json 必须是 {string: string} / aliases must map strings to strings")
    return {k.strip().lower(): v.strip().lower() for k, v in data.items()}


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if not path.is_file():
        raise UsageError("文件不存在 / file not found", {"path": str(path)})
    out: list[tuple[int, dict[str, Any]]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            raise SchemaError("第 %d 行不是合法 JSON / line %d is not valid JSON" % (n, n), {"line": n}) from e
        if not isinstance(obj, dict):
            raise SchemaError("第 %d 行不是对象 / line %d is not an object" % (n, n), {"line": n})
        out.append((n, obj))
    return out


def normalize_job_obj(obj: dict[str, Any], aliases: dict[str, str], line: int = 0) -> dict[str, Any]:
    company = obj.get("company")
    title = obj.get("title")
    if isinstance(company, str):
        company = {"raw": company}
    if isinstance(title, str):
        title = {"raw": title}
    if not isinstance(company, dict) or not isinstance(company.get("raw"), str):
        raise SchemaError("第 %d 行缺 company.raw / line %d missing company.raw" % (line, line), {"line": line})
    if not isinstance(title, dict) or not isinstance(title.get("raw"), str):
        raise SchemaError("第 %d 行缺 title.raw / line %d missing title.raw" % (line, line), {"line": line})
    key = make_dedup_key(str(company["raw"]), str(title["raw"]), aliases)
    out = dict(obj)
    out["company"] = {**company, "normalized": key.company_norm}
    out["title"] = {**title, "normalized": key.title_norm}
    for name, got, want in (
        ("company.normalized", company.get("normalized"), key.company_norm),
        ("title.normalized", title.get("normalized"), key.title_norm),
        ("dedup_key", obj.get("dedup_key"), key.key),
        ("job_id", obj.get("job_id"), key.job_id),
    ):
        if got not in (None, "") and got != want:
            raise SchemaError(
                "第 %d 行 %s 与脚本计算值不一致（以脚本为准，请用 `jobs normalize` 重生成）/ line %d: %s disagrees with computed value"
                % (line, name, line, name),
                {"line": line, "field": name, "computed": want},
            )
    out["dedup_key"] = key.key
    out["job_id"] = key.job_id
    return out


def job_record_from_obj(obj: dict[str, Any], seen_at: str | None = None) -> JobRecord:
    company = obj["company"]
    title = obj["title"]
    source = obj.get("source") or {}
    match = obj.get("match") or {}
    return JobRecord(
        job_id=str(obj["job_id"]), dedup_key=str(obj["dedup_key"]), company_raw=str(company["raw"]),
        company_norm=str(company["normalized"]), title_raw=str(title["raw"]), title_norm=str(title["normalized"]),
        platform=str(obj["platform"]), source_type=str(source.get("type", "other")), channel=obj.get("channel"),
        url=obj.get("url"), apply_url=obj.get("apply_url"), req_id=obj.get("req_id"), location=obj.get("location"),
        company_domain=company.get("domain"), source_ref=source.get("ref"), source_added_by=source.get("added_by"),
        posted_at=obj.get("posted_at"), closes_at=obj.get("closes_at"), jd_summary=obj.get("jd_summary"),
        jd_hash=obj.get("jd_hash"), hard_conditions=obj.get("hard_conditions"), match_score=match.get("score"),
        match_json=match or None, risks=list(obj.get("risks") or []), screening=obj.get("screening"),
        notes=obj.get("notes"), seen_at=seen_at or obj.get("discovered_at"),
    )


def check_key(conn: sqlite3.Connection, key: DedupKey) -> CheckResult:
    existing = get_job(conn, key.job_id)
    apps = applications_for_job(conn, key.job_id) if existing else []
    hit = [a for a in apps if a["status"] in enums.DEDUP_HIT_STATUSES]
    similar: list[DedupMatch] = []
    legacy_unknown_norm = normalize_title(enums.LEGACY_UNKNOWN_TITLE)
    for other in jobs_by_company_norm(conn, key.company_norm):
        if other["job_id"] == key.job_id:
            continue
        sim = title_similarity(key.title_norm, str(other["title_norm"]))
        if str(other["title_norm"]) == legacy_unknown_norm:
            sim = max(sim, enums.DEDUP_JACCARD_THRESHOLD)  # company applied before, title unknown -> review
        if sim >= enums.DEDUP_JACCARD_THRESHOLD:
            statuses = tuple(sorted({str(a["status"]) for a in applications_for_job(conn, str(other["job_id"]))}))
            similar.append(DedupMatch(str(other["job_id"]), str(other["company_raw"]), str(other["title_raw"]),
                                      str(other["title_norm"]), round(sim, 3), statuses))
    similar.sort(key=lambda m: -m.similarity)
    if hit:
        # 泛化残根保护：标题规范化后只剩通用词（"intern" 等）时，不同岗位会撞成同一个键。
        # 原始标题不同就降级为 dedup_review 交人确认，避免把没投过的岗位误判为已投。
        stored_raw = str(existing["title_raw"]).strip().lower() if existing else ""
        if is_generic_title(key.title_norm) and stored_raw and stored_raw != key.title_raw.strip().lower():
            decision = "dedup_review"
            reason = ("generic title stub %r: same dedup key but different raw titles (%r vs %r) — confirm before skipping"
                      % (key.title_norm, existing["title_raw"], key.title_raw))
        else:
            decision, reason = "dedup_hit", "already_applied: %s" % ", ".join(sorted({a["status"] for a in hit}))
    elif any(any(s in enums.DEDUP_HIT_STATUSES for s in m.statuses) for m in similar):
        decision, reason = "dedup_review", "same company, similar title already applied (>= %.1f)" % enums.DEDUP_JACCARD_THRESHOLD
    elif existing:
        prior = sorted({a["status"] for a in apps}) or ["no application"]
        decision, reason = "seen", "job known in ledger, prior status: %s" % ", ".join(prior)
    elif similar:
        decision, reason = "dedup_review", "same company, similar title seen before (not applied)"
    else:
        decision, reason = "new", "no match in ledger"
    return CheckResult(key.company_norm, key.title_norm, key.key, key.job_id, decision, reason, existing, apps, similar)


def check_company_title(conn: sqlite3.Connection, paths: DataPaths, company: str, title: str) -> CheckResult:
    return check_key(conn, make_dedup_key(company, title, load_aliases(paths)))


def add_candidates(conn: sqlite3.Connection, paths: DataPaths, schemas: SchemaSet, candidates: Path,
                   run_id: str | None = None) -> DedupReport:
    aliases = load_aliases(paths)
    report = DedupReport()
    rows = read_jsonl(candidates)
    report.lines_total = len(rows)
    normalized: list[tuple[int, dict[str, Any]]] = []
    for n, obj in rows:
        fixed = normalize_job_obj(obj, aliases, n)
        if run_id and not fixed.get("run_id"):
            fixed["run_id"] = run_id
        fixed.setdefault("discovered_at", now_iso())
        res = schemas.check("job", fixed)
        if not res.ok:
            raise SchemaError("candidates 第 %d 行不符合 job schema / line %d fails job schema" % (n, n),
                              {"line": n, "errors": res.errors[:20]})
        normalized.append((n, fixed))
    seen_in_file: dict[str, int] = {}
    for n, obj in normalized:
        key = make_dedup_key(str(obj["company"]["raw"]), str(obj["title"]["raw"]), aliases)
        check = check_key(conn, key)
        entry = {"line": n, "job_id": key.job_id, "company": obj["company"]["raw"], "title": obj["title"]["raw"],
                 "decision": check.decision, "reason": check.reason,
                 "similar": [m.__dict__ for m in check.similar[:3]]}
        if key.job_id in seen_in_file:
            entry["reason"] = "duplicate of line %d in the same file (same dedup_key)" % seen_in_file[key.job_id]
            entry["decision"] = "dedup_hit" if check.decision == "dedup_hit" else "seen"
        seen_in_file.setdefault(key.job_id, n)
        try:
            upsert_job(conn, job_record_from_obj(obj))
        except LedgerError:
            raise
        add_event(conn, "candidate_added", "sourcing",
                  {"job_id": key.job_id, "company": obj["company"]["raw"], "title": obj["title"]["raw"],
                   "platform": obj.get("platform"), "source": (obj.get("source") or {}).get("type"), "decision": check.decision},
                  run_id=obj.get("run_id"), job_id=key.job_id)
        if check.decision == "new":
            report.added.append(entry)
        elif check.decision in ("dedup_hit",):
            report.existing.append(entry)
        elif check.decision == "dedup_review":
            report.suspected.append(entry)
        else:
            report.existing.append(entry)
    log_write(paths, run_id, "jobs_add", {"file": candidates.name, "counts": report.to_dict()["counts"]})
    return report


def write_normalized_jsonl(src: Path, dest: Path, aliases: dict[str, str], run_id: str | None = None) -> int:
    rows = read_jsonl(src)
    lines: list[str] = []
    for n, obj in rows:
        fixed = normalize_job_obj(obj, aliases, n)
        if run_id and not fixed.get("run_id"):
            fixed["run_id"] = run_id
        fixed.setdefault("discovered_at", now_iso())
        lines.append(json.dumps(fixed, ensure_ascii=False, sort_keys=True))
    dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)

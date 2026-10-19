"""Fictional fixtures for verify scripts. Every person, email, phone and company here is invented
(CODE_STANDARDS §9): Alex Tan / alex.tan@example.com / +65 0000 1234 / Example Robotics Pte Ltd."""

from __future__ import annotations

from pathlib import Path
from typing import Any

FAKE_RUN_ID_PATTERN = r"^run_[0-9]{8}_[0-9]{6}$"


def profile(resume_path: Path, *, submit_mode: str = "confirm", per_company_max: int = 3, per_round: int = 10,
            per_day: int = 20, blacklist: list[str] | None = None, reserve: list[str] | None = None) -> dict[str, Any]:
    return {
        "meta": {"profile_id": "verify_user", "language": "zh", "created_at": "2026-09-01T10:00:00+08:00",
                 "updated_at": None, "version": "1", "runtime": "claude_code", "intake_signed_at": "2026-09-01T11:00:00+08:00"},
        "identity": {
            "name": {"full": "Alex Tan", "given": "Alex", "family": "Tan", "native": None, "name_order": "given_first", "preferred": "Alex"},
            "emails": {"primary": "alex.tan@example.com", "signup": None, "others": ["alex.old@example.sg"]},
            "phones": [{"country_code": "+65", "number": "0000 1234", "label": "sg", "is_default": True}],
            "gender": None, "date_of_birth": None,
            "address": {"country": "Singapore", "city": "Singapore", "line1": None, "postal_code": None},
        },
        "status": {"nationality": "Example", "country_of_residence": "Singapore", "work_pass": "student_pass",
                   "work_pass_other_label": None, "work_pass_expiry": None, "authorised_to_work_in_sg": True,
                   "requires_sponsorship_now": False, "requires_sponsorship_future": True,
                   "internship_nature": "credit_bearing", "work_pass_exempt_for_internship": True,
                   "school_can_issue_letter": True, "notes": None},
        "education": [
            {"institution": "Example University", "faculty": None, "major": "Computer Science", "degree": "master",
             "degree_title": "MSc Computer Science", "start": "2025-08", "end_expected": "2027-06", "is_current": True,
             "gpa": None, "rank_or_honours": None, "location": "Singapore", "confirmed_by_user": True},
            {"institution": "Example College", "faculty": None, "major": "Engineering", "degree": "bachelor",
             "degree_title": None, "start": "2021-09", "end_expected": "2025-06", "is_current": False,
             "gpa": None, "rank_or_honours": None, "location": None, "confirmed_by_user": True},
        ],
        "experience": [
            {"kind": "internship", "organisation": "Example Software Ltd", "title": "Software Intern", "start": "2024-06",
             "end": "2024-09", "is_current": False, "location": "Singapore", "bullets": ["Built an internal tool used by 12 people."],
             "source": "resume", "confirmed_by_user": True}
        ],
        "skills": {"languages_spoken": [{"name": "English", "level": "fluent"}], "tools": ["Python"], "certifications": [], "other": []},
        "intent": {"types": ["internship"], "keywords": ["ai", "data"], "excluded_directions": ["sales"],
                   "locations": ["Singapore"], "remote_ok": None, "relocation_ok": None,
                   "window": {"start": "2027-01", "end": "2027-06", "flexibility_weeks": 4},
                   "hours_per_week": None, "min_commitment_months": 5, "earliest_start": None,
                   "term_time_vs_vacation_notes": None, "degree_level_targets": ["master", "any"],
                   "apply_to_bachelor_only_postings": False},
        "salary": {"currency": "SGD", "period": "month", "expected_min": 1500, "expected_max": 3000, "hard_floor": 1500,
                   "apply_if_undisclosed": True, "allow_unpaid": False, "negotiable": True, "notes": None},
        "rules": {
            "company_blacklist": [{"name": n, "reason": "test", "until": None} for n in (blacklist or ["Blocked Corp"])],
            "industry_exclusions": ["gambling"], "title_exclusions": ["Sales Executive"],
            "reserve_for_referral": [{"name": n, "reason": "referral", "until": None} for n in (reserve or ["Referral Labs"])],
            "global_quota_rule": {"mode": "skip_if_in_reserve_list", "notes": None},
            "per_company_max": per_company_max, "per_round": per_round, "per_day": per_day,
            "channel_priority": ["company_site", "jobstreet", "linkedin"], "existing_accounts": [], "legacy_ledger_imported": None,
        },
        "materials": {"resumes": [{"path": str(resume_path), "language": "en", "label": "english_default", "version": "v1",
                                   "is_default": True, "sha256": None, "known_mismatches": [], "notes": None}],
                      "portfolio_url": None, "github_url": None, "linkedin_url": "https://www.linkedin.com/in/alex-tan-example",
                      "website_url": None, "transcript_path": None, "cover_letter_template_path": None, "certificates": []},
        "policy": {"submit_mode": submit_mode,
                   "autopilot_consent": {"enabled_at": "2026-09-01T11:00:00+08:00", "statement": "I authorise autopilot submission for this test profile."} if submit_mode == "autopilot" else None,
                   "gate_mode": "interactive", "open_question_policy": "approve", "cover_letter_policy": "approve",
                   "allow_ai_self_intro": False, "eeo_default": "prefer_not_to_say",
                   "declarations": {"criminal_record": "no", "bankruptcy": None, "vaccination_status": None,
                                    "relatives_in_company": "no", "previously_applied_or_employed": None, "non_compete": None,
                                    "background_check_consent": None, "data_processing_consent": "yes", "other": []},
                   "mail_readonly_consent": True, "mail_backend_preference": "webmail", "allow_verification_link_click": False,
                   "report_every_n": 5, "platform_tos_acknowledged": True, "pending_item_expiry_days": 7},
    }


def resume_parse(resume_path: Path, *, email: str = "alex.tan@example.com", phone: str = "0000 1234",
                 expected: str = "2027-06", name: str = "Alex Tan") -> dict[str, Any]:
    return {"resume_path": str(resume_path), "sha256": "0" * 64, "parsed_at": "2026-09-01T10:30:00+08:00",
            "parsed": {"full_name": name, "emails": [email], "phones": [{"country_code": "+65", "number": phone}],
                       "graduation": {"institution": "Example University", "degree": "MSc", "expected": expected},
                       "linkedin_url": "https://linkedin.com/in/alex-tan-example", "location": "Singapore"}}


def facts_card(signed: bool = True) -> dict[str, Any]:
    return {
        "meta": {"profile_id": "verify_user", "generated_at": "2026-09-01T10:00:00+08:00", "updated_at": None, "version": "1",
                 "language": "zh", "signed_by_user": signed, "signed_at": "2026-09-01T11:00:00+08:00" if signed else None,
                 "resume_sha256": []},
        "facts": [
            {"fact_id": "f_001", "category": "education", "statement": "2025 年 8 月起在 Example University 攻读 MSc Computer Science，预计 2027 年 6 月毕业。",
             "statement_en": "MSc Computer Science at Example University since Aug 2025, expected June 2027.",
             "source": {"type": "resume", "ref": "resume p1"}, "status": "confirmed",
             "user_signature": {"signed": True, "signed_at": "2026-09-01T11:00:00+08:00", "note": None},
             "usable_in_open_answers": True, "sensitivity": "public", "quantified": False},
            {"fact_id": "f_002", "category": "experience", "statement": "2024 年 6–9 月在 Example Software Ltd 实习，开发了 12 人使用的内部工具。",
             "statement_en": None, "source": {"type": "resume", "ref": "resume p1"}, "status": "confirmed",
             "user_signature": None, "usable_in_open_answers": True, "sensitivity": "standard", "quantified": True},
            {"fact_id": "f_003", "category": "work_permit", "statement": "持 Student's Pass，学分实习期间免工作准证。", "statement_en": None,
             "source": {"type": "user_stated", "ref": "round 2"}, "status": "draft", "user_signature": None,
             "usable_in_open_answers": False, "sensitivity": "restricted", "quantified": None},
        ],
        "forbidden_claims": ["不得声称有全职工作经验 / never claim full-time work experience"],
    }


def candidate(company: str, title: str, *, platform: str = "greenhouse", channel: str = "company_site",
              run_id: str = "run_20260905_100000", url: str | None = None, hard: dict[str, Any] | None = None,
              screening: dict[str, Any] | None = None, closes_at: str | None = None, req_id: str | None = None,
              domain: str | None = None) -> dict[str, Any]:
    obj: dict[str, Any] = {
        "company": {"raw": company, "domain": domain}, "title": {"raw": title},
        "url": url or "https://jobs.example.com/%s/%s" % (company.lower().replace(" ", "-"), title.lower().replace(" ", "-")),
        "apply_url": None, "req_id": req_id, "platform": platform, "channel": channel,
        "source": {"type": "user_list", "ref": "list.md:1", "added_by": "sourcing"},
        "location": "Singapore", "posted_at": None, "closes_at": closes_at,
        "jd_summary": "Fictional posting used by verify scripts.", "jd_hash": None,
        "hard_conditions": hard, "match": None, "risks": [], "screening": screening,
        "discovered_at": "2026-09-05T10:00:00+08:00", "run_id": run_id, "notes": None,
    }
    return obj


LEGACY_MD = """# 求职投递台账（防重复主清单）

> 建立日期：2026-08-25。虚构测试数据，所有公司与岗位均为编造。
> 口径：只有「明确成功页 / 雇主确认邮件」才算已投。

## 一、已确认投递（禁止重复）

### 早期批次（2026-08-05 ~ 08-08，约 5 份）
- Example Robotics Pte Ltd — AI Engineer Intern（Jobstreet，成功页 /job/93624878/apply/success）
- Sample Systems — [Uni – Jan till Jun 2027] Agentic AI Intern（SmartRecruiters）
- Demo Semiconductor — AI, Automation & Database（#55）/ Data Scientist & Automation（#56）/ AI Solutions & Analytics（#77）
- Jobstreet 快速申请批（3 封回执，含）：Alpha Logistics、Beta Transit、Gamma Capital（岗位已关闭但申请保留）等
- 邮件投递：Delta AI — AI Application Engineer Intern；Epsilon Media（收到自动回复）；Zeta Group — AI-Powered BD Intern

### 大批次（2026-08-13 ~ 08-15，编号 1–6）
1. Sample Systems（官网+LinkedIn 有同名重复提交）：GenAI SWE、Agentic AI、AI Engineer (Middleware)、SWE (Low Code) —— **Sample Systems 全线视为已覆盖，不再新投**
2. Omega Retail — Data Analyst Intern Spring 2027；Ad Tech Operations Intern
3. Demo Semiconductor — AI Solutions & Analytics (HRC1666025)；AI Engineer (HRC1714354)（注意：累计已 5 份）
4. Theta Bank — Services Summer Analyst SG 2027 (26978591)
5. Iota Labs — Quantitative Developer Intern (Python)（Greenhouse 验证码后确认）
6. Kappa Insurance — AI Builder Intern (134401)

## 二、未投但有中间状态（重投前需先查状态）
- Lambda Holdings — Generative AI Intern：账号已建未激活（邮箱激活链接），待本人激活后可投
- Mu Fintech：要求 NRIC/FIN，未授权，跳过
- Nu Consulting — Strategy Analyst Intern：注册到 41%，卡在高中学历细节（不编造），草稿保留
- Xi Tech / Pi Systems 等：日期冲突已跳过
- Rho Corp：要求立即到岗，已放弃

## 三、既定投递规则（Codex 沿用，继续有效）
- 目标：新加坡，2027-01 ~ 2027-06 实习
- 新表单联系邮箱默认 **someone@example.com**（虚构，用于验证本节被跳过）

## 四、状态追踪表（新投递与状态变化只在这里追加）

| 日期 | 公司 | 岗位 | 渠道 | 状态 | 证据/备注 |
|---|---|---|---|---|---|
| 2026-08-25 | Lambda Holdings | Generative AI Citizen Developer Intern (Req 12170, Jan–Jun 2027) | SuccessFactors | **草稿已保存，未提交** | 表单填完并 Save 成功；点 Apply 后 CSRF 失效 |
| 2026-08-26 | Sigma Games | Product Intern | Jobstreet | 已投（成功页） | /job/12345678/apply/success |
| 2026-08-27 | Omega Retail | Data Analyst Intern Spring 2027 | 官网 | 简历筛选中 | 我的投递页实时状态 |
"""

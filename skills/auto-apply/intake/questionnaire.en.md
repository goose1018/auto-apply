# Intake questionnaire (English) / questionnaire.en.md

> `AA` = `python3 <skill_dir>/scripts/autoapply/cli.py [--data-dir DIR] --profile <profile_id>`（定义见 `SKILL.md` §开场）。

> Scope: the only question bank the Intake Agent (`agents/01-intake.md`) may use while the run is in the `intake` state. Status: `[未验证]` (not yet exercised with a real resume before Phase 2). Date: 2026-09-05.
> Parent documents: `BRIEF.md` §7 (8-round skeleton), §3 (hard boundaries), D1/D3/D6/D8/D9/D13, R3/R8; `ARCHITECTURE.md` §2.2 (`intake` checkpoints), §8 (consistency gate); `schemas/profile.schema.json`, `schemas/facts_card.schema.json`. BRIEF wins on conflict.
> `questionnaire.zh.md` is the content-equivalent Chinese version; `meta.language` decides which one is used. Never ask the same question in both languages.

---

## 0. Questioning discipline (read before speaking)

1. **One decisive question at a time within a round.** "Decisive" = the answer changes screening, form filling or gate behaviour (hard salary floor, submit mode, declarations). Purely informational fields (portfolio links, for example) may be grouped into one confirmation table that the user reviews and confirms once.
2. **Anything parsable from the resume is shown first for correction, never asked from scratch.** Display format: `resume_parse_guide.md` §4; low-confidence fields are named individually.
3. **"Skip / don't know / later" → the field becomes `null`** (arrays become `[]`) and the question id is recorded in `intake_state.json`. When a form later requires that field, follow `gates.md` §11 (`unknown_required_field`). Never guess.
4. **No leading, no guessing on the user's behalf.** Declaration questions (section 7) are offered as enumerations only, with no "recommended answer". Defaults exist only for policy-type fields (throttles, modes, frequencies) and their source is stated in the table.
5. **Follow the user's language**: Chinese first message → `questionnaire.zh.md`; English → this file. Switching mid-way switches the file; progress is kept.
6. **State "why we ask" in one sentence before each question** (which form or rule it serves). The user may probe; the agent answers from this file and does not improvise.
7. **Field paths are those in `schemas/profile.schema.json`.** As of 2026-09-05 the fields listed in section 10 (`intent.can_start_immediately/full_time/days_per_week/notice_period/work_mode`, `salary.current`, `rules.company_caps/notes`, `materials.job_list_paths`, `policy.source_channel_default/platform_option_overrides`, `skills.years_by_skill/proficiency`) are in the schema; Intake writes them directly and no longer parks them in `policy.declarations.other[]` or `notes`. For any field genuinely still missing from the schema, keep parking it in the stated holding place (`policy.declarations.other[]` with the prefixes in section 10, or the section's `notes`) and raise it in the task report — do not add schema fields unilaterally.
8. If the user pastes a password / ID number / bank detail at any point → reply with the fixed wording in `SECURITY.md` §3; do not use, do not repeat, ask them to change it; then continue.
9. **Persist progress**: write `intake_state.json.last_question_id` after each answer (ids below); write `round_done` at the end of each round. After a disconnect, resume from that question, not from the start.
10. **When to write the profile**: only after a whole round is confirmed, and only through the script (`validate profile` must pass). facts_card is signed as a whole at the end of round 6.
11. **Never collected** (any round, any platform): passwords, NRIC / FIN / passport / any ID number, bank or payment details, OTPs. Not even when volunteered (SECURITY §2).
12. Plain wording, no exclamation marks, no assumption about the user's nationality or school (D1).

**Table fields per question**: `Prompt` (read out or paraphrase) / `Field path` (JSON path inside profile.json) / `Allowed answers` (enum or format) / `Default` (value written when the user does not answer; "none" = mandatory) / `Skippable` / `Why we ask` (form or rule, citing playbook section numbers).

---

## 1. Round 0 Materials (`materials.*`, `meta.*`)

**Goal**: obtain at least one resume, fix the profile id and language. No resume content is parsed in this round.

### q0_1 Profile id

| Item | Content |
|---|---|
| Prompt | Choose a short id for this profile (lowercase letters, digits, `_`, `-`, 2–32 characters). It is also the name of the data directory on your computer, e.g. `alex_tan`. |
| Field path | `meta.profile_id` |
| Allowed answers | matches `^[a-z0-9][a-z0-9_-]{1,31}$` |
| Default | none (mandatory; the agent may suggest one from the resume filename for the user to confirm) |
| Skippable | No |
| Why we ask | Data directory `~/auto-apply-data/<profile_id>/` (ARCHITECTURE §5.2); distinguishes multiple profiles. |

### q0_2 Interface language

| Item | Content |
|---|---|
| Prompt | Should questions and reports from now on be in Chinese or English? |
| Field path | `meta.language` |
| Allowed answers | `zh` / `en` |
| Default | detected from the user's first message, confirmed once |
| Skippable | No |
| Why we ask | D1: user-facing text follows the user's language; decides which questionnaire file applies. |

### q0_3 Resume files

| Item | Content |
|---|---|
| Prompt | Give me the full path of your resume (PDF or DOCX). If you have Chinese, English or purpose-specific versions, give all of them and say what each is for. |
| Field path | `materials.resumes[]`: `path`, `language`, `label`, `version`, `is_default`, `notes`; `sha256` is computed by the agent |
| Allowed answers | `path` = absolute local path; `language` ∈ `en` / `zh` / `other`; `label` = purpose tag (e.g. `english_default`, `chinese_pm`); exactly one `is_default=true` |
| Default | none (at least 1); a single resume gets `is_default=true` |
| Skippable | No |
| Why we ask | Every platform needs a resume (playbooks §8); D6 no generation or translation — a job requiring a language you do not have triggers `resume_missing_language`; `sha256` feeds R3 and the check against platform-stored resumes (jobstreet.md §8, incident I-03). |

### q0_4 Purpose of each resume version (only when more than one)

| Item | Content |
|---|---|
| Prompt | When is each of these resumes used? Which one is the default? |
| Field path | `materials.resumes[].label` / `.version` / `.is_default` / `.notes` |
| Allowed answers | free-text labels; exactly one `is_default=true` |
| Default | none |
| Skippable | No (mandatory with multiple resumes, otherwise the Executor cannot choose) |
| Why we ask | R10 pre-submit item "resume version"; platform-stored resumes may be stale (jobstreet.md §8). |

### q0_5 Public links

| Item | Content |
|---|---|
| Prompt | Do you have LinkedIn, GitHub, a portfolio or a personal website? Give the links, or say "none". |
| Field path | `materials.linkedin_url` / `materials.github_url` / `materials.portfolio_url` / `materials.website_url` |
| Allowed answers | URL or `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Some Greenhouse tenants require LinkedIn (greenhouse.md §5; missing → gate); Workday "Websites" (workday.md §5); Ashby / Lever have LinkedIn / GitHub / Portfolio fields. |

### q0_6 Transcript

| Item | Content |
|---|---|
| Prompt | Do you have a transcript file (some companies require it)? Give the path if so. |
| Field path | `materials.transcript_path` |
| Allowed answers | absolute local path or `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Some Workday tenants require a transcript (workday.md §5, PwC); otherwise that job hits `unknown_required_field`. |

### q0_7 Certificates and cover-letter template

| Item | Content |
|---|---|
| Prompt | Do you have certificate files or a cover-letter template you wrote yourself? Give names and paths. |
| Field path | `materials.certificates[]` (`name`, `path`); `materials.cover_letter_template_path` |
| Allowed answers | array / path / `null` |
| Default | `[]` / `null` |
| Skippable | Yes |
| Why we ask | The Content Agent may follow the user's template when drafting a CL (D9); certificate upload fields appear occasionally. |

### q0_8 Runtime (not asked, recorded automatically)

| Item | Content |
|---|---|
| Prompt | (not asked) The agent records the current runtime. |
| Field path | `meta.runtime`; `meta.created_at` and `meta.version="1"` are written at the same time |
| Allowed answers | `claude_code` / `codex` |
| Default | current runtime |
| Skippable | — |
| Why we ask | D2/D3 credential policy depends on the runtime. |

---

## 2. Round 1 Resume parse confirmation (`identity.*`, `education[]`, `experience[]`, `skills.*`, incl. the R3 consistency gate)

**Goal**: the agent first parses every resume per `resume_parse_guide.md`, shows the result in blocks; the user corrects block by block; the consistency gate runs at the end. All entries in this round have `source=resume` and get `confirmed_by_user=true` once confirmed.

### q1_1 Name

| Item | Content |
|---|---|
| Prompt | From the resume I read: full name `<full>`, given `<given>`, family `<family>`, order `<given_first/family_first>`. Is this the full name to use on application forms? Tell me a native-script name or a preferred name if you have one. |
| Field path | `identity.name.full` / `.given` / `.family` / `.native` / `.name_order` / `.preferred` |
| Allowed answers | `full` mandatory (Latin script, matches resume); `name_order` ∈ `given_first` / `family_first` / `null` |
| Default | parsed values; `native`, `preferred` default `null` |
| Skippable | `full` no; the rest yes |
| Why we ask | Workday / Greenhouse / SmartRecruiters split First / Last (playbooks §5); R10 pre-submit "name order"; incident I-03 (ATS parsed the name order wrongly). |

### q1_2 Emails

| Item | Content |
|---|---|
| Prompt | The email on the resume is `<masked>`. Which email should forms use by default? Do you want a separate email for new ATS accounts? Any other emails bound to old accounts? |
| Field path | `identity.emails.primary` / `.signup` / `.others[]` |
| Allowed answers | valid email format; `signup` may be `null` (= use `primary`) |
| Default | `primary` = resume email (user confirms); `signup=null`; `others=[]` |
| Skippable | `primary` no; the rest yes |
| Why we ask | Every form; Greenhouse sends its verification code here (greenhouse.md §2); Workday allows one account per email per tenant (workday.md §3); R3 checks resume email ∈ profile email set (ARCHITECTURE §8.2); `others` stops old emails from triggering alarms. |

### q1_3 Phones

| Item | Content |
|---|---|
| Prompt | The phone on the resume is `<masked>`, country code `<code>`. Is this the default for forms? If you have a second number (e.g. home country), give it with a label. |
| Field path | `identity.phones[]`: `country_code`, `number`, `label`, `is_default` |
| Allowed answers | `country_code` like `+65`; `number` digits and spaces only; `label` ∈ `sg` / `home` / `other` / `null`; first entry is the default |
| Default | parsed values (if the resume shows no country code, ask; never assume `+65`) |
| Skippable | Yes (but most forms require it; skipping triggers `unknown_required_field` often) |
| Why we ask | Workday's country-code dropdown once switched itself (workday.md §5); SmartRecruiters' parser brought in an old code (smartrecruiters.md §5); R10 "country code"; R3 phone comparison. |

### q1_4 Education (confirm each entry)

| Item | Content |
|---|---|
| Prompt | Education entry `<n>` as I read it: `<institution>` / `<faculty>` / `<major>` / `<degree_title>` (level `<degree>`) / `<start>`–`<end_expected>` / current `<is_current>` / location `<location>` / GPA `<value or "not on resume">`. Correct? The expected graduation month must be exact. |
| Field path | `education[]`: `institution`, `faculty`, `major`, `degree`, `degree_title`, `start`, `end_expected`, `is_current`, `gpa{value,scale}`, `rank_or_honours`, `location`, `confirmed_by_user` |
| Allowed answers | `degree` ∈ `diploma` / `bachelor` / `master` / `phd` / `other`; year-month `YYYY-MM`; `gpa` only when written on the resume or stated by the user, else `null` |
| Default | parsed values; GPA is never inferred |
| Skippable | `institution`, `degree` no; the rest yes |
| Why we ask | Education sections of every ATS (playbooks §5); graduation year-month is a `block`-level R3 item and an R10 item, incident I-03 (ATS filled the year one early); `is_current` + `degree` answer "bachelor completed / master ongoing" questions (linkedin.md §5) and degree-threshold filtering; `location` answers "is your school in Singapore" (linkedin.md §5). |

### q1_5 Secondary / high-school details (optional)

| Item | Content |
|---|---|
| Prompt | A few forms (banks, trading firms) require secondary or high-school details. Add an entry now? If not, such jobs are skipped and logged when it comes up. |
| Field path | new `education[]` entry: `degree="other"`, `degree_title` = exam / qualification type, `rank_or_honours` = result |
| Allowed answers | as q1_4 |
| Default | not added |
| Skippable | Yes |
| Why we ask | Incident I-16 (UBS stalled on high-school details); greenhouse.md §6 (Optiver asks for secondary exam type and score). |

### q1_6 Experience (confirm each entry)

| Item | Content |
|---|---|
| Prompt | Experience entry `<n>` as I read it: `<kind>` / `<organisation>` / `<title>` / `<start>`–`<end>` / `<location>`, bullets `<bullets>`. Is the kind right (internship / job / project / competition / publication / volunteer)? Are all numbers and dates in the bullets taken verbatim from the resume? |
| Field path | `experience[]`: `kind`, `organisation`, `title`, `start`, `end`, `is_current`, `location`, `bullets[]`, `source="resume"`, `confirmed_by_user` |
| Allowed answers | `kind` ∈ `internship` / `job` / `project` / `competition` / `publication` / `volunteer` / `other`; each bullet ≤ 600 characters, verbatim from the resume or dictated by the user (`source="user_stated"`) |
| Default | parsed values |
| Skippable | individual entries may be deleted; the section cannot be skipped (confirming zero entries must be explicit) |
| Why we ask | Structured experience sections in Workday / SuccessFactors / SmartRecruiters (playbooks §5); SmartRecruiters mistakes projects for employment (smartrecruiters.md §5), so `kind` must be exact; `bullets` are the source of `experience` facts on the facts card. |

### q1_7 Skills and languages

| Item | Content |
|---|---|
| Prompt | Languages, tools / technologies and certifications I read from the resume: `<list>`. Rate language levels as native / fluent / professional / conversational / basic. Anything to add or remove? |
| Field path | `skills.languages_spoken[]` (`name`, `level`), `skills.tools[]`, `skills.certifications[]` (`name`, `issuer`, `date`), `skills.other[]` |
| Allowed answers | `level` ∈ `native` / `fluent` / `professional` / `conversational` / `basic` / `null` |
| Default | parsed values; `level` is `null` when the resume does not state it |
| Skippable | Yes |
| Why we ask | Workday Languages / Skills dropdowns (workday.md §5); Lever / LinkedIn Languages (lever.md §5, linkedin.md §5). |

### q1_8 Skill years and self-ratings (optional presets)

| Item | Content |
|---|---|
| Prompt | LinkedIn and other forms ask "years of experience with `<skill>`" (integers only) or ask you to rate proficiency. Preset answers now for skills on your resume? Anything not preset is suspended and asked when it comes up. |
| Field path | `skills.years_by_skill{<skill>: years}` / `skills.proficiency{<skill>: level}` |
| Allowed answers | years as a non-negative integer; rating as `basic` / `intermediate` / `advanced` or `null` (schema has no `none` tier; leave the key out or set it to `null` if unset) |
| Default | not preset (`null` → gate) |
| Skippable | Yes |
| Why we ask | linkedin.md §5 integer-only years; greenhouse.md §5 / smartrecruiters.md §5 self-rating questions; skills not on the resume are never self-rated. |

### q1_9 Consistency gate (R3; executed by script, not a question)

| Item | Content |
|---|---|
| Action | After q1_1–q1_4 are confirmed, write `resume_parse.json`, run `AA profile consistency --profile <id>`, read `consistency_report.json`. |
| Result `pass` / `info` | no interruption; continue to round 2. |
| Result `warn` | show the masked differences and ask once "noted, continue?"; the user may edit the profile. |
| Result `block` | raise the `consistency_mismatch` gate (`gates.md` §16), wording in `resume_parse_guide.md` §6; the user picks one: ① keep the profile → write `materials.resumes[].known_mismatches[]`; ② replace the resume → back to q0_3 and re-parse; ③ update the profile → re-run. |
| Field path | `materials.resumes[].known_mismatches[]` |
| Why | Incident I-03; P2 DoD "the consistency gate catches contact mismatches". |

---

## 3. Round 2 Identity and work authorisation (`status.*`, `identity.address`, `identity.date_of_birth`, `identity.gender`)

**Goal**: settle once the work-authorisation questions ATS forms keep asking, split into three separate questions. **No ID numbers are collected in this round**; volunteered numbers are not recorded.

### q2_1 Nationality

| Item | Content |
|---|---|
| Prompt | What is your nationality? (Country name only; no document numbers.) |
| Field path | `status.nationality` |
| Allowed answers | country name or ISO 3166 code; `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Some Lever / LinkedIn forms ask Nationality (lever.md §5, linkedin.md §5); Workday Self Identify asks nationality (workday.md §4 step 5). |

### q2_2 Country / city of residence and address

| Item | Content |
|---|---|
| Prompt | Which country and city do you live in? Some forms require a street address and postal code; give them now (stored locally only, never logged)? |
| Field path | `status.country_of_residence`; `identity.address.country` / `.city` / `.line1` / `.postal_code` |
| Allowed answers | free text; `postal_code` ≤ 20 characters; `null` |
| Default | `null` |
| Skippable | Yes (some Workday tenants suspend when the postal code is missing) |
| Why we ask | Workday step 1 address and postal code mandatory (workday.md §4/§5); Greenhouse Location, Lever Current location autocomplete (lever.md §5, incident I-09), SmartRecruiters City / Country. |

### q2_3 Current status in Singapore

| Item | Content |
|---|---|
| Prompt | What pass or status do you currently hold in Singapore? (No document number needed.) |
| Field path | `status.work_pass`; `status.work_pass_other_label` when `other`; expiry in `status.work_pass_expiry` |
| Allowed answers | `citizen` / `permanent_resident` / `student_pass` / `employment_pass` / `s_pass` / `work_permit` / `dependant_pass` / `ltvp` / `training_employment_pass` / `work_holiday_pass` / `other` / `none` / `unknown` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Jobstreet right-to-work dropdown (jobstreet.md §9), SmartRecruiters "Current pass" (smartrecruiters.md §5), Lever Visa status (lever.md §5); D1 enumeration covers every nationality case. |

### q2_4 Work authorisation (question one)

| Item | Content |
|---|---|
| Prompt | Under your current status, are you legally allowed to do the kind of work you are applying for (internship / full-time) in Singapore? |
| Field path | `status.authorised_to_work_in_sg` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` (never derived from `work_pass`) |
| Skippable | Yes |
| Why we ask | "Are you legally authorized to work in Singapore" appears in Workday / Ashby / Workable / LinkedIn (playbooks §5). The three questions are split because Workday merges "now or in the future require sponsorship" into one item and the Executor needs each part. |

### q2_5 Work authorisation (question two)

| Item | Content |
|---|---|
| Prompt | For this internship / job itself, do you **now** need the employer to apply for a work pass for you? |
| Field path | `status.requires_sponsorship_now` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Greenhouse DRW "work pass during internship" (greenhouse.md §5), Lever "sponsorship during internship" (lever.md §5), LinkedIn "need additional work pass" (linkedin.md §5). |

### q2_6 Work authorisation (question three)

| Item | Content |
|---|---|
| Prompt | After graduation or in the future, will you need an employer to sponsor a work pass? |
| Field path | `status.requires_sponsorship_future` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workday "now or in the future require sponsorship" (answer Yes if future is true, workday.md §5); SmartRecruiters "after graduation" (smartrecruiters.md §5). |

### q2_7 Nature of the internship

| Item | Content |
|---|---|
| Prompt | Which kind of internship are you applying for: credit-bearing, school-approved non-credit, vacation, leave-of-absence, or not applicable (full-time roles)? |
| Field path | `status.internship_nature` |
| Allowed answers | `credit_bearing` / `school_approved_non_credit` / `vacation` / `leave_of_absence` / `not_applicable` / `unknown` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | LinkedIn "school-recognised internship" (linkedin.md §5), Ashby / Lever "credit-bearing" (ashby.md §5, lever.md §5), Workable "Internship type" (workable.md §5), SuccessFactors credit-internship question (successfactors.md §5). |

### q2_8 Work-pass exemption during the internship

| Item | Content |
|---|---|
| Prompt | As far as you know, does your internship period not require a separate work pass (e.g. a school-approved internship on a Student's Pass)? Say "not sure" if unsure; I do not decide this for you. |
| Field path | `status.work_pass_exempt_for_internship` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Combined with q2_5 to answer "do you need a pass during the internship"; the agent does not explain immigration rules, it records the user's answer. |

### q2_9 Can the school issue an internship letter

| Item | Content |
|---|---|
| Prompt | Can your school issue an internship letter / approval? |
| Field path | `status.school_can_issue_letter` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Some employer screening questions require it; not cited by the Content Agent, used only by the Executor. |

### q2_10 Date of birth (optional, sensitive)

| Item | Content |
|---|---|
| Prompt | A few forms require a date of birth. Store it now? Local only, used only when a form requires it, never logged. You may decline; the job is suspended and you are asked when it comes up. |
| Field path | `identity.date_of_birth` |
| Allowed answers | `YYYY-MM-DD` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | LinkedIn Easy Apply has asked Date of birth (linkedin.md §5); Workday step 5 age question (workday.md §4); SECURITY §2 lists it as a caution field. |

### q2_11 Gender (optional)

| Item | Content |
|---|---|
| Prompt | How should a plain gender field on a form be filled? This is separate from the default for EEO questions (round 6). |
| Field path | `identity.gender` |
| Allowed answers | `female` / `male` / `non_binary` / `prefer_not_to_say` / `other` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Some forms make gender an ordinary mandatory field rather than a voluntary EEO field; `policy.eeo_default` governs EEO fields only. |

### q2_12 Status notes

| Item | Content |
|---|---|
| Prompt | Anything else about your status or work authorisation I should know (pass application pending, status changing soon)? |
| Field path | `status.notes` |
| Allowed answers | ≤ 1000 characters / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Read by Screening and the Executor; not on the facts card unless explicitly signed in round 6. |

---

## 4. Round 3 Job-search intent (`intent.*`)

### q3_1 Job types

| Item | Content |
|---|---|
| Prompt | Which types: internship, full-time, part-time, graduate programme, contract? Multiple allowed. |
| Field path | `intent.types[]` |
| Allowed answers | `internship` / `full_time` / `part_time` / `graduate_programme` / `contract`, at least 1 |
| Default | none |
| Skippable | No |
| Why we ask | Sourcing filters and Screening hard conditions. |

### q3_2 Direction keywords

| Item | Content |
|---|---|
| Prompt | Describe the direction in 3–5 keywords (e.g. data analyst, backend, product). |
| Field path | `intent.keywords[]` |
| Allowed answers | string array |
| Default | `[]` |
| Skippable | Yes (if skipped, Sourcing only consumes user lists and does no site search) |
| Why we ask | R2 site-search terms; Screening match score. |

### q3_3 Excluded directions

| Item | Content |
|---|---|
| Prompt | Which directions are explicitly out (e.g. pure sales, customer service, pure hardware)? |
| Field path | `intent.excluded_directions[]` |
| Allowed answers | string array |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | Screening exclusion; complements round-5 title exclusions (`rules.title_exclusions`): directions here, title substrings there. |

### q3_4 Locations

| Item | Content |
|---|---|
| Prompt | Which work locations do you accept? Default is Singapore only. |
| Field path | `intent.locations[]` |
| Allowed answers | string array, at least 1 |
| Default | `["Singapore"]` (user confirms) |
| Skippable | No |
| Why we ask | LinkedIn / Lever location hard rule: `Hong Kong / Taipei / Asia / APAC / Remote / Hybrid` is not Singapore (linkedin.md §9, lever.md §9); Greenhouse hidden `job_location` check (greenhouse.md §6). |

### q3_5 Remote and relocation

| Item | Content |
|---|---|
| Prompt | Do you accept remote roles? Relocation to another country? |
| Field path | `intent.remote_ok` / `intent.relocation_ok` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | LinkedIn "On-site at <location>?" (linkedin.md §5); remote roles must explicitly allow working from Singapore (lever.md §9). |

### q3_6 Internship / availability window

| Item | Content |
|---|---|
| Prompt | From which month to which month can you work? How many weeks can either end move? |
| Field path | `intent.window.start` / `.end` / `.flexibility_weeks` |
| Allowed answers | `YYYY-MM`; `flexibility_weeks` integer 0–52 |
| Default | `null` |
| Skippable | Yes (if skipped the date-window filter is off, at your own risk) |
| Why we ask | Hard boundary "date window mismatch → skip and log"; incident I-10 (Grab's form only offered 2026 windows); Workday internship period, SmartRecruiters start / end, Ashby / Lever dates (playbooks §5). |

### q3_7 Earliest start date

| Item | Content |
|---|---|
| Prompt | What is the earliest day you can start? At least month-precise; if you only know the month, use the 1st and say so. |
| Field path | `intent.earliest_start` |
| Allowed answers | `YYYY-MM-DD` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workday "Available start date" month-precise (workday.md §4 step 3); Greenhouse "Earliest start date", Ashby "Earliest available date" (playbooks §5). "Can you start immediately?" still defaults to the Executor answering truthfully from `earliest_start` versus the application date; `false` on a must-be-Yes question skips the whole job (linkedin.md §11, smartrecruiters.md §5). If the user wants to preset this, write `intent.can_start_immediately` (now in the schema); the Executor reads it first and only falls back to the date conversion when unset. |

### q3_8 Hours per week

| Item | Content |
|---|---|
| Prompt | How many hours per week can you work? Full-time is about 40; if term time and vacation differ, say both. |
| Field path | `intent.hours_per_week`; differences in `intent.term_time_vs_vacation_notes` |
| Allowed answers | integer 1–80 / `null`; notes free text |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Lever "Hours per week" (lever.md §5); "Full-time?" questions still default to being answered from the hours; SmartRecruiters "Days per week" (smartrecruiters.md §5) is likewise converted from `hours_per_week`. If the user wants to preset this, write `intent.full_time` / `intent.days_per_week` (both now in the schema); the Executor reads them first and only converts when unset. |

### q3_9 Minimum commitment

| Item | Content |
|---|---|
| Prompt | What is the shortest internship / job length you can commit to, in months? |
| Field path | `intent.min_commitment_months` |
| Allowed answers | number ≥ 0 / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | LinkedIn "Can you commit N months full-time?" (linkedin.md §5); Ashby / Lever duration (ashby.md §5, lever.md §5). |

### q3_10 Degree level targets

| Item | Content |
|---|---|
| Prompt | Which degree levels should postings target: bachelor, master, PhD, diploma, or any? |
| Field path | `intent.degree_level_targets[]` |
| Allowed answers | `diploma` / `bachelor` / `master` / `phd` / `any` |
| Default | `[]` (= no filter; Screening logs a warning) |
| Skippable | Yes |
| Why we ask | Hard boundary "degree threshold mismatch → skip"; Screening filter. |

### q3_11 Bachelor-only postings

| Item | Content |
|---|---|
| Prompt | When a posting says bachelor's students only, apply or not? Note: a master's student never poses as a bachelor's student; a mandatory "currently pursuing Bachelor's" question causes a skip. |
| Field path | `intent.apply_to_bachelor_only_postings` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | successfactors.md §5 (master's student must not pose as bachelor's → skip). |

---

## 5. Round 4 Salary and conditions (`salary.*`)

### q4_1 Currency and period

| Item | Content |
|---|---|
| Prompt | Which currency and period for salary? Default SGD per month. |
| Field path | `salary.currency` / `salary.period` |
| Allowed answers | ISO 4217 three letters (e.g. `SGD`); `month` / `day` / `hour` / `year` |
| Default | `SGD` / `month` (user confirms) |
| Skippable | Yes |
| Why we ask | Unit for the following numbers; Screening comparisons. |

### q4_2 Expected range

| Item | Content |
|---|---|
| Prompt | What is your expected salary range? Forms asking "expected salary" get the lower bound. |
| Field path | `salary.expected_min` / `salary.expected_max` |
| Allowed answers | number ≥ 0 / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workday / Jobstreet / Ashby "Expected salary" (playbooks §5); R10 "salary". |

### q4_3 Hard floor

| Item | Content |
|---|---|
| Prompt | Below what amount do you definitely not apply? This is a hard rule: a posting with a published salary below it is skipped and logged. |
| Field path | `salary.hard_floor` |
| Allowed answers | number ≥ 0 / `null` |
| Default | `null` (= no salary filter) |
| Skippable | Yes |
| Why we ask | Hard boundary "salary below floor → skip and log"; jobstreet.md §11. |

### q4_4 Undisclosed salary

| Item | Content |
|---|---|
| Prompt | Apply when the posting shows no salary? |
| Field path | `salary.apply_if_undisclosed` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Screening hard condition. |

### q4_5 Unpaid internships

| Item | Content |
|---|---|
| Prompt | Apply to unpaid internships? |
| Field path | `salary.allow_unpaid` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Screening hard condition. |

### q4_6 Negotiable

| Item | Content |
|---|---|
| Prompt | Tick "negotiable" when a form offers it? |
| Field path | `salary.negotiable` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Ashby salary range negotiable (ashby.md §5). |

### q4_7 Current salary and notes

| Item | Content |
|---|---|
| Prompt | How should "current salary" be answered (students usually enter 0 and note "student")? Other salary notes go here too. |
| Field path | `salary.current` (number; students may leave `0` or `null`); other salary-related notes go to `salary.notes` |
| Allowed answers | `salary.current`: non-negative number / `null`; `salary.notes`: free text / `null` |
| Default | `null` (→ gate when mandatory) |
| Skippable | Yes |
| Why we ask | Workday step 3 "Current salary" (workday.md §5). |

---

## 6. Round 5 Exclusions and strategy (`rules.*`, R8 / D13)

**Goal**: the round the user emphasised most. Every item becomes a Screening filter or an Executor throttle. List questions accept several entries at once.

### q5_1 Company blacklist

| Item | Content |
|---|---|
| Prompt | Which companies are never applied to? Include companies you have applied to enough and do not want more of. Each may carry a reason and an expiry date. |
| Field path | `rules.company_blacklist[]`: `name`, `reason`, `until` |
| Allowed answers | `name` mandatory; `until` = `YYYY-MM-DD` or `null` |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | Hard boundary "blacklist → skip and log"; R8. |

### q5_2 Industry exclusions

| Item | Content |
|---|---|
| Prompt | Which industries are out (gambling, tobacco, defence, crypto, others)? |
| Field path | `rules.industry_exclusions[]` |
| Allowed answers | string array |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | Screening filter; R8. |

### q5_3 Title exclusions

| Item | Content |
|---|---|
| Prompt | Which words in a job title mean "do not apply" (e.g. sales, telemarketing, driver)? |
| Field path | `rules.title_exclusions[]` |
| Allowed answers | substring array (case-insensitive) |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | Screening title filter; complements q3_3. |

### q5_4 Reserved-for-referral list

| Item | Content |
|---|---|
| Prompt | Which companies do you intend to reach through a referral and must never be auto-applied to (an auto-application could use up the referral slot)? Reason and expiry optional. |
| Field path | `rules.reserve_for_referral[]`: `name`, `reason`, `until` |
| Allowed answers | as q5_1 |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | R8; hard boundary "reserved-for-referral → skip and log"; the user's own rule quoted in Plan §1 (global-quota roles versus referral slots). |

### q5_5 Global-quota rule

| Item | Content |
|---|---|
| Prompt | Some companies allow one application or one global consideration per person. How to treat such postings: ignore, skip only for companies on the referral list, or skip all of them? |
| Field path | `rules.global_quota_rule.mode` / `.notes` |
| Allowed answers | `ignore` / `skip_if_in_reserve_list` / `skip_all_global_quota` |
| Default | `null` (→ Screening puts such postings on the shortlist flagged as a risk; the user decides at approval) |
| Skippable | Yes |
| Why we ask | R8; greenhouse.md §9 (one application considered globally), §12 (one role only); workday.md §12 (one application per person). |

### q5_6 Per-company cap

| Item | Content |
|---|---|
| Prompt | At most how many applications to the same company? Default 3. |
| Field path | `rules.per_company_max`; stricter company-level caps (e.g. one application per person) are set via `rules.company_caps[{company, max_applications}]`, sourced from playbook §12, not asked here |
| Allowed answers | integer 1–3 (schema `maximum` is now tightened to 3, aligned with SECURITY §7.2's hard cap) |
| Default | `3` (D13) |
| Skippable | Yes (default applies) |
| Why we ask | D13; incident I-01 duplicates within a company. |

### q5_7 Per round

| Item | Content |
|---|---|
| Prompt | Target applications per round? Default 10, maximum 20. |
| Field path | `rules.per_round` |
| Allowed answers | integer 1–20 |
| Default | `10` (D13) |
| Skippable | Yes |
| Why we ask | D13; SECURITY §7.2 throttle table. |

### q5_8 Per day

| Item | Content |
|---|---|
| Prompt | Maximum applications per day across all platforms? Default 20, which is also the hard cap; it can only be lowered. |
| Field path | `rules.per_day` |
| Allowed answers | integer 1–20 |
| Default | `20` (D13) |
| Skippable | Yes |
| Why we ask | D13; `quota_exhausted` gate (gates.md §18); ToS risk (SECURITY §7). |

### q5_9 Channel priority

| Item | Content |
|---|---|
| Prompt | When the same job is open on several channels, which comes first? Order them. Default: company site > LinkedIn > Jobstreet > MyCareersFuture > email > other. |
| Field path | `rules.channel_priority[]` |
| Allowed answers | ordered subset of `company_site` / `linkedin` / `jobstreet` / `mycareersfuture` / `email` / `other` |
| Default | `["company_site","linkedin","jobstreet","mycareersfuture","email","other"]` (user confirms) |
| Skippable | Yes |
| Why we ask | R1: one channel per job, channel is an attribute not a key (incident I-01); R6: fallback order when LinkedIn's quota is hit. |

### q5_10 Platforms with existing accounts

| Item | Content |
|---|---|
| Prompt | On which job platforms / ATS do you already have accounts? Which email logs in to each? Is the password saved in Chrome's password manager? (Do not tell me the password.) |
| Field path | `rules.existing_accounts[]`: `platform`, `login_email`, `saved_in_browser`, `notes` |
| Allowed answers | `platform` ∈ `jobstreet` / `linkedin_easy_apply` / `linkedin_external` / `mycareersfuture` / `workday` / `successfactors` / `greenhouse` / `ashby` / `smartrecruiters` / `lever` / `workable` / `company_custom` / `email` / `other` / `unknown`; one entry per company tenant for Workday / SuccessFactors, company name in `notes` |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | Avoids duplicate registration (one account per email on Workday, workday.md §3); decides login versus sign-up before the `password_or_signup` gate; onboarding pre-registration list (`onboarding_checklist.md` §5). |

### q5_11 Import of past applications

| Item | Content |
|---|---|
| Prompt | Do you have a record of jobs you already applied to (an old ledger in Markdown, a spreadsheet, or a company + title list)? Give the path; once imported these jobs are caught by deduplication and never re-applied. |
| Field path | `rules.legacy_ledger_imported` (set `true` after a successful import); data enters the ledger via `AA ledger migrate-legacy <file>` |
| Allowed answers | path / "none" |
| Default | `false` |
| Skippable | Yes |
| Why we ask | R1 deduplication; D17; P3 DoD "100% of past applications caught". Lists not in the four-section format: Intake first rewrites them into that Markdown format (ARCHITECTURE §5.6) and shows the result to the user before importing. |

### q5_12 User job lists / links (shortlist raw material)

| Item | Content |
|---|---|
| Prompt | Do you have a list of jobs or links you want to apply to? Give the path or paste the links. Sourcing consumes them first, then searches on its own. |
| Field path | `materials.job_list_paths[]`; may also be given directly to Sourcing at the start of each round |
| Allowed answers | list of paths / URLs / "none" |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | R2 user list first (incident I-02). |

### q5_13 Other sourcing constraints

| Item | Content |
|---|---|
| Prompt | Any other screening rules (only JDs that explicitly say Singapore, no agency postings, no "immediate start" roles)? |
| Field path | map what fits (location → `intent.locations`; immediate start → `intent.earliest_start`); anything else that does not fit a specific field goes to `rules.notes` |
| Allowed answers | free text |
| Default | none |
| Skippable | Yes |
| Why we ask | Catches rules the user stresses that have no schema slot, so they are not lost. |

---

## 7. Round 6 Content and declarations (`policy.*`, facts_card)

**Goal**: set the open-question / CL policy; preset every declaration question seen in the playbooks as a "my preset answer" list; generate and sign the facts card. **Any declaration not preset = `null` = suspended and asked in person at application time** (`personal_declaration` gate, gates.md §7).

### q6_1 Cover-letter policy

| Item | Content |
|---|---|
| Prompt | Cover letters: never, draft then you approve before filling, or fill automatically? Drafts cite only your signed facts card. |
| Field path | `policy.cover_letter_policy` |
| Allowed answers | `never` / `approve` / `auto` |
| Default | `approve` (D9) |
| Skippable | Yes (default applies) |
| Why we ask | D9 / R9; `content_approval` gate (gates.md §9). |

### q6_2 Open-question policy

| Item | Content |
|---|---|
| Prompt | Open questions on forms (e.g. "Why us?"): skip, draft then you approve, or fill automatically? |
| Field path | `policy.open_question_policy` |
| Allowed answers | `skip` / `approve` / `auto` |
| Default | `approve` (D9) |
| Skippable | Yes |
| Why we ask | Incident I-12 (Razer / PwC mandatory open questions); `skip` on a mandatory question skips the whole job and logs it. |

### q6_3 One-line self-introduction

| Item | Content |
|---|---|
| Prompt | May a one-line self-introduction be generated from the facts card for short "About you" fields? |
| Field path | `policy.allow_ai_self_intro` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` (= not generated) |
| Skippable | Yes |
| Why we ask | SmartRecruiters "Hiring Team Message" (smartrecruiters.md §9), Lever "Additional information" (lever.md §9). |

### q6_4 Default for EEO questions

| Item | Content |
|---|---|
| Prompt | Voluntary disclosure questions (gender / ethnicity / disability / veteran status): always prefer not to say, answer from the profile, or ask me each time? |
| Field path | `policy.eeo_default` |
| Allowed answers | `prefer_not_to_say` / `answer_from_profile` / `ask_me` |
| Default | `prefer_not_to_say` (BRIEF §7) |
| Skippable | Yes |
| Why we ask | Workday step 4 Voluntary Disclosures (workday.md §4); `ask_me` → `personal_declaration` each time. |

### q6_5 Declaration: criminal record

| Item | Content |
|---|---|
| Prompt | When a form asks "criminal record / pending charges", what is your preset answer? Your own words only; if not preset, you are asked each time. |
| Field path | `policy.declarations.criminal_record` |
| Allowed answers | text ≤ 300 characters (usually `No` / `Yes: <detail>`) / `null` |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workable PRISM+ criminal-record question (workable.md §9); Workday step 5 compliance declarations (workday.md §4); hard boundary "declarations that must be answered by the person". |

### q6_6 Declaration: bankruptcy

| Item | Content |
|---|---|
| Prompt | Preset answer for "ever bankrupt / undischarged bankruptcy"? |
| Field path | `policy.declarations.bankruptcy` |
| Allowed answers | as q6_5 |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Listed in ARCHITECTURE §3.1 `personal_declaration`; common with financial tenants `[未验证：具体平台]`. |

### q6_7 Declaration: vaccination

| Item | Content |
|---|---|
| Prompt | Preset answer for "vaccination status"? |
| Field path | `policy.declarations.vaccination_status` |
| Allowed answers | as q6_5 |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workday Keppel Covid vaccination question (workday.md §4 step 5, §9). |

### q6_8 Declaration: relatives / related persons at the company

| Item | Content |
|---|---|
| Prompt | Preset answer for "any relative, spouse or close associate employed by the company (or a client / business relationship with it)"? A valid default is "None, unless I note it when approving the shortlist". |
| Field path | `policy.declarations.relatives_in_company` |
| Allowed answers | as q6_5 |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workday step 3 relatives / client relationship, step 5 conflict of interest (workday.md §4/§9). |

### q6_9 Declaration: previously applied to / employed by the company

| Item | Content |
|---|---|
| Prompt | Preset answer for "previously worked for / previously applied to this company"? Name exceptions inside the answer. |
| Field path | `policy.declarations.previously_applied_or_employed` |
| Allowed answers | as q6_5 (e.g. `No, except <company>: worked 2025-06 to 2025-08`) |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Workday step 1 "Have you previously worked for X", step 3 "applied before" (workday.md §4/§5); companies already in the ledger are answered "applied" by the Executor from the ledger, not from this field. |

### q6_10 Declaration: non-compete

| Item | Content |
|---|---|
| Prompt | Preset answer for "bound by a non-compete / confidentiality agreement"? |
| Field path | `policy.declarations.non_compete` |
| Allowed answers | as q6_5 |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Listed in ARCHITECTURE §3.1; `[未验证：出现平台]`. |

### q6_11 Declaration: background-check consent

| Item | Content |
|---|---|
| Prompt | Preset answer for "consent to a background check"? |
| Field path | `policy.declarations.background_check_consent` |
| Allowed answers | as q6_5 |
| Default | `null` |
| Skippable | Yes |
| Why we ask | Listed in ARCHITECTURE §3.1; SuccessFactors Singtel identity-verification step before success (successfactors.md §9) `[未验证：是否为背景调查同意]`. |

### q6_12 Declaration: personal-data processing consent (PDPA / privacy)

| Item | Content |
|---|---|
| Prompt | The "I consent to processing of my personal data under the privacy policy" checkbox at the end of forms: preset to agree? Without it nothing can be submitted. |
| Field path | `policy.declarations.data_processing_consent` |
| Allowed answers | `Yes` / `null` |
| Default | `null` (→ suspended each time) |
| Skippable | Yes |
| Why we ask | Greenhouse privacy / PDPA checkbox (greenhouse.md §4/§5); SECURITY §6. |

### q6_13 Other declarations and fixed-option questions (one at a time, `declarations.other[]`)

One question each; `question` uses the fixed prefixes of section 10; `answer` is the user's own words or `null`. **Only questions seen in the playbooks or listed in ARCHITECTURE are included**; anything else is suspended at application time.

| # | Prompt | `question` value | Allowed answers | Default | Why we ask |
|---|---|---|---|---|---|
| a | Preset answer for "ever dismissed / asked to resign"? | `common:previously_dismissed` | text / `null` | `null` | Workday step 5 (workday.md §4) |
| b | Preset answer for "are you or a relative a government official / politically exposed person"? | `common:government_official_relative` | text / `null` | `null` | Workday GSK / Micron (workday.md §9) |
| c | Preset answer for "any conflict of interest"? | `common:conflict_of_interest` | text / `null` | `null` | Workday step 5 |
| d | Preset answer for "any directorships / external appointments"? | `common:directorships` | text / `null` | `null` | Workday Micron (workday.md §4) |
| e | Preset answer for "are you 18 or older"? (no date of birth asked) | `common:age_18_plus` | `Yes` / `No` / `null` | `null` | Workday age question (workday.md §4) |
| f | Preset answer for "military service status" (not applicable / completed / liable / exempt)? | `common:military_service_status` | text / `null` | `null` | Workday Micron step 3 (workday.md §4) |
| g | Default answer for "referred by an employee"? | `common:employee_referral` | text / `null` (e.g. `No unless noted at shortlist approval`) | `null` | Workday step 3 (workday.md §4) |
| h | Fixed answer for "How did you hear about us"? If not fixed, the Executor fills the job's actual source channel from the ledger (a fact, not a guess) | write `policy.source_channel_default` (no longer parked in `declarations.other[]`) | `$defs/channel` enum value (`company_site`/`linkedin`/`jobstreet`/`mycareersfuture`/`email`/`other`) / `null` | `null` | Workday step 1 (workday.md §4/§5) |
| i | Tick "receive recruiting emails / join talent pool"? | `common:marketing_consent` | `Yes` / `No` / `null` | `No` (policy default: least consent; the user may change it) | Common before submit on Greenhouse / Workday `[未验证]` |
| j | Fixed answer for "currently employed / notice period"? | write `intent.notice_period` (no longer parked in `declarations.other[]`) | text / `null` (e.g. `Not employed; available from <earliest_start>`) | `null` | Greenhouse "Notice period" (greenhouse.md §5) |
| k | Jobstreet's right-to-work dropdown **has no Student's Pass option**; its fixed options are: Citizen / PR / holds EP·S Pass·Work Permit / Training Employment Pass·Work Permit / "I require sponsorship…". Which one do you fix? If none, it is suspended each time. The agent never maps Student's Pass to any of them. | write `policy.platform_option_overrides.jobstreet["work_rights_option"]` (no longer parked in `declarations.other[]`) | verbatim option / `null` | `null` | jobstreet.md §9/§11 |
| l | On some Lever forms, which Visa status option do you fix (e.g. "already hold the relevant visa")? | `platform:lever:visa_status_option` | verbatim option / `null` | `null` | lever.md §5 |
| m | For companies allowing one role only / one application considered globally, which direction is chosen by default? | `common:single_application_preference` | text / `null` | `null` | greenhouse.md §9/§12; works with q5_5 |

### q6_14 Facts card: motivation and preference facts

| Item | Content |
|---|---|
| Prompt | Open questions often ask "why us / why this direction". Which genuine motivations, preferences or reflections **may the AI cite**? One per line, no rhetoric. Say "none" if none. |
| Field path | `facts_card.facts[]`, `category="motivation"`, `source.type="user_stated"`, `source.ref="intake:q6_14"` |
| Allowed answers | each ≤ 600 characters |
| Default | none |
| Skippable | Yes (open answers then cite resume facts only) |
| Why we ask | D9 / R9: the Content Agent cites signed facts only; motivations are not on the resume and must be dictated. |

### q6_15 Facts card: forbidden claims

| Item | Content |
|---|---|
| Prompt | Which statements must never appear in your cover letters or open answers (e.g. "expert in X", naming a certain employer, any exaggeration)? |
| Field path | `facts_card.forbidden_claims[]` |
| Allowed answers | string array |
| Default | `[]` |
| Skippable | Yes |
| Why we ask | facts_card.schema `forbidden_claims`; the Content Agent checks every draft against it. |

### q6_16 Facts card sign-off (fact by fact, then whole card)

| Item | Content |
|---|---|
| Action | The agent renders `facts_card.md` from `facts_card.template.md`, shows it category by category; the user replies "confirm all" or "change f_003 to …" / "drop f_007"; edits go back into `facts_card.json` (`status=edited/rejected`), re-rendered until the user says "sign the card". |
| Field path | `facts_card.facts[].status` / `.user_signature`; `facts_card.meta.signed_by_user` / `.signed_at` / `.resume_sha256[]` |
| Allowed answers | `confirmed` / `edited` / `rejected` (no `draft` may remain) |
| Default | none |
| Skippable | No (unsigned card blocks entry to `source`) |
| Why we ask | D9 / R9; ARCHITECTURE §2.2 `intake` exit condition. |

---

## 8. Round 7 Authorisation and pace (`policy.*`, `meta.intake_signed_at`)

### q7_1 Submit mode

| Item | Content |
|---|---|
| Prompt | How is the final submit handled? **confirm**: every application stops at the submit button until you say "submit". **autopilot**: after pre-submit checks pass the agent clicks submit and you review the ledger afterwards. Autopilot requires a written consent sentence from you and acknowledgement of these consequences: (1) submitted content follows your signed profile and facts card, errors are yours; (2) a submission cannot be withdrawn; (3) gates (passwords, CAPTCHAs, ID numbers, unpreset declarations) still stop; (4) you can switch back to confirm at any time. |
| Field path | `policy.submit_mode`; with autopilot, `policy.autopilot_consent.enabled_at` / `.statement` are mandatory |
| Allowed answers | `confirm` / `autopilot`; `statement` ≥ 10 characters, in the user's own words (the agent does not draft it) |
| Default | `confirm` (D8) |
| Skippable | Yes (default applies) |
| Why we ask | D8; `final_submit` gate (gates.md §8). |

### q7_2 Gate handling

| Item | Content |
|---|---|
| Prompt | When a gate needs you: **interactive** = you are present and are asked on the spot; **batch** = you are away, everything that can be suspended is suspended with a saved draft, the next item continues, and you get a pending list at the end of the round. Which one? In both modes the final submit (confirm mode), shortlist approval, consistency mismatch and browser disconnect always stop immediately. |
| Field path | `policy.gate_mode` |
| Allowed answers | `interactive` / `batch` |
| Default | `interactive` (recommended value from ARCHITECTURE §13 open question 2, **pending decision**) |
| Skippable | Yes |
| Why we ask | gates.md §0 two handling modes. |

### q7_3 Read-only mailbox consent

| Item | Content |
|---|---|
| Prompt | May I read your mailbox **read-only** to find receipts, status emails and verification codes? Read only; never send, delete or relabel. Which route: the runtime's mailbox connector (you authorise it yourself in settings; Gmail / Outlook recommended), webmail in the logged-in Chrome, or no access? |
| Field path | `policy.mail_readonly_consent`; `policy.mail_backend_preference` |
| Allowed answers | `true` / `false`; `connector` / `webmail` / `none` |
| Default | `null` / `null` (= no tracking, stated in the report) |
| Skippable | Yes |
| Why we ask | D10; SECURITY §8; prerequisite for automatic code reading at the `otp` gate (gates.md §3); connector reads may change read status `[未验证]`, which the user must be told. |

### q7_4 Verification-link click consent

| Item | Content |
|---|---|
| Prompt | After an ATS sign-up, may I click the account-activation link on your behalf once the sender domain and link domain match? Activation links only; never password-reset, unlink or authorisation links. |
| Field path | `policy.allow_verification_link_click` |
| Allowed answers | `true` / `false` / `null` |
| Default | `null` (= suspended for you to click) |
| Skippable | Yes |
| Why we ask | `email_verification_link` gate (gates.md §4); incident I-15 (expired link). |

### q7_5 Report frequency

| Item | Content |
|---|---|
| Prompt | Report progress after every how many applications? Default 5. |
| Field path | `policy.report_every_n` |
| Allowed answers | integer 1–50 |
| Default | `5` (D13) |
| Skippable | Yes |
| Why we ask | D13; reports cite the ledger only. |

### q7_6 Pending-item expiry

| Item | Content |
|---|---|
| Prompt | After how many days does an unhandled pending item expire (job marked abandoned, revivable)? Default 7. |
| Field path | `policy.pending_item_expiry_days` |
| Allowed answers | integer 1–90 |
| Default | `7` |
| Skippable | Yes |
| Why we ask | ARCHITECTURE §3.4 timeout rules. |

### q7_7 Platform ToS disclaimer (not asked again)

| Item | Content |
|---|---|
| Action | Read `onboarding.json.tos_acknowledged_at`; if present write `policy.platform_tos_acknowledged=true`; if absent return to onboarding, show the SECURITY §7.3 text and continue only after the user types "I understand and agree". |
| Field path | `policy.platform_tos_acknowledged` |
| Allowed answers | `true` |
| Default | none |
| Skippable | No |
| Why we ask | D13. |

### q7_8 Overall sign-off

| Item | Content |
|---|---|
| Prompt | Profile summary (no contact details in clear): `<intent / salary / rules / policy summary>`. Reply "sign" if correct; otherwise say what to change. |
| Field path | `meta.intake_signed_at`; `meta.updated_at` |
| Allowed answers | "sign" / an edit instruction |
| Default | none |
| Skippable | No |
| Why we ask | ARCHITECTURE §2.2 `intake` exit condition; written only after `validate profile` passes. |

---

## 9. Fixed actions at the end of each round

| Round | Written at the end | Check |
|---|---|---|
| 0 | `materials.*`, `meta.*`; `intake_state.round_done=0` | files exist and are readable |
| 1 | `identity.*`, `education[]`, `experience[]`, `skills.*`; `resume_parse.json`; `consistency_report.json`; `round_done=1` | `consistency` not `block` (or `known_mismatches` recorded) |
| 2 | `status.*`, `identity.address`, `identity.date_of_birth`, `identity.gender`; `round_done=2` | — |
| 3 | `intent.*`; `round_done=3` | `intent.types`, `intent.locations` non-empty |
| 4 | `salary.*`; `round_done=4` | `hard_floor ≤ expected_min` when both present, otherwise warn |
| 5 | `rules.*`; legacy ledger import; `round_done=5` | no company appears on both the blacklist and the referral list |
| 6 | `policy.cover_letter_policy` … `policy.declarations`; `facts_card.json` + `facts_card.md` (signed); `round_done=6` | `validate facts_card` exit code 0; `signed_by_user=true` |
| 7 | `policy.submit_mode` … `policy.pending_item_expiry_days`; `meta.intake_signed_at`; `round_done=7` | `validate profile` exit code 0 |

---

## 10. Naming convention for `policy.declarations.other[].question` (holding place)

| Prefix | Meaning | Example |
|---|---|---|
| `common:<key>` | cross-platform declaration / fixed-answer question | `common:previously_dismissed` |
| `platform:<platform>:<key>` | the user's choice for a platform's fixed-option question (still with no dedicated field) | `platform:lever:visa_status_option` (q6_13 l) |

The Executor matches prefixes exactly; not found = `null` semantics (suspend). These prefixes are a convention outside the schema and should migrate once the corresponding fields exist (section 11). **The `skill_years:<skill>` / `skill_level:<skill>` prefixes were retired on 2026-09-05** — skill years and self-ratings now write directly to `skills.years_by_skill` / `skills.proficiency` (q1_8) and no longer go through `declarations.other[]`.

---

## 11. Schema fields now implemented (formerly "suggested"; approved by the product owner and added to the schema on 2026-09-05)

These fields used to be "suggested additions" parked by various questions in `declarations.other[]` / `notes` / `intake_state.json` (non-contract). `schemas/profile.schema.json` now has them; Intake writes the formal path directly and no longer parks the value.

| Field | Reason | Related question | Pre-migration holding place (retired) |
|---|---|---|---|
| `skills.years_by_skill{<skill>: int}` | LinkedIn years question is integer-only (linkedin.md §5) | q1_8 | `declarations.other[]` `skill_years:*` |
| `skills.proficiency{<skill>: enum}` | Greenhouse / SmartRecruiters self-rating questions | q1_8 | `declarations.other[]` `skill_level:*` |
| `intent.can_start_immediately: bool` | "start immediately" questions must be Yes to pass (linkedin.md §11, smartrecruiters.md §5) | q3_7 (falls back to converting `earliest_start` when unset) | derived from `earliest_start` |
| `intent.full_time: bool`, `intent.days_per_week: int` | asked directly by Ashby / Lever / SmartRecruiters | q3_8 (falls back to converting `hours_per_week` when unset) | derived from `hours_per_week` |
| `intent.notice_period: string` | asked by Greenhouse | q6_13 j | `declarations.other[]` `common:notice_period` |
| `intent.work_mode: enum(onsite/hybrid/remote/any)` | LinkedIn "On-site at <location>?" | no dedicated question yet; Intake may set it after a q3_* follow-up | approximated by `remote_ok` |
| `salary.current: number` | Workday "Current salary" | q4_7 | `salary.notes` |
| `rules.company_caps[{company, max_applications}]` | stricter company-level caps (PwC 1 application, workday.md §12) | q5_6 follow-up | none (Screening reads playbooks) |
| `rules.notes: string` | catch-all free rules | q5_13 | `intake_state.json.free_rules[]` (pending) |
| `materials.job_list_paths[]` | R2 user list paths (incident I-02) | q5_12 | `intake_state.json.user_job_lists[]` (pending) |
| `policy.source_channel_default` (`$defs/channel` enum) | Workday "How did you hear about us" | q6_13 h | `declarations.other[]` `common:source_channel` |
| `policy.platform_option_overrides.<platform>.<field_label>: string` | Jobstreet / Lever fixed-option questions (jobstreet.md §9, lever.md §5) | q6_13 k | `declarations.other[]` `platform:*` |
| `rules.per_company_max` `maximum` 50 → 3 | align with the SECURITY §7.2 hard cap | q5_6 | Intake wrote ≤ 3 only (now enforced by the schema) |
| `intake_state.json` gains `skipped_questions[]` | needed by discipline rule 3 | throughout | pending (`user_job_lists[]`/`free_rules[]` migrated above, no longer needed) |

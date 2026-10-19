# checklists/evidence_rules.md — 证据规则 / Evidence rules

> 适用范围：QA（提交后取证）、Tracker（邮件 / 门户补证据）、Reporter（第 1 栏口径）、Executor（知道什么不算）。状态：[未验证]（Phase 1，2026-09-05）。
> 规范来源：`ARCHITECTURE.md` §7（本文只引用与举例，不另立口径）；上位：`BRIEF.md` §3"已投"标准；`SECURITY.md` §4 截图脱敏；`INCIDENTS.md` I-18。
> 一句话：**`status=applied` 仅当 `evidence` 表存在 ≥ 1 条 `qualifies=1` 的证据，`qualifies` 只由 `app evidence` 脚本判定，Agent 不得手写。**（ARCHITECTURE §7.1；`ledger assert applied-has-evidence`，写入前强制检查，失败退出码 3）

## 1. BRIEF §3 原文

> **"已投"标准**：只有职位级成功页或雇主/ATS 确认邮件才算。填完表、最终确认页、账号验证邮件、打开的标签页都不算。

## 2. 证据类型与合格性（ARCHITECTURE §7.1，`evidence_type` 枚举）

| `evidence_type` | 合格 | 说明 |
|---|---|---|
| `success_page` | 是 | 职位级成功页：含岗位名或需求编号 + "application submitted / received / thank you for applying" 等语义；`job_title_seen` 必填且与 job 的 `title` / `req_id` 模糊匹配 ≥ 0.6，否则不合格 |
| `ats_confirmation_email` | 是 | ATS / 雇主发的**该岗位**确认邮件（主题或正文含岗位名 / 编号），发件域 ∈ 公司域或已知 ATS 域 |
| `employer_confirmation_email` | 是 | 雇主人工回复确认收到 |
| `ats_portal_status` | 是（B 级，[待定]） | ATS 候选人门户"我的申请"列出该岗位且状态为 Submitted / Applied / Under review；是否与成功页同等待产品负责人裁定（ARCHITECTURE §13 第 1 条），裁定前只作补充证据 |
| `legacy_import` | 是（C 级） | 旧台账经 `ledger migrate-legacy` 导入，原台账已按同一口径确认 |
| `review_page_screenshot` | 否 | 最终确认页 / Review 页，尚未提交 |
| `form_completed_screenshot` | 否 | 填完表 |
| `draft_saved` | 否 | 草稿已保存 |
| `account_verification_email` | 否 | 账号 / 邮箱验证邮件，与岗位无关（I-15） |
| `external_redirect` | 否 | Jobstreet `/apply/external` "访问了雇主网站"等跳转（I-18） |
| `open_tab` | 否 | 只是打开了页面 |
| `generic_ack_email` | 否 | 不含岗位信息的泛回执（"我们收到了您的信息"）→ Tracker 进一步匹配后才可能转为合格类型 |

## 3. 每条证据必须记录的字段（ARCHITECTURE §7.2；经 `AA app evidence` 传入，无独立参数的写 `--note`，[未验证]）

- 共同：`evidence_type`、`captured_at`、`captured_by`（agent 名）、`notes`；`qualifies` 由脚本写。
- 页面类（`success_page` / `ats_portal_status` / `review_page_screenshot` / `form_completed_screenshot` / `external_redirect` / `open_tab`）：`url`（必填）、`page_title`、`file`（截图或页面文本，相对 `evidence/`，必填其一）、`sha256`、`job_title_seen`（`success_page` 必填）。
- 邮件类（`*_email`）：`email_subject`、`email_from`（域名）、`email_received_at`（必填）、`email_message_id`、`email_excerpt`（≤ 300 字，脱敏）、`matched_job_by` ∈ `title | req_id | company_domain | manual`。发件域须 ∈ 公司域或已知 ATS 域（`myworkday.com`、`successfactors.com`、`greenhouse.io`、`ashbyhq.com`、`smartrecruiters.com`、`lever.co`、`workable.com`、`jobstreet.com`、`seek.com`、`linkedin.com`、`mycareersfuture.gov.sg`…；列表由 D 维护）或主题含岗位名。
- `legacy_import`：`legacy_ref`（原台账行文本）、`imported_at`。

## 4. 文件命名与脱敏（ARCHITECTURE §7.3；SECURITY §4）

- `<data>/evidence/<app_id>/<NN>_<evidence_type>.<png|txt|html|json>`，`NN` 两位递增；截图优先 png，页面文本 txt，邮件元数据 json。
- 文本类写入前脱敏：邮箱 → `a***@example.com`，手机 → `+65 ****1234`，NRIC/FIN 模式 → `[REDACTED:nric]`；CLI 无 `redact` verb，Agent 手工处理（缺口，SKILL.md §12）。
- 只截必要区域，优先页面文本；禁止截密码框有内容、OTP 正文、含证件号字段的表单、支付页、简历预览。
- 成功页截图可含用户自己的姓名 / 邮箱（本机证据），永不进仓库；分享前打码。
- 文件名不含个人信息。

## 5. 各平台合格示例（来自 `playbooks/<platform>.md` §10，观察 2026-08，Codex 内置浏览器 / Chrome 扩展；证据来源缩写见 `playbooks/README.md` §3）

| 平台 | 合格（`success_page` / `ats_portal_status` / 邮件） | 不合格（常见误判） |
|---|---|---|
| Jobstreet | URL `…/job/<id>/apply/success` + "申请已发送 / 已发送给 <雇主>"（已验证 L90、L100、L112；台账 §一）；岗位卡 `Applied on Jobstreet`（L2532）；Jobstreet 自动"成功提交"回执邮件（L716） | `…/apply/external` "访问了雇主申请网站"（L256、L5039）；收藏提醒邮件（L871）；职位推荐邮件（L765）；"职位已停止接收新申请"邮件（不是拒信也不是证据） |
| LinkedIn Easy Apply | 岗位页刷新后"申请状态：申请已提交"（L4808、L4840）；成功框"您的申请已发送给 <Company>"（L4586）；LinkedIn 申请确认邮件（地点字段可能错，L7400，证据仍合格但地点须以官网核对） | 追踪器"进行中"（草稿）；"已申请"计数（不含岗位名，非个人证据）；职位推荐邮件；主页浏览通知 |
| Workday | 弹窗 "Application Submitted"（L3171、L5007）/ "您的申请已成功提交"（L5207）；Candidate Home `Application Submitted / In Progress / In Process`（L3264、L3521）；`Application Received` + 日期（L3155）；Vopak "Your application is now complete"（L2870）；"You've already applied for this job"（历史已投补记，不重复计数，L3701） | 账号验证邮件；服务错误后回到表单；Review 页 "No Response" |
| SuccessFactors | "Your application has been sent. Thank you!"（Singtel L3292）；"Thank you … for submitting your application"（L7332）；EY 回执邮件（L718） | Apply 后 Loading 卡死无回执（Temasek，I-07）→ `draft_saved` / `submitted_unverified`；账号激活邮件 |
| Greenhouse | "Thank you for applying. Your application has been received."（L7045）及变体（L3813、L7256、L7159、L7212）；Greenhouse 代发确认邮件（L7196） | 邮箱验证码邮件本身；填完但未过验证码的表单（L4907、L7095） |
| Ashby | "Your application was successfully submitted"（L2607、L2699、L7320）；"Success — application was successfully submitted"（L3835） | 反垃圾拦截页；填完未提交 |
| SmartRecruiters | "Application submitted!"（L4023、L4039）/ "申请已提交"（L4319）；正式确认邮件（L6816） | "Next" 假可点的停留页（I-08）；解析超时页 |
| Lever | "Application submitted!"（L3649、L3887）；确认邮件（L7196） | 地点控件返空后被清空的表单（I-09） |
| Workable | 回执文案 "Your application has been submitted successfully."（L276）；自动确认邮件（L708） | 卡在声明题 / 上传的表单 |
| MyCareersFuture | **未验证**：只认用户本人截图的提交成功页或 MCF / 雇主回执邮件 | 岗位卡 "N applications" 计数 |
| 未知平台 | 按 `_template.md` §10：至少一种职位级证据（URL / 文案 / 门户状态 / 回执主题）；拿不到 → `submitted_unverified` | 一切"看起来提交了" |

`ats_portal_status` 与 `success_page` 的 URL 模式多数**未验证**（各 playbook §14），所以 `job_title_seen` 与页面文案是主要判定依据，URL 只作辅助。

## 6. 流程（谁在什么时候调什么）

1. Executor 点提交 → `AA app status <app_id> submitted_unverified` → 交 QA。
2. QA：读成功页（`get_page_text` / `read_page`；必要时 `screenshot`）→ 存 `evidence/<app_id>/01_success_page.txt|png` → `AA app evidence <app_id> --type success_page --url "<URL>" --screenshot "<相对路径>" --note "page_title=<标题>; job_title_seen=<页面上的岗位名或编号>"` → 退出码 0 且脚本判合格 → `AA app status <app_id> applied`；脚本判不合格 → 保持 `submitted_unverified`，`verify.json` 写缺项。
3. Tracker：收到该岗位确认邮件 → `AA app evidence <app_id> --type ats_confirmation_email --subject "<主题>" --note "from_domain=<域>; received_at=<ISO>; matched_job_by=<req_id|title|company_domain>"` → 合格 → `AA app status <app_id> applied`。
4. 用户说"我自己提交了"（`user_completed`）≠ 已投：QA / Tracker 按上面 2–3 找证据，找到合格证据才 `applied`（`gates.md` §0）。
5. `applied` 写入被脚本拒绝（退出码 3）→ 原样转述 stderr，状态保持 `submitted_unverified`，不重试"换个类型再写"。
6. Reporter 第 1 栏只取 `applied`；`submitted_unverified` 进第 3 栏并注明"等回执"。

## 7. 计数口径（R1、ARCHITECTURE §6.1）

- 去重岗位数 `unique_jobs_applied` = `COUNT(DISTINCT job_id) WHERE status='applied'`；提交动作数 `submission_actions` = `SUM(submission_action_count)`；重复 = 差值。同一岗位官网 + LinkedIn 各投一次 = 1 岗 / 2 次（I-01）。
- 证据条数不是计数单位；一岗多证据仍是 1 岗。

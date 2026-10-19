# Playbook 模板（通用流程 + 未知平台兜底）

> 所有平台 playbook 严格按下面 14 节写；架构师的 Executor 契约按同一结构读。
> 证据标签规则：每条事实必须带 **已验证（来源）** 或 **未验证**。来源缩写见 `README.md`「证据来源」。
> 本模板同时是**未知平台的默认流程**：遇到 `README.md` 识别表之外的 ATS，按本文件执行，并把新发现写进 `INCIDENTS.md`（由 Orchestrator 记录，playbook 本身不写真实个人数据）。

---

## 1. 识别特征
- URL 模式：`<写域名/路径模式>`；页面特征：`<品牌/控件/文案>`。
- 未知平台：先记录 `apply_url`、页面 `<title>`、表单步骤数、是否要求登录，作为 INCIDENTS 条目的识别字段。

## 2. 登录态检测
- 判定已登录的证据（顶栏用户名 / "Candidate Home" / "My applications" 等）。
- 无登录态时的动作：**先判断该岗位是否允许免登录申请**（很多 ATS 允许），允许则直接申请；否则进入第 3 节注册关口。
- 硬规则（BRIEF §3）：Agent 永不输入密码；出现 OTP / CAPTCHA / 邮箱验证 → 挂起并写 `pending_actions.md`。

## 3. 账号注册关口
- Agent 可预填：`identity.full_name_en`、`identity.email`、`identity.phone.*`（注册页允许的非密码字段）。
- 必须停给用户：密码框、密码确认、CAPTCHA、OTP、生日（若 profile 未提供）、证件号（永不填，BRIEF D3）。
- 运行时差异：只引用 **BRIEF D3**，不展开。
- 记账：账号创建 ≠ 已投（BRIEF §3「已投标准」）。

## 4. 表单流程步骤
- 分步/分页顺序（例：① 个人信息 → ② 简历/经历 → ③ 声明题 → ④ 自愿披露 → ⑤ 复核 → ⑥ 提交）。
- 每步的「Next/Continue/Save and Continue」按钮名与卡点。

## 5. 字段映射（profile → 表单）
profile 顶层分组固定为 `identity / status / education[] / experience[] / skills / intent / salary / rules / materials / policy`。

| 表单字段（英文原文） | profile 字段 | 备注 |
|---|---|---|
| First / Given name | `identity.given_name` | 按护照拆分 |
| Last / Family name | `identity.family_name` | |
| Email | `identity.email` | |
| Phone country code / number | `identity.phone.country_code` / `identity.phone.number` | 提交前复核区号（R10） |
| Current location / City / Country | `identity.address.city` / `identity.address.country` | |
| LinkedIn / GitHub / Portfolio | `identity.linkedin_url` / `identity.github_url` / `identity.portfolio_url` | 无则留空，不猜 |
| School / Degree / Major / Dates | `education[].school` / `.degree` / `.major` / `.start_date` / `.graduation_date` | 毕业年份易被解析错（R10） |
| Employer / Title / Dates / Description | `experience[].company` / `.title` / `.start_date` / `.end_date` / `.description` | 注意字符上限（第 6 节） |
| Skills | `skills.technical[]` | 平台下拉无匹配项则留空 |
| Languages | `skills.languages[]` | |
| Available from / to / Duration | `intent.available_from` / `intent.available_to` / `intent.duration_months` | |
| Full-time? / Days per week | `intent.full_time` / `intent.days_per_week` | |
| Expected salary | `salary.expected_min` / `salary.expected_max` / `salary.currency` / `salary.period` | 区间内取值；低于 `salary.floor` → 跳过记账 |
| Legally authorised to work (this internship) | `status.authorized_to_work_internship` | 与「需赞助」是两题，不能混（第 9 节） |
| Require sponsorship (this internship) | `status.requires_sponsorship_internship` | |
| Require sponsorship (future full-time) | `status.requires_sponsorship_future` | |
| Visa / Pass type | `status.visa_type` | 下拉无对应项 → 挂起，不选近似项 |
| Resume / CV | `materials.resume_en_path`（或 `materials.resume_zh_path`） | 只用 profile 指定版本（D6） |
| Transcript | `materials.transcript_path` | 无则跳过并记账 |
| Cover letter / Message to hiring team | `materials.cover_letter_policy` → Content Agent | D9：生成后需批准 |

## 6. 字符上限与控件坑
- 长文本字段：写明上限（若已知）与超限表现（Next 看似可点但不跳转、静默截断、红字报错）。
- 特殊控件：日期分段控件、地点自动完成、隐藏原生文件控件、折叠必答题、解析器污染字段。
- 通用对策：超限先按 `experience[].description` 的分段压缩策略（Content Agent 只删不改事实）；解析器带入的内容逐项与 profile 比对再保存。

## 7. Save 草稿与超时策略
- 有 Save 的平台：单份 >20 分钟先 Save 一次；长表单每完成一页 Save（R5、job-apply SKILL 经验）。
- 会话失效表现（登出 / CSRF 失效 / Loading 卡死）→ 重新登录后从草稿恢复，**不重填、不重复提交**。
- 无 Save 的平台：把已填内容作为 `runs/<run_id>/draft_<job_id>.json` 落盘，页面丢失后可重填。

## 8. 简历上传方式
- 上传通道优先级：① 页面可见的文件输入/"Attach"按钮 → ② 平台已存简历（先核对文件名/哈希是否为 profile 指定版本）→ ③ "Enter manually"/粘贴文本（用 `materials.resume_text_en`）→ ④ 系统文件选择器（需 computer-use，且仅在真实 Chrome 中可行）。
- 扩展前置条件：Chrome 扩展需 "Allow access to file URLs"（onboarding 检查清单项，Codex 扩展已验证；Claude Code 扩展的对应项未验证）。
- 上传后必须核对：页面显示的文件名 == profile 指定文件名。

## 9. 开放题与声明题出现的位置
- 开放题（"Why X?" 等）：位置、是否必填 → Content Agent（D9）。
- 声明题（司法记录 / 疫苗 / 利益冲突 / 政府官员亲属 / 曾被解雇 / 董事职务 / EEO）：位置 → 只从 `policy.declarations.*` 取值；未预设 → 挂起（BRIEF §3）。
- 签证三问拆分（已验证，逐字稿 L2651-2657）：「有权在新加坡完成本次实习」≠「本次实习需赞助」≠「毕业后全职需赞助」，分别映射 `status.authorized_to_work_internship` / `status.requires_sponsorship_internship` / `status.requires_sponsorship_future`。

## 10. 成功页特征
- URL 模式 / 页面文案 / 候选人主页状态 / 回执邮件主题模式，至少给一种「职位级」证据。
- 不算证据：账号验证邮件、最终确认页、"Visited external site"、LinkedIn 追踪器计数、打开的标签页（BRIEF §3）。
- QA Agent 抓证据：成功页 URL + 截图 + （若有）回执主题，写入 `evidence/`。

## 11. 失败模式与处理
每条：**现象 → 判断 → 动作 → 记账状态**。记账状态**只能**使用 `ARCHITECTURE.md` §9 的 `applications.status` 枚举：`queued` / `in_progress` / `draft_saved` / `pending_user` / `ready_to_submit` / `submitted_unverified` / `applied` / `skipped` / `failed` / `withdrawn` / `abandoned`；`skipped` 必须附 `skip_reason_code`（同 §9 枚举）；`applied` 只能在脚本判定证据合格后由脚本置位。
- 扩展断连 / 标签页锁死 → 挂起 → 恢复后先读页面状态再决定是否重填 → `failed`（R4，禁止假装完成）。
- CAPTCHA / OTP / 密码 → 挂起 → `pending_user`。
- 证件号 / 未预设声明题 / 高中成绩等未知事实 → 跳过 → `skipped`（附 skip_reason_code）（不编造）。
- "You've already applied" → 查台账；台账无记录则补记 `applied`（须有合格证据，否则 `submitted_unverified`）（证据=该提示截图）→ `skipped`（already_applied）。

## 12. 配额与节流
- 全局：每轮 10、每日 ≤20、同公司 ≤3（D13）。
- 平台特有配额（LinkedIn 日配额、公司级 "最多 N 份/年" 规则）写在各 playbook。

## 13. 已知事故
- 引用来源：逐字稿行号 / 台账条目 / INCIDENTS 编号。

## 14. 未验证项
- 凡是没有一手证据、只是常识推断的内容，列在这里并标「未验证」，不混进正文。

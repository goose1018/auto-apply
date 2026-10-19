# BRIEF — auto-apply v1 冻结需求与决策（项目宪法）

> 冻结日期：2026-09-05。来源：2026-09-04/05 与产品负责人的两轮需求确认，Plan 原件在
> `~/Documents/Codex/2026-09-04/自动投递工作流_Plan与需求确认_v0.md`。
> **每个构建 Agent 开工前必读本文件；与本文件冲突的设计一律以本文件为准，改动需回到本文件先改。**

## 1. 定位

`auto-apply` 是面向**在新加坡找实习/工作的学生（任何国籍）**的 AI 投递流水线 skill：
求职者丢一份简历 → AI 分轮问清意向、硬信息与排除项 → 多 Agent 自动找岗、筛岗、填表、投递、记账、追状态 → 人只在**密码 / 验证码 / 证件号 / 本人声明题 / 最终授权**关口出面。

产品形态 = **A：通用型个人工具**。每个用户在自己电脑安装 skill、用自己的简历和自己的浏览器跑；个人数据只存本机；仓库里没有任何真实个人数据。

## 2. 冻结决策（D）

| # | 决策 | 说明 |
|---|---|---|
| D1 | 用户群 | 在新加坡找工作的学生，不限国籍；用户可见文案中英双语，跟随用户语言 |
| D2 | 运行时 | **Claude Code 主运行时**；Codex 薄适配层（同一 skill 目录，`runtime/` 下分文件）；核心内容运行时无关 |
| D3 | 凭据策略 | Claude Code：Agent 永不输入密码，注册时预填非密码字段→停在密码框→用户手输并存 Chrome→之后 Chrome 自动填。Codex：用户在本机 `secrets.env` 指定**求职专用密码**后，Codex 可代输。两运行时都**永不**收集证件号/银行信息，密码永不进 profile、日志、会话、仓库 |
| D4 | 浏览器 | 用户已登录的 Chrome（Claude Code 走 claude-in-chrome 扩展；Codex 走其浏览器/扩展）主通道；备用无登录态浏览器仅用于只读核验。Executor 单线程；只读 Agent 可并行 |
| D5 | v1 平台集 | 新加坡：Jobstreet/SEEK、LinkedIn Easy Apply、MyCareersFuture、公司官网 ATS（Workday、SuccessFactors、Greenhouse、Ashby、SmartRecruiters、Lever、Workable）。中国招聘平台与中国校招官网 = v2 |
| D6 | 简历 | **不生成、不翻译、不改写**简历；岗位需要某语言版本而用户没给 → 提示用户补一份 |
| D7 | 母清单流程 | 每轮先出母清单（来源/JD 摘要/匹配理由/风险/平台类型）→ 用户批量批准并勾排除 → 才进入投递队列。自主搜索结果必须经用户批准入队 |
| D8 | 最终提交 | 默认 `confirm`（停在提交前）；`autopilot` 需用户在 profile 中书面开启 |
| D9 | 开放题/CL | Content Agent 只引用 facts_card 生成；默认生成后须用户批准才填；用户可设为跳过/自动 |
| D10 | 邮件追踪 | 邮件后端抽象：优先运行时邮箱连接器（Codex gmail 插件；Claude Code 的 claude.ai Gmail/Outlook 连接器，需用户自行授权），无连接器则退回已登录 Chrome 读网页邮箱。推荐用户用 Gmail/Outlook。**只读，不发不删** |
| D11 | 台账 | SQLite 主存 + 导出 Markdown（兼容"四节"格式：已确认/中间状态/规则/状态追踪表） |
| D12 | 技术栈 | Python 3.9+，**仅标准库**（用户零安装；覆盖 macOS 自带 /usr/bin/python3）；JSON Schema 作文档 + 手写校验；无服务器、无 API key |
| D13 | 节奏与节流 | 默认每轮 10 份、每日 ≤20 份、同公司 ≤3、每 5 份汇报一次；LinkedIn 日配额感知；onboarding 含平台 ToS 免责说明 |
| D14 | 目录与仓库 | 代码 `~/cursor/auto-apply/`；数据 `~/auto-apply-data/<profile_id>/`；GitHub 仓库、commit、push 由产品负责人操作，Agent 不提交 |
| D15 | 禁止脚本直连 | 不做 Playwright/HTTP 直连 ATS，不绕过反自动化；全部走真实浏览器 |
| D16 | v1 成功定义 | 两位外部同学各 ≥10 份**有证据**的确认投递，一周内完成；新用户 onboarding ≤ 60 分钟 |
| D17 | 现有资产 | `~/.claude/skills/job-apply/`（作者个人版）保持不动，直到本 skill 通过 Phase 7 再迁移；首位用户的台账通过 `migrate_legacy_ledger.py` 导入 |

## 3. 硬边界（Harness，不可越过）

- **事实底线**：不编造任何经历、指标、日期、签证答案、声明题答案。缺失字段 = 跳过并记账，绝不猜。
- **"已投"标准**：只有职位级成功页或雇主/ATS 确认邮件才算。填完表、最终确认页、账号验证邮件、打开的标签页都不算。
- **必停关口**：密码/新建账号（Claude Code）、CAPTCHA、邮箱/短信 OTP、证件号、支付、必须本人回答的声明题（司法记录/疫苗/EEO 若用户未预设）、最终提交（confirm 模式）。
- **必跳过并记账**：日期窗不符、学历门槛不符、薪资低于下限、已投、公司黑名单/保留内推名单。
- **浏览器断连/扩展失效** = 挂起并记录，**禁止假装完成**。
- **禁止在会话里传密码**；Agent 收到密码文本必须拒绝使用并提醒更换。
- 汇报只引用台账，不凭记忆报数。

## 4. 从 2026-08 真实事故反推的需求（R，写进 DoD）

- R1 去重键 = normalize(公司) + normalize(岗位名)；渠道是属性；计数只数去重岗位，提交动作另计。
- R2 母清单优先：先消费用户清单/链接，再自主搜索；每条候选标来源。
- R3 简历-档案一致性门：解析简历里的联系方式/毕业年份与 profile 比对，不一致先报警。
- R4 浏览器双通道，断连挂起不假装。
- R5 平台适配：每个 ATS 一份 playbook（字段上限、Save 草稿节奏、超时策略、成功页特征、控件坑）。
- R6 LinkedIn 日配额感知，达上限自动切平台。
- R7 SECURITY.md 写死密码红线与日志脱敏。
- R8 公司策略字段：黑名单、保留内推名单、全球限额岗位规则。
- R9 开放题：只引用 facts_card，生成后批准。
- R10 提交前复核清单脚本化（姓名顺序/区号/毕业年份/简历版本/实习期/薪资）。

## 5. 运行时架构

```
/auto-apply ──► Orchestrator（状态机：onboard → intake → source → screen → apply → verify → ledger → track → report）
                 ├─ ① Intake 问诊       简历解析 → profile.json + facts_card.md → 分轮提问 → 用户签字
                 ├─ ② Sourcing 找岗     用户清单/链接优先 + 站内搜索 → candidates（母清单）
                 ├─ ③ Screening 筛岗    硬条件过滤 + 台账查重 + 公司策略 + 匹配打分 → apply_queue（用户批准）
                 ├─ ④ Executor 填表     按平台 playbook 在已登录浏览器填表；关口挂起；长表单 Save 节奏
                 ├─ ⑤ Content 内容      cover letter / 开放题，只引用 facts_card；默认需批准
                 ├─ ⑥ QA 复核           提交前清单核对；提交后抓证据（成功页 URL / 截图 / 回执主题）
                 ├─ ⑦ Tracker 状态      邮件后端 → 回执 / 审核中 / 实质进展 / 拒信 → 写台账
                 └─ ⑧ Reporter 汇报     三栏：已确认投递 / 待用户动作 / 卡壳原因
```

关口协议：Orchestrator 统一管理。挂起 → 写 `runs/<run_id>/pending_actions.md`（待用户动作清单）→ 用户处理后说"继续" → 从检查点恢复。

## 6. 仓库与数据布局

```
~/cursor/auto-apply/
├── BRIEF.md（本文件） README.md CLAUDE.md ARCHITECTURE.md CODE_STANDARDS.md SECURITY.md HISTORY.md INCIDENTS.md
├── skills/auto-apply/                 # 可安装、自包含的 skill；install.sh 软链到 ~/.claude/skills 与 ~/.codex/skills
│   ├── SKILL.md                       # Orchestrator（运行时无关）
│   ├── runtime/{claude-code.md, codex.md}   # 工具映射 + 凭据策略差异
│   ├── agents/01-intake.md … 08-reporter.md
│   ├── intake/{questionnaire.zh.md, questionnaire.en.md, facts_card.template.md, onboarding_checklist.md}
│   ├── playbooks/{_template.md, jobstreet.md, linkedin.md, mycareersfuture.md, workday.md, successfactors.md,
│   │              greenhouse.md, ashby.md, smartrecruiters.md, lever.md, workable.md}
│   ├── checklists/{pre_submit.md, evidence_rules.md}
│   ├── gates.md
│   └── scripts/autoapply/             # Python 包（stdlib only）：profile 校验、台账、查重、导出、运行状态、自检
├── schemas/                           # profile / job / application / facts_card 的 JSON Schema
├── examples/profile.example.json      # 虚构人物，不含任何真实个人数据
├── scripts/verify/                    # 每功能一个 verify 脚本，退出码非零即失败
├── tests/                             # pytest（标准库 unittest 亦可）+ fixtures（假 ATS 页面）
├── install.sh  pyproject.toml  .gitignore

~/auto-apply-data/<profile_id>/
├── profile.json  facts_card.md  secrets.env(仅 Codex，gitignored)
├── ledger.sqlite  evidence/  runs/<run_id>/  exports/投递台账.md
```

## 7. 问诊（Intake）8 轮骨架

0 材料 → 1 简历解析确认（含一致性门）→ 2 身份与工作许可 → 3 求职意向（含排除方向）→ 4 薪资与条件（含硬下限）→ 5 排除与策略（黑名单/行业/岗位/保留内推/全球限额/同公司上限/渠道优先级/已有账号）→ 6 内容与声明（CL、开放题策略、EEO 默认 prefer not to say、本人声明题）→ 7 授权与节奏（confirm/autopilot、邮箱只读授权、汇报频率）。
原则：每轮内一次只问一个决定性问题；能从简历解析的先解析再确认；任何字段可"跳过/不知道"。

## 8. 阶段 DoD

- P1 地基：仓库结构、BRIEF/ARCHITECTURE/CODE_STANDARDS/SECURITY/CLAUDE/INCIDENTS、schema、状态机、verify 脚手架全部就位；`python3 scripts/verify/all.py` 通过。
- P2 Intake：用示例简历跑通问诊生成 profile + facts_card，schema 校验通过，一致性门能抓出联系方式不一致。
- P3 Sourcing+Screening：回放首位用户 8 月台账，已投岗 100% 被查重拦下；硬条件过滤有测试。
- P4 Executor：3 个平台（Jobstreet、Greenhouse/Ashby、Workday）真实投到"提交前"，关口全部正确挂起。
- P5 QA+Ledger：无证据不得标"已投"（verify 断言）；导出 Markdown 与四节格式兼容。
- P6 Tracker+Reporter：邮件四分类回放一周邮件正确；三栏汇报只引用台账。
- P7 真人试跑（首位用户 5 份）→ P8 第二位用户。

## 9. 写作与代码约定（摘要，详见 CODE_STANDARDS.md）

- 文档：中文为主，README 含英文安装段；用户可见问诊双语。
- 代码：Python 3.9+ 标准库；类型注解；模块边界（路由/服务/工具分层思想）；每功能 verify 脚本；日志脱敏。
- Agent 规范文件（agents/*.md）统一结构：职责 / 输入 / 输出 / 工具 / 关口 / 禁止 / 完成标准。
- 一切"已完成"必须附验证方式；FAIL 不得包装成完成。

# ARCHITECTURE — auto-apply v1 运行时无关架构与数据契约

> 版本：v1.0（2026-09-05，架构师 Agent A 起草）。上位文件：`BRIEF.md`（冲突以 BRIEF 为准）。
> 本文件定义**模块边界、状态机、关口协议、文件契约、去重/证据/一致性规范、台账 DDL、agents/playbooks 结构契约**。
> 实现由 B（playbooks）、C（intake）、D（scripts/ledger）、E（规范安全）、F（tests）承接；本文只写"是什么、边界在哪"，不写实现细节。
> 标注 **[待定]** = 需产品负责人拍板；**[未验证]** = 平台事实未经实测，B/F 在 P4 前核实。

---

## 0. 一页总览

```
用户 ──/auto-apply──► Orchestrator (skills/auto-apply/SKILL.md)
                       │  状态机 + 关口协议 + 检查点；不碰浏览器、不做业务判断
                       │
        ┌──────────────┼───────────────────────────────────────────┐
        ▼              ▼                                           ▼
  8 个职能 Agent    Python 脚本 (stdlib only)                 数据目录 ~/auto-apply-data/<profile_id>/
  (会话内 LLM)     AA <verb>                 profile.json / facts_card.* / ledger.sqlite
  读写文件、        校验 / 去重 / 台账 / 导出 / 复核 /          evidence/ / runs/<run_id>/ / exports/
  操作浏览器        运行状态 / 自检 / 脱敏
```

三条铁律贯穿全文：
1. **LLM 只做判断与操作，脚本只做确定性事情**；凡是能被脚本断言的（去重、复核、证据合格、状态转移合法性）都不交给记忆。
2. **一切进度以文件为准**：Agent 的"我记得"不算数；断连、换会话、换运行时后从检查点文件恢复。
3. **无证据不算已投**（BRIEF §3）；**无用户批准不入队**（D7）；**无签字事实不引用**（D9/R9）。

---

## 1. 模块边界（三层）

### 1.1 Orchestrator（`skills/auto-apply/SKILL.md`，运行时无关）

| 能做 | 不能做 |
|---|---|
| 读 `run_state.json` 决定当前状态；按 §2 状态机转移 | 直接操作浏览器（任何点击/填表） |
| 派发职能 Agent（顺序或并行，见 §1.4） | 做筛岗/匹配等业务判断（那是 Screening 的事） |
| 统一处理关口：收 Agent 上报 → 写 `pending_actions.jsonl` → 渲染 md → 挂起 | 替用户批准队列、替用户回答声明题、替用户点最终提交（confirm 模式） |
| 恢复：读 pending 项的用户处置 → 更新状态 → 重派 Agent | 从记忆汇报数字（必须调 Reporter，Reporter 只读台账） |
| 每 `report_every_n` 份触发一次进度汇报 | 修改 profile.json（只有 Intake 在用户确认后可写） |
| 调 `autoapply selfcheck / runstate / pending / report` 脚本 | 接收/转发/存储任何密码文本（见 SECURITY.md，收到即拒绝并提醒更换） |

### 1.2 职能 Agent（`skills/auto-apply/agents/01-intake.md … 08-reporter.md`）

| # | Agent | 角色一句话 | 碰浏览器？ | 可并行？ |
|---|---|---|---|---|
| ① | Intake 问诊 | 简历解析 → 8 轮提问 → `profile.json` + `facts_card.*` → 一致性门 | 否 | 否（与用户对话，单线程） |
| ② | Sourcing 找岗 | 先消费用户清单/链接，再站内搜索 → `candidates.jsonl`，每条标来源 | **读**（搜索页/JD 页） | 是（只读，可按来源拆多个子 Agent，各用自己的标签页） |
| ③ | Screening 筛岗 | 硬条件 + `autoapply dedup` + 公司策略 + 匹配打分 → `shortlist.md` → 用户批准 → `apply_queue.jsonl` | 否（JD 已在 candidates 内；需补读 JD 时为**读**） | 是（纯判断） |
| ④ | Executor 填表 | 按 playbook 在已登录浏览器填表；触发关口即上报；长表单 Save 节奏 | **写**（唯一） | **否，全局单线程** |
| ⑤ | Content 内容 | cover letter / 开放题草稿，只引用已签字事实 → 默认待批准 | 否 | 是（可为队列中后续岗位预生成） |
| ⑥ | QA 复核 | 提交前跑 `autoapply presubmit`；提交后抓证据、跑 `autoapply evidence check` | **读**（成功页/截图） | 否（与 Executor 共用同一标签页，串行） |
| ⑦ | Tracker 状态 | 邮件后端四分类（回执/审核中/实质进展/拒信）+ ATS 候选人页 → 台账 | 连接器：否；网页邮箱：**读** | 连接器模式可并行；网页邮箱模式**不得**与 apply 阶段并行 |
| ⑧ | Reporter 汇报 | 三栏汇报 + `exports/投递台账.md`；只引用台账 | 否 | 是 |

每个 Agent 的能力边界写在各自 `agents/NN-<name>.md`，结构见 §10.1。共同禁令：
- 不编造事实；缺字段 = 跳过并记账。
- 不写 `ledger.sqlite`（只有 `autoapply ledger` 脚本能写；Agent 通过 CLI 调用）。
- 不写 `profile.json`（只有 Intake 在用户逐条确认后通过 `autoapply profile write` 写）。
- 不把任何密码、OTP、证件号写进任何文件（含日志、pending、evidence 文本）。

### 1.3 Python 脚本层（`skills/auto-apply/scripts/autoapply/`，Python 3.9+，仅标准库，D12）

**只做确定性事情；无网络、无浏览器、无 LLM、无第三方包。** 统一入口 `AA <verb> [--profile <id>] [--run <run_id>] ...`，退出码 0 = 通过，非 0 = 失败并在 stderr 给出机器可读原因（JSON 一行）。

| 模块（建议文件名） | CLI verb | 职责 | 输入 → 输出 |
|---|---|---|---|
| `paths.py` | — | 解析数据目录（`AUTO_APPLY_DATA_DIR` 环境变量 > `~/auto-apply-data/`） | — |
| `schema.py` | — | 手写 JSON Schema 校验器，支持关键字子集见 §11 | schema + instance → errors[] |
| `validate.py` | `validate <kind> <file>` | 校验 profile / facts_card / job / application / run_state / pending_action | 文件 → 退出码 + 错误列表 |
| `normalize.py` | `normalize --company X --title Y` | §6 规范化与 `dedup_key` / `job_id` | 字符串 → JSON |
| `dedup.py` | `dedup <candidates.jsonl>` | 候选逐条对台账查重（精确 + 疑似） | candidates + ledger → 标注后的 jsonl |
| `ledger.py` | `ledger init / upsert-job / upsert-app / add-evidence / add-event / add-gate / query / assert` | §9 DDL、写入、断言（如"applied 必有合格证据"） | JSON 行 → sqlite |
| `export_md.py` | `export` | 台账 → `exports/投递台账.md`（四节格式，§5.6） | sqlite → md |
| `runstate.py` | `runstate init / get / set-phase / suspend / resume` | `run_state.json` 读写；**校验转移合法性**（§2.3 转移表之外一律拒绝） | json ↔ json |
| `pending.py` | `pending add / render / resolve / expire` | `pending_actions.jsonl` 追加、渲染 md、标记处置、过期 | jsonl ↔ md |
| `evidence.py` | `evidence register / check` | 证据文件登记（sha256、命名、字段完整性）、是否够格判定 `applied`（§7） | 文件 + 元数据 → evidence 行 |
| `consistency.py` | `consistency` | R3：`resume_parse.json` 与 `profile.json` 比对 → `consistency_report.json` | json → json + 退出码 |
| `presubmit.py` | `presubmit <app_id>` | R10：`form_state.json` 与 profile/job 逐项比对 → `pre_submit_check.json` | json → json + 退出码 |
| `quota.py` | `quota check / bump` | D13/R6：每轮/每日/同公司/LinkedIn 日配额计数 | ledger + run_state → 允许/拒绝 + 建议切换平台 |
| `selfcheck.py` | `selfcheck` | onboarding 前置：Python 版本、数据目录可写、schema 自校验、profile 存在性、`secrets.env` 权限(仅 Codex) | → `onboarding.json` 片段 |
| `migrate_legacy_ledger.py` | `migrate-legacy <md>` | D17：四节 md → jobs/applications（证据类型 `legacy_import`） | md → sqlite |
| `redact.py` | — | R7：写日志前脱敏（邮箱局部、手机、任何形如密码/OTP/NRIC 的 token） | str → str |
| `report.py` | `report` | 三栏汇报的数据部分（只查台账；文案由 Reporter Agent 组织） | sqlite + run_state → JSON |

脚本**不能**：判断"这个岗位适不适合"、生成任何自然语言答案、决定是否提交、访问网络。

### 1.4 并发与浏览器租约

- 浏览器只有一个（D4）。定义 **browser lease**：`runs/<run_id>/browser.lock`（内容 = 持有 Agent 名 + 时间戳）。
  - 只有 Executor（写）与 QA（提交后取证）可持有**写租约**，二者串行。
  - Sourcing / Tracker(网页邮箱) 持**读租约**，读租约之间可并行（各开各的标签页），但**写租约存在时不得发放读租约**。
  - 租约过期：30 分钟无更新视为失效（防 Agent 崩溃后死锁），Orchestrator 可强制回收并记 `events`。
- **[未验证]** Claude Code 子 Agent 能否共享 claude-in-chrome 的标签页上下文；若不能，并行退化为顺序执行，不影响正确性。并行是"允许"不是"要求"。
- Content Agent 无浏览器，可在 Executor 填表当前岗位时预生成下一岗位的开放题草稿。

---

## 2. 状态机（run 级）

### 2.1 状态集合

```
onboard → intake → source → screen → apply ⇄ verify ⇄ ledger → track → report → done
                                        ▲                        │
                                        └──── (队列有余且配额未满) ┘
任意状态 ──关口──► pending_user ──用户"继续"──► resume_to（挂起前状态或指定状态）
任意状态 ──用户放弃/致命错误──► aborted
```

`apply → verify → ledger` 是**每个申请项一个循环**：ledger 写完第 i 项，队列有余且 `quota check` 通过 → 回到 `apply` 处理第 i+1 项；否则 → `track`。

### 2.2 每个状态的职责与检查点

| 状态 | 进入条件 | 负责方 | 检查点文件（写在哪，恢复读哪） | 退出转移 |
|---|---|---|---|---|
| `onboard` | 无 `<data>/onboarding.json`，或 `selfcheck` 失败，或 ToS 未确认（D13） | Orchestrator + `selfcheck` | `<data>/onboarding.json`：`{tos_acknowledged_at, selfcheck{...}, browser_channel, file_upload_ok, accounts_preregistered[]}` | 通过 → `intake`（无 profile 或未签字）/ `source`（profile 已签字） |
| `intake` | 无 `profile.json`，或 `facts_card` 未签字，或用户要求修改档案 | ① Intake | `<data>/intake_state.json`（`{round_done: 0..7, last_question_id}`）、`resume_parse.json`、`profile.json`、`facts_card.json` + 渲染 `facts_card.md`、`consistency_report.json` | `validate profile` 通过 ∧ facts_card 签字 ∧ 一致性门通过 → `source`；一致性 `block` → `pending_user(consistency_mismatch)` |
| `source` | profile 就绪 ∧ 本轮目标份数 > 0 | ② Sourcing | `runs/<run_id>/candidates.jsonl`；`sourcing_state.json`（每个来源消费到哪：清单行号/链接序号/搜索词+页码） | 候选 ≥ 1 → `screen`；候选 = 0 → `report`（空轮，报告原因） |
| `screen` | candidates 就绪 | ③ Screening + `dedup` | `screened.jsonl`（每条决策与原因码）、`shortlist.md`（母清单）、`apply_queue.jsonl` | 母清单生成 → `pending_user(queue_approval)`；用户批准 → `apply`；批准后队列为空 → `report` |
| `apply` | 队列非空 ∧ 浏览器 ok ∧ `quota check` 通过 | ④ Executor（⑤ Content 协作） | `items/<app_id>/form_state.json`（playbook 步骤游标、已填字段快照、草稿 URL、Save 时间）、`items/<app_id>/content/*.md` | 完成一次提交动作 → `verify`；命中关口 → `pending_user`（item 级不停整轮，见 §3.4）；命中跳过规则 → `ledger` |
| `verify` | 一次提交动作后 | ⑥ QA | `items/<app_id>/verify.json`、`<data>/evidence/<app_id>/*` | 有合格证据 → `ledger`（status=applied）；无 → `ledger`（status=submitted_unverified，交 Tracker 后补） |
| `ledger` | verify 完成或 skip | `ledger` 脚本 | `<data>/ledger.sqlite`；`runs/<run_id>/ledger_writes.jsonl`（追加日志，可重放） | 队列有余 ∧ 配额未满 → `apply`；每满 `report_every_n` 份先出进度快照（不改状态）；否则 → `track` |
| `track` | 本轮 apply 结束，或用户 `/auto-apply status` | ⑦ Tracker | `runs/<run_id>/track_results.jsonl`；`<data>/tracker_state.json`（邮件后端类型、上次扫描时间戳/游标） | → `report`；无邮件后端授权 → 跳过并在报告标明 |
| `report` | track 完成或任何终止 | ⑧ Reporter + `export` | `runs/<run_id>/report.md`；`<data>/exports/投递台账.md` | → `done` |
| `pending_user` | 任何关口（§3） | Orchestrator | `pending_actions.jsonl` + `pending_actions.md`；`run_state.resume_to` | 用户"继续" → `resume_to`；全部过期且无可继续项 → `report` |
| `done` / `aborted` | 终态 | — | `run_state.json`（`phase` 终值 + `ended_at`） | 新 run 从 `onboard` 快速通过 |

### 2.3 合法转移表（`runstate set-phase` 只接受这些；其余拒绝并退出码 2）

```
onboard      → intake | source | aborted
intake       → source | pending_user | aborted
source       → screen | report | pending_user | aborted
screen       → pending_user | apply | report | aborted
apply        → verify | ledger | pending_user | aborted
verify       → ledger | pending_user | aborted
ledger       → apply | track | report | pending_user | aborted
track        → report | pending_user | aborted
report       → done | aborted
pending_user → <resume_to> | report | aborted
```

### 2.4 恢复规则

1. `/auto-apply` 启动时：找 `<data>/runs/` 下 `phase ∉ {done, aborted}` 的最新 run → 问用户"继续该轮还是新开一轮"（一次只问这一个问题）。
2. 恢复 = 读 `run_state.json` → 若 `phase == pending_user`：先跑 `pending resolve`（用户在会话里逐项说"处理好了 / 跳过"）→ `runstate resume` → 进入 `resume_to`。
3. 进入 `apply` 恢复某项：读 `items/<app_id>/form_state.json.last_step`，按 playbook 的步骤 id 从**该步骤重新开始**（不是从头），先核对页面仍在该步骤（URL/标题/字段值），不符则退回上一个可确认的步骤。
4. 浏览器断连恢复：`browser.status` 置 `ok` 后，Executor 必须先**只读核对**当前页面状态再继续写。
5. 会话/运行时切换（Claude Code ↔ Codex）：所有检查点都是纯文件，任一运行时可接手；差异只在 `runtime/*.md` 的工具映射与凭据策略。

---

## 3. 关口协议（Gate Protocol）

### 3.1 关口类型枚举（`gate_type`，schema 与 SQLite 共用）

| gate_type | 触发条件（Executor/QA/Intake 识别到） | scope | 默认 mode |
|---|---|---|---|
| `password_or_signup` | 需要新建账号 / 输入密码 / SSO 登录且浏览器无已保存凭据（含 Auth0 登录墙、Apple Account、学校 SSO、账号 ToS 勾选） | item | interactive: sync；batch: async |
| `captcha` | reCAPTCHA / hCaptcha / Cloudflare 挑战 / 图形滑块 | item | sync（用户在场）/ async |
| `otp` | 邮箱或短信一次性验证码输入框 | item | sync / async |
| `email_verification_link` | 注册后需点邮件激活链接 | item | 若 `policy.allow_verification_link_click` ∧ 邮件后端可用 → Agent 自动点并记事件；否则 async |
| `id_number` | 表单必填 NRIC / FIN / 护照号 / 身份证号 / 税号 | item | **永不填**；默认 `skip`（记账原因 `id_number_required`），用户可在 pending 中选择"我自己填" |
| `payment` | 出现支付/银行卡/银行账户字段 | item | **永不填**；默认 `skip` |
| `personal_declaration` | 司法记录 / 疫苗 / 竞业 / 亲属在职 / 破产 / EEO（当 `eeo_default` 未预设或选 `ask_me`）/ 任何"本人声明"且 `policy.declarations` 中对应值为 null | item | sync / async |
| `final_submit` | `submit_mode == confirm` 且 `presubmit` 通过，站在提交按钮前 | item | **sync**（必须等用户"提交"）；autopilot 模式不触发 |
| `content_approval` | `open_question_policy == approve` 或 `cover_letter_policy == approve`，Content 已出草稿 | item | sync / async（async 时 Executor 先填其它字段并 Save 草稿） |
| `resume_missing_language` | 岗位要求某语言简历而 `materials.resumes` 无该语言（D6） | item | async；默认 `skip`，用户补简历后可复活 |
| `unknown_required_field` | 必填字段在 profile / facts_card 中无对应值（如高中信息、推荐人、期望入职日期以外的未知项） | item | async；默认 `skip`（原因 `unknown_required_field`），pending 中列出字段名供用户一次性补进 profile |
| `file_upload_blocked` | 浏览器扩展无法上传本地文件（文件 URL 权限 / 文件选择器不可控） | item | sync / async；恢复路径见 gates.md |
| `session_expired` | 填表中途被登出 / CSRF 失效 / 页面重置（Temasek 2026-08-25 事故） | item | async；先尝试 `password_or_signup` 路径重新登录 + 找回草稿 |
| `dedup_review` | 疑似重复（同公司 + 岗位名相似度 ≥ 阈值但非精确命中，§6.4） | item（在 screen 阶段并入母清单） | 随 `queue_approval` 一起处理 |
| `queue_approval` | 母清单生成，等待用户批量批准/勾排除（D7） | **run** | sync |
| `consistency_mismatch` | R3 一致性门 `block` 级不一致 | **run** | sync |
| `browser_disconnected` | 扩展无响应 / 标签页丢失 / 运行时报浏览器不可用 | **run** | sync；**禁止假装完成** |
| `quota_exhausted` | 每日份数达上限，或所有可用平台都达配额（R6 自动切平台后仍无可投） | **run** | 信息性：写 pending（用户可选"提高今日上限"）并转 `track` |

`scope`：`item` = 只挂起该申请项，Executor 保存草稿、释放浏览器、处理下一项；`run` = 整轮挂起。
`mode`：`sync` = Agent 结束当前回合、在会话里直接问用户、页面保持打开；`async` = 记入 pending、项状态置 `pending_user`、继续队列，在下一次汇报/轮末集中展示。默认由 `policy.gate_mode`（`interactive` | `batch`）决定，个别类型有强制值（表中加粗）。

### 3.2 挂起时写什么

Agent 上报关口 = 调用 `AA app gate / run gate '<pending_action 对象>'`（对象结构 = `schemas/pending_action.schema.json`），脚本追加到 `runs/<run_id>/pending_actions.jsonl` 并重新渲染 `pending_actions.md`。同时：
- `autoapply ledger add-gate`（写 `gates` 表）；
- item 级：`autoapply ledger upsert-app --status pending_user`，`items/<app_id>/form_state.json` 记 `last_step` + `draft_saved` + `draft_url`；
- run 级：`autoapply runstate suspend --gate <type> --resume-to <phase>`。

**`pending_actions.md` 渲染格式（固定，用户可见，中英双语）**

```markdown
# 待用户动作 / Pending actions — run_20260905_101500
> 生成 2026-09-05 11:42 · 打开 3 · 已处理 1 · 过期 0
> 处理完后回到会话说「继续」或 "continue"；只处理部分也可以，说明哪几项即可。

## 1. [otp] Workato — Business Technology Intern　　优先级 高 · 到期 2026-09-12
- 页面 / Page: https://…
- 卡在 / Stuck at: 登录 → 邮箱验证码（playbook step `login.otp`）
- 草稿 / Draft: 已保存（https://…/draft）
- 你需要做 / What you do: 把邮件里的验证码贴到会话（不要贴密码），或自己在页面输入完成后说「继续」。
  Paste the one-time code into the chat (never a password), or enter it on the page yourself and say "continue".
- 恢复后 Agent 会 / After resume: 回到 `login.otp` → 继续填表 → 提交前复核 → 停在提交前等你确认。
- id: pa_20260905_ab12cd

## 2. [final_submit] …
```

顺序：run 级关口置顶，其余按优先级（`high` > `normal` > `low`）再按打开时间。已处理/过期的项折叠到文末"已处理"小节。

### 3.3 用户处理后如何恢复

1. 用户在会话里说"继续"（或 "continue"、`/auto-apply continue`），可附带处置："1 已处理，2 跳过，3 我自己填了"。
2. Orchestrator 调 `pending resolve --id <id> --resolution resolved|skipped|user_completed [--note]`。`user_completed` = 用户自己把该项做到提交了 → 转 `verify` 找证据，**不是**直接标已投。
3. 有 `resolved` 的 item 级项 → 优先重排到队列头（`apply_queue.jsonl` 中该项 `priority=high`），Orchestrator `runstate resume` → `apply`。
4. run 级项 resolved → `runstate resume` → `resume_to`。
5. 任何恢复前，Executor 必须先只读核对页面（§2.4 第 3 条）。

### 3.4 超时与放弃

| 情形 | 规则 |
|---|---|
| OTP 码过期 | 用户晚给 → Agent 重新触发发码，从 `login.otp` 重来；重发 ≥ 3 次仍失败 → `expired` |
| item 级 pending 无人处理 | 默认 7 天（`expires_at`）→ `expired`，application.status = `abandoned`，记 events；用户随时可"复活"（回到队列） |
| 岗位关闭 | Executor/Tracker 发现 JD 下线 → application `skipped` + 原因 `job_closed`，pending 项 `expired` |
| run 级 pending | 不过期；下次 `/auto-apply` 询问继续或新开 |
| 草稿保活 | SuccessFactors / Workday 类草稿保存在服务端，恢复走"重新登录 → 我的申请 → 继续"；Jobstreet 快速申请无草稿，重做 **[未验证：各平台草稿保留时长，B 在 playbook 标注]** |
| 用户明说放弃某项 | `skipped` + 原因 `user_excluded` |

### 3.5 两个运行时的差异点（细节由 `runtime/claude-code.md`、`runtime/codex.md` 承接）

| gate_type | Claude Code | Codex |
|---|---|---|
| `password_or_signup` | Agent 预填所有非密码字段 → 停在密码框 → **用户手输**并让 Chrome 保存 → 用户说继续 → Agent 点 Sign in；之后登录靠 Chrome 自动填 | 用户在 `secrets.env` 设 `JOB_ACCOUNT_PASSWORD`（求职专用、非主密码）→ Agent 代输，**永不回显/记录**；其它同左 |
| `otp` | 用户贴码到会话，或有已授权邮箱连接器时 Agent 读取（只读） | 同左；Codex 的 gmail 插件可读 |
| `email_verification_link` | 邮箱连接器（用户自行在 claude.ai 授权）或已登录 Chrome 网页邮箱找到链接 → 经 `allow_verification_link_click` 点击 | 同左（gmail 插件） |
| `captcha` / `id_number` / `payment` | 完全一致：用户自己按验证码；证件号/支付永不填 | 一致 |
| `browser_disconnected` | 检测 claude-in-chrome 不可达；备用 Browser pane 仅只读核验 | 检测 Codex 浏览器/扩展；备用其内置浏览器仅只读 |
| `file_upload_blocked` | 提示用户在扩展设置开 "Allow access to file URLs"，或用户手动选文件 | Codex 可用 computer-use 点系统文件窗口；否则用户手动 |
| 会话里出现密码文本 | 两者一致：拒绝使用、提醒立即更换、写 `events(kind=password_in_chat_refused)`，**不记录内容** | 一致 |

---

## 4. 数据流图（每个 Agent 的输入 → 输出）

```
用户材料(简历 PDF/DOCX、链接) ─┐
                               ▼
┌─ ① Intake ───────────────────────────────────────────────────────────┐
│ in : 简历文件, intake/questionnaire.*.md, intake_state.json          │
│ out: resume_parse.json → consistency_report.json (脚本)              │
│      profile.json (validate 通过后写), facts_card.json + facts_card.md │
└──────────────────────────────────────────────────────────────────────┘
                               ▼
┌─ ② Sourcing ─────────────────────────────────────────────────────────┐
│ in : profile.intent/rules, 用户清单/链接文件, sourcing_state.json     │
│ out: runs/<run>/candidates.jsonl (job 对象, 每条 source 标注)         │
└──────────────────────────────────────────────────────────────────────┘
                               ▼
┌─ ③ Screening ────────────────────────────────────────────────────────┐
│ in : candidates.jsonl, profile, ledger.sqlite(经 dedup 脚本)         │
│ out: screened.jsonl → shortlist.md(母清单) → [用户批准] → apply_queue.jsonl │
└──────────────────────────────────────────────────────────────────────┘
                               ▼
┌─ ④ Executor ⇄ ⑤ Content ─────────────────────────────────────────────┐
│ in : apply_queue.jsonl + candidates.jsonl(join job_id), profile,     │
│      facts_card.json(仅 confirmed), playbooks/<platform>.md,          │
│      items/<app>/content/*.md(approved)                              │
│ out: items/<app>/form_state.json, pending_actions.jsonl(关口),        │
│      items/<app>/content/*.md(草稿, Content 产出)                     │
└──────────────────────────────────────────────────────────────────────┘
                               ▼
┌─ ⑥ QA ───────────────────────────────────────────────────────────────┐
│ in : form_state.json, profile, job → presubmit 脚本                   │
│ out: items/<app>/pre_submit_check.json;                              │
│      提交后: evidence/<app>/NN_<type>.<ext> + verify.json (evidence 脚本) │
└──────────────────────────────────────────────────────────────────────┘
                               ▼
        ledger 脚本: ledger.sqlite (+ ledger_writes.jsonl)
                               ▼
┌─ ⑦ Tracker ──────────────────────────────────────────────────────────┐
│ in : ledger(applied/submitted_unverified), 邮件后端, tracker_state.json │
│ out: track_results.jsonl → ledger(events, tracking_status, 补证据)   │
└──────────────────────────────────────────────────────────────────────┘
                               ▼
┌─ ⑧ Reporter ─────────────────────────────────────────────────────────┐
│ in : report 脚本输出(只读 ledger + run_state + pending)               │
│ out: runs/<run>/report.md (三栏), exports/投递台账.md (四节)          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. 文件契约

### 5.1 标识符

| id | 格式 | 生成方 |
|---|---|---|
| `profile_id` | `^[a-z0-9][a-z0-9_-]{1,31}$`，用户在 onboarding 自选（如 `alex_tan`） | Intake |
| `run_id` | `run_<YYYYMMDD>_<HHMMSS>`（本地时间） | `runstate init` |
| `job_id` | `job_` + sha256(`dedup_key`) 前 12 位 hex；**由 dedup_key 唯一决定**（同岗位不同渠道 → 同一 job_id） | `normalize` |
| `app_id` | `app_<YYYYMMDD>_<6 hex 随机>` | `ledger upsert-app` |
| `evidence_id` | `ev_<app_id 去前缀>_<NN>` | `evidence register` |
| `gate_id` / `action_id` | `pa_<YYYYMMDD>_<6 hex>` | `pending add` |
| `fact_id` | `f_<3 位序号>`（facts_card 内唯一） | Intake |

### 5.2 数据目录（`~/auto-apply-data/<profile_id>/`）

```
profile.json                 # 唯一档案（schema: profile）
facts_card.json              # 机器版事实卡（schema: facts_card），canonical
facts_card.md                # 由 json 渲染的可读版（用户签字对象）
resume_parse.json            # Intake 从简历解析出的联系方式/教育（供 R3）
consistency_report.json      # R3 报告
intake_state.json            # 问诊进度
onboarding.json              # onboarding 结果
tracker_state.json           # 邮件扫描游标
dedup_aliases.json           # 用户可编辑的公司别名表（§6.2 第 7 条）
secrets.env                  # 仅 Codex；chmod 600；只含 JOB_ACCOUNT_PASSWORD 等；gitignored
ledger.sqlite                # 台账主存（§9）
evidence/<app_id>/NN_<type>.<ext>
runs/<run_id>/…              # §5.3
exports/投递台账.md          # §5.6
```

### 5.3 `runs/<run_id>/` 布局

```
run_state.json               # schema: run_state
candidates.jsonl             # 母清单原料：每行一个 job 对象
sourcing_state.json          # 每个来源消费位置
screened.jsonl               # 每行 {job_id, decision, reason_code, reason, dedup_match?}
shortlist.md                 # 母清单（给用户批的可读版，见 5.5）
apply_queue.jsonl            # 每行一个 application 对象（status=queued/…）
pending_actions.jsonl        # 每行一个 pending_action 对象（追加写，状态更新以最后一行为准）
pending_actions.md           # 渲染版（§3.2）
browser.lock                 # 浏览器租约（§1.4）
items/<app_id>/
  form_state.json            # {playbook, last_step, fields_filled{label: value_ref}, draft_url, saved_at, attempts}
  content/cover_letter.md    # 头部一行 JSON：{"status":"draft|approved|filled|skipped","approved_at":…,"facts_used":["f_012",…]}
  content/q_01.md …          # 开放题草稿，同上格式；正文第一行为题目原文
  pre_submit_check.json      # presubmit 脚本输出
  verify.json                # {qualified: bool, evidence_ids[], checked_at, notes}
track_results.jsonl          # 每行 {app_id?, source, subject, from, received_at, category, matched_by, action}
ledger_writes.jsonl          # 每次 ledger 写操作的入参（可重放/审计）
report.md                    # 三栏汇报
log.jsonl                    # 脱敏事件日志（redact 后）
```

`form_state.fields_filled` 只记**字段名 → 值的来源引用**（如 `"profile.identity.emails.primary"`、`"fact:f_012"`、`"user_input"`），不复制值本身，避免个人数据在 runs/ 里再落一份。

### 5.4 `candidates.jsonl` / `apply_queue.jsonl` 行契约

- `candidates.jsonl`：每行一个符合 `schemas/job.schema.json` 的对象。Sourcing 写入时至少填：`job_id, dedup_key, company, title, url, platform, channel, source, jd_summary, discovered_at, run_id`；`hard_conditions`/`match`/`risks` 允许 Sourcing 初填、Screening 覆写。
- `apply_queue.jsonl`：每行一个符合 `schemas/application.schema.json` 的对象，`status` 初值 `queued`，必含 `approval {approved_by_user: true, approved_at, approval_note}`。Executor 通过 `job_id` 回 `candidates.jsonl` 取岗位数据。
- 两个文件都是**追加写**；同一 `job_id`/`app_id` 出现多次时，以最后一行为准（脚本 `--compact` 可折叠）。

### 5.5 `shortlist.md`（母清单，D7）固定列

| # | 公司 | 岗位 | 平台/渠道 | 来源 | JD 摘要 | 匹配理由 | 风险 | 建议 | 你的决定 |
|---|---|---|---|---|---|---|---|---|---|

"建议" ∈ {投, 跳过(原因码), 疑似重复→请确认}；"你的决定"留空由用户填（或在会话里说"全部批准，排除 3、7"）。**未经用户批准的行不得进入 `apply_queue.jsonl`**。

### 5.6 `exports/投递台账.md` 与"四节"格式映射

| 台账节 | 数据来源（SQL 口径） | 行格式 |
|---|---|---|
| 一、已确认投递（禁止重复） | `applications.status='applied'`（必然有合格 evidence），按 `jobs.company_raw` 分组，同公司多岗合并一行 | `- 公司 — 岗位A；岗位B（渠道，证据类型摘要）`；公司达到 `per_company_max` 时追加 `—— **已投 N 份，不再新投**` |
| 二、未投但有中间状态 | `status ∈ {pending_user, draft_saved, submitted_unverified, failed, abandoned}` ∪ `skipped` 且 `skip_reason_code ∈ {id_number_required, resume_language_missing, unknown_required_field, date_window_mismatch}` | `- 公司 — 岗位：状态（原因/关口类型，最近一次 gate 说明）` |
| 三、既定投递规则 | `profile.intent / salary / rules / policy` 渲染（**不含任何联系方式与密码**）+ 固定的证据口径与关口规则文案 | 项目符号 |
| 四、状态追踪表 | `events` 表中 `kind ∈ {applied, status_change, tracking_update, gate_opened, skipped}` 按时间升序 | `\| 日期 \| 公司 \| 岗位 \| 渠道 \| 状态 \| 证据/备注 \|` |

导出必须**幂等**（同一台账导出两次内容一致），并在文件头写 `> 由 auto-apply 导出于 <时间>，来源 ledger.sqlite；手改会被覆盖`。首位用户旧台账经 `migrate-legacy` 导入后再导出，第一节内容须包含全部旧"已确认"条目（P3 DoD 的回放依据）。

---

## 6. 去重规范（R1）

### 6.1 原则
- 键 = `normalize(company) + "|" + normalize(title)`。**渠道（channel）与平台（platform）是属性不是键**：同一岗位官网 ATS 投一次、LinkedIn 再投一次 = 1 个去重岗位、2 次提交动作。
- 两个计数永远并列出现：`unique_jobs_applied`（去重岗位数，`COUNT(DISTINCT job_id) WHERE status='applied'`）与 `submission_actions`（提交动作数，`SUM(applications.submission_action_count)`）；`duplicates = submission_actions − unique_jobs_applied`。汇报一律写成"去重 N 岗 / 提交 M 次（其中重复 K）"。

### 6.2 `normalize_company(s)` 步骤（顺序执行）
1. Unicode NFKC；全角→半角；去首尾空白；连续空白折叠为单个空格。
2. 中英文括号统一：`（）【】「」『』〔〕` → `()`；括号内若为地区/实体后缀（`singapore|sg|asia|apac|pte|ltd|group|holdings|s\.?e\.?a\.?|international`）则连括号删除，否则保留内容去掉括号。
3. 全部小写（仅 Latin；CJK 不变）。
4. `&` → `and`；`.`、`,`、`'`、`"`、`’`、`/`、`-`、`_` → 空格。
5. 去掉**首部** `the `。
6. 反复去掉**尾部**法律/地区后缀（每次去一个，直到不再匹配且剩余 ≥ 1 个 token）：
   `pte ltd`, `pte`, `ltd`, `limited`, `inc`, `incorporated`, `llc`, `llp`, `plc`, `co`, `corp`, `corporation`, `company`, `gmbh`, `ag`, `sa`, `bv`, `nv`, `sdn bhd`, `bhd`, `pvt`, `private`, `holdings`, `holding`, `group`, `international`, `global`, `singapore`, `sg`, `asia pacific`, `asia-pacific`, `apac`, `asia`, `sea`（仅当作为**尾部** token 且剩余 ≥ 1 token）, `有限公司`, `股份有限公司`, `私人有限公司`, `集团`, `公司`, `新加坡`。
7. 查 `dedup_aliases.json`（`{"ncs group": "ncs", "ncs": "ncs", …}`）：命中则替换为规范名。别名表由用户/Screening 维护，脚本只读。
8. 折叠空白，输出。

示例：`NCS Pte. Ltd.` → `ncs`；`Panasonic Asia Pacific` → `panasonic`；`Sea Limited` → `sea`；`Fraser & Neave (Singapore)` → `fraser and neave`；`华为技术有限公司` → `华为技术`。

### 6.3 `normalize_title(s)` 步骤
1. NFKC、括号统一、小写、`&`→`and`，`/`、`|`、`–`、`—`、`-`、`_`、`:`、`,`、`•` → 空格。
2. **括号段处理**：对每个 `(...)`/`[...]` 段，若**整段**匹配下列任一模式则删除整段，否则只去括号保留内容：
   - 需求编号：`^(jr|req|hrc|uni|r|id|job|ref|no)?\s*[-#]?\s*\d{3,}[a-z]?$`
   - 时间/批次：含 `20\d\d`、月份名/缩写、`jan\s*(-|to|till)\s*jun` 类区间、`spring|summer|fall|autumn|winter|h1|h2|q[1-4]|batch|intake|cohort|cycle|off\s*cycle|term`
   - 地点：`singapore|sg|remote|hybrid|onsite|on\s*site|apac|asia|sea|global|regional`
   - 人群：`uni|university|student|undergraduate|graduate|postgraduate|penultimate|final\s*year|masters?|phd|m\s*/\s*f\s*/\s*d|f\s*/\s*m\s*/\s*x`
3. 对非括号的**首/尾段**（以原分隔符切开后的第一段和最后一段）套用同样的模式：整段匹配则删。例：`Data Analyst Intern Spring 2027` → `data analyst intern`；`2027 APAC Summer Internship` → `internship`；`[Uni – Jan till Jun 2027] Agentic AI Intern` → `agentic ai intern`。
4. 删除任意位置的独立需求编号 token（`^(jr|req|hrc|uni)?\d{4,}$`）和纯年份 token（`^20\d\d$`）。
5. 同义归一（token 级，可扩展表 `normalize.py: TITLE_SYNONYMS`）：`internship|interns|internships → intern`；`swe → software engineer`；`ml → machine learning`；`sr|snr → senior`；`jr → junior`；`mgr → manager`；`eng → engineer`（仅整 token）；`genai → generative ai`；`asst → assistant`。
6. 删除填充词：`a|an|the|of|for|in|at|and|with|to|position|role|opening|program|programme`（`and` 在 title 中删；company 中保留）。
7. 折叠空白，**保持 token 顺序**（不排序），输出。

示例：`AI Solutions & Analytics (HRC1666025)` → `ai solutions analytics`；`SWE Intern (Edge AI Toolchain)` → `software engineer intern edge ai toolchain`（保留括号内容，避免与 `SWE Intern` 误合并）；`Technology Consulting - AI & Cybersecurity Intern Jan-Jun 2027` → `technology consulting ai cybersecurity intern`。

### 6.4 命中判定
- **精确命中**：`dedup_key` 相等（即 `job_id` 相同）且台账中该 job 存在 `status ∈ {applied, submitted_unverified, pending_user, draft_saved}` 的 application → `decision=dedup_hit`，**自动跳过**，原因码 `already_applied`。
- **疑似重复**：`normalize(company)` 相等 ∧（title token 集 Jaccard ≥ 0.8 ∨ 一方 token 序列是另一方的连续子序列）→ `decision=dedup_review`，在母清单标"疑似重复"，默认建议跳过，用户可强制批准（记 `approval_note`）。
- 台账内 `skipped` / `abandoned` 的 job 不构成命中，但母清单需提示"上次跳过原因"。
- 旧台账导入（`legacy_import`）视同 `applied` 参与命中；P3 DoD：回放首位用户 8 月台账，已投岗 100% 被拦。

---

## 7. 证据规范

### 7.1 "已投"（`status=applied`）判定
仅当 `evidence` 表存在 ≥ 1 条 `qualifies=1` 的证据，且该证据类型 ∈ **合格类型**。`ledger assert applied-has-evidence` 在每次 `upsert-app --status applied` 时强制检查，失败则拒绝写入（退出码 3）。

| evidence_type | 合格？ | 说明 |
|---|---|---|
| `success_page` | **是** | 职位级成功页（含岗位名或需求编号 + "application submitted / received / thank you for applying" 等语义） |
| `ats_confirmation_email` | **是** | ATS/雇主发的**该岗位**确认邮件（主题或正文含岗位名/编号） |
| `employer_confirmation_email` | **是** | 雇主人工回复确认收到 |
| `ats_portal_status` | **是（B 级）** | ATS 候选人门户"我的申请"列出该岗位且状态为 Submitted/Applied/Under review **[待定：是否与成功页同等，建议同等]** |
| `legacy_import` | **是（C 级）** | 从旧台账导入，原台账已按同一口径确认 |
| `review_page_screenshot` | 否 | 最终确认页，尚未提交 |
| `form_completed_screenshot` | 否 | 填完表 |
| `draft_saved` | 否 | 草稿已保存 |
| `account_verification_email` | 否 | 账号/邮箱验证邮件，与岗位无关 |
| `external_redirect` | 否 | Jobstreet "访问雇主网站"等跳转 |
| `open_tab` | 否 | 只是打开了页面 |
| `generic_ack_email` | 否 | 不含岗位信息的泛回执（如"我们收到了您的信息"）→ 需 Tracker 进一步匹配 |

### 7.2 每条证据必须记录的字段
共同：`evidence_id, app_id, evidence_type, captured_at, captured_by (agent), qualifies (由脚本判定), notes`。
- 页面类（`success_page`, `ats_portal_status`, `review_page_screenshot`, `form_completed_screenshot`, `external_redirect`, `open_tab`）：`url`（必填）、`page_title`、`file`（截图或页面文本，相对 `evidence/` 路径，必填其一）、`sha256`（file 的）、`job_title_seen`（页面上看到的岗位名/编号，`success_page` 必填且须与 job 的 title/req_id 模糊匹配 ≥ 0.6，否则不合格）。
- 邮件类（`*_email`）：`email_subject, email_from, email_received_at`（必填）、`email_message_id`、`email_excerpt`（≤ 300 字，脱敏后）、`matched_job_by`（`title|req_id|company_domain`）。`from` 域名须匹配公司域或已知 ATS 域（`myworkday.com`, `successfactors.com`, `greenhouse.io`, `ashbyhq.com`, `smartrecruiters.com`, `lever.co`, `workable.com`, `jobstreet.com`, `seek.com`, `linkedin.com`, `mycareersfuture.gov.sg`…；列表由 D 维护）或主题含岗位名。
- `legacy_import`：`legacy_ref`（原台账行文本）、`imported_at`。

### 7.3 文件命名
`evidence/<app_id>/<NN>_<evidence_type>.<png|txt|html|json>`，`NN` 两位递增。截图优先 png；网页文本 txt；邮件元数据 json。**文本类证据写入前必须过 `redact`**。

---

## 8. 一致性门规范（R3）

### 8.1 输入
- `resume_parse.json`：Intake（LLM）阅读每份 `materials.resumes[]` 后写出 `{resume_path, sha256, parsed: {full_name, emails[], phones[{country_code, number}], graduation: {institution, degree, expected}, linkedin_url, location}, parsed_at}`（每份简历一条）。
- `profile.json`。

### 8.2 比对规则（`consistency` 脚本，确定性）

| 字段 | 比对方式 | 不一致级别 |
|---|---|---|
| 主邮箱 | 小写后精确；简历上任一邮箱 ∈ profile 邮箱集合 即通过 | `block`（简历邮箱不在档案内） |
| 手机 | 去空格/横线/括号后比 `country_code + number`；简历任一号码 ∈ profile 号码集合 即通过 | `block` |
| 毕业年月 | `education[].end_expected` 与简历解析的 expected 比较，精确到月；只比 `is_current=true` 的那段 | `block`（年不同）/ `warn`（年同月不同） |
| 姓名 | 规范化后 token 集相等即通过（顺序不同 = `warn`：姓名顺序） | `warn` |
| 学校/学位 | 别名表（`NTU`=`Nanyang Technological University`…）后比 | `warn` |
| LinkedIn URL | 规范化路径后比 | `info` |

### 8.3 输出与报警格式
`consistency_report.json`：`{checked_at, resumes: [{resume_path, findings: [{field, level, resume_value_masked, profile_value_masked, hint}]}], overall: "pass|warn|block"}`。**值一律脱敏**（邮箱 `z***@gmail.com`、手机 `+65 ****1234`）。
- `overall=block` → run 级关口 `consistency_mismatch`，会话文案：
  > 简历《X.pdf》上的邮箱与档案不一致（简历 `z***@163.com`，档案 `z***@gmail.com`）。请选：① 以档案为准（简历不改，但注意招聘方会看到简历上的旧邮箱）② 我去换一份简历 ③ 改档案为简历上的值。
- 用户选 ① 时写 `profile.materials.resumes[].known_mismatches[]` 记录已知差异，此后不再重复报警。
- P2 DoD 断言：给一份联系方式不一致的示例简历，`consistency` 退出码非零且 `overall=block`。

---

## 9. 台账 SQLite 规范（DDL）

> D 实现；schema 版本写在 `meta` 表；所有时间 ISO-8601 本地带时区字符串；布尔用 0/1；JSON 列存 `TEXT`。

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);  -- schema_version, profile_id, created_at

CREATE TABLE IF NOT EXISTS jobs (
  job_id            TEXT PRIMARY KEY,                 -- job_<12hex>, = f(dedup_key)
  dedup_key         TEXT NOT NULL UNIQUE,
  company_raw       TEXT NOT NULL,
  company_norm      TEXT NOT NULL,
  title_raw         TEXT NOT NULL,
  title_norm        TEXT NOT NULL,
  platform          TEXT NOT NULL CHECK (platform IN (
                      'jobstreet','linkedin_easy_apply','linkedin_external','mycareersfuture',
                      'workday','successfactors','greenhouse','ashby','smartrecruiters','lever',
                      'workable','company_custom','email','other','unknown')),
  url               TEXT,
  apply_url         TEXT,
  req_id            TEXT,
  location          TEXT,
  source_type       TEXT NOT NULL CHECK (source_type IN (
                      'user_list','user_link','site_search','recommendation','referral','legacy_import','other')),
  source_ref        TEXT,
  jd_summary        TEXT,
  jd_hash           TEXT,
  hard_conditions   TEXT,                             -- JSON (job.schema hard_conditions)
  match_score       INTEGER,
  match_json        TEXT,                             -- JSON (reasons/concerns)
  risks_json        TEXT,                             -- JSON array
  first_seen_at     TEXT NOT NULL,
  last_seen_at      TEXT NOT NULL,
  closed_at         TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_company_norm ON jobs(company_norm);
CREATE INDEX IF NOT EXISTS idx_jobs_platform     ON jobs(platform);

CREATE TABLE IF NOT EXISTS applications (
  app_id                  TEXT PRIMARY KEY,           -- app_<YYYYMMDD>_<6hex>
  job_id                  TEXT NOT NULL REFERENCES jobs(job_id),
  run_id                  TEXT,
  channel                 TEXT NOT NULL CHECK (channel IN (
                            'company_site','linkedin','jobstreet','mycareersfuture','email','other')),
  platform                TEXT NOT NULL,              -- 同 jobs.platform 枚举
  status                  TEXT NOT NULL CHECK (status IN (
                            'queued','in_progress','draft_saved','pending_user','ready_to_submit',
                            'submitted_unverified','applied','skipped','failed','withdrawn','abandoned')),
  tracking_status         TEXT NOT NULL DEFAULT 'none' CHECK (tracking_status IN (
                            'none','receipt','under_review','assessment','interview','offer','rejected','closed')),
  skip_reason_code        TEXT CHECK (skip_reason_code IS NULL OR skip_reason_code IN (
                            'date_window_mismatch','degree_mismatch','salary_below_floor','unpaid',
                            'already_applied','blacklist','reserve_for_referral','global_quota',
                            'industry_excluded','title_excluded','id_number_required','payment_required',
                            'resume_language_missing','unknown_required_field','quota_reached',
                            'job_closed','user_excluded','work_pass_mismatch','start_immediately','other')),
  submission_action_count INTEGER NOT NULL DEFAULT 0, -- 每次点提交 +1（含重试与跨渠道重复）
  submitted_at            TEXT,
  applied_confirmed_at    TEXT,                       -- 首条合格证据时间
  resume_path             TEXT,
  resume_language         TEXT,
  resume_sha256           TEXT,
  pre_submit_passed       INTEGER,                    -- 0/1/NULL
  approval_json           TEXT,                       -- {approved_by_user, approved_at, approval_note}
  content_json            TEXT,                       -- content_items[]
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
  evidence_type    TEXT NOT NULL CHECK (evidence_type IN (
                     'success_page','ats_confirmation_email','employer_confirmation_email','ats_portal_status',
                     'legacy_import','review_page_screenshot','form_completed_screenshot','draft_saved',
                     'account_verification_email','external_redirect','open_tab','generic_ack_email')),
  qualifies        INTEGER NOT NULL DEFAULT 0,        -- 脚本判定，Agent 不得手写 1
  captured_at      TEXT NOT NULL,
  captured_by      TEXT NOT NULL,                     -- agent 名
  url              TEXT,
  page_title       TEXT,
  file             TEXT,                              -- 相对 evidence/ 的路径
  sha256           TEXT,
  job_title_seen   TEXT,
  email_subject    TEXT,
  email_from       TEXT,
  email_received_at TEXT,
  email_message_id TEXT,
  email_excerpt    TEXT,                              -- 已脱敏，≤300 字
  matched_job_by   TEXT,
  legacy_ref       TEXT,
  notes            TEXT
);
CREATE INDEX IF NOT EXISTS idx_ev_app ON evidence(app_id);
CREATE INDEX IF NOT EXISTS idx_ev_qual ON evidence(app_id, qualifies);

CREATE TABLE IF NOT EXISTS gates (
  gate_id       TEXT PRIMARY KEY,                     -- = pending_action.action_id
  run_id        TEXT NOT NULL,
  app_id        TEXT REFERENCES applications(app_id), -- run 级关口为 NULL
  gate_type     TEXT NOT NULL CHECK (gate_type IN (
                  'password_or_signup','captcha','otp','email_verification_link','id_number','payment',
                  'personal_declaration','final_submit','content_approval','resume_missing_language',
                  'unknown_required_field','file_upload_blocked','session_expired','dedup_review',
                  'queue_approval','consistency_mismatch','browser_disconnected','quota_exhausted')),
  scope         TEXT NOT NULL CHECK (scope IN ('item','run')),
  mode          TEXT NOT NULL CHECK (mode IN ('sync','async')),
  playbook_step TEXT,
  opened_at     TEXT NOT NULL,
  expires_at    TEXT,
  resolved_at   TEXT,
  resolution    TEXT CHECK (resolution IS NULL OR resolution IN (
                  'resolved','skipped','user_completed','expired','abandoned')),
  summary       TEXT,                                 -- 脱敏后的一句话
  runtime       TEXT CHECK (runtime IS NULL OR runtime IN ('claude_code','codex'))
);
CREATE INDEX IF NOT EXISTS idx_gates_open ON gates(run_id, resolved_at);

CREATE TABLE IF NOT EXISTS events (
  event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  run_id     TEXT,
  app_id     TEXT REFERENCES applications(app_id),
  job_id     TEXT REFERENCES jobs(job_id),
  kind       TEXT NOT NULL CHECK (kind IN (
               'run_started','phase_change','candidate_added','screened','queued','apply_started',
               'draft_saved','submit_clicked','applied','submitted_unverified','skipped','failed',
               'gate_opened','gate_resolved','evidence_added','tracking_update','status_change',
               'quota_switch','browser_disconnected','browser_recovered','password_in_chat_refused',
               'legacy_imported','export','report','note')),
  actor      TEXT NOT NULL,                           -- orchestrator / agent 名 / script / user
  payload    TEXT                                     -- JSON，已脱敏
);
CREATE INDEX IF NOT EXISTS idx_events_at   ON events(at);
CREATE INDEX IF NOT EXISTS idx_events_app  ON events(app_id);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
```

**断言（`ledger assert`，F 写成 verify）**
- `applied-has-evidence`：`SELECT COUNT(*) FROM applications a WHERE status='applied' AND NOT EXISTS (SELECT 1 FROM evidence e WHERE e.app_id=a.app_id AND e.qualifies=1)` 必须为 0。
- `unique-vs-actions`：`unique_jobs_applied ≤ submission_actions`。
- `no-secrets`：全表扫描不得匹配 `redact` 的密码/OTP/NRIC 正则。
- `per-company-cap`：任一 `company_norm` 的 applied 数 ≤ `rules.per_company_max`（超出者须有 `approval_note` 明示用户放行）。

---

## 10. agents/*.md 与 playbooks/*.md 结构契约

### 10.1 `agents/NN-<name>.md`（固定 7 个二级标题，顺序不可变，缺一不可）

```markdown
# <NN> <Agent 名>（中文名 / English name）
> 一句话角色；所属状态：<state>；并行性：<是/否>；浏览器：<无/读/写>

## 职责
（3–8 条，动词开头；明确"只做/不做"）
## 输入
（文件路径 + 读取哪些字段；引用 §5 契约名，不复制结构）
## 输出
（文件路径 + 写入方式：追加/覆盖/经哪个脚本；每个输出对应的 schema）
## 可用工具
（按运行时分列：Claude Code / Codex；脚本 verb 列表；明确"禁用"的工具）
## 关口
（本 Agent 可能触发的 gate_type 列表 + 每种触发时的最小上报内容）
## 禁止
（硬边界，至少含 BRIEF §3 中与本 Agent相关的条目）
## 完成标准
（可被 verify 脚本断言的条件；FAIL 不得包装成完成）
```

### 10.2 `playbooks/<platform>.md`（固定 14 个二级标题，编号与措辞以 `playbooks/_template.md` 为准）

```markdown
# Playbook — <平台名>（platform 枚举值：<value>）
> 适用：<公司示例>；最后核实：<日期>；核实人：<agent/user>；置信度：<高/中/低>

## 1. 识别特征                   # URL 模式、页面标题、DOM 特征、品牌字样
## 2. 登录态检测                 # 如何判断已登录/未登录；未登录时的 gate_type
## 3. 账号注册关口               # 是否强制建号；密码规则；SSO；ToS 勾选；两运行时差异
## 4. 表单流程步骤               # 步骤 id 列表（form_state.last_step 用），每步入口/出口特征
## 5. 字段映射（profile → 表单） # 表单字段 → profile/facts_card 路径；姓名顺序、区号、日期格式
## 6. 字符上限与控件坑           # 字段长度、富文本、自动完成控件（地点/学校）、日期选择器
## 7. Save 草稿与超时策略        # 是否有草稿、多久 Save 一次、会话超时、CSRF 失效表现
## 8. 简历上传方式               # 上传控件、格式/大小限制、平台已存简历复用、扩展上传限制
## 9. 开放题与声明题出现的位置   # 哪一步出现、题型、是否必填、EEO/声明题清单
## 10. 成功页特征                # URL/标题/文案；与"确认页"的区别；对应 evidence_type
## 11. 失败模式与处理            # 已知报错、提交被清空、重复申请提示
## 12. 配额与节流                # 平台侧限制（日申请上限、频率）；本地节流建议
## 13. 已知事故                  # 日期 + 一句话 + 处置（引用 INCIDENTS.md 编号）
## 14. 未验证项                  # 明确列出未实测的断言，禁止写成事实
```

每节末尾可加"变更记录"行（日期 / 谁 / 改了什么），不单列一节。步骤 id（第 4 节）必须与 `pending_action.playbook_step`、`form_state.last_step` 使用同一命名（如 `login.otp`、`review.submit`）。

playbook 中**不得**出现任何真实个人数据；示例一律用虚构人物（如 `Alex Tan`, `alex.tan@example.com`）。

---

## 11. Schema 约定（供 D 的手写校验器与所有写 schema 的人）

- Draft 2020-12；文件在 `schemas/`；`$id` 用 `https://auto-apply.local/schemas/<name>.schema.json`；只用**本地** `$ref`（`#/$defs/...`）。
- 校验器必须支持的关键字（其余忽略并警告）：`type`（含数组形式如 `["string","null"]`）、`properties`、`required`、`additionalProperties`（仅 `false`/schema）、`enum`、`const`、`items`、`minItems`、`maxItems`、`minimum`、`maximum`、`minLength`、`maxLength`、`pattern`（Python `re`）、`$ref`、`$defs`、`not`、`anyOf`、`allOf`、`default`（仅注释）、`description`、`examples`、`title`。
- 每个 `description` 为"中文 / English"双语。
- 所有对象 `additionalProperties: false`（禁止字段主要靠这一条），敏感字段再用 `not: {anyOf: [{required: [...]}]}` 明示。
- 允许缺失/未知的字段用 `["<type>", "null"]`，语义：`null` = 用户"跳过/不知道"；投递时遇到需要该字段的表单 → `unknown_required_field` 关口（或按默认跳过记账）。

---

## 12. 与 BRIEF 的对照表

| BRIEF 条目 | 落点（模块 / 文件） | 本文位置 |
|---|---|---|
| D1 用户群不限国籍、双语 | `profile.status.work_pass` 枚举含 Citizen/PR/Student's Pass/EP/S Pass/WP/DP/LTVP/TEP/WHP/Other/None；`meta.language`；pending/shortlist/report 双语 | §3.2, schemas |
| D2 Claude Code 主 + Codex 薄适配 | `runtime/claude-code.md`、`runtime/codex.md`；本文只写差异点 | §3.5 |
| D3 凭据策略 | `password_or_signup` 关口；`secrets.env` 仅 Codex；profile schema `not` 禁密码；`events.password_in_chat_refused` | §3.1, §3.5, §9 |
| D4 浏览器主备 + Executor 单线程 | browser lease；`run_state.browser`；`browser_disconnected` 关口 | §1.4, §2.2 |
| D5 v1 平台集 | `platform` 枚举；`playbooks/` 11 份 | §9, §10.2 |
| D6 不生成/翻译简历 | `resume_missing_language` 关口；`materials.resumes[].language` | §3.1 |
| D7 母清单批准入队 | `screen` 状态 + `queue_approval` 关口 + `shortlist.md` + `application.approval` | §2.2, §5.5 |
| D8 confirm/autopilot | `policy.submit_mode` + `autopilot_consent`；`final_submit` 关口 | §3.1, schemas |
| D9 开放题只引 facts_card 且需批准 | Content Agent 输入仅 `facts_card.json[status=confirmed]`；`content_approval` 关口；`content/*.md` 头部 `facts_used[]` | §1.2, §5.3 |
| D10 邮件后端抽象、只读 | Tracker `tracker_state.backend ∈ {connector, webmail, none}`；`policy.mail_readonly_consent` | §1.2, §2.2 |
| D11 SQLite + 四节导出 | §9 DDL + `export_md.py` + §5.6 映射 | §5.6, §9 |
| D12 stdlib only + 手写校验 | §1.3 脚本层；§11 关键字子集 | §1.3, §11 |
| D13 节奏与节流、ToS | `rules.per_round/per_day/per_company_max`、`policy.report_every_n`、`quota` 脚本、`onboarding.tos_acknowledged_at` | §1.3, §2.2 |
| D14 目录与不提交 | §5.2 数据目录；本文不含任何 git 操作 | §5.2 |
| D15 不直连 ATS | 脚本层"无网络、无浏览器"；Executor 只经真实浏览器 | §1.3 |
| D16 成功定义 | `report` 三栏 + `unique_jobs_applied` 口径 | §6.1 |
| D17 旧资产迁移 | `migrate-legacy` + `legacy_import` 证据类型 | §1.3, §7.1 |
| R1 去重键 | §6 | §6 |
| R2 母清单优先、标来源 | `job.source.type` 枚举 + `sourcing_state.json` 先消费用户来源 | §4, §5.3 |
| R3 一致性门 | §8 + `consistency_mismatch` 关口 | §8 |
| R4 断连挂起不假装 | `browser_disconnected` 关口（run 级、sync） | §3.1 |
| R5 平台 playbook | §10.2 14 节骨架（以 _template.md 为准） | §10.2 |
| R6 LinkedIn 配额感知 | `run_state.quotas.linkedin_*`、`quota` 脚本、`events.quota_switch` | §1.3, schemas |
| R7 密码红线与脱敏 | `redact.py`；evidence 文本先脱敏；`ledger assert no-secrets`（细则在 SECURITY.md） | §1.3, §7.3, §9 |
| R8 公司策略字段 | `rules.company_blacklist / reserve_for_referral / global_quota_rule / industry_exclusions / title_exclusions` | schemas |
| R9 开放题 | 同 D9 | — |
| R10 提交前复核脚本化 | `presubmit` 脚本 → `pre_submit_check.json`；`final_submit` 关口前置条件 | §1.3, §3.1 |
| §3 "已投"标准 | §7.1 合格类型 + `applied-has-evidence` 断言 | §7, §9 |
| §3 必跳过并记账 | `skip_reason_code` 枚举 | §9 |
| §7 问诊 8 轮 | `intake_state.round_done`；profile 顶层分组与 8 轮一一对应 | §2.2, schemas |

---

## 13. 开放问题（需产品负责人拍板）

1. `ats_portal_status`（候选人门户显示 Submitted）是否与成功页同等合格？建议同等（B 级），否则 Tracker 无法后补证据。
2. `policy.gate_mode` 默认值：`interactive`（用户在场、逐个关口同步问）还是 `batch`（"睡醒看到 20 份"、关口集中批处理）？建议默认 `interactive`，onboarding 第 7 轮询问。
3. `facts_card` 以 JSON 为 canonical、MD 为渲染版（本文方案），还是反过来（用户直接改 MD）？建议 JSON canonical，改动经 Intake 回写。
4. `dedup_review` 相似度阈值 0.8 与"连续子序列"规则是否可接受；P3 回放后可能需调。
5. 同一岗位的第二渠道（官网已投、LinkedIn 又见）默认 `dedup_hit` 自动跳过；是否允许用户在 rules 里开"允许双渠道"？建议 v1 不开。

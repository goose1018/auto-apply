# INCIDENTS — 事故簿

> 记录 2026-08 人工 + Codex/Claude 投递期间的真实事故。每条规则背后都有一次真实翻车；改规则前先来这里看它是怎么来的。状态：Phase 1 初版，2026-09-05。
> 证据来源：`~/codex-chat-export/2026-08-07/16-24-12 继续投递简历 [57727641e3e8].md`（下称"主稿"）、`~/codex-chat-export/2026-08-13/11-30-25 继续投递简历 [885a83d62bd3].md`（下称"8-13 稿"）、`~/Documents/Codex/投递台账.md`（下称"台账"）、`~/Documents/Codex/2026-09-04/自动投递工作流_Plan与需求确认_v0.md`（下称"Plan"）。以上文件在产品负责人本机，不在仓库。
> 写法约定：只写现象与字段名，不写任何个人字段值（SECURITY §9）。"强制执行"列用 ARCHITECTURE.md 的模块名、`gate_type`、`skip_reason_code`、`events.kind` 枚举；标 `[未实现]` 的表示规则已冻结、代码未落地。

---

## 0. 索引

| 编号 | 事故 | 规则 | 强制执行位置 | 状态 |
|---|---|---|---|---|
| I-01 | 口径灾难 102 / 92 / 10 | R1、D11、硬边界"只引用台账" | `ledger.py`（`jobs.dedup_key UNIQUE`、`submission_action_count`）；`report.py` 的 `unique_jobs_applied` / `submission_actions`；verify `ledger_dedupe.py` | `[未实现]` |
| I-02 | 偏离母清单、从推荐页凑数 | R2、D7 | `agents/02-sourcing.md`；`jobs.source_type` 必填枚举；`sourcing_state.json`；`queue_approval` 关口；verify `sourcing_source_tag.py` | `[未实现]` |
| I-03 | 简历-档案漂移（联系方式、毕业年份） | R3、R10 | `consistency.py` + `consistency_mismatch` 关口；`presubmit.py` + `checklists/pre_submit.md`；verify `intake_consistency_gate.py` | `[未实现]` |
| I-04 | Chrome 扩展单点故障 | R4、D4 | `browser_disconnected` / `file_upload_blocked` 关口；browser lease；`runtime/claude-code.md` | `[未实现]` |
| I-05 | 会话里出现明文密码 | R7、D3 | SECURITY §3；`events.kind=password_in_chat_refused`；所有 `agents/*.md` 禁止段 | 规则已写 |
| I-06 | record-and-replay 路线失败 | D15 | 无录制器；`playbooks/` 以文字知识代替录制 | 规则已写 |
| I-07 | Temasek 长表单超时登出、CSRF 失效 | R5 | `playbooks/successfactors.md` §7；`session_expired` 关口；`form_state.saved_at` | `[未实现]` |
| I-08 | NCS 项目描述超 4,000 字符，Next 假可点 | R5、R9 | `playbooks/smartrecruiters.md` §6；`agents/05-content.md` 长度校验 | `[未实现]` |
| I-09 | Lever 地点自动完成控件返空，提交被清空 | R5、R10 | `playbooks/lever.md` §6；`presubmit.py` 对 `form_state.fields_filled` 回读 | `[未实现]` |
| I-10 | Grab 申请表只给 2026 日期窗 | 硬边界"日期窗不符必跳过"、R5 | Screening 硬条件 + `skip_reason_code=date_window_mismatch`；verify `screening_hard_filters.py` | `[未实现]` |
| I-11 | GoTo 表单强制 NRIC/FIN | 硬边界"证件号必停"、D3 | `schemas/profile.schema.json` 无此字段；`id_number` 关口 → `skip_reason_code=id_number_required`；SECURITY §2 | 规则已写 |
| I-12 | Razer / PwC 必答开放题 "Why X?" | R9、D9 | `agents/05-content.md`；`content_approval` 关口；`content/*.md` 头部 `facts_used[]` | `[未实现]` |
| I-13 | Bank of America 注册页 CAPTCHA | 硬边界"CAPTCHA 必停" | `captcha` 关口；SECURITY §1.1 | 规则已写 |
| I-14 | Apple 强制新建 Apple Account | D3、硬边界"新建账号必停" | `password_or_signup` 关口；`runtime/claude-code.md` 预填范围 | 规则已写 |
| I-15 | Keppel 账号验证链接过期 | D10 | `email_verification_link` 关口；`policy.allow_verification_link_click`；`agents/07-tracker.md` | `[未实现]` |
| I-16 | UBS 卡在高中学历细节，草稿停 41% | 硬边界"事实底线" | `unknown_required_field` 关口；`status=draft_saved` | 规则已写 |
| I-17 | Workday 拒绝直引号等字符 | R5 | `playbooks/workday.md` §6；平台字符清理函数（归属待架构定） | `[未实现]` |
| I-18 | Jobstreet "访问雇主网站" 被当成已投 | 硬边界"已投标准" | `evidence.py` 合格类型表（`external_redirect` 不合格）；`ledger assert applied-has-evidence`；verify `ledger_applied_has_evidence.py` | `[未实现]` |
| I-19 | Codex 侧从未落地 skill，每次会话重述规则 | D2、D14 | `install.sh`；`skills/auto-apply/SKILL.md` | `install.sh` 已产出 |
| I-20 | Accenture / Synapxe / Singtel 强制邮箱验证码 | 硬边界"OTP 必停" | `otp` 关口；SECURITY §1.3 | 规则已写 |
| I-21 | Razer 日期控件掩码异常（年份可能被填错） | R5、R10 | 对应 ATS playbook §6；`presubmit.py` 日期回读 | `[未实现]` |

---

## 1. 逐条记录

### I-01 口径灾难：102 / 92 / 10
- **事故**：向用户汇报"累计 102 份"，被追问后拆成 102 次提交动作 / 92 个去重岗位（公司 + 岗位）/ 10 次重复（同一岗位在官网 ATS 与 LinkedIn 各投一次，NCS 尤其多）。用户信任受损，全部重算。
- **根因**：计数单位从未定义，把"提交动作"当"岗位"报；渠道没有当成属性；数字靠会话记忆而不是台账。
- **规则**：R1（去重键 = normalize(公司) + normalize(岗位名)，渠道是属性，计数只数去重岗位、提交动作另计）；D11；硬边界"汇报只引用台账，不凭记忆报数"。
- **强制执行**：`ledger.py`：`jobs.dedup_key UNIQUE`，同岗位不同渠道共用一个 `job_id`，每次点提交 `applications.submission_action_count += 1`；`report.py` 只输出 `unique_jobs_applied` 与 `submission_actions` 两个并列数字，Reporter 文案固定为"去重 N 岗 / 提交 M 次（其中重复 K）"（ARCHITECTURE §6.1）；`ledger assert unique-vs-actions`；verify `ledger_dedupe.py` 断言同岗两渠道去重数为 1。
- **证据**：主稿 :L4419、:L4550、:L4601；台账 §一第 25 条（NCS 同名重复提交）。
- **状态**：`[未实现]`

### I-02 偏离母清单，从推荐页凑数
- **事故**：用户给了一份经核验的 100 岗位母清单；Agent 投到第 17 份后为了凑数，改从平台推荐页选岗，被用户当场发现："你是不是没有按照之前总结好的 md 文件里面 100 个岗位？"随后所有清单外投递单独归档、重新核验。
- **根因**：Sourcing 没有"先消费用户清单，再自主搜索"的顺序约束；候选没有来源标签，事后无法区分。
- **规则**：R2；D7（母清单 → 用户批准 → 才入队；自主搜索结果必须经用户批准）。
- **强制执行**：`agents/02-sourcing.md` 第一步固定为消费用户清单 / 链接，`sourcing_state.json` 记录每个来源消费到哪；`jobs.source_type` 必填枚举（`user_list` / `user_link` / `site_search` / `recommendation` / `referral` / `legacy_import` / `other`）；未经 `queue_approval` 关口批准的行不得进入 `apply_queue.jsonl`（ARCHITECTURE §5.5）；verify `sourcing_source_tag.py`。
- **证据**：主稿 :L116–L142。
- **状态**：`[未实现]`

### I-03 简历-档案漂移
- **事故**：简历 PDF 上的联系邮箱、电话区号与表单实际填写的不一致（旧邮箱 / 旧区号 vs 新邮箱 / 新加坡号）；ATS 简历解析多次把姓名顺序、国家、区号填错；毕业年份被系统解析成早一年，需要逐份人工纠正。
- **根因**：简历文件与 profile 两份真相源，没有一致性检查；提交前复核靠 Agent 记忆而不是清单。
- **规则**：R3（解析简历里的联系方式 / 毕业年份与 profile 比对，不一致先报警）；R10（提交前复核清单脚本化：姓名顺序 / 区号 / 毕业年份 / 简历版本 / 实习期 / 薪资）。
- **强制执行**：`consistency.py` 比对 `resume_parse.json` 与 `profile.json`，`overall=block` 触发 run 级 `consistency_mismatch` 关口（ARCHITECTURE §8）；`presubmit.py` 按 `checklists/pre_submit.md` 逐项比对 `form_state.json`，不通过则 `final_submit` 关口不开；verify `intake_consistency_gate.py` 用两份故意不一致的虚构简历 / profile 断言能抓出。
- **证据**：Plan §1 事故 3；主稿 :L3304；台账 §三"提交前逐项复核"。
- **状态**：`[未实现]`

### I-04 Chrome 扩展单点故障
- **事故**：Chrome 扩展多次断连、超时、无响应、需重装；扩展默认无"Allow access to file URLs"导致本地简历上传被拦；一批 LinkedIn 操作整批无法执行，用户被反复要求点连接按钮。
- **根因**：登录态浏览器只有一条通道；断连后没有"挂起并记录"的协议，Agent 要么反复重试要么改口。
- **规则**：R4（双通道，断连挂起不假装）；D4（已登录 Chrome 主通道，备用浏览器只读核验）。
- **强制执行**：run 级 `browser_disconnected` 关口（sync，禁止假装完成）与 item 级 `file_upload_blocked` 关口（ARCHITECTURE §3.1）；browser lease 30 分钟过期回收（§1.4）；恢复前 Executor 先只读核对页面（§2.4 第 4 条）；`runtime/claude-code.md` 列出主 / 备通道；onboarding `selfcheck` 记录 `file_upload_ok`。
- **证据**：Plan §1 工具机制与事故 4；主稿 :L2121、:L2199；`playbooks/README.md` §4 引用的 :L72、:L2545、:L4862、:L7003。
- **状态**：`[未实现]`

### I-05 会话里出现明文密码
- **事故**：用户在会话里贴了两个密码；Codex 拒绝使用并要求立即更换。密码由此进入聊天记录导出文件。
- **根因**：凭据传递没有事先约定的通道；用户为了推进进度走了最快的路。
- **规则**：R7；D3；硬边界"禁止在会话里传密码，Agent 收到必须拒绝并提醒更换"。
- **强制执行**：SECURITY §3 标准回应文案；`events.kind=password_in_chat_refused`（不记内容）；每个 `agents/*.md` 的禁止段复述；Codex 运行时唯一凭据通道是 `secrets.env`（SECURITY §1.2）；`ledger assert no-secrets` 全表扫描。
- **证据**：主稿 :L1938（本事故簿不引用密码值，也不引用该行原文）。
- **状态**：规则已写；agents 复述待架构落地。

### I-06 record-and-replay 路线失败
- **事故**：2026-08-07 尝试"录制一次投递、之后回放"的技能路线，用户中途取消，无产物；真正跑通的是"台账 + 规则文本 + 每次会话重述"。
- **根因**：ATS 表单结构、控件、验证逐家不同，录制脚本无法泛化；脚本回放也意味着绕过真实浏览器。
- **规则**：D15（不做 Playwright / HTTP 直连，不绕过反自动化，全部走真实浏览器）。
- **强制执行**：仓库无任何录制 / 回放代码，脚本层"无网络、无浏览器"（ARCHITECTURE §1.3）；平台知识以 `playbooks/*.md` 文字形式沉淀，Executor 按 playbook 步骤 id 在真实浏览器里执行并用 `form_state.last_step` 断点续填。
- **证据**：Plan §1"Codex 侧从未落地投递技能……record-and-replay 录制被你中途取消"；`~/codex-chat-export/2026-08-07/08-52-47 创建重复投递简历技能`。
- **状态**：规则已写。

### I-07 Temasek 长表单超时登出、CSRF 失效
- **事故**：SuccessFactors 表单填写超过 30 分钟，会话登出；2026-08-25 再次尝试时表单 100% 填完并 Save 成功，点 Apply 后旧会话 CSRF 令牌失效卡在 Loading，邮箱无回执，按规则不计入已投。
- **根因**：长表单没有 Save 草稿节奏；没有"超过 N 分钟先存一次"的硬规则；提交前没有刷新会话。
- **规则**：R5（每个 ATS 一份 playbook：Save 草稿节奏、超时策略）。
- **强制执行**：`playbooks/successfactors.md` §7 "Save 与超时策略"：单份超过 20 分钟先 Save，每页完成即 Save；`form_state.saved_at` 记录；命中登出 / CSRF → `session_expired` 关口，重新登录后从草稿恢复，不重填不重复提交（ARCHITECTURE §3.1、§3.4）。
- **证据**：台账 §四 2026-08-25 Temasek 行；`~/.claude/skills/job-apply/SKILL.md` 第 5 步"防超时"。
- **状态**：`[未实现]`

### I-08 NCS 项目描述超 4,000 字符
- **事故**：SmartRecruiters 把简历解析出的项目描述塞进单个字段，超过 4,000 字符；"Next"按钮看似可点但实际过不去。Agent 一度把"页面打开了"当进度报。
- **根因**：不知道字段上限；解析结果未经长度校验直接填；进度口径混乱。
- **规则**：R5（字段上限进 playbook）；R9 / D9（Content Agent 生成内容受长度约束）；硬边界"填完表不算已投"。
- **强制执行**：`playbooks/smartrecruiters.md` §6 字段上限表（4,000 为观察值，其他字段"未验证"）；`agents/05-content.md` 生成前读 playbook 上限，超限压缩后**重新经 `content_approval`**；Executor 填长文本后回读字段长度；`open_tab` 证据类型不合格（ARCHITECTURE §7.1）。
- **证据**：8-13 稿 :L31。
- **状态**：`[未实现]`

### I-09 Lever 地点自动完成控件返空
- **事故**：ShopBack（Lever）表单全部填好、简历上传成功，但 `Current location` 自动完成控件不返回任何选项，提交时该字段被清空，无法计入已投。
- **根因**：自动完成 / 下拉类控件需要选中选项而非输入文本；填完没有回读控件实际值。
- **规则**：R5（控件坑进 playbook）；R10（提交前回读）。
- **强制执行**：`playbooks/lever.md` §6 记录该控件行为与对策（输入后等待下拉、选中候选、回读值；仍为空则挂起交用户）；`presubmit.py` 对 `form_state.fields_filled` 中每个必填字段回读比对，回读为空 = 不通过，`final_submit` 关口不开。
- **证据**：主稿 :L2675、:L2700。
- **状态**：`[未实现]`

### I-10 Grab 申请表只给 2026 日期窗
- **事故**：Grab Strategy & Analytics（SmartRecruiters）申请表只提供 2026 年三个实习窗口，与用户 2027 上半年档期冲突；未提交。同类：Klook、Univers、Legrand、TCS（要求立即到岗）。
- **根因**：JD 里的日期窗与表单里的日期选项不一致，筛岗阶段没抓到；到填表阶段才发现，浪费一轮。
- **规则**：硬边界"日期窗不符必跳过并记账"；R5（playbook 记录"表单日期选项可能比 JD 更窄"）。
- **强制执行**：Screening 硬条件用 `job.hard_conditions` 与 `profile.intent.available_from / available_to` 比对；Executor 在表单出现日期选项时再比对一次，不符 → `status=skipped skip_reason_code=date_window_mismatch`（立即到岗类用 `start_immediately`），不填后续字段；verify `screening_hard_filters.py`。
- **证据**：台账 §二 Grab 条目；8-13 稿 :L362。
- **状态**：`[未实现]`

### I-11 GoTo 表单强制 NRIC/FIN
- **事故**：GoTo 岗位匹配，但申请表必填 NRIC/FIN；用户未授权提供，Agent 按规则跳过且不计数。
- **根因**：无。这是正确行为；记录是为了把"证件号"作为设计红线写死，而不是每次靠 Agent 判断。
- **规则**：硬边界"证件号必停"；D3（两运行时都永不收集证件号）。
- **强制执行**：`schemas/profile.schema.json` 没有任何证件号字段且用 `not` 明示禁止（ARCHITECTURE §11）；`id_number` 关口永不填、默认 `skip`，`skip_reason_code=id_number_required`，pending 中用户可选"我自己填"；SECURITY §2 禁止数据清单。
- **证据**：主稿 :L4129、:L7240、:L7344。
- **状态**：规则已写。

### I-12 Razer / PwC 必答开放题
- **事故**：Razer 表单出现必填开放题 "Why Razer?"；PwC 第二页出现 "Why PwC / Why this position"。Agent 按当时规则跳过不编答案，也不计数。之后用户明确要求"每个岗位的开放题、求职动机要针对 JD 填写"。
- **根因**：当时没有"只引用事实卡生成 + 用户批准"的机制，只能在"编造"与"跳过"之间二选一。
- **规则**：R9；D9（Content Agent 只引用 facts_card 生成，默认生成后须批准才填；用户可设为跳过 / 自动）。
- **强制执行**：`agents/05-content.md`：输入只有 `facts_card.json[status=confirmed]` + JD，草稿头部 JSON 的 `facts_used[]` 列出引用的 `fact_id`，无引用的句子不得出现；默认 `content_approval` 关口；`policy.open_question_policy` / `cover_letter_policy` 三选一（ARCHITECTURE §3.1、§5.3）。
- **证据**：主稿 :L3429、:L3461、:L7693。
- **状态**：`[未实现]`

### I-13 Bank of America 注册页 CAPTCHA
- **事故**：注册提交被 `Captcha validation failed` 拦下；第二次会话系统不复用上次注册，再次要求账号密码与 reCAPTCHA。Agent 保留注册页、不代填凭据、不计数。同类：StraitsX（Greenhouse）、Optiver、Lendingpot（InternSG）出现 reCAPTCHA。
- **根因**：无。正确行为；记录用于把 CAPTCHA 写成平台级红线并给出关口协议。
- **规则**：硬边界"CAPTCHA 必停"；SECURITY §1.1 第 4 条（用户授权也不能越过）。
- **强制执行**：`captcha` 关口（item 级；用户在场 sync，否则 async）：Agent 停在页面、写 `pending_actions.jsonl`、等待用户按完说"继续"；`playbooks/greenhouse.md` 标注该平台常见 reCAPTCHA。
- **证据**：主稿 :L3175、:L7360、:L3919、:L4907、:L5060。
- **状态**：规则已写。

### I-14 Apple 强制新建 Apple Account
- **事故**：Apple 2027 IS&T 岗位匹配，但提交跳转到 Apple Account 登录；注册页强制出生日期、长期可用手机验证与图片验证码。Agent 停在登录页，不猜生日、不碰验证码，不计数。
- **根因**：无。记录用于定义"强制新建账号"关口在 Claude Code 上的标准动作。
- **规则**：D3（Claude Code：预填非密码字段 → 停在密码框 → 用户手输并存 Chrome）；硬边界"新建账号必停"。
- **强制执行**：`password_or_signup` 关口（ARCHITECTURE §3.1、§3.5）；`runtime/claude-code.md` 写明预填范围（`identity.*` 中的非密码字段）与停止点；出生日期属谨慎字段（SECURITY §2），profile 里为 null 则不预填并转 `unknown_required_field`。
- **证据**：主稿 :L2886、:L3637、:L7236。
- **状态**：规则已写。

### I-15 Keppel 账号验证链接过期
- **事故**：Keppel 只收到账号验证邮件，验证链接过期后未能完成注册；Temasek 账号也曾停在"已建未激活"。
- **根因**：验证链接有时效，Tracker 没有在有效期内提醒用户或（经授权）点击。
- **规则**：D10（邮件追踪）；SECURITY §1.3（验证链接默认挂起交用户，可书面预授权）。
- **强制执行**：`email_verification_link` 关口：`policy.allow_verification_link_click` 且邮件后端可用 → Agent 自动点并记 `events`；否则 async 挂起，`pending_actions.md` 附收到时间与 `expires_at`；`account_verification_email` 证据类型不合格，不得据此标已投（ARCHITECTURE §3.1、§7.1）。
- **证据**：台账 §二 Keppel、Temasek 条目。
- **状态**：`[未实现]`

### I-16 UBS 卡在高中学历细节
- **事故**：UBS 注册到 41%，表单要求高中学历细节；用户简历与 profile 里没有，Agent 不编造，草稿保留。
- **根因**：无。正确行为；记录用于说明"缺失字段 = 跳过并记账"在长表单中的具体形态是"保留草稿 + 挂起"，而不是放弃。
- **规则**：硬边界"事实底线：缺失字段 = 跳过并记账，绝不猜"。
- **强制执行**：`unknown_required_field` 关口（item 级 async）：平台支持 Save 则先 Save，`status=draft_saved`，pending 中列出字段名供用户一次性补进 profile；默认 `skip_reason_code=unknown_required_field`（ARCHITECTURE §3.1）。
- **证据**：台账 §二 UBS 条目。
- **状态**：规则已写。

### I-17 Workday 拒绝直引号等字符
- **事故**：CapitaLand（Workday）三段经历中的直引号等字符被校验拦下；只能清理平台禁止的符号，不删减内容。VIAVI 也遇到描述字符校验。
- **根因**：从 PDF 解析出的文本含平台不接受的标点；没有统一的清理规则。
- **规则**：R5。
- **强制执行**：`playbooks/workday.md` §6 记录禁用字符（已观察：直引号；其余"未验证"）；提供按平台的字符清理函数（只替换标点、不改词句；模块归属待架构确认，`normalize.py` 目前只负责去重键）；Executor 回读字段确认内容未被截断。
- **证据**：主稿 :L4995、:L3260。
- **状态**：`[未实现]`

### I-18 Jobstreet "访问雇主网站" 被当成已投
- **事故**：Jobstreet 上部分岗位点 Apply 后只是跳转雇主网站（`/apply/external`，标题 "Visited external site"）；打开的标签页、填完的表、账号验证邮件都曾被误报为进度。
- **根因**："已投"没有可机器判定的定义。
- **规则**：硬边界"已投标准：只有职位级成功页或雇主 / ATS 确认邮件才算"。
- **强制执行**：`evidence.py` 按 ARCHITECTURE §7.1 合格类型表判定 `qualifies`（`external_redirect` / `open_tab` / `form_completed_screenshot` / `account_verification_email` 一律 0）；`ledger assert applied-has-evidence` 在 `upsert-app --status applied` 时强制检查，失败退出码 3；外跳后必须重新识别目标平台（`playbooks/README.md` §1）；verify `ledger_applied_has_evidence.py`。
- **证据**：Plan §1 平台坑位表 Jobstreet 行；8-13 稿 :L31（"不再把页面打开了算成进度"）；`playbooks/README.md` §1 Jobstreet 行引用的证据。
- **状态**：`[未实现]`

### I-19 Codex 侧从未落地 skill
- **事故**：2026-08 的投递全靠"台账 + 规则文本 + 每次会话重述"，Codex 的 `~/.codex/skills/` 只有 chronicle；规则口径在不同会话间漂移。
- **根因**：没有可安装、自包含的 skill 目录。
- **规则**：D2（同一 skill 目录、`runtime/` 分文件）；D14（代码在 `~/cursor/auto-apply/`，软链安装）。
- **强制执行**：`install.sh` 把 `skills/auto-apply` 软链到 `~/.claude/skills/auto-apply` 与 `~/.codex/skills/auto-apply`；`skills/auto-apply/SKILL.md` 是唯一入口，规则不再靠会话重述。
- **证据**：Plan §1"Codex 侧从未落地投递技能"。
- **状态**：`install.sh` 已产出（验证：临时 HOME 下首装 / 重跑 / 目标被占三种情形通过，2026-09-05）；`SKILL.md` 由架构 Agent 产出 `[未实现]`。

### I-20 强制邮箱验证码
- **事故**：Accenture、Synapxe、Singtel 部分岗位、Razer 注册后强制邮箱验证；无用户在场时只能跳过。
- **根因**：无。记录用于定义 OTP 关口的恢复路径。
- **规则**：硬边界"邮箱 / 短信 OTP 必停"；SECURITY §1.3。
- **强制执行**：`otp` 关口：挂起 → 用户贴码 → 继续；重发 ≥ 3 次仍失败 → `expired`（ARCHITECTURE §3.4）；Tracker 若在已授权邮箱里读到验证码，只展示给用户、由用户决定是否使用；验证码不写台账、不写日志。
- **证据**：台账 §二 Accenture、Synapxe、Singtel 条目；主稿 :L3252。
- **状态**：规则已写。

### I-21 Razer 日期控件掩码异常
- **事故**：Razer 表单的日期组件有输入掩码异常，直接输入可能把年份填成错误值；Agent 改用官方日历逐月定位。
- **根因**：日期控件行为因平台而异；直接键入不可靠。
- **规则**：R5；R10（提交前回读毕业年份 / 实习期）。
- **强制执行**：对应 ATS 的 playbook §6 记录"日期控件用日历选择，不直接键入"（Razer 所用 ATS 类型待核对，"未验证"）；`presubmit.py` 对所有日期字段做回读比对。
- **证据**：主稿 :L3609。
- **状态**：`[未实现]`

---

## 2. 新增事故的写法

1. 编号顺延 `I-NN`；标题一句话说清平台 + 现象。
2. 六行固定：事故 / 根因（没有根因就写"无，正确行为，记录原因是……"）/ 规则（BRIEF 的 D、R 或硬边界原文）/ 强制执行（ARCHITECTURE 的模块名、`gate_type`、`skip_reason_code` + verify 名）/ 证据（CODE_STANDARDS §10.2 格式）/ 状态。
3. 只写字段名与现象，不写任何个人字段值；不引用含密码的原文。
4. 同步更新 §0 索引；若事故落在某个 ATS，对应 `playbooks/<平台>.md` 的"已知事故"章节必须引用本编号（CODE_STANDARDS §11.3）。
5. 用户运行时遇到的新坑（含未知平台）先由 Orchestrator 写进 `runs/<run_id>/` 的脱敏记录，再由人经 PR 汇入本文件与 playbook；Agent 不在用户机器上直接改仓库文件。

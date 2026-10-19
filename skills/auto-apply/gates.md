# gates.md — 关口协议运行时手册 / Gate Protocol Runtime Manual

> `AA` = `python3 <skill_dir>/scripts/autoapply/cli.py [--data-dir DIR] --profile <profile_id>`（定义见 `SKILL.md` §开场）。

> 适用于 Orchestrator 与全部职能 Agent；规范来源 `ARCHITECTURE.md §3`，冲突以 BRIEF §3 为准。
> 用户可见文案中英双语（跟随 `profile.meta.language`，另一种语言作为副本附在后面）。
> 运行时工具差异只写"差异点"，具体工具名/命令看 `runtime/claude-code.md`、`runtime/codex.md`。

## 0. 通用规则（所有关口共用）

**关口 = Agent 必须停下、把决定权交回用户的时刻。** 触发后 Agent 只做四件事，顺序固定：

1. **保存现场**：能 Save 草稿就 Save；把当前 playbook 步骤 id 写进 `runs/<run_id>/items/<app_id>/form_state.json.last_step`。
2. **登记**：`AA app gate / run gate '<pending_action>'`（结构见 `schemas/pending_action.schema.json`），脚本会追加 `pending_actions.jsonl`、重渲染 `pending_actions.md`、写 `gates` 表。
3. **改状态**：item 级 → `ledger upsert-app --status pending_user`；run 级 → `runstate suspend --gate <id> --resume-to <phase>`。
4. **对用户说话**（sync）或**继续下一项**（async）。说话模板见各关口；说完就结束回合，**不要**自己等。

**两种处理模式**（`profile.policy.gate_mode`，默认 `interactive`）：
- `interactive`（用户在场）：item 级关口也当场问（sync），页面保持打开。
- `batch`（用户不在，"睡醒看到 20 份"）：能挂起的一律挂起（async）、保存草稿、释放浏览器、处理下一项；轮末或每 `report_every_n` 份时把 `pending_actions.md` 一次性给用户。
- 无论哪种模式，`final_submit`、`queue_approval`、`consistency_mismatch`、`browser_disconnected` **永远 sync**；`id_number`、`payment` **永远不填**。

**恢复口令**：用户说「继续」/ "continue" / `/auto-apply continue`，可附处置（"1 好了，2 跳过，3 我自己提交了"）。Orchestrator：`pending resolve` → `runstate resume` → 重派 Agent。Executor 恢复任何一项前**先只读核对页面**仍在 `last_step`，不符则退回上一个可确认步骤。

**"我自己做完了"（`user_completed`）≠ 已投**：转 `verify` 找证据，找到合格证据才标 `applied`。

**绝对禁止**：
- 会话里出现任何看起来像密码的文本 → 不使用、不复述、不记录；回复固定文案（§1 末尾）并写 `events(kind=password_in_chat_refused)`。
- 关口文案、pending 文件、日志里出现 OTP 原文、证件号、密码。
- 把"填完了 / 到了确认页 / 打开了页面"说成"已投"。
- 浏览器断了还继续报进度（R4）。

---

## 1. `password_or_signup` — 密码 / 新建账号 / SSO 登录

**触发**：需要登录而浏览器没有已保存凭据；需要新建账号（含设密码、勾 ToS）；SSO/Auth0/Apple Account/学校 SSO 登录墙；密码框出现且未自动填充。
**Agent 先做**：预填**所有非密码字段**（姓名、邮箱用 `identity.emails.signup` 或 `primary`、手机等）；把页面停在密码框；不点"注册/登录"。
**Agent 该说**：
> 【需要你输密码】<公司> — <岗位>（<平台>）要求登录/注册。我已把姓名、邮箱等填好，停在密码框。请你在页面上输入密码（建议让浏览器保存，下次就不用再来），完成后回复「继续」。请**不要**把密码发到对话里。
> [Password needed] <Company> — <Title> (<platform>) requires sign-in/sign-up. Non-password fields are filled; I stopped at the password box. Please type your password on the page (let the browser save it), then reply "continue". Never paste a password into this chat.
**用户做**：在页面输入密码（并勾选浏览器保存）；有 ToS 勾选框自己勾；点 Sign in/Register 或让 Agent 点；回「继续」。
**恢复**：Agent 检查已登录（playbook「登录态检测」）→ 从 `last_step` 继续；若页面回到登录页 → 再触发一次本关口（最多 2 次，之后 `failed`，原因 `other: login_loop`）。
**运行时差异**：Claude Code = 上述；Codex = 若 `secrets.env` 有 `JOB_ACCOUNT_PASSWORD`，Agent 代输密码（不回显、不记录、只用于求职账号），仍由用户处理 ToS 与 OTP；无该变量则同 Claude Code。
**超时**：item 级默认 7 天过期。
**收到密码文本时的固定回复**：
> 我不能使用对话里的密码，也不会记录它。请立即更换这个密码；之后在页面上手输并让浏览器保存即可。
> I can't use a password sent in chat and will not record it. Please change it now; type it on the page and let the browser save it instead.

## 2. `captcha` — 验证码 / 人机挑战

**触发**：reCAPTCHA、hCaptcha、Cloudflare 挑战、滑块/图形题、"I'm not a robot"。
**Agent 该说**：
> 【需要你过验证码】<公司> — <岗位> 页面出现人机验证，我不能代按。请你在页面完成验证，然后回复「继续」。
> [CAPTCHA] Please complete the human verification on the page yourself, then reply "continue".
**用户做**：自己完成验证，不要刷新页面。
**恢复**：Agent 只读核对验证已通过（挑战消失/进入下一步）→ 继续 `last_step`。
**运行时差异**：无（两运行时都禁止代按）。
**超时**：验证会话通常几分钟内失效【未验证：各平台时长】；用户晚回来 → Agent 重新走到该步再让用户按一次。

## 3. `otp` — 邮箱/短信一次性验证码

**触发**：登录/注册/提交前要求输入验证码。
**Agent 先做**：若 `policy.mail_readonly_consent=true` 且邮件后端可用 → 先只读查找验证码邮件；找到则直接输入并**不记录码本身**；找不到或无授权才触发关口。
**Agent 该说**：
> 【需要验证码】<公司> — <岗位> 要求邮箱/短信验证码。请把验证码贴到对话（验证码可以，密码不行），或自己在页面输入后回复「继续」。
> [One-time code] Please paste the code here (codes are fine, passwords are not), or enter it on the page and reply "continue".
**用户做**：贴码或自填。
**恢复**：Agent 输入码 → 核对通过 → 继续。码过期 → 触发重发，最多 3 次，之后 `expired`。
**运行时差异**：Codex 可用 gmail 插件读码；Claude Code 需用户已在 claude.ai 授权邮箱连接器，否则走已登录 Chrome 网页邮箱或用户贴码。
**超时**：码通常 5–15 分钟【未验证】；item 7 天。

## 4. `email_verification_link` — 邮箱激活链接

**触发**：注册后提示"请到邮箱点击链接激活"。
**Agent 先做**：`policy.allow_verification_link_click=true` 且邮件后端可用 → 找到该邮件、核对发件域与链接域一致 → 点击 → 记 `events(kind=gate_resolved, auto)`，不触发关口。否则触发。
**Agent 该说**：
> 【需要点激活链接】<公司> 已发送账号激活邮件到 <邮箱脱敏>。请你打开邮件点击链接，完成后回复「继续」。链接一般有时效，尽快处理。
> [Activation link] Please open the activation email and click the link, then reply "continue". Links expire.
**用户做**：点链接；若已过期，在页面点"重新发送"。
**恢复**：Agent 回到登录步骤 → 登录 → 继续。
**运行时差异**：同 §3。
**超时**：Keppel 类事故——链接过期未激活 = 未投（记 `二、中间状态`）。

## 5. `id_number` — 证件号（NRIC / FIN / 护照 / 身份证 / 税号）

**触发**：任何证件号字段为**必填**。（选填 → 留空继续，不触发。）
**Agent 做**：**永不填、永不问、永不存**。默认 `skipped`，原因 `id_number_required`，记账；同时登记一条 pending 让用户知情。
**Agent 该说**：
> 【已跳过】<公司> — <岗位> 的申请表必填证件号，我不收集也不填写这类信息。已按规则跳过并记账。如果你想投，可以自己在页面填完这一项后回复「继续」，我会接着处理其余字段。
> [Skipped] This form requires a national ID number, which I never collect or enter. If you want to proceed, fill that field yourself, then reply "continue".
**用户做**：可选——自己填该字段。
**恢复**：用户自填后 → Agent 核对该字段已有值（不读取内容）→ 继续 `last_step`。
**运行时差异**：无。
**超时**：不适用（默认已跳过）。

## 6. `payment` — 支付 / 银行信息

同 §5：永不填；默认 `skipped` 原因 `payment_required`。文案把"证件号"换成"支付/银行信息"。求职申请出现付费 = 高风险信号，在 pending 里加一句"请核实是否为正规招聘"。

## 7. `personal_declaration` — 必须本人回答的声明题

**触发**：司法记录、破产、疫苗、竞业、亲属在职、背景调查同意、EEO 类（性别/种族/残障/退伍）等，且 `policy.declarations` 对应值为 `null`，或 `eeo_default=ask_me`。
**Agent 先做**：能预填的（`declarations` 已预设、`eeo_default=prefer_not_to_say`）直接填，不触发。
**Agent 该说**：
> 【需要你本人回答】<公司> — <岗位> 表单有必须本人回答的声明题：「<题目原文>」。请告诉我答案（只这一题），或自己在页面选择后回复「继续」。如果你希望以后都这样答，我会把它写进你的档案。
> [Your answer needed] The form asks: "<question>". Tell me your answer, or select it on the page and reply "continue". I can save it to your profile for next time.
**用户做**：回答；可说"以后都这样答"→ Intake 写入 `policy.declarations`（需用户确认一次）。
**恢复**：填入 → 继续。
**运行时差异**：无。
**超时**：item 7 天。

## 8. `final_submit` — 最终提交（confirm 模式）

**触发**：`policy.submit_mode=confirm`，且 `AA presubmit <app_id>` 通过，Agent 站在提交按钮前。**presubmit 不通过不得进入本关口**（先修字段或挂 `unknown_required_field`）。
**Agent 该说**（引用 `pre_submit_check.json`，不凭记忆）：
> 【等你确认提交】<公司> — <岗位>（<平台>/<渠道>）
> 复核通过：姓名顺序 ✓ 区号 ✓ 邮箱 ✓ 毕业年月 ✓ 简历版本 <label> ✓ 实习期 ✓ 薪资 ✓
> 开放题/CL：<已批准 N 条 / 无>
> 回复「提交」我就点 Submit；回复「跳过」则保存草稿不提交。
> [Ready to submit] Pre-submit checks passed (see list). Reply "submit" to send, or "skip" to keep the draft.
**用户做**：回「提交」或「跳过」。
**恢复**：「提交」→ 点 Submit → `submission_action_count += 1` → 进入 `verify`；「跳过」→ `draft_saved`。
**运行时差异**：无。autopilot 模式（须 `policy.autopilot_consent` 存在）不触发本关口。
**超时**：不过期，但草稿可能被平台清理【未验证】。

## 9. `content_approval` — 开放题 / cover letter 待批准

**触发**：`open_question_policy=approve` 或 `cover_letter_policy=approve`，Content Agent 已生成草稿（只引用 `facts_card` 中 `confirmed` 事实，头部列出 `facts_used`）。
**Agent 该说**：
> 【请批准内容】<公司> — <岗位> 有 <N> 道开放题/一封 CL。草稿在 `runs/<run>/items/<app>/content/`，摘要如下：
> Q1「<题目>」→ <草稿前 100 字>…（引用事实 f_003, f_012）
> 回复「批准」/「改：…」/「跳过这题」。
> [Approve content] Drafts cite only your signed facts. Reply "approve", "edit: …", or "skip".
**用户做**：批准 / 改 / 跳过。
**恢复**：批准 → 填入；改 → Content 重生成一次再问；跳过 → 该题留空（若必填 → `unknown_required_field`）。
**运行时差异**：无。
**超时**：item 7 天。async 模式下 Executor 先填其它字段并 Save。

## 10. `resume_missing_language` — 缺少对应语言简历（D6）

**触发**：岗位/表单要求某语言简历，`materials.resumes` 无该语言。
**Agent 做**：默认 `skipped` 原因 `resume_language_missing`；**不翻译、不生成**。
**Agent 该说**：
> 【缺 <语言> 简历】<公司> — <岗位> 需要 <语言> 简历，你的档案里只有 <已有语言>。我不会替你生成或翻译。如果你补一份，把路径告诉我，我会加进档案并把这个岗位放回队列。
> [Missing <lang> resume] Provide a <lang> resume path and I'll add it and re-queue this job. I never generate or translate resumes.
**用户做**：补简历路径或放弃。
**恢复**：Intake 把新简历加入 `materials.resumes`（重跑一致性门）→ 该项回队列。

## 11. `unknown_required_field` — 档案里没有的必填字段

**触发**：必填字段在 profile/facts_card 中无对应值（如高中信息、推荐人、GPA、证书编号…）。
**Agent 做**：**绝不猜**。默认 `skipped` 原因 `unknown_required_field`，pending 里列出字段名。
**Agent 该说**：
> 【缺信息，已跳过】<公司> — <岗位> 必填我不知道的信息：<字段 1>、<字段 2>。我不会编造。告诉我答案我就写进档案并把岗位放回队列；或自己在页面填好后回复「继续」。
> [Missing info] Required fields I don't have: <fields>. Tell me and I'll save them to your profile, or fill them on the page and reply "continue".
**恢复**：写入 profile（经 Intake 确认）→ 回队列；或用户自填 → 继续。

## 12. `file_upload_blocked` — 无法上传本地文件

**触发**：文件选择器无法被控制、扩展缺少本地文件权限、上传后页面无反应。
**Agent 先做**：优先用平台"已存简历"（若与 `resume_used` 同一 sha256/版本）。
**Agent 该说**：
> 【简历上传需要你】<公司> — <岗位> 的简历上传我做不了。请你在页面选择文件 `<label> (<文件名>)`，上传完成后回复「继续」。（Claude Code：也可在扩展设置里打开 "Allow access to file URLs" 后回复「继续」让我重试。）
> [Upload needed] Please pick the resume file on the page, then reply "continue".
**恢复**：核对上传控件显示文件名 → 继续。
**运行时差异**：Claude Code = 用户手动或开扩展权限；Codex = 可尝试 computer-use 点系统文件窗，失败再交用户。

## 13. `session_expired` — 会话过期 / CSRF 失效 / 页面重置

**触发**：填表中途被登出、提交按钮卡 Loading 无回执、页面回到首步（Temasek 2026-08-25 事故）。
**Agent 做**：立即停止写操作；记录 `last_step`、`draft_url`；**不重复点提交**（防重复申请）；尝试重新登录（走 §1 规则）→ 在"我的申请"找草稿。
**Agent 该说**（仅在无法自恢复时）：
> 【会话过期】<公司> — <岗位> 填到「<步骤>」时被登出，草稿 <已保存/未保存>。我没有点提交，也没收到回执，所以**不算已投**。请你重新登录后回复「继续」，我会从草稿接着做。
> [Session expired] Logged out at step <step>; draft <saved/not saved>; nothing was submitted. Please sign in again and reply "continue".
**恢复**：登录 → 找草稿 → 只读核对已填字段 → 继续。
**超时**：item 7 天。

## 14. `dedup_review` — 疑似重复

**触发**：Screening 发现同公司 + 岗位名相似度 ≥ 0.8（或子序列）但非精确命中。
**处理**：不单独打断，并入母清单（`shortlist.md`）标"疑似重复：与 <已投岗位> 相似 0.86，上次 <日期> 经 <渠道>"，建议跳过。用户批准入队时需明确写 `approval_note`。
**精确命中**（同 `job_id` 已投）不是关口：自动跳过，原因 `already_applied`。

## 15. `queue_approval` — 母清单批准（run 级，D7）

**触发**：`screen` 阶段生成 `shortlist.md`。
**Agent 该说**：
> 【请批准本轮母清单】共 <N> 条：建议投 <a>，建议跳过 <b>（原因已标），疑似重复 <c>。清单：`runs/<run>/shortlist.md`。
> 回复「全部批准」或「批准 1,2,5；排除 3」。未批准的不会投。
> [Approve shortlist] Reply "approve all" or "approve 1,2,5; exclude 3". Nothing is applied without your approval.
**恢复**：写 `apply_queue.jsonl`（每行 `approval.approved_by_user=true`）→ `apply`。

## 16. `consistency_mismatch` — 简历与档案不一致（run 级，R3）

**触发**：`AA profile consistency` 返回 `overall=block`。
**Agent 该说**（值脱敏）：
> 【简历与档案不一致，暂停投递】《<简历文件>》上的 <字段> 是 <脱敏值>，档案里是 <脱敏值>。请选：
> ① 以档案为准，简历不改（招聘方会看到简历上的旧值）
> ② 我换一份简历（给我路径）
> ③ 把档案改成简历上的值
> [Resume/profile mismatch] Choose: keep profile / replace resume / update profile.
**恢复**：① → `materials.resumes[].known_mismatches` 记录 → 继续；② → 重新解析 + 重跑门；③ → Intake 改档案（用户确认）→ 重跑门。

## 17. `browser_disconnected` — 浏览器断连（run 级，R4）

**触发**：扩展无响应/报错、标签页丢失、运行时提示浏览器工具不可用。
**Agent 做**：**立刻停止**，不得假装完成；把当前项标 `pending_user`（如已点提交但未见成功页 → `submitted_unverified`，交 Tracker 后补证据）；`runstate suspend`。
**Agent 该说**：
> 【浏览器断开，已暂停】在 <公司> — <岗位> 的「<步骤>」时浏览器连接丢失。当前进度已保存；<是否已点提交> 。请检查浏览器扩展（重新打开/重连），然后回复「继续」，我会先核对页面状态再接着做。
> [Browser disconnected] Paused at <step>. Progress saved. Reconnect the browser extension and reply "continue"; I will verify the page state before doing anything.
**恢复**：`browser.status=ok` → 只读核对 → 继续。
**运行时差异**：Claude Code = claude-in-chrome 扩展；备用 Browser pane 只做只读核验。Codex = 其浏览器/扩展；备用内置浏览器只读。

## 18. `quota_exhausted` — 配额用尽（run 级，信息性）

**触发**：`quota check` 返回今日 ≥ `rules.per_day`，或所有可用平台达配额（R6 自动切平台后仍无可投）。
**Agent 做**：自动转 `track` → `report`；登记 pending 让用户知情（可选"提高今日上限"）。
**Agent 该说**：
> 【今日额度已用完】已提交 <M> 次 / 去重 <N> 岗，今日上限 <per_day>。LinkedIn 配额 <已达/未知>。明天继续，或回复「今天再投 X 份」临时放宽。
> [Daily quota reached] <M> actions / <N> unique jobs. Continue tomorrow, or reply "allow X more today".

---

## 附：`pending_actions.md` 里每一项的固定字段

`[gate_type] 公司 — 岗位 · 优先级 · 到期` / 页面 / 卡在（步骤 id） / 草稿 / 你需要做（zh+en） / 恢复后 Agent 会 / id。
run 级置顶；已处理与过期折叠到末尾"已处理"。用户只需回「继续」+ 处置。

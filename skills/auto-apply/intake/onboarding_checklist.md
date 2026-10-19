# Onboarding 检查清单 / Onboarding checklist

> `AA` = `python3 <skill_dir>/scripts/autoapply/cli.py [--data-dir DIR] --profile <profile_id>`（定义见 `SKILL.md` §开场）。

> 适用范围：新用户第一次运行 `/auto-apply`，状态机 `onboard` 阶段；Orchestrator 按本清单逐项走，结果写 `~/auto-apply-data/<profile_id>/onboarding.json`。状态：`[未验证]`（Phase 1，无一项端到端跑过）。日期：2026-09-05。
> 上位文件：`BRIEF.md` D2/D3/D4/D10/D13/D16（onboarding ≤ 60 分钟）；`ARCHITECTURE.md` §2.2（`onboard` 状态与 `onboarding.json` 字段）；`SECURITY.md` §1（凭据）、§7.3（免责文案）、§8（邮箱只读）；`README.md` §4–§5。冲突以 BRIEF 为准。
> 每项先中文后英文（EN）。用户只看自己语言那行即可。

---

## 0. 时间预算 / Time budget（目标 ≤ 60 分钟 / target ≤ 60 min）

| 步骤 / Step | 预计 / Est. | 谁做 / Who |
|---|---|---|
| §1 前置自检 / Prerequisites | 10 min | 用户 + `selfcheck` 脚本 |
| §2 数据目录 / Data directory | 2 min | `install.sh` |
| §3 使用须知确认 / Disclaimer | 3 min | 用户 |
| §4 邮箱 / Mailbox | 5 min | 用户（授权）|
| §5 账号预注册 / Account pre-registration | 20 min | Agent 预填 + 用户输密码 |
| §6 进入问诊 / Hand-off to intake | — | Orchestrator |
| 合计 / Total | ≈ 40 min（不含问诊 8 轮 / excluding the 8 intake rounds） | |

超时不是失败；每一项都可以中断后从 `onboarding.json` 续做。 / Running over is not a failure; every step resumes from `onboarding.json`.

---

## 1. 前置自检 / Prerequisites

自检脚本：`AA selfcheck`（`[未验证]`，由 D 实现；只检查存在性与权限，不读任何内容）。脚本检不到的项由用户口头确认，Agent 记录 `checked_by=user`。
EN: Self-check script `AA selfcheck` (`[未验证]`, implemented by D; checks existence and permissions only, never reads content). Items the script cannot see are confirmed verbally by the user and recorded as `checked_by=user`.

### 1.1 运行时 A：Claude Code（主运行时 / primary）

| # | 检查项 / Check | 通过标准 / Pass | 不通过怎么办 / If it fails |
|---|---|---|---|
| A1 | Claude Code 已安装并能打开本仓库 skill（`/auto-apply` 可识别） | skill 目录软链存在：`~/.claude/skills/auto-apply` → `skills/auto-apply` | 跑 `bash install.sh` |
| A2 | **claude-in-chrome** 扩展已安装、已连接到当前会话 | Agent 能列出浏览器标签页（只读操作） | 用户在 Chrome 安装 / 重连扩展；连不上 = `browser_disconnected`，不进入投递 |
| A3 | 扩展详情页已开启 **"Allow access to file URLs"** | 用户口头确认（Agent 不能读扩展设置）；记 `file_upload_ok=true/false/unknown` | 不开也能继续，但简历上传会被拦（INCIDENTS I-04）；投递时走 `file_upload_blocked` 关口 |
| A4 | Chrome 已登录要用的平台（LinkedIn、Jobstreet、MyCareersFuture 等） | 用户口头确认；Agent 可只读打开首页核对已登录（不点任何登录按钮） | 未登录的平台投递时触发 `password_or_signup` |
| A5 | Python ≥ 3.9 | `python3 --version` 输出 ≥ 3.9 | macOS 自带的 `/usr/bin/python3`（3.9.6）已够用；D12 仅标准库、不装包 |
| A6 | 备用只读浏览器（Browser pane）可用 | 可选；只用于只读核验（D4） | 缺失不阻塞 |

EN: A1 Claude Code installed and the skill symlinked (`bash install.sh`). A2 claude-in-chrome extension installed and connected (the agent can list tabs; if not, that is `browser_disconnected` and applying does not start). A3 "Allow access to file URLs" enabled on the extension's details page (user confirms; without it resume uploads are blocked, INCIDENTS I-04, and the `file_upload_blocked` gate handles it). A4 Chrome logged in to the platforms you use (agent may open a homepage read-only to verify; never clicks sign-in). A5 Python 3.9+ (macOS ships 3.9.6 at /usr/bin/python3, which already satisfies this; standard library only). A6 optional read-only Browser pane.

### 1.2 运行时 B：Codex（薄适配层 / thin adapter，`[未验证]`）

| # | 检查项 / Check | 通过标准 / Pass |
|---|---|---|
| B1 | Codex 已安装，skill 软链 `~/.codex/skills/auto-apply` 存在 | `bash install.sh` |
| B2 | Codex 的浏览器 / 扩展可复用 Chrome 登录态 | 以 `runtime/codex.md` 为准 `[未验证]` |
| B3 | 可选：`~/auto-apply-data/<profile_id>/secrets.env` | **只**按 `SECURITY.md` §1.2 创建（单行、chmod 600、求职专用密码）；本清单不重复其规定；`selfcheck` 只检查权限位 |
| B4 | Python ≥ 3.9 | 同 A5 |

EN: B1 Codex installed and the skill symlinked. B2 Codex browser tooling reuses the Chrome login state (per `runtime/codex.md`, unverified). B3 optional `secrets.env` created **only** as specified in `SECURITY.md` §1.2 (this checklist does not restate it; `selfcheck` only checks the mode bits). B4 Python 3.9+.

### 1.3 材料 / Materials

| # | 检查项 / Check |
|---|---|
| M1 | 至少一份简历 PDF / DOCX 的绝对路径（多语言版本可选；D6 不生成不翻译） / At least one resume path (PDF/DOCX); other language versions optional; never generated or translated |
| M2 | 可选：成绩单、作品集链接、旧投递台账 / Optional: transcript, portfolio links, old application ledger |

---

## 2. 数据目录 / Data directory

- `bash install.sh` 创建 `~/auto-apply-data/`（权限 700）；`profile_id` 在问诊 q0_1 确定后再建子目录。
- 数据根目录只从环境变量 `AUTO_APPLY_DATA_DIR` 读取（默认 `~/auto-apply-data`，CLAUDE.md §3）。
- 布局见 ARCHITECTURE §5.2。全部只在本机；仓库 `.gitignore` 已排除。
- 写入 `onboarding.json.selfcheck.data_dir_writable=true`。

EN: `bash install.sh` creates `~/auto-apply-data/` (mode 700); the per-profile subdirectory is created after q0_1. The root is read only from `AUTO_APPLY_DATA_DIR` (default `~/auto-apply-data`). Layout: ARCHITECTURE §5.2. Everything stays on this machine.

---

## 3. 平台使用须知（ToS 免责说明）/ Platform terms disclaimer

**展示位置 / Where it is shown**：
1. 本步骤（onboarding §3）：全文展示 `SECURITY.md` §7.3 的中文或英文版（按用户语言），用户输入「我已了解并同意」/ "I understand and agree" 后写 `onboarding.json.tos_acknowledged_at`，问诊 q7_7 据此写 `policy.platform_tos_acknowledged=true`。
2. `README.md` §3 / English "Disclaimer" 段：安装前可读。
3. 每次新 run 进入 `apply` 前：不再全文展示，只在首次汇报头部加一行「本轮受 SECURITY §7.3 使用须知约束」。

Agent 不代替用户输入同意语；未确认不得进入 `intake` 之后的任何状态（ARCHITECTURE §2.2 `onboard` 进入条件）。
EN: Show the full SECURITY §7.3 text in the user's language; the user types the agreement sentence; record `tos_acknowledged_at`. Also readable in README §3 / "Disclaimer". Later runs only add a one-line reminder in the first report. The agent never types the agreement itself; without it nothing beyond `onboard` runs.

---

## 4. 邮箱 / Mailbox（D10，只读 / read-only）

| 项 | 内容 |
|---|---|
| 推荐 | Gmail 或 Outlook 作为求职邮箱（回执、状态邮件、验证码都发这里）。其它邮箱 v1 只能走"已登录 Chrome 读网页邮箱"或不追踪。 |
| 连接器授权 | **用户自己**在运行时的连接器设置里授权（Claude Code：claude.ai 的 Gmail / Outlook 连接器；Codex：其 gmail 插件）。Agent 不代点任何授权页（SECURITY §1.1 第 6 条）。 |
| 权限范围 | 只读：读列表、读正文、按主题 / 发件人搜索。不发、不删、不改标签、不建规则（SECURITY §8）。 |
| 副作用提示 | 连接器读取是否会把邮件标为已读 `[未验证]`；先告知用户再授权。 |
| 无授权 | 可以继续；Tracker 阶段跳过并在报告标明；OTP 关口改为用户贴码。 |
| 落盘 | 问诊 q7_3 写 `policy.mail_readonly_consent` / `policy.mail_backend_preference`；本步只记 `onboarding.json.mail_connector_authorised=true/false/unknown`（**待定**：该键不在 ARCHITECTURE §2.2 列表中，建议加入）。 |

EN: Use Gmail or Outlook for job mail. Authorise the mailbox connector **yourself** in the runtime's settings (the agent never clicks consent screens). Access is read-only: no sending, deleting, labelling or rules (SECURITY §8). Whether connector reads mark mail as read is unverified; you are told before authorising. Without authorisation the tool still works; tracking is skipped and OTPs are pasted by you. Intake q7_3 records the consent fields; this step only records `mail_connector_authorised` (key pending addition to ARCHITECTURE §2.2).

---

## 5. 账号预注册 / Account pre-registration（D3，约 20 分钟 / about 20 min）

**目的**：一次坐下来把常用 ATS 账号建好并存进 Chrome 密码管理器，之后投递基本不再碰密码。可以跳过；跳过则投递时逐个触发 `password_or_signup`。
EN: Create the commonly needed ATS accounts once and let Chrome save the passwords, so later applications rarely hit a password gate. Skippable; if skipped, `password_or_signup` fires per job.

### 5.1 平台清单 / Platform list

| 平台 / Platform | 账号体系 / Accounts | 预注册建议 / Pre-register? |
|---|---|---|
| LinkedIn | 用户必须已有个人账号 | 不新建；只确认已登录（linkedin.md §3） |
| Jobstreet / SEEK | 一个账号 | 已有则确认登录；无则注册（注册页字段 `[未验证]`，jobstreet.md §3） |
| MyCareersFuture | Singpass 登录 `[未验证]` | 用户自行登录；Agent 不碰 Singpass |
| Workday | **按公司租户各一个账号**；强制设密码（workday.md §3） | 只对用户清单里已知的目标公司预注册；一个邮箱一个租户只能一个账号 |
| SuccessFactors | 按公司租户；强制登录（successfactors.md） | 同上 |
| Greenhouse / Ashby / Lever / Workable | 无账号体系（greenhouse.md §2、ashby.md、lever.md、workable.md） | 不需要 |
| SmartRecruiters | 通常无需账号 `[未验证]` | 不需要 |

### 5.2 每个账号的标准流程 / Standard flow per account

| 步 | Claude Code | Codex |
|---|---|---|
| 1 | Agent 打开注册页，**预填全部非密码字段**（姓名、`identity.emails.signup` 或 `primary`、手机等，来自问诊结果；若 onboarding 先于问诊，则用户口头给这几项，Agent 不落盘） | 同左 |
| 2 | Agent 停在密码框，**不点注册**，说明关口文案（gates.md §1） | 若 `secrets.env` 存在：Agent 在密码框代输（不回显、不记录）；否则同左 |
| 3 | **用户手输密码**，让 Chrome 弹出的"保存密码"点保存；ToS 勾选框用户自己勾 | 用户勾 ToS |
| 4 | 用户回「继续」；Agent 点 Sign up / Register（如用户未点） | 同左 |
| 5 | 邮箱激活链接：`policy.allow_verification_link_click=true` 且邮件后端可用 → Agent 核对域名后点；否则用户点（gates.md §4；链接有时效，INCIDENTS I-15） | 同左 |
| 6 | 登录一次确认 Chrome 自动填充生效；Agent 只点 Sign in | 同左 |
| 7 | 写 `rules.existing_accounts[]`（`platform`、`login_email`、`saved_in_browser=true`、`notes=<公司/租户>`）与 `onboarding.json.accounts_preregistered[]` | 同左 |

**红线**（两运行时）：Agent 永不在会话里接收密码；用户贴了密码 → SECURITY §3 固定回应。Codex 的 `secrets.env` 规定只引用 `SECURITY.md` §1.2，本清单不复述。证件号 / 支付信息在任何注册页出现 → 该平台跳过预注册并记录。
EN red lines (both runtimes): the agent never accepts a password in chat (SECURITY §3 response if one is pasted); Codex `secrets.env` rules live only in `SECURITY.md` §1.2; any sign-up page demanding an ID number or payment is skipped and recorded.

### 5.3 落盘 / Recorded

`onboarding.json.accounts_preregistered[] = [{platform, tenant, login_email_masked, saved_in_browser, verified_login, at}]`（`login_email_masked` 只存脱敏值；明文邮箱在 profile）。**待定**：字段形状由架构定；ARCHITECTURE §2.2 只写了 `accounts_preregistered[]`。

---

## 6. 交接到问诊 / Hand-off to intake

`onboarding.json` 齐备（示意）：
```json
{
  "tos_acknowledged_at": "2026-09-05T09:30:00+08:00",
  "selfcheck": {"python_ok": true, "data_dir_writable": true, "skill_linked": true, "runtime": "claude_code"},
  "browser_channel": "claude_in_chrome",
  "file_upload_ok": true,
  "mail_connector_authorised": "unknown",
  "accounts_preregistered": []
}
```
→ Orchestrator `runstate set-phase intake`（无 profile 或未签字）或 `source`（profile 已签字）。`tos_acknowledged_at` 缺失 → 不得离开 `onboard`。
EN: With `onboarding.json` complete the Orchestrator moves to `intake` (no signed profile yet) or `source` (profile already signed). Missing `tos_acknowledged_at` blocks leaving `onboard`.

---

## 7. 常见失败 / Common failures

| 现象 / Symptom | 处理 / Handling |
|---|---|
| 扩展列不出标签页 / extension cannot list tabs | `browser_disconnected`；用户重连后重试；不改走脚本直连（D15） |
| Phase 1 脚本层未落地 / script layer not yet shipped | 问诊仍可继续，但 `validate` 等脚本不可用 → 汇报标 `[未验证]` |
| 用户在会话贴密码 / password pasted | SECURITY §3 固定回应；记 `events(kind=password_in_chat_refused)`；继续 |
| 注册页要求证件号 / sign-up demands an ID number | 跳过该平台预注册；记录；投递时走 `id_number` 关口 |
| 激活链接过期 / activation link expired | 用户在登录页点"重新发送"；INCIDENTS I-15 |

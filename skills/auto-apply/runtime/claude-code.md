# runtime/claude-code.md — Claude Code 运行时适配（主运行时，BRIEF D2）

> 适用范围：本 skill 在 Claude Code 里运行时的工具映射、凭据策略、邮件后端、已知限制。状态：[未验证]（Phase 1，2026-09-05；工具名来自本机 Claude Code 会话 2026-09-05 的工具清单与 schema，尚未用本 skill 端到端跑过）。
> 上位文件：`BRIEF.md` D3/D4/D10、`SECURITY.md` §1.1/§3/§4/§8、`ARCHITECTURE.md` §1.4/§3.5、`gates.md`。本文只写差异点与映射，不重复规则正文。

## 1. 识别与路径

- 判定为 Claude Code：会话工具清单里有 `mcp__claude-in-chrome__*`、`Agent`、`Skill`；或本 skill 位于 `~/.claude/skills/auto-apply`（`install.sh` 软链）。
- `<skill_dir>` = `~/.claude/skills/auto-apply`。CLI：`python3 <skill_dir>/scripts/autoapply/cli.py [--data-dir DIR] --profile <profile_id> <command>`，用 `Bash` 工具执行。数据目录 `AUTO_APPLY_DATA_DIR`（默认 `~/auto-apply-data`）。
- 工具处于延迟加载时，先用 `ToolSearch` 一次性加载本文 §2 的浏览器工具（`select:` 逗号分隔），不要逐个加载。
- Skill 触发：`/auto-apply …` 经 `Skill` 工具加载本目录 `SKILL.md`；SKILL.md 顶部 YAML frontmatter `name` / `description` 为 Claude Code 格式（本机 `~/.claude/skills/job-apply/SKILL.md` 同格式，观察 2026-09-05）。

## 2. 工具映射

### 2.1 浏览器主通道 = 用户已登录的 Chrome（claude-in-chrome 扩展，BRIEF D4）

| 用途 | 工具（确知，来自 2026-09-05 会话 schema） | 用法要点 |
|---|---|---|
| 取标签页上下文（每次浏览器操作前必做一次） | `mcp__claude-in-chrome__tabs_context_mcp`（`createIfEmpty: true`） | 每个 run 用自己新建的标签页，不复用用户标签页 |
| 新建 / 关闭标签页 | `mcp__claude-in-chrome__tabs_create_mcp` / `mcp__claude-in-chrome__tabs_close_mcp` | 任务结束关闭自己开的页；关口挂起时**不关**当前页 |
| 导航 | `mcp__claude-in-chrome__navigate`（`url`、`tabId`；`back` / `forward`） | 只打开 `candidates.jsonl` 里的 `url` / `apply_url`、平台登录后跳转页、邮箱页 |
| 读页面结构（首选） | `mcp__claude-in-chrome__read_page`（`filter: interactive` / `ref_id` / `depth`） | 用来识别字段、密码框（`type=password`）、按钮、文件控件；返回 `ref_N` |
| 找元素 | `mcp__claude-in-chrome__find`（自然语言 query） | 定位"Submit application"、"Save"、"Resume"等控件 |
| 读页面文本 | `mcp__claude-in-chrome__get_page_text` | JD 摘要、成功页文案、候选人主页状态、邮件列表；优先于截图（SECURITY §4） |
| 填字段 | `mcp__claude-in-chrome__form_input`（`ref`、`value`；checkbox 用 boolean，select 用选项文本或值） | 填表首选；值只来自 profile / facts_card / 已批准 content |
| 点击 / 键盘 / 滚动 / 等待 | `mcp__claude-in-chrome__computer`（`left_click` 可用 `ref` 或坐标；`type`、`key`、`scroll`、`scroll_to`、`wait`、`hover`） | `type` 只用于 form_input 不生效的控件与站内搜索框；**永不**对密码框 `type` |
| 截图（证据 / 定位） | `mcp__claude-in-chrome__computer` `action: screenshot`（`save_to_disk: true` 才落盘；`zoom` 看局部） | 截图进入会话上下文；焦点在密码 / OTP / 证件号 / 支付字段时禁止截图（SECURITY §4） |
| 上传本地文件 | `mcp__claude-in-chrome__file_upload`（`tabId`、`ref` = 文件 input 的 ref、`paths` = 绝对路径数组，单次 ≤ 10 MB） | 不点"上传"按钮（会弹本机文件对话框，不可见）；先用 `read_page` / `find` 找到 `<input type=file>` 的 ref |
| 批量顺序执行 | `mcp__claude-in-chrome__browser_batch` | 可预测两步以上时用；遇域名权限缺失会停在该步，按错误处理，不假装完成 |
| 多浏览器实例 | `mcp__claude-in-chrome__list_connected_browsers` / `select_browser` / `switch_browser` | onboarding 时确认连的是用户本机 Chrome |
| 调试只读 | `mcp__claude-in-chrome__read_console_messages` / `read_network_requests` | 只用于判断页面是否卡死 / 请求失败；不读取含 token 的 URL 进日志 |

禁用于本 skill：`mcp__claude-in-chrome__javascript_tool`（不得用脚本填表、点提交、绕过控件，D15）、`gif_creator`、`shortcuts_*`、`resize_window`、`upload_image`（只用于图片，不用于简历）。

### 2.2 备用只读通道（无登录态，仅核验）

Browser pane 工具 `mcp__Claude_Browser__navigate` / `read_page` / `get_page_text` / `find` / `computer`（screenshot）存在于本机会话（观察 2026-09-05）。它没有用户登录态，只能做只读核验（如岗位是否仍在线、官网 JD 地点），**不得**用于登录、填表、提交（D4）。主通道断连时不得切换到它继续投递。

### 2.3 子代理

`Agent` 工具（`subagent_type: general-purpose` 做多步任务；`Explore` 只读搜索）。用于 Sourcing / Screening / Tracker（连接器模式）/ Reporter 的并行。子代理能否共享主会话的 claude-in-chrome 标签页组 [未验证]；不能则退化为顺序执行（ARCHITECTURE §1.4）。Executor 永不派子代理。

### 2.4 文件与命令

`Read` / `Write` / `Edit` / `Grep` / `Glob` 读写 `~/auto-apply-data/<profile_id>/` 下的检查点文件；`Bash` 只用于执行 CLI 与 `ls` 之类只读命令。不写仓库目录，不 git 写操作（CLAUDE.md §2）。

## 3. 凭据策略（BRIEF D3；SECURITY §1.1 平台级红线，用户授权也不能越过）

1. **永不输入密码**（登录、注册、改密都不行）。识别方式：`read_page` 看到 `type=password` 的 input，或标签含 password / 密码 / 密碼。
2. **永不新建账号并设置密码**。注册流程：预填所有非密码字段（姓名、`identity.emails.signup` 或 `primary`、手机、profile 里用户自愿填写的出生日期；证件号永不填）→ 停在密码框 → 不点 Register / Sign up → `app gate <app_id> --type password_or_signup` → 用户手输并让 Chrome 保存 → 用户「继续」→ Agent 只读核对已登录 → 从 `form_state.last_step` 继续。之后登录靠 Chrome 自动填充，Agent 只点 Sign in；未自动填充 → 再触发一次关口（最多 2 次，gates.md §1）。
3. **永不填证件号**（NRIC / FIN / 护照 / 任何政府 ID）→ `id_number` 关口，默认 `skipped --reason id_number_required`。
4. **永不过 CAPTCHA**（reCAPTCHA / hCaptcha / Cloudflare / 滑块）→ `captcha` 关口。
5. **永不填支付 / 银行信息** → `payment` 关口。
6. **永不代点 OAuth / SSO 授权**（含 "Sign in with Google/Apple"、"Apply with SEEK"、邮箱连接器授权）→ `password_or_signup` 关口，由用户点。
7. 会话里出现密码文本：不使用、不复述、不记录；回复 `SECURITY.md` §3 固定文案；在 `runs/<run_id>/log.jsonl` 记 `kind=password_in_chat_refused`（不记值）。用户说"我授权你用"→ 重复一次，不再讨论。
8. OTP：用户贴到会话或自己在页面输入；Agent 用完即忘，不写任何文件。

## 4. 文件上传前置（BRIEF R4、INCIDENTS I-04）

- 首选 `mcp__claude-in-chrome__file_upload`，`paths` 指向 `profile.materials.resumes[].path`（绝对路径）。该工具由客户端按自己的文件读取权限读文件；数据目录 `~/auto-apply-data/<profile_id>/` 与用户简历所在目录是否在其可读范围内 [未验证]，onboarding 时用一个岗位的上传控件实测并把结果写 `onboarding.file_upload_ok`。
- Chrome 扩展详情页的 "Allow access to file URLs" 是 2026-08 最频繁的上传故障点（Codex 扩展已验证，`playbooks/_template.md` §8）；对 Claude Code 扩展 + `file_upload` 工具是否仍需要 [未验证]。上传失败时的处置顺序：① 平台"已存简历"（先核对文件名 / 版本）→ ② "Enter manually"（`materials` 无 `resume_text` 字段时不可用 [未验证]）→ ③ 提示用户开该权限后重试一次 → ④ `file_upload_blocked` 关口，用户手选文件。
- 上传后必须 `read_page` / `get_page_text` 核对页面显示的文件名 == profile 指定文件名。
- 不点原生文件对话框（不可见）；本运行时无 computer-use 权限操作系统对话框时不要尝试。

## 5. 邮件后端（BRIEF D10；SECURITY §8 只读）

优先级：
1. **claude.ai 邮箱连接器**（Gmail / Outlook，用户自行在 claude.ai 授权，Agent 不代点授权）。工具名随连接器而定 [未验证]；用 `mcp__mcp-registry__list_connectors`（keywords `gmail` / `outlook` / `mail`）查已安装项。本机 2026-09-05 查询结果：无已安装邮箱连接器。
2. **已登录 Chrome 网页邮箱**：`navigate` 到 `mail.google.com` / `outlook.office.com`（或 profile 指定的网页邮箱），`get_page_text` / `read_page` 读列表与正文，搜索框可 `type` 关键词（公司名、"application"、"申请"）。
3. `policy.mail_readonly_consent` 非 true → 不读任何邮箱，报告写"未授权邮箱，状态未追踪"。

只读红线（SECURITY §8）：不点 Send / Reply / Forward / Delete / Archive / 标签 / 星标 / 过滤器 / 设置；不对撰写框 `form_input`；连接器读取是否改变已读状态 [未验证]。账号验证链接只在 `policy.allow_verification_link_click=true` 且发件域与链接域一致时点击（SECURITY §1.3）。OTP 邮件正文不截图、不写文件。

## 6. 断连判定与恢复（R4）

- 断连信号：`tabs_context_mcp` / `read_page` / `navigate` 返回扩展不可达、超时、标签页不存在；`browser_batch` 首步即失败；`list_connected_browsers` 无本机实例。
- 动作：立刻停止写操作 → 当前项 `app status <app_id> pending_user`（已点提交未见成功页则 `submitted_unverified`）→ `app gate … --type browser_disconnected --scope run` → `run checkpoint --state pending_user`。不得改走 Browser pane 或脚本继续。
- 恢复：用户重连后 `tabs_context_mcp` 成功 → Executor 先只读核对页面状态（URL / 标题 / 已填字段 / "Applied jobs" 页）再继续。

## 7. 已知限制

- Claude Code 的安全规则要求对"提交任何表单""输入个人数据到表单"逐次取得用户明确许可；因此 `policy.submit_mode=autopilot` 在本运行时可能仍会在提交前停下（退化为 `confirm`）[未验证]。onboarding 第 7 轮向用户说明这一点。
- 扩展单点故障（I-04）：断连、超时、需重连；每份提交后刷新核对成功状态，不靠记忆。
- 截图进入会话上下文并可能被导出；受 SECURITY §4 约束。
- `browser_batch` 内每步都过域名权限；首次访问新域名可能需要用户在扩展里允许。
- `computer` 的 `type` 是逐键输入，长文本优先 `form_input`；日期分段控件用日历逐段选（`playbooks/workday.md` §6，I-21）；自动完成控件填后必须回读（I-09）。
- 子代理不能持有浏览器写租约；Executor 只在主会话运行。
- `Bash` 里不得出现用户目录绝对路径以外的硬编码；不装任何 pip 包（D12）。

## 8. 未验证清单

- `file_upload` 对 `~/auto-apply-data/` 与用户简历目录的可读性；是否仍需 "Allow access to file URLs"。
- 子代理共享标签页组。
- 邮箱连接器工具名与已读状态副作用。
- autopilot 在 Claude Code 的实际行为。
- 各平台域名权限提示的表现。

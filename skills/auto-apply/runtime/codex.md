# runtime/codex.md — Codex 运行时适配（薄适配层，BRIEF D2）

> 适用范围：本 skill 在 Codex 里运行时的工具映射、凭据策略、邮件后端、已知限制。状态：[未验证]（Phase 1，2026-09-05；本 skill 从未在 Codex 中触发过。下文"本机观察"指 2026-09-05 只读查看 `~/.codex/` 目录与 `config.toml` 节名，未读取任何值）。
> 上位文件：`BRIEF.md` D3/D4/D10、`SECURITY.md` §1.2/§3/§4/§8、`ARCHITECTURE.md` §3.5、`gates.md`。除本文列出的差异点外，一切与 `runtime/claude-code.md` 相同。

## 1. 识别与路径

- 判定为 Codex：本 skill 位于 `~/.codex/skills/auto-apply`（`install.sh` 软链），且会话工具清单里没有 `mcp__claude-in-chrome__*`。
- Skill 格式：`~/.codex/skills/<name>/SKILL.md`，顶部 YAML frontmatter `name` / `description`，与 Claude Code 同一 Agent Skills 格式。[部分验证：本机 `~/.codex/skills/chronicle/SKILL.md` 与 `~/.codex/skills/.system/*/SKILL.md` 使用同样的 frontmatter（观察 2026-09-05）；本 skill 本身尚未在 Codex 里被触发]。Codex 是否支持 SKILL.md 内相对路径引用同目录文件 [未验证]。
- `<skill_dir>` = `~/.codex/skills/auto-apply`。CLI 同 SKILL.md §4，用 Codex 的 shell 工具执行（工具名 [未验证]）。数据目录 `AUTO_APPLY_DATA_DIR`（默认 `~/auto-apply-data`）。
- 本机 `codex` 命令不在当前 shell 的 PATH（观察 2026-09-05）；Codex 以桌面应用形态存在（`~/.codex/config.toml`、`~/.codex/browser/`、`~/.codex/chrome-native-hosts-v2.json` 存在）。

## 2. 工具映射（全部 [未验证]，只写本机 config.toml 观察到的插件节名，不写工具名）

| 用途 | Codex 侧 | 备注 |
|---|---|---|
| 浏览器主通道（用户已登录 Chrome） | `plugins."chrome@openai-bundled"`（Chrome 扩展 / native host） | 2026-08 的 Jobstreet / LinkedIn 投递经此完成（`playbooks/jobstreet.md` §2、`linkedin.md` §2 引用的逐字稿）；具体工具名 [未验证] |
| 备用只读通道 | `plugins."browser@openai-bundled"`（Codex 内置浏览器） | 无登录态，打开 Jobstreet 停在登录页（逐字稿 L2567，观察 2026-08）；只做只读核验（D4） |
| 系统级点击（文件对话框） | `plugins."computer-use@openai-bundled"`、`plugins."unified-computer-use@openai-bundled"`、`[mcp_servers.computer-use]` | 仅用于本机文件选择窗（`file_upload_blocked` 关口前的最后尝试）；不用于绕过任何验证 |
| 邮件连接器 | `plugins."gmail@openai-curated"` | Tracker 后端第一优先；只读；工具名 [未验证] |
| 子代理 | `[agents]` 节存在 | 机制与是否共享浏览器 [未验证]；默认顺序执行 |
| 禁用 | `plugins."record-and-replay@openai-bundled"` | BRIEF D15、INCIDENTS I-06：不录制、不回放、不脚本直连 |
| 文件读写、shell | Codex 内置工具 | 只写 `~/auto-apply-data/`；不 git 写操作 |

`agents/*.md` 的"可用工具"段在 Codex 下按本表对照；找不到对应项的工具就不用，改走人机关口。

## 3. 凭据策略（BRIEF D3；SECURITY §1.2）

与 Claude Code 唯一的差异：**求职专用密码可由 Codex 代输**。

| 项 | 规定 |
|---|---|
| 文件 | `~/auto-apply-data/<profile_id>/secrets.env`，单行 `JOB_ACCOUNT_PASSWORD=<用户自设>`，`chmod 600`，用户手动创建；`install.sh` 与 `selfcheck` 不读内容（`selfcheck` 只查存在与权限位） |
| 何时读 | 只在 Executor 停在密码框那一步（步骤 id `login.password` / `login.signup_password`），且该账号是求职专用账号（`rules.existing_accounts[].login_email` 为 `identity.emails.signup` 或用户在 Intake 声明为求职专用） |
| 怎么读 | 用 shell 只读该文件的这一行，取 `=` 后的值，直接作为浏览器输入工具的文本参数填入密码框；读取与填入之间不经过任何文件、日志、台账。具体工具调用 [未验证]，验证后回填 `SECURITY.md` §1.2 |
| 不回显 | 会话里永不显示、不复述、不确认该值（即使用户要求"确认一下密码"）；不截图含密码框的页面；`pending_actions.md`、`log.jsonl`、`form_state.json` 只记 `fields_filled.password = "secrets.env"` 这样的来源引用，不记值 |
| 限制 | 值会经过模型上下文才能填入；这是已知限制，不是许可。用户改密码只需改文件；文件内容进过会话或截图 → 立即更换 |
| 缺文件 / 权限不是 600 / 不是求职专用账号 | 退回 Claude Code 策略：预填非密码字段，停在密码框，`password_or_signup` 关口 |
| 不适用 | LinkedIn、已有的 Jobstreet 等个人账号密码由用户在 Chrome 管理；学校 SSO、主邮箱、Apple Account 永不代输 |

其余红线与 Claude Code 完全一致：不新建账号设密码之外的凭据、不填证件号、不过 CAPTCHA、不填支付、不代点 OAuth / SSO 授权（含 "Apply with SEEK"）、OTP 由用户贴或 gmail 插件只读取后即忘（不写任何文件）。会话里出现密码文本：`SECURITY.md` §3 固定文案，记 `password_in_chat_refused`。

## 4. 文件上传

- Codex Chrome 扩展需在扩展详情页开启 "Allow access to file URLs"（`playbooks/_template.md` §8 标注 Codex 扩展已验证，2026-08）；onboarding 检查项，结果写 `onboarding.file_upload_ok`。
- 顺序：① 页面文件控件（扩展直接上传）→ ② 平台已存简历（先核对文件名 / 版本）→ ③ computer-use 点本机文件窗 [未验证] → ④ `file_upload_blocked` 关口，用户手选。
- 上传后核对页面显示的文件名 == profile 指定文件名。

## 5. 邮件后端（BRIEF D10；SECURITY §8 只读）

1. `gmail@openai-curated` 插件（用户自行授权；Agent 不代点授权）：读列表 / 正文 / 搜索；工具名与是否改变已读状态 [未验证]。
2. 无插件或非 Gmail：已登录 Chrome 网页邮箱只读（同 `runtime/claude-code.md` §5）。
3. `policy.mail_readonly_consent` 非 true → 不读。
只读红线同 SECURITY §8：不发、不删、不改标签、不建规则、不改设置。

## 6. 断连判定与恢复

同 `runtime/claude-code.md` §6，把"claude-in-chrome 扩展"换成 Codex Chrome 扩展 / native host；备用内置浏览器只读。2026-08 的扩展连接超时（逐字稿 L2252、L2842、L2912、L3139）即此类信号。

## 7. 已知限制

- 本 skill 在 Codex 中从未触发；`~/.codex/skills/` 里此前只有 `chronicle`（INCIDENTS I-19）。首次触发时先只跑 `selfcheck` 与 `onboard`，不进入 `apply`。
- Codex 内置浏览器无登录态，不能替代主通道。
- 子代理机制 [未验证]，并行一律退化为顺序。
- 密码值经模型上下文（§3）。
- `record-and-replay` 插件存在于本机但禁用。

## 8. 未验证清单

- Codex 浏览器 / 扩展 / gmail / computer-use 各工具名与参数。
- 读取 `secrets.env` 的具体工具调用与不回显保证。
- Codex 对 SKILL.md 相对路径引用、frontmatter 之外字段（如 `metadata`）的处理。
- Codex 子代理与浏览器共享。

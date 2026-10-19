# auto-apply

**A human-in-the-loop job application copilot for Claude Code and Codex.** Drop in your resume; agents interview you about what you want, find and screen jobs, fill application forms in *your own* logged-in browser, collect proof of submission, keep a deduplicated ledger, and track replies. You step in only at the gates that should be yours: passwords, CAPTCHAs, ID numbers, personal declarations, and the final submit.

- Local-first: no server, no API keys, Python 3.9 standard library only. Your data never leaves your machine.
- No fabrication: forms and open answers may only cite facts you signed off in a facts card.
- "Applied" means evidence: a job-level success page or an employer/ATS confirmation email — not "I filled the form".
- Dedup by company + title across every channel, per-company and per-day caps to protect your accounts.
- Built for students job-hunting in Singapore (Jobstreet, LinkedIn, MyCareersFuture, Workday, SuccessFactors, Greenhouse, Ashby, Lever, SmartRecruiters, Workable playbooks).

**Status (honest):** the pipeline, ledger, schemas and CLI pass 19/19 self-checks, and sourcing + screening have run on a real search (303 postings → 261 deduplicated → shortlist). End-to-end submission on live sites is not yet verified; every capability is labelled in the table below.

```bash
git clone https://github.com/goose1018/auto-apply ~/cursor/auto-apply && cd ~/cursor/auto-apply && ./install.sh
# then in Claude Code:  /auto-apply
```

> Using automation on job platforms may breach their terms. Read `SECURITY.md` §7 before use. MIT licensed.

---


> 面向在新加坡找实习 / 工作的学生（不限国籍）的 AI 投递流水线 skill。运行在你自己的电脑、你自己的浏览器、你自己的账号上；个人数据只存本机。
> 状态：**Phase 1（地基）**，2026-09-05。目前没有任何功能端到端跑通；下方能力水位表以标签为准，`[未验证]` 就是还不能用。

## 1. 这是什么

你丢一份简历 → AI 分轮问清意向、硬信息、排除项 → 多个 Agent 找岗、筛岗、填表、投递、记账、追状态 → 你只在**密码 / 验证码 / 证件号 / 本人声明题 / 最终授权**这些关口出面。

它是一个安装到 Claude Code（主运行时）或 Codex 的 skill，不是网站、不是服务。没有服务器、没有 API key、没有第三方 Python 包。

## 2. 这不是什么

- 不生成、不翻译、不改写简历。岗位要某种语言版本而你没有 → 提示你补一份。
- 不做中国大陆招聘平台（v2 再说）。
- 不用脚本直连 ATS、不绕过验证码或反自动化；全部走你登录好的真实浏览器。
- 不输入密码（Claude Code）、不填证件号、不填银行信息、不发邮件。
- 不替别人投：每个人在自己电脑上装、用自己的数据。

## 3. 能力水位（诚实版）

标签含义见 `CODE_STANDARDS.md` §10.1：`[已验证 方式]` 有可重跑证明；`[未验证]` 设计了没跑过；`[需你出面]` 人机关口；`[不做]` scope 外。

### 3.1 计划能做（Phase 1 全部未落地）

| 能力 | 状态 |
|---|---|
| 解析简历，生成 profile.json + facts_card.md，分轮问诊确认 | `[未验证]` |
| 简历与档案一致性检查（联系方式、毕业年份） | `[未验证]` |
| 先消费你给的岗位清单 / 链接，再站内搜索，出母清单给你批 | `[未验证]` |
| 硬条件筛选（日期窗、学历、薪资下限、黑名单）+ 台账查重 | `[未验证]` |
| 按平台 playbook 在已登录 Chrome 里填表到提交前 | `[未验证]` |
| Cover letter / 开放题草稿，只引用事实卡，默认你批准后才填 | `[未验证]` |
| confirm 模式下停在提交前等你；autopilot 需你在 profile 书面开启 | `[未验证]` |
| 提交后抓证据（成功页 URL / 截图 / 回执主题），无证据不记"已投" | `[未验证]` |
| 只读邮箱，把回复分四类写台账 | `[未验证]` |
| 三栏汇报：已确认投递 / 待你动作 / 卡壳原因 | `[未验证]` |
| SQLite 台账 + Markdown 导出 | `[未验证]` |
| v1 平台：Jobstreet/SEEK、LinkedIn Easy Apply、MyCareersFuture、Workday、SuccessFactors、Greenhouse、Ashby、SmartRecruiters、Lever、Workable | 每个 playbook 单独标注 `[未验证]` |

### 3.2 需要你出面

| 关口 | 你做什么 |
|---|---|
| 密码 | Claude Code：你自己在浏览器输入并让 Chrome 保存。Codex：把求职专用密码写进本机 `secrets.env`（见 `SECURITY.md` §1.2） |
| 新建账号 | Agent 预填非密码字段，停在密码框 |
| CAPTCHA / 人机验证 | 你按 |
| 邮箱 / 短信验证码 | 你贴到会话 |
| 证件号（NRIC/FIN/护照） | 不填。表单强制要求的岗位会跳过并记账，你决定是否本人去投 |
| 必须本人回答的声明题（司法记录 / 疫苗 / EEO 等） | 问诊时一次性设好；没设的遇到就停 |
| 母清单批准、内容批准、最终提交（confirm） | 你批 |
| 浏览器扩展断连、本地文件上传被拦 | 你重连 / 开权限；Agent 挂起等你，不假装完成 |

### 3.3 不做

生成 / 改写简历；中国平台；脚本直连 ATS；发 / 删邮件；多账号或代理；托管代投；填证件号或银行信息；绕过验证码。

## 4. 前置条件

- macOS 或 Linux；Python **3.9+**（macOS 自带的 `/usr/bin/python3` 就是 3.9.6，够用，无需另装）。
- **Claude Code**（主运行时）+ **claude-in-chrome** 扩展，并在 Chrome 扩展详情里开启 **Allow access to file URLs**（不开的话简历上传会被拦，2026-08 多次踩坑）。
  或 **Codex** 及其浏览器 / 扩展（Codex 适配层 `[未验证]`）。
- Chrome 已登录你要用的平台（LinkedIn、Jobstreet、MyCareersFuture 等）。
- 推荐用 Gmail 或 Outlook 收求职邮件；追踪状态时需要你自行在运行时里授权邮箱连接器（只读），或让 Agent 在已登录 Chrome 里读网页邮箱。
- 一份简历 PDF（英文；岗位需要其他语言版本你再补）。

## 5. 安装

```bash
git clone https://github.com/goose1018/auto-apply ~/cursor/auto-apply
cd ~/cursor/auto-apply
bash install.sh
```

`install.sh` 做的事（幂等，重复跑无副作用）：
- 把 `skills/auto-apply` 软链到 `~/.claude/skills/auto-apply` 与 `~/.codex/skills/auto-apply`（目标已存在且不是软链 → 备份为 `.bak-<时间戳>` 后提示）；
- 创建 `~/auto-apply-data/`（权限 700）；
- 检查 `python3` 版本并提示；
- 不安装任何 Python 包，不创建也不读取 `secrets.env`。

安装后自检：

```bash
python3 scripts/verify/all.py
```

Phase 1 阶段这里可能只有脚手架；输出末行 `SUMMARY passed=<n> failed=<m> total=<t>`，`failed` 不为 0 就是没通过。

## 6. 数据目录

```
~/auto-apply-data/<profile_id>/
├── profile.json            问诊结果（硬信息、意向、排除项、节流规则、授权模式）
├── facts_card.json / .md   只从你简历和你的回答提炼的事实卡（json 为准，md 给你签字）；开放题 / CL 只能引用它
├── resume_parse.json       简历解析结果，用于与 profile 做一致性检查
├── onboarding.json         使用须知确认时间、自检结果
├── secrets.env             仅 Codex；一行 JOB_ACCOUNT_PASSWORD=...，chmod 600
├── ledger.sqlite           台账主存
├── evidence/<app_id>/      成功页截图 / 页面文本等证据
├── runs/<run_id>/          运行状态、候选、队列、脱敏日志、pending_actions.md（待你动作清单）
└── exports/                投递台账.md（四节格式）
```

完整布局与文件契约见 `ARCHITECTURE.md` §5。

全部只在本机；仓库 `.gitignore` 已排除；删掉这个目录就删掉了你的全部数据。仓库里的 `examples/` 全是虚构人物。

## 7. 快速开始（计划中的流程，`[未验证]`）

1. 在 Claude Code 里输入 `/auto-apply`。
2. 阅读并确认平台使用须知（`SECURITY.md` §7.3）。
3. 给简历路径 → 回答问诊（每轮一个决定性问题；任何字段可"跳过 / 不知道"）→ 签字确认 profile 与事实卡。
4. 一次性把常用 ATS 账号注册好并存进 Chrome（约 20 分钟）。
5. 给岗位清单或链接（可选）→ 批母清单 → Agent 开始投；每 5 份汇报一次；遇关口写 `pending_actions.md` 等你。
6. `/auto-apply status` 追邮件状态；`/auto-apply report` 看三栏汇报。

## 8. 文档地图

| 文件 | 内容 |
|---|---|
| `BRIEF.md` | 项目宪法：决策 D1–D17、硬边界、R1–R10、目录布局 |
| `CLAUDE.md` | Agent 接手铁律与必读顺序 |
| `ARCHITECTURE.md` | 状态机、包布局、schema（架构 Agent 产出） |
| `CODE_STANDARDS.md` | 代码 / 文档 / verify / 评审 / DoD 规范 |
| `SECURITY.md` | 凭据、禁止数据、截图脱敏、PDPA、ToS 与节流、邮箱只读 |
| `INCIDENTS.md` | 2026-08 真实事故 → 规则 → 强制执行位置 |
| `HISTORY.md` | 每日决策日志 |

---

## English

### What it is

`auto-apply` is a Claude Code (primary) / Codex skill for students in Singapore, of any nationality, who are applying for internships or jobs. You provide a resume; the agents interview you, source and screen roles, fill in application forms in your own logged-in browser, keep a ledger with evidence, and track replies in your mailbox (read-only). You step in only at gates: passwords, CAPTCHAs, OTPs, national ID numbers, declarations that must be answered by you, and the final submit.

It runs entirely on your machine with the Python standard library only. No server, no API key, no third-party packages. All personal data stays in `~/auto-apply-data/`; the repository contains no real personal data.

### Status

Phase 1 (foundations), 2026-09-05. **Nothing runs end to end yet.** Every capability in the table above is `[未验证]` (unverified). Watch `HISTORY.md` for progress.

### Prerequisites

- macOS or Linux, Python **3.9+** (macOS ships 3.9.6 at `/usr/bin/python3`, which already satisfies this).
- **Claude Code** with the **claude-in-chrome** extension, and **Allow access to file URLs** enabled in the extension's Chrome details page (resume uploads get blocked otherwise). Alternatively **Codex** with its browser tooling (Codex adapter is unverified).
- Chrome logged in to the platforms you use (LinkedIn, Jobstreet, MyCareersFuture, company ATS accounts).
- Gmail or Outlook recommended for tracking; you authorise the mailbox connector yourself (read-only).
- One resume PDF.

### Install

```bash
git clone https://github.com/goose1018/auto-apply ~/cursor/auto-apply
cd ~/cursor/auto-apply
bash install.sh
python3 scripts/verify/all.py
```

`install.sh` is idempotent: it symlinks `skills/auto-apply` into `~/.claude/skills/` and `~/.codex/skills/` (backing up any non-symlink that is already there), creates `~/auto-apply-data/` (mode 700), checks your `python3` version, installs no packages, and never creates or reads `secrets.env`.

### Data directory

```
~/auto-apply-data/<profile_id>/
  profile.json  facts_card.json/.md  resume_parse.json  onboarding.json
  secrets.env (Codex only, one line, chmod 600)
  ledger.sqlite  evidence/<app_id>/  runs/<run_id>/  exports/
```

Delete the directory and all your data is gone. `examples/` in the repo uses fictional people only.

### What you must do yourself

Type passwords (Claude Code never will; Codex uses a job-search-only password you store locally), solve CAPTCHAs, paste OTPs, decide on roles that require a national ID number (the tool skips them), pre-set your answers to declarations during onboarding, approve the candidate list and generated text, and press the final submit in `confirm` mode.

### What it will not do

Write or rewrite your resume; automate mainland-China platforms; connect to ATS APIs or bypass anti-automation; send or delete email; use multiple accounts or proxies; apply on someone else's behalf; enter ID or banking details.

### Disclaimer

Most job platforms restrict automated use. This tool works inside your own browser with built-in limits (default 20 submissions/day, 3 per company, stop on risk signals), which reduce but do not remove the risk of account limits. You accept that risk; you are responsible for what is submitted. Full text: `SECURITY.md` §7.3.

# auto-apply 脚本层 — 命令速查与数据目录

> `AA` = `python3 <skill_dir>/scripts/autoapply/cli.py [--data-dir DIR] --profile <profile_id>`（定义见 `SKILL.md` §开场）。

> 适用范围：`skills/auto-apply/scripts/autoapply/`（Python 3.9+，仅标准库）。状态：Phase 1，2026-09-05。
> 上位文件：`BRIEF.md`（D11/D12/D14、§3 硬边界、R1/R3/R7/R10）、`ARCHITECTURE.md`（§2 状态机、§3 关口、§5 文件契约、§6 去重、§7 证据、§9 DDL、§11 schema 子集）。
> 验证：`python3 scripts/verify/all.py`（无需任何覆盖变量，见 §5）。

脚本只做确定性事情：校验、去重、台账、证据判定、状态机、关口记录、导出、迁移、汇报数据、自检、脱敏。
不访问网络、不碰浏览器、不调 LLM、不读 `secrets.env`。判断"岗位合不合适"、生成任何文案、决定是否提交，都不在这里。

## 1. 调用方式

```bash
python3 skills/auto-apply/scripts/autoapply/cli.py [全局参数] <命令>      # 直接运行
cd skills/auto-apply/scripts && AA [全局参数] <命令>    # 模块方式
```

| 全局参数 | 含义 | 默认 |
|---|---|---|
| `--data-dir DIR` | 数据根目录 | `$AUTO_APPLY_DATA_DIR`，否则 `~/auto-apply-data` |
| `--profile ID` | profile_id，数据目录 = `<data-dir>/<ID>/` | `$AUTO_APPLY_PROFILE`；都没有时若根目录下恰有一个 profile 则自动选用，否则报错（退出码 2） |
| `--json` | stdout 输出机器可读 JSON | 人类可读文本 |

退出码（CODE_STANDARDS §5）：`0` 成功 · `1` 业务断言失败（一致性门 block、`ledger assert` 之外的断言、证据不合格且要求标 applied）· `2` 用法/配置/非法状态转移 · `3` 数据完整性（schema 不合、台账损坏、无合格证据标 applied、`ledger assert` 失败、脱敏命中密码/证件号）。
失败时 stderr 第一行是一行 JSON：`{"error": "<code>", "detail": "<不含个人数据>"}`。

## 2. 命令速查（与 H Agent 规范一致，名称与参数不可改）

```
selfcheck                                                    环境自检；浏览器/邮箱连接器项固定输出「未验证，请手动确认」
profile validate <profile.json> [--no-file-check]            schema + 禁止字段 + 语义（autopilot 需书面授权、简历文件存在）
profile consistency <profile.json> --resume-facts <resume_parse.json> [-o report.json]   R3；block 时退出码 1
facts render <facts_card.json> -o <facts_card.md>            事实卡 JSON → 可读 MD（签字对象）
run new [--mode interactive|batch] [--invocation apply|status|report] [--runtime claude_code|codex] [--target N]
                                                             第一行输出 run_id；创建 runs/<run_id>/
run checkpoint <run_id> --state <phase> [--resume-to <phase>] [--gate <id>]   按 §2.3 校验转移；非法退出码 2
run show <run_id>                                            状态、合法下一步、本轮统计
run pending <run_id>                                         重新渲染 pending_actions.md 并打印
run resolve <run_id> <action_id> [--resolution resolved|skipped|user_completed|expired|abandoned] [--note ...]
run gate <run_id> --type <gate_type> --message "..."         run 级关口（无 application）——补充命令
run list                                                     列出所有 run ——补充命令
jobs add <candidates.jsonl> [--run <run_id>]                 校验每行 → 写 jobs 表 → 去重报告（新增/已存在或已投/疑似重复）
jobs check "<company>" "<title>"                             打印规范化键、job_id、台账里的申请状态与疑似重复
jobs normalize <in.jsonl> -o <out.jsonl>                     填充 normalized/dedup_key/job_id ——补充命令
queue build <run_id> --from <candidates.jsonl> [-o apply_queue.jsonl] [--approve-all "<用户原话>"] [--exclude job_id,...]
                                                             硬规则过滤 + 查重 + 同公司/每轮/每日上限；只入队已批准候选（D7）
app start <run_id> <job_id> --channel <channel> [--platform ...] [--resume PATH] [--note ...] [--force]
                                                             输出 application_id；已投岗位需 --force
app status <application_id> <status> [--reason ...] [--note ...] [--count-submission] [--tracking ...]
                                                             status=applied 无合格证据 → 退出码 3；skipped 需 --reason <skip_reason_code>
app evidence <application_id> --type <type> [--url ...] [--screenshot FILE] [--job-title-seen ...] [--status-seen ...]
             [--subject ...] [--from ...] [--received-at ...] [--excerpt ...] [--legacy-ref ...] [--note ...] [--mark-applied]
                                                             登记证据；qualifies 只由脚本判定（§7.1）
app gate <application_id> --type <gate_type> --message "..." [--scope item|run] [--step login.otp] [--url ...] [--draft-url ...]
         [--field ...] [--missing a,b] [--option ...] [--priority ...] [--mode sync|async]
app show <application_id>                                    申请 + 岗位 + 证据 ——补充命令
ledger stats [--run <run_id>]                                去重岗 / 提交动作 / 重复、按公司、今日计数（节流用）
ledger export -o <path.md>                                   四节台账（默认 exports/投递台账.md）
ledger migrate-legacy <投递台账.md> [--dry-run]              解析旧四节台账 → jobs/applications/evidence(legacy_import)
ledger assert                                                §9 四条断言 ——补充命令
report <run_id> [-o report.md]                               三栏汇报（只读台账）
```

典型顺序：`selfcheck` → `profile validate` → `profile consistency` → `run new` → `run checkpoint --state source` → `jobs add` → `run checkpoint --state screen` → `queue build`（先不带 `--approve-all` 生成母清单材料；用户批准后再带上）→ `run checkpoint --state apply` → `app start` → （关口）`app gate` / `run pending` / `run resolve` → `app evidence --mark-applied` → `ledger stats` → `report` → `ledger export`。

## 3. 数据目录（`~/auto-apply-data/<profile_id>/`，永不进仓库）

```
profile.json                 唯一档案（schema: profile）
facts_card.json / .md        事实卡（JSON canonical，MD 由 facts render 生成）
resume_parse.json            Intake 写；profile consistency 的 --resume-facts 输入
consistency_report.json      profile consistency 默认输出
dedup_aliases.json           {"ncs group": "ncs"} 公司别名表（可选，用户维护）
secrets.env                  仅 Codex；脚本只检查权限位 600，永不读取内容
ledger.sqlite                台账主存（表：meta/jobs/applications/evidence/gates/events）
evidence/<app_id>/NN_<type>.<ext>   证据文件；文本类写入前必经 redact
exports/投递台账.md          ledger export 默认输出
runs/<run_id>/
  run_state.json             检查点（schema: run_state）
  run_options.json           {gate_mode}（run_state schema 无此字段，故单独存放）
  candidates.jsonl · screened.jsonl · apply_queue.jsonl · pending_actions.jsonl · pending_actions.md
  ledger_writes.jsonl        每次台账写操作的入参（脱敏后）
  items/<app_id>/            form_state.json、content/ 由 Agent 写
```

## 4. 与 schema / ARCHITECTURE 的差异（以 schema 为准，D 不改 schema）

| 项 | 处理 |
|---|---|
| `jobs` 表 | 在 §9 DDL 之上增加 `channel`、`company_domain`、`source_added_by`、`posted_at`、`closes_at`、`screening_json`、`notes`（job.schema 有、DDL 没有） |
| `applications` 表 | 增加 `profile_id`、`priority`、`failure_reason`、`form_state_ref`（application.schema 有、DDL 没有）；`resume_used{}` 拆成 `resume_path/resume_language/resume_sha256` |
| `run new --mode interactive\|batch` | 契约里的 `--mode` 是关口模式，而 run_state.schema 的 `mode` 枚举是 `apply\|status\|report`；关口模式存 `run_options.json`，`run_state.mode` 用 `--invocation` |
| `ats_portal_status` | 按 HISTORY 裁定：需 URL + 截图 + 岗位名匹配 + 门户状态为 Submitted/Application received（`--status-seen`）；"under review" 不合格 |
| `evidence.matched_job_by` | 采用 schema 枚举（含 `manual`） |
| 去重键弱点 | `AI Singapore` → `ai`（§6.2 尾部地区词规则）；`Summer Intern`/`PhD Intern` → `intern`（§6.3 首尾段规则）。用 `dedup_aliases.json` 或母清单人工确认兜底；阈值待 P3 回放后调 |
| 环境变量 | `AUTO_APPLY_DATA_DIR`（HISTORY 已统一）；`AUTO_APPLY_PROFILE`；`AUTO_APPLY_SCHEMA_DIR`（可选，默认 `<repo>/schemas`） |

## 5. Python 版本门

入口第一件事检查 `sys.version_info >= (3, 9)`，否则退出码 2（无覆盖变量）。底线定为 3.9 是为了覆盖 macOS 自带的 `/usr/bin/python3`（3.9.6），对齐 BRIEF D12「用户零安装」。代码禁止使用 3.10+ 专有语法（`match`、运行时求值的 `X | Y` 联合、`dataclass(slots=True)`、`itertools.pairwise`、`tomllib`、`typing.Self` 等）；类型注解一律配 `from __future__ import annotations` + `Optional`/`Union`。本机 `/usr/bin/python3` 即 3.9.6，`python3 scripts/verify/all.py` 已在其上验证通过。

## 6. verify

```bash
python3 scripts/verify/all.py            # 末行 SUMMARY passed=<n> failed=<m> total=<t>
python3 scripts/verify/verify_<功能>.py  # 单个；末行 PASS/FAIL
```

| 脚本 | 断言的功能 |
|---|---|
| verify_schema | 六份 schema 加载无未支持关键字；关键字子集；禁止字段/值；`profile validate` 退出码 |
| verify_dedupe | §6.2/6.3 规范化示例；同岗两渠道 = 去重 1 / 提交 2 / 重复 1；疑似重复；别名；job_id 不一致拒收 |
| verify_ledger_assertions | 无合格证据不得 applied（退出码 3）；不合格类型永不合格；四条 `ledger assert` 各有通过/失败路径 |
| verify_runstate | 合法链路；非法/同态/终态转移退出码 2；pending_user 的 resume_to |
| verify_gates | item/run 关口；pending_actions.md 固定格式；resolve 的重排/移交/恢复；密码文本拒收 |
| verify_evidence | §7.1 合格表；岗位名/域名/门户规则；文本证据脱敏；NRIC 拒收 |
| verify_queue_build | 14 条硬规则的 skip_reason_code；D7 批准门；同公司/每轮上限；已投/疑似重复 |
| verify_export_format | 四节顺序；旧台账条目全部进第一节；同公司上限标记；第三节无联系方式；幂等 |
| verify_migrate_legacy | 虚构台账解析/导入/幂等/回放；真实台账（若存在）只读解析 ≥100 条并回放 100% 拦截 |
| verify_redact | 掩码；邮箱/手机替换；需求编号不误伤；NRIC/密码抛异常；台账与 pending 已脱敏 |
| verify_report | 三栏与 `ledger stats` 一致；只读 |
| verify_consistency | R3：邮箱/手机/毕业年 block；月份/姓名顺序 warn；known_mismatches；值脱敏 |
| verify_facts_render | MD 渲染；无效卡退出码 3 |
| verify_selfcheck | ok/warn/fail/unverified；secrets.env 权限位；失败退出码 1 |
| verify_layering | 入口→业务→工具；仅标准库；print/os.environ/secrets.env 限制 |
| verify_cli_contract | 契约命令与参数逐条存在；`-m` 入口；stderr JSON；版本门 |

# 03 Screening（筛岗 / Screening）
> 一句话角色：对母清单原料做硬条件、台账查重、公司策略、匹配打分，出母清单给用户批，批准后建投递队列；所属状态：`screen`；并行性：是（纯判断，可按候选分片）；浏览器：无（需补读 JD 时为读）
> 状态：[未验证]（Phase 1，2026-09-05）。上位文件：`BRIEF.md` §3"必跳过并记账"/ D7 / R1 / R8、`ARCHITECTURE.md` §5.5/§6、`SKILL.md` §7、`gates.md` §14/§15、`INCIDENTS.md` I-01/I-02/I-10。

## 职责
- 逐条决策：`recommend` / `skip`（附 `reason_code`）/ `dedup_hit` / `dedup_review`，理由一句话，写回 `candidates.jsonl` 的 `screening` 块与 `screened.jsonl`。
- 硬条件（脚本能断言的以脚本为准，`queue build` 复核）：
  - 日期窗：`hard_conditions.work_window` 与 `intent.window.start/end`（容忍 `flexibility_weeks`）不交 → `date_window_mismatch`；`start_immediately=true` 而 `intent.earliest_start` 晚于当前 → `start_immediately`（I-10）。
  - 学历：`bachelor_only=true` 且 `intent.apply_to_bachelor_only_postings≠true` → `degree_mismatch`；`degree_required` 高于用户最高在读 / 已获学位 → `degree_mismatch`。
  - 薪资：`salary.disclosed=true` 且换算后 `< profile.salary.hard_floor` → `salary_below_floor`；`unpaid=true` 且 `allow_unpaid≠true` → `unpaid`；未披露且 `apply_if_undisclosed=false` → `skip`（`other`，理由"薪资未披露且用户不投"）。
  - 工作准证：`work_pass_requirement ∈ {citizen_only, citizen_pr_only}` 而 `status.work_pass ∉ {citizen, permanent_resident}` → `work_pass_mismatch`；`no_sponsorship` 且 `status.requires_sponsorship_now=true` → `work_pass_mismatch`。
  - `requires_local_id=true` → `id_number_required`（BRIEF §3 证件号永不填）。
  - `resume_language_required` 不在 `materials.resumes[].language` → `resume_language_missing`（D6，不翻译）。
  - 公司策略（R8）：`rules.company_blacklist`（`until` 未过期）→ `blacklist`；`rules.reserve_for_referral` → `reserve_for_referral`；`hard_conditions.global_quota=true` 按 `rules.global_quota_rule.mode` → `global_quota`；`rules.industry_exclusions` / `title_exclusions` → `industry_excluded` / `title_excluded`；地点不在 `intent.locations`（且非 `remote_ok`）→ `other`（理由"地点冲突"，`playbooks/README.md` §4）。
  - 同公司上限：台账已投 + 本轮建议投 > `rules.per_company_max`（默认 3，D13）→ 超出部分 `skip`（`global_quota` 不对，用 `other`，理由"同公司已达上限 N"）；用户可强制放行并记 `approval_note`。
- 台账查重（R1、ARCHITECTURE §6.4）：`AA jobs check` 精确命中（同 `job_id` 且台账有 `applied / submitted_unverified / pending_user / draft_saved`）→ `dedup_hit`，`already_applied`，自动跳过；疑似（同公司 + 标题相似）→ `dedup_review`，母清单标"疑似重复：与 <已投岗位> 相似 <相似度>，上次 <日期> 经 <渠道>"，建议跳过；台账里 `skipped / abandoned` 的不算命中，但母清单提示"上次跳过原因"。同岗位第二渠道默认 `dedup_hit`（ARCHITECTURE §13 第 5 条）。
- 匹配打分（模型写）：`match.score` 0–100、`reasons[]`（对照 `intent.keywords`、`facts_card` 已签字事实与 JD 要求，每条可追溯）、`concerns[]`。分数只用于排序与"建议"列，不决定跳过。
- 渲染 `shortlist.md`（固定列），交 Orchestrator 触发 `queue_approval`；批准后写回决定并 `queue build`。
- 不做：改 profile / rules；替用户批准；填表；从台账以外的记忆判断"投过没投过"。

## 输入
- `runs/<run_id>/candidates.jsonl`（`job.schema.json`）；缺 `hard_conditions` 关键项时用只读浏览器补读 JD（读租约），补不到就 `null`。
- `<data>/profile.json`：`intent / salary / rules / status / education / materials / meta.language`。
- `<data>/facts_card.json`：只读 `status=confirmed` 的事实，用于匹配理由。
- 台账：`AA jobs check "<company.raw>" "<title.raw>"`（逐条；输出字段 [未验证]）。
- `runs/<run_id>/run_state.json`：`round.target`、`round.per_company_counts`。
- `playbooks/<platform>.md` §11–§12：把平台已知风险写进"风险"列。

## 输出
- `runs/<run_id>/candidates.jsonl`：追加写，每个 `job_id` 追加一行含 `screening{decision, reason_code, reason, dedup_match?, decided_at}` 与 `match{score, reasons, concerns}`（其余字段原样复制）。
- `runs/<run_id>/screened.jsonl`：追加写，每行 `{job_id, decision, reason_code, reason, dedup_match?}`。
- `runs/<run_id>/shortlist.md`：覆盖写。表头固定：`| # | 公司 | 岗位 | 平台/渠道 | 来源 | JD 摘要 | 匹配理由 | 风险 | 建议 | 你的决定 |`；"建议" ∈ {投, 跳过(原因码), 疑似重复→请确认}；文首一行双语说明怎么批（SKILL.md §7 第 3 步文案）；末尾列"自动跳过（不需你决定）"小节。不含任何联系方式。
- 批准后：对每个 `job_id` 再追加一行 `screening.decision = approved | excluded_by_user`（疑似重复被放行时 `reason` 写用户原话作 `approval_note` 依据）→ `AA queue build <run_id> --from runs/<run_id>/candidates.jsonl -o runs/<run_id>/apply_queue.jsonl`。`queue build` 是否只取 `decision=approved` [未验证]；若不是，先写只含已批准行的 `runs/<run_id>/approved_candidates.jsonl` 作 `--from`。队列每行须有 `approval{approved_by_user:true, approved_at, approval_note}`（`application.schema.json`）；`priority` 按 `rules.channel_priority` 与 `match.score` 排。
- 队列为空时告知 Orchestrator → `report`。

## 可用工具
- 脚本：`AA jobs check "<company>" "<title>"`、`AA queue build <run_id> --from <candidates.jsonl> [-o apply_queue.jsonl]`、`AA ledger stats`（同公司累计数，字段 [未验证]）。
- 文件：Read / Write（只写 `candidates.jsonl`、`screened.jsonl`、`shortlist.md`、`apply_queue.jsonl` 经脚本）。
- 浏览器（仅补读 JD）：Claude Code `mcp__claude-in-chrome__navigate` / `get_page_text` / `read_page`，或备用只读通道 `mcp__Claude_Browser__*`；Codex 对应读工具 [未验证]。
- 子代理：`Agent`（Claude Code）分片打分；每片只写自己的临时 jsonl，由本 Agent 合并后写正式文件。
- 禁用：`form_input`、`file_upload`、`app start`、`app status`、任何登录动作。

## 关口
- `queue_approval`（run 级，sync）：`shortlist.md` 生成即触发。上报字段：`gate_type=queue_approval`、`scope=run`、`context.options=["全部批准 / approve all", "批准 1,2,5；排除 3 / approve 1,2,5; exclude 3"]`、`agent_message` 用 `gates.md` §15 文案（N / a / b / c 数字来自 `screened.jsonl` 行数）。恢复条件：用户给出批准范围 → 写回 decision → `queue build` 退出码 0。
- `dedup_review`（item 级，随 `queue_approval` 一起）：不单独打断；母清单"建议"列写"疑似重复→请确认"；用户强制批准须有明确原话，写入 `approval_note`。
- `browser_disconnected`（run 级）：只在补读 JD 时可能触发；处理同 `02-sourcing.md`。
- 精确命中 `already_applied` 不是关口：自动跳过并在母清单"自动跳过"小节列出。

## 禁止
- BRIEF §3 原文：**必跳过并记账**：日期窗不符、学历门槛不符、薪资低于下限、已投、公司黑名单/保留内推名单。→ 这五类不得因"匹配度高"放行；用户要放行必须在 `approval_note` 留原话。
- BRIEF §3 原文：**事实底线**：不编造任何经历、指标、日期、签证答案、声明题答案。缺失字段 = 跳过并记账，绝不猜。→ 匹配理由只引用 `facts_card` 已签字事实与 JD 原文；JD 未写的硬条件不推断为"符合"。
- BRIEF D7：未经用户批准的行不得进入 `apply_queue.jsonl`；自主搜索与推荐来源尤其如此（I-02）。
- BRIEF R1 / I-01：去重键 = normalize(公司)+normalize(岗位名)，渠道是属性；不得因"换个渠道"把已投岗位再放进队列；去重判定以 `jobs check` 为准，不用记忆。
- 不写 `ledger.sqlite`、不写 `profile.json`、不改 `dedup_aliases.json`（可建议用户改）。
- SECURITY §2 / §3：母清单与 `screened.jsonl` 不含联系方式；会话里出现密码 / 证件号文本 → 固定文案回应。

## 完成标准
- `screened.jsonl` 行数 = `candidates.jsonl` 去重后的 `job_id` 数，每行 `decision` ∈ 枚举、`skip` 类必有 `reason_code` ∈ 枚举。
- 台账精确命中的岗位 100% 为 `dedup_hit`（P3 DoD：回放旧台账，verify `screening_hard_filters.py` / `ledger_dedupe.py`，F 产出 [未验证]）。
- `shortlist.md` 存在且表头与 ARCHITECTURE §5.5 一字不差。
- 批准后 `apply_queue.jsonl` 每行 `approval.approved_by_user=true` 且 `job_id` 的最后一条 `screening.decision=approved`；`queue build` 退出码 0。
- 汇报里的 N / a / b / c 与文件行数一致。

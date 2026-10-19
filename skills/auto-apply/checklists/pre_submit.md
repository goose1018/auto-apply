# checklists/pre_submit.md — 提交前复核清单 / Pre-submit checklist（R10）

> 适用范围：QA Agent（`agents/06-qa.md`）在 Executor 站在复核页 / 提交按钮前时逐项执行；结果写 `runs/<run_id>/items/<app_id>/pre_submit_check.json`（结构 = `schemas/application.schema.json` 的 `pre_submit_check`）。状态：[未验证]（Phase 1，2026-09-05）。
> 上位文件：`BRIEF.md` R3 / R10 / §3、`ARCHITECTURE.md` §3.1（`final_submit` 前置条件）、`INCIDENTS.md` I-03 / I-08 / I-09 / I-10 / I-21。
> 规则：每一项都要**从页面回读实际值**，不得用"刚才填的就是对的"代替（I-03）。任一项 `ok=false` → `passed=false` → `final_submit` 关口不得打开。`seen_masked` 一律脱敏，`expected_ref` 写来源路径不写值。CLI 无 `presubmit` verb（SKILL.md §12），本清单由 QA 手工执行。

## 0. 怎么回读

- 首选 `read_page`（`filter: interactive` 或 `ref_id` 指向复核区块）读控件当前值；下拉 / 单选读选中项文本；日期分段控件逐段读；文件控件读显示的文件名。
- 折叠的复核区块先展开（Workday Review、SmartRecruiters 折叠必答题）。
- 回读值为空 = 不通过（I-09），不管是不是必填提示。
- 长文本回读长度并与草稿比对，被截断 = 不通过（I-08）。

## 1. 清单（`items[].name` 用枚举；枚举外的用 `other` 并在 `note` 写条目名）

| # | `name` | 检查什么 | 期望来源 `expected_ref` | 回读方式 | 不通过时 |
|---|---|---|---|---|---|
| 1 | `name_order` | 姓 / 名字段顺序与拆分和简历一致；Legal name 字段按护照拆 | `profile.identity.name.given` / `.family` / `.name_order` | 读 First / Given、Last / Family 两个字段 | Executor 改；平台解析颠倒时手动纠正 |
| 2 | `phone_country_code` | 区号下拉 = 默认手机的区号；号码无多余前缀 | `profile.identity.phones[is_default].country_code` / `.number` | 读区号下拉选中项 + 号码框 | Executor 改（Workday 区号曾自动切错，`playbooks/workday.md` §5） |
| 3 | `email` | 邮箱 = 主邮箱（新注册账号 = `emails.signup`；旧账号绑定的 = `emails.others` 之一）；与简历上的邮箱差异须在 `known_mismatches` 内 | `profile.identity.emails.primary` / `.signup` / `.others`；`materials.resumes[].known_mismatches` | 读邮箱字段；账号邮箱不可改的平台读账号区 | 不在集合内 → `consistency_mismatch`（run 级）；可改 → Executor 改 |
| 4 | `graduation_year` | 预计毕业年月（精确到月）= 档案；系统常落到错误年份 | `profile.education[is_current].end_expected` | 读日期控件各段 / 下拉 | Executor 用日历逐段改（I-21） |
| 5 | `resume_version` | 已上传 / 已选简历的文件名 = 档案指定文件名（有 sha256 时比对） | `profile.materials.resumes[is_default 或岗位语言].path`（basename）/ `.sha256` | 读文件控件显示名 / 已存简历下拉选中项 | 不符 → `file_upload_blocked` 或改选；不得用旧版本提交（事故 #3） |
| 6 | `internship_window` | 可到岗 / 实习起止 / 时长 / 全职与档案一致；"能否立即开始"答案与 `earliest_start` 一致 | `profile.intent.window.start` / `.end` / `.flexibility_weeks` / `.min_commitment_months` / `.hours_per_week` / `.earliest_start` | 读日期与选项 | 表单只给不交的窗口 → `skipped --reason date_window_mismatch`（I-10）；必答"立即开始"且不符 → `start_immediately` |
| 7 | `salary` | 期望薪资在 `expected_min–expected_max` 内、币种与周期正确、≥ `hard_floor`；在读现薪按档案（无则不填） | `profile.salary.expected_min` / `.expected_max` / `.currency` / `.period` / `.hard_floor` | 读数值框与币种 / 周期下拉 | 低于下限 → `skipped --reason salary_below_floor`；否则 Executor 改 |
| 8 | `location` | 表单 / 官网 JD 地点 ∈ `intent.locations`（或 `remote_ok`）；LinkedIn / 聚合站标签不算数 | `profile.intent.locations` / `.remote_ok`；`candidates.jsonl.location` | 读地点字段 + 打开官网 JD 核对（`Hong Kong / Taipei / Asia / APAC / Remote / Hybrid` ≠ 新加坡） | 冲突 → `skipped --reason other --note location_conflict`（`playbooks/linkedin.md` §9） |
| 9 | `work_pass_answer` | "是否合法可在新加坡工作 / 当前准证类型"答案 = 档案；下拉必须是准确项，不选近似项 | `profile.status.authorised_to_work_in_sg` / `.work_pass` / `.work_pass_exempt_for_internship` | 读单选 / 下拉选中项 | 无准确项 → `unknown_required_field`（Jobstreet 无 Student's Pass，`playbooks/jobstreet.md` §9） |
| 10 | `sponsorship_answer` | "现在是否需要赞助"与"未来是否需要赞助"是两题，各自 = 档案 | `profile.status.requires_sponsorship_now` / `.requires_sponsorship_future` | 读两题选中项 | 混填 → Executor 改（`playbooks/README.md` §4 签证三问） |
| 11 | `other`（note: `declarations_preset`） | 每道声明题（司法记录 / 破产 / 疫苗 / 亲属 / 曾申请或任职 / 竞业 / 背景调查 / 数据处理）与 EEO 的选中值 = 档案预设；平台默认勾选而档案为 `null` 的不算通过 | `profile.policy.declarations.*` / `.eeo_default` | 读每题选中项 | `null` → `personal_declaration` 关口；不符 → Executor 改 |
| 12 | `other`（note: `open_answers_approved`） | 每个已填的开放题 / CL 文本 = 对应 `content/*.md` 正文，且文件头 `status ∈ {approved, filled}`；未批准的草稿不得在页面上 | `runs/<run_id>/items/<app_id>/content/<file>.md` | 读文本框内容首尾 50 字与长度 | 草稿未批准 → `content_approval`；被截断 → Content 压缩重批（I-08） |
| 13 | `other`（note: `dedup_not_applied`） | 提交前最后一次 `AA jobs check "<company>" "<title>"` 无精确命中 | 台账（`jobs check` 输出） | 运行命令 | 命中 → `skipped --reason already_applied`，不提交 |
| 14 | `other`（note: `required_fields_readback`） | 页面所有标必填的字段回读非空；自动完成控件已选中选项而非仅有输入文字 | `form_state.fields_filled` | `read_page` 逐个必填控件 | 空 → `unknown_required_field`（I-09） |
| 15 | `other`（note: `attachments`） | 岗位要求的成绩单 / 证书已上传且文件名正确；不要求的不上传 | `profile.materials.transcript_path` / `.certificates[]` | 读附件区 | 要求而档案无 → `unknown_required_field`（`resume_language_missing` 仅限简历语言） |
| 16 | `other`（note: `no_forbidden_fields_filled`） | 页面上证件号 / 银行 / 支付字段为空（选填留空；必填已走 `id_number` / `payment` 关口） | — | 读这些字段是否有值（不读内容） | 有值且非用户自填 → 停止，上报 |

## 2. 输出示例（虚构，字段名以 schema 为准）

```json
{
  "passed": false,
  "checked_at": "2026-09-05T15:02:11+08:00",
  "items": [
    {"name": "name_order", "expected_ref": "profile.identity.name", "seen_masked": "A** / T**", "ok": true, "note": null},
    {"name": "phone_country_code", "expected_ref": "profile.identity.phones[0].country_code", "seen_masked": "+65 ****0000", "ok": true, "note": null},
    {"name": "graduation_year", "expected_ref": "profile.education[0].end_expected", "seen_masked": "2027-0*", "ok": false, "note": "页面年份与档案不符，需日历逐段改"},
    {"name": "other", "expected_ref": "runs/run_20260905_150000/items/app_20260905_a1b2c3/content/q_01.md", "seen_masked": null, "ok": true, "note": "open_answers_approved"}
  ]
}
```

## 3. 用户可见文案（`final_submit` 关口引用本文件结果，`gates.md` §8）

> 复核通过：姓名顺序 ✓ 区号 ✓ 邮箱 ✓ 毕业年月 ✓ 简历版本 <label> ✓ 实习期 ✓ 薪资 ✓ 地点 ✓ 工作授权三问 ✓ 声明题 ✓ 开放题 <N> 条已批准 ✓ 去重 ✓
> Pre-submit checks passed: name order, country code, email, graduation date, resume version <label>, internship window, salary, location, work-pass answers, declarations, <N> approved open answers, dedup.

不通过时列出不通过项的 `name` 与 `note`，不列值。

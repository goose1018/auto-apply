# 事实红线卡渲染模板 / facts_card.template.md

> 适用范围：Intake Agent 由 `facts_card.json`（canonical，schema `schemas/facts_card.schema.json`）渲染 `facts_card.md`；Content Agent 只读 JSON，本模板只决定用户看到的版本。状态：`[未验证]`。日期：2026-09-05。
> 上位文件：`BRIEF.md` D9 / R9、§3 事实底线；`ARCHITECTURE.md` §5.2（JSON canonical、MD 渲染版，开放问题 3 建议值）、§1.2 共同禁令；`facts_card.schema.json`。冲突以 BRIEF 为准。
> 模板里 `{{…}}` 是占位符；`{{#each …}} … {{/each}}` 表示按数组逐条展开；`{{#if …}}` 表示条件段。渲染由会话内模型完成（无第三方模板库，D12）。

---

## 1. 规则（写在渲染文件头部，用户和 Agent 都看）

1. **只有 `status=confirmed` 的条目可以被 Content Agent 引用**；`draft` / `edited`（未再次确认）/ `rejected` 一律不可引用。`edited` 条目在用户对改后文本说"确认"后转为 `confirmed`。
2. 每条事实 = 一句可核实的话，含数字与时间；来源必须是简历（`resume`）、用户口述（`user_stated`）、用户提供的文件（`document`）之一；`inferred_needs_confirmation` 只能是 `draft`，用户确认后改为对应真实来源。
3. `sensitivity=restricted` 的条目（如签证、薪资、声明类）只在表单必填时使用，**不进开放题 / CL**。
4. `usable_in_open_answers=false` 的条目即使 `confirmed` 也不进开放题 / CL（只供 Executor 答结构化题）。
5. `forbidden_claims[]` 里的说法在任何生成文本中不得出现，Content Agent 生成后逐条对照。
6. 简历文件变了（sha256 与 `meta.resume_sha256[]` 不符）→ `meta.signed_by_user=false`，整卡重签。
7. 事实卡不含：联系方式明文以外的敏感数据、证件号、密码、任何第三方个人数据（SECURITY §2）。
8. 用户改动只通过会话告诉 Intake，由 Intake 回写 JSON 再渲染；**不手改 `.md`**（会被覆盖）。

## 2. 渲染模板

````markdown
# 事实红线卡 / Facts card — {{meta.profile_id}}

> 生成 / Generated: {{meta.generated_at}} · 更新 / Updated: {{meta.updated_at}} · 版本 / Version: {{meta.version}}
> 整卡签字 / Card signed: {{#if meta.signed_by_user}}是 / yes（{{meta.signed_at}}）{{else}}**否 / no** — 未签字前 Content Agent 不得引用任何条目 / nothing may be cited before sign-off{{/if}}
> 依据简历 / Resume fingerprints: {{#each meta.resume_sha256}}`{{this}}`{{/each}}
> 规则 / Rules: 只有状态为 `confirmed` 的条目可被引用；`restricted` 只在表单必填时使用；`forbidden_claims` 永不出现。 / Only `confirmed` facts may be cited; `restricted` facts only when a form requires them; `forbidden_claims` never appear.
> 怎么签 / How to sign: 回复「全部确认」/ "confirm all"，或「f_003 改为 …」/ "change f_003 to …"，或「f_007 删掉」/ "drop f_007"；全部处理完后回复「整卡签字」/ "sign the card"。

## 统计 / Summary
| 状态 / Status | 条数 / Count |
|---|---|
| confirmed | {{count.confirmed}} |
| edited（待再次确认 / awaiting re-confirmation） | {{count.edited}} |
| draft | {{count.draft}} |
| rejected | {{count.rejected}} |

{{#each categories}}
## {{category_label}}（`{{category}}`）

| id | 事实 / Statement | 英文 / English | 来源 / Source | 状态 / Status | 签字 / Signature | 开放题可用 / Open-answer | 敏感度 / Sensitivity | 量化 / Quantified |
|---|---|---|---|---|---|---|---|---|
{{#each facts}}
| `{{fact_id}}` | {{statement}} | {{statement_en_or_dash}} | {{source.type}}{{#if source.ref}} · {{source.ref}}{{/if}} | `{{status}}` | {{signature_label}} | {{usable_label}} | {{sensitivity_or_standard}} | {{quantified_label}} |
{{/each}}

{{/each}}

## 禁止说法 / Forbidden claims
{{#if forbidden_claims}}
{{#each forbidden_claims}}
- {{this}}
{{/each}}
{{else}}
（无 / none）
{{/if}}

---
> 由 auto-apply Intake 从 `facts_card.json` 渲染；手改本文件会被覆盖。 / Rendered from `facts_card.json`; manual edits are overwritten.
````

## 3. 占位符与派生值定义

| 占位符 | 来源 / 计算 |
|---|---|
| `categories` | 按 `facts[].category` 分组，固定顺序：`identity` → `education` → `experience` → `skill` → `achievement` → `availability` → `work_permit` → `salary` → `declaration` → `motivation` → `other`；空类别不渲染 |
| `category_label` | 中英固定标签：identity=身份 / Identity；education=教育 / Education；experience=经历 / Experience；skill=技能 / Skills；achievement=成果 / Achievements；availability=档期 / Availability；work_permit=工作许可 / Work permit；salary=薪资 / Salary；declaration=声明 / Declarations；motivation=动机 / Motivation；other=其它 / Other |
| `facts` 组内顺序 | 按 `fact_id` 升序 |
| `statement_en_or_dash` | `statement_en` 非空则显示，否则 `—` |
| `signature_label` | `user_signature.signed=true` → `已签 / signed {{user_signature.signed_at}}`（有 `note` 追加 `（note）`）；否则 `未签 / unsigned` |
| `usable_label` | `usable_in_open_answers=false` → `否 / no`；其余（含 `null`，默认 `true`）→ `是 / yes` |
| `sensitivity_or_standard` | `sensitivity` 非空显示原值；`null` 显示 `standard` |
| `quantified_label` | `true` → `是 / yes`；`false` → `否 / no`；`null` → `—` |
| `count.*` | 按 `status` 计数 |

## 4. 事实条目写法（Intake 生成草稿时遵守）

| 类别 | 一条事实的样子（虚构示例） | 来源 | 默认敏感度 |
|---|---|---|---|
| identity | `Full name on applications: Priya Nair (given first).` | resume | standard；`usable_in_open_answers=false` |
| education | `MSc Computer Science, National University of Singapore, 2025-08 to 2027-06 (expected), currently enrolled.` | resume | public |
| experience | `Software engineering intern at Example Robotics Pte Ltd, Singapore, 2026-05 to 2026-08: built a data-labelling pipeline processing 12,000 images per day (resume bullet 2).` | resume | public |
| skill | `Python: used in two internships and one course project (resume skills section).` | resume | public |
| achievement | `Second place, Sample Hackathon 2025 (team of 4).` | resume | public |
| availability | `Available for a full-time internship from 2027-01-04 to 2027-06-30; up to 40 hours per week.` | user_stated · intake:q3_6 | standard；`usable_in_open_answers=false` |
| work_permit | `Holds a Student's Pass; requires employer sponsorship after graduation.` | user_stated · intake:q2_3 | **restricted** |
| salary | `Expected SGD 1,800–2,500 per month; hard floor SGD 1,500.` | user_stated · intake:q4_2 | **restricted** |
| declaration | `Criminal record declaration preset: No.` | user_stated · intake:q6_5 | **restricted**；`usable_in_open_answers=false` |
| motivation | `Wants to work on applied machine learning in logistics because of the 2026 internship project.` | user_stated · intake:q6_14 | public |
| other | 用户明说的其它可引用事实 | user_stated | standard |

- 一条只说一件事；数字、日期、机构名照简历原文；不写形容词（"优秀""领先"）。
- `experience` 类每条对应一条简历要点（bullet），`source.ref` 写 `<文件名>:bullet <n>` 或页码。
- 简历原文非英文 → `statement` 用原文，`statement_en=null`（D6 不翻译；用户可在签字时自己提供英文版，来源仍是 `user_stated`）。
- `inferred_needs_confirmation` 只用于 Agent 从多条简历信息拼出的一句（如"共 3 段实习"）；用户确认后改 `source.type` 为 `resume` 或 `user_stated`。

## 5. Content Agent 引用规则（本模板同时是 Content Agent 的输入契约摘要）

1. 读 `facts_card.json`，过滤 `meta.signed_by_user=true` ∧ `status=confirmed` ∧ `usable_in_open_answers≠false` ∧ `sensitivity≠restricted`。
2. 草稿头部列出 `facts_used: [fact_id, …]`；正文每句话必须能对应到至少一个 `facts_used` 条目，对应不上的句子删掉。
3. 不得出现 `forbidden_claims[]` 中任何说法（含同义改写）。
4. 不得引用 `profile.json` 的 `experience[]` / `education[]`（那是表单用的，不是引用源，ARCHITECTURE §1.2）。
5. 卡未签字 / 简历指纹不匹配 → 不生成，向 Orchestrator 报 `content_approval` 无法进行，理由 `facts_card_unsigned`。

## 6. 渲染示例（虚构，节选）

```markdown
# 事实红线卡 / Facts card — priya_nair

> 生成 / Generated: 2026-09-05T10:20:00+08:00 · 更新 / Updated: 2026-09-05T11:02:00+08:00 · 版本 / Version: 1
> 整卡签字 / Card signed: 是 / yes（2026-09-05T11:02:00+08:00）
> 依据简历 / Resume fingerprints: `3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8550`
> …

## 经历 / Experience（`experience`）

| id | 事实 / Statement | 英文 / English | 来源 / Source | 状态 / Status | 签字 / Signature | 开放题可用 / Open-answer | 敏感度 / Sensitivity | 量化 / Quantified |
|---|---|---|---|---|---|---|---|---|
| `f_004` | Software engineering intern at Example Robotics Pte Ltd, Singapore, 2026-05 to 2026-08: built a data-labelling pipeline processing 12,000 images per day. | — | resume · resume_en.pdf:bullet 2 | `confirmed` | 已签 / signed 2026-09-05T11:00:00+08:00 | 是 / yes | standard | 是 / yes |

## 薪资 / Salary（`salary`）

| id | 事实 / Statement | 英文 / English | 来源 / Source | 状态 / Status | 签字 / Signature | 开放题可用 / Open-answer | 敏感度 / Sensitivity | 量化 / Quantified |
|---|---|---|---|---|---|---|---|---|
| `f_011` | Expected SGD 1,800–2,500 per month; hard floor SGD 1,500. | — | user_stated · intake:q4_2 | `confirmed` | 已签 / signed 2026-09-05T11:01:00+08:00 | 否 / no | restricted | 是 / yes |
```

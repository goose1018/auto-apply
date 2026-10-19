# Intake 问诊问卷（中文版）/ questionnaire.zh.md

> `AA` = `python3 <skill_dir>/scripts/autoapply/cli.py [--data-dir DIR] --profile <profile_id>`（定义见 `SKILL.md` §开场）。

> 适用范围：Intake Agent（`agents/01-intake.md`）在 `intake` 状态下向用户提问时的唯一题库。状态：`[未验证]`（Phase 2 前未用真实简历跑过）。日期：2026-09-05。
> 上位文件：`BRIEF.md` §7（8 轮骨架）、§3（硬边界）、D1/D3/D6/D8/D9/D13、R3/R8；`ARCHITECTURE.md` §2.2（`intake` 状态检查点）、§8（一致性门）；`schemas/profile.schema.json`、`schemas/facts_card.schema.json`。冲突以 BRIEF 为准。
> 英文版 `questionnaire.en.md` 与本文内容对等；问诊语言由 `meta.language` 决定，另一种语言版本只作对照，不双语重复提问。

---

## 0. 提问纪律（Agent 开口前必读）

1. **每轮内一次只问一个决定性问题。** "决定性"= 答案会改变筛岗、填表或关口行为的问题（如硬下限、提交模式、声明题）。纯信息型字段（如作品集链接）可以并入一张确认表，让用户一次看完、一次确认。
2. **能从简历解析出来的先展示解析结果，让用户改，不重复问。** 展示格式见 `resume_parse_guide.md` §4；解析置信度低的字段单独点名确认。
3. **用户说"跳过 / 不知道 / 以后再说"→ 该字段置 `null`**（数组置 `[]`），并在 `intake_state.json` 记录该问题 id；投递时遇到需要该字段的表单按 `gates.md` §11（`unknown_required_field`）处理，绝不猜。
4. **不得诱导、不得替用户猜。** 声明题（本文第 7 节）只给枚举，不给"推荐答案"；有"默认值"的只限策略类字段（节流、模式、频率），默认值来源写在表里。
5. **问诊语言跟随用户**：用户第一句是中文就用本文件，英文就用 `questionnaire.en.md`；中途切换语言则切换文件，进度不变。
6. **每题先说一句"为什么问"**（对应哪张表单或哪条规则），再问；用户可以追问，Agent 引用本文件回答，不自行发挥。
7. **字段路径以 `schemas/profile.schema.json` 为准。** 2026-09-05 起，第 10 节列出的字段（`intent.can_start_immediately/full_time/days_per_week/notice_period/work_mode`、`salary.current`、`rules.company_caps/notes`、`materials.job_list_paths`、`policy.source_channel_default/platform_option_overrides`、`skills.years_by_skill/proficiency`）已进 schema，Intake 直接写入这些正式路径，**不再**暂存到 `policy.declarations.other[]` 或 `notes`。此后若再遇到 schema 里确实没有的字段，仍先按"暂存位置"落到 `policy.declarations.other[]`（`question` 用第 10 节的固定前缀）或对应节的 `notes`，并在任务汇报中提出，不自行加 schema 字段。
8. 用户任何时候贴出密码 / 证件号 / 银行信息 → 按 `SECURITY.md` §3 固定文案回应，不使用、不复述、提醒更换；问诊继续。
9. **进度落盘**：每题答完写 `intake_state.json.last_question_id`（题号见各表）；每轮结束写 `round_done`；会话断了从该题继续，不从头来。
10. **写档案的时机**：每轮全部确认后才通过脚本写 `profile.json`（`validate profile` 不通过不写）；facts_card 在第 6 轮末整卡签字。
11. **不收集的东西**（任何轮次、任何平台）：密码、NRIC / FIN / 护照号 / 任何证件号、银行 / 支付信息、OTP。用户主动给也不收（SECURITY §2）。
12. 文案平实，不用感叹号，不预设用户国籍或学校（D1）。

**每题的表格字段说明**：`问题文案`（照读或按意思说）/ `字段路径`（profile.json 内的 JSON 路径）/ `允许答案`（枚举或格式）/ `默认值`（用户不答时写入的值；"无"= 必答）/ `可否跳过` / `为什么问`（对应表单或规则，引用 playbook 节号）。

---

## 1. 轮 0 材料（`materials.*`、`meta.*`）

**目标**：拿到至少一份简历、确定档案 id 与语言。本轮不解析简历内容。

### q0_1 档案 id

| 项 | 内容 |
|---|---|
| 问题文案 | 给这份档案起一个短 id（小写字母、数字、`_`、`-`，2–32 位），它也是你电脑上数据目录的名字，例如 `alex_tan`。 |
| 字段路径 | `meta.profile_id` |
| 允许答案 | 匹配 `^[a-z0-9][a-z0-9_-]{1,31}$` |
| 默认值 | 无（必答；Agent 可根据简历文件名建议一个，用户确认） |
| 可否跳过 | 否 |
| 为什么问 | 数据目录 `~/auto-apply-data/<profile_id>/`（ARCHITECTURE §5.2）；多档案并存时的区分。 |

### q0_2 界面语言

| 项 | 内容 |
|---|---|
| 问题文案 | 之后的提问和汇报用中文还是英文？ |
| 字段路径 | `meta.language` |
| 允许答案 | `zh` / `en` |
| 默认值 | 按用户第一句话的语言检测，向用户确认一次 |
| 可否跳过 | 否 |
| 为什么问 | D1 用户可见文案跟随用户语言；决定本文件与 `questionnaire.en.md` 哪个生效。 |

### q0_3 简历文件

| 项 | 内容 |
|---|---|
| 问题文案 | 把简历文件的完整路径给我（PDF 或 DOCX）。有中文、英文或不同用途的版本就都给，每份说明用途。 |
| 字段路径 | `materials.resumes[]`：`path`、`language`、`label`、`version`、`is_default`、`notes`；`sha256` 由 Agent 计算后写入 |
| 允许答案 | `path` = 本机绝对路径；`language` ∈ `en` / `zh` / `other`；`label` = 用途标签（如 `english_default`、`chinese_pm`）；`is_default` 只能有一份为 `true` |
| 默认值 | 无（至少 1 份）；只有一份时 `is_default=true` |
| 可否跳过 | 否 |
| 为什么问 | 所有平台都要简历（各 playbook §8）；D6 不生成、不翻译，岗位要某语言版本而档案没有 → `resume_missing_language` 关口；`sha256` 供 R3 与平台已存简历核对（jobstreet.md §8 事故 I-03）。 |

### q0_4 简历版本用途（多份时才问）

| 项 | 内容 |
|---|---|
| 问题文案 | 这几份简历分别在什么情况下用？哪一份是默认？ |
| 字段路径 | `materials.resumes[].label` / `.version` / `.is_default` / `.notes` |
| 允许答案 | 自由文本标签；`is_default` 恰好一份 `true` |
| 默认值 | 无 |
| 可否跳过 | 否（多份时必答，否则 Executor 无法选择） |
| 为什么问 | R10 复核项"简历版本"；平台已存简历可能是旧版（jobstreet.md §8）。 |

### q0_5 公开链接

| 项 | 内容 |
|---|---|
| 问题文案 | 有 LinkedIn、GitHub、作品集、个人网站吗？有就给链接，没有说"没有"。 |
| 字段路径 | `materials.linkedin_url` / `materials.github_url` / `materials.portfolio_url` / `materials.website_url` |
| 允许答案 | URL 或 `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Greenhouse 部分租户 LinkedIn 必填（greenhouse.md §5，无则挂起）；Workday "Websites"（workday.md §5）；Ashby / Lever 有 LinkedIn / GitHub / Portfolio 栏。 |

### q0_6 成绩单

| 项 | 内容 |
|---|---|
| 问题文案 | 有成绩单文件吗（部分公司必传）？有就给路径。 |
| 字段路径 | `materials.transcript_path` |
| 允许答案 | 本机绝对路径或 `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday 部分租户成绩单必传（workday.md §5，PwC）；无则该岗位 `unknown_required_field`。 |

### q0_7 证书与求职信模板

| 项 | 内容 |
|---|---|
| 问题文案 | 有证书文件或你自己写的求职信模板吗？有就给名称和路径。 |
| 字段路径 | `materials.certificates[]`（`name`、`path`）；`materials.cover_letter_template_path` |
| 允许答案 | 数组 / 路径 / `null` |
| 默认值 | `[]` / `null` |
| 可否跳过 | 是 |
| 为什么问 | Content Agent 生成 CL 时可参考用户模板（D9）；证书文件偶有上传栏。 |

### q0_8 运行时（不问，自动记录）

| 项 | 内容 |
|---|---|
| 问题文案 | （不提问）Agent 按当前运行时写入。 |
| 字段路径 | `meta.runtime`；`meta.created_at`、`meta.version="1"` 同时写入 |
| 允许答案 | `claude_code` / `codex` |
| 默认值 | 当前运行时 |
| 可否跳过 | — |
| 为什么问 | D2/D3 凭据策略按运行时切换。 |

---

## 2. 轮 1 简历解析确认（`identity.*`、`education[]`、`experience[]`、`skills.*`，含 R3 一致性门）

**目标**：Agent 先按 `resume_parse_guide.md` 解析每份简历，把结果分块展示；用户逐块改；最后跑一致性门。本轮所有条目 `source=resume`，确认后 `confirmed_by_user=true`。

### q1_1 姓名

| 项 | 内容 |
|---|---|
| 问题文案 | 简历上的姓名我读到的是：完整名 `<full>`，名 `<given>`，姓 `<family>`，顺序是 `<given_first/family_first>`。申请表要用的完整姓名就是这个吗？有母语写法或习惯称呼也告诉我。 |
| 字段路径 | `identity.name.full` / `.given` / `.family` / `.native` / `.name_order` / `.preferred` |
| 允许答案 | `full` 必填（拉丁字母，与简历一致）；`name_order` ∈ `given_first` / `family_first` / `null` |
| 默认值 | 解析值；`native`、`preferred` 默认 `null` |
| 可否跳过 | `full` 否；其余是 |
| 为什么问 | Workday / Greenhouse / SmartRecruiters 分 First / Last 填（各 playbook §5）；R10 复核"姓名顺序"；事故 I-03 姓名顺序被 ATS 解析错。 |

### q1_2 邮箱

| 项 | 内容 |
|---|---|
| 问题文案 | 简历上的邮箱是 `<脱敏>`。申请表默认填哪个邮箱？新注册 ATS 账号想用另一个专用邮箱吗？还有绑定过旧账号的其它邮箱吗？ |
| 字段路径 | `identity.emails.primary` / `.signup` / `.others[]` |
| 允许答案 | 合法邮箱格式；`signup` 可 `null`（= 用 `primary`） |
| 默认值 | `primary` = 简历邮箱（用户确认）；`signup=null`；`others=[]` |
| 可否跳过 | `primary` 否；其余是 |
| 为什么问 | 所有表单；Greenhouse 验证码发到此邮箱（greenhouse.md §2）；Workday 一个邮箱一个租户只能一个账号（workday.md §3）；R3 比对简历邮箱 ∈ 档案邮箱集合（ARCHITECTURE §8.2）；`others` 让旧邮箱不再触发报警。 |

### q1_3 手机

| 项 | 内容 |
|---|---|
| 问题文案 | 简历上的手机是 `<脱敏>`，区号 `<code>`。申请表默认填这个号吗？有第二个号（如原籍国号码）也一并给，标明用途。 |
| 字段路径 | `identity.phones[]`：`country_code`、`number`、`label`、`is_default` |
| 允许答案 | `country_code` 形如 `+65`；`number` 只含数字与空格；`label` ∈ `sg` / `home` / `other` / `null`；第一项为默认 |
| 默认值 | 解析值（区号简历没写就问，不假设 `+65`） |
| 可否跳过 | 是（但多数表单必填，跳过会频繁触发 `unknown_required_field`） |
| 为什么问 | Workday 区号下拉曾自动切错（workday.md §5）；SmartRecruiters 解析带入旧区号（smartrecruiters.md §5）；R10 复核"区号"；R3 比对手机。 |

### q1_4 教育经历（逐段确认）

| 项 | 内容 |
|---|---|
| 问题文案 | 第 `<n>` 段教育我读到的是：`<institution>` / `<faculty>` / `<major>` / `<degree_title>`（层级 `<degree>`）/ `<start>`–`<end_expected>` / 在读 `<is_current>` / 地点 `<location>` / GPA `<有则显示，无则"简历未写">`。对吗？预计毕业年月一定要准确到月。 |
| 字段路径 | `education[]`：`institution`、`faculty`、`major`、`degree`、`degree_title`、`start`、`end_expected`、`is_current`、`gpa{value,scale}`、`rank_or_honours`、`location`、`confirmed_by_user` |
| 允许答案 | `degree` ∈ `diploma` / `bachelor` / `master` / `phd` / `other`；年月 `YYYY-MM`；`gpa` 只在简历写了或用户明说时填，否则 `null` |
| 默认值 | 解析值；GPA 不推断 |
| 可否跳过 | `institution`、`degree` 否；其余是 |
| 为什么问 | 所有 ATS 教育栏（各 playbook §5）；毕业年月是 R3 `block` 级比对项与 R10 复核项，事故 I-03 毕业年被 ATS 填早一年；`is_current` + `degree` 决定"本科已毕业 / 硕士在读"类题（linkedin.md §5）与学历门槛过滤；`location` 决定"学校是否在新加坡"（linkedin.md §5）。 |

### q1_5 中学 / 高中信息（可选）

| 项 | 内容 |
|---|---|
| 问题文案 | 少数表单（银行、交易公司）必填中学或高中信息。要不要现在加一段？不加也可以，遇到时会跳过并记账。 |
| 字段路径 | `education[]` 新增一段：`degree="other"`，`degree_title` 写考试/学历类型，`rank_or_honours` 写成绩 |
| 允许答案 | 同 q1_4 |
| 默认值 | 不加 |
| 可否跳过 | 是 |
| 为什么问 | 事故 I-16（UBS 卡在高中学历细节）；greenhouse.md §6（Optiver 要求中学考试类型与分数）。 |

### q1_6 经历（逐条确认）

| 项 | 内容 |
|---|---|
| 问题文案 | 第 `<n>` 条经历我读到的是：`<kind>` / `<organisation>` / `<title>` / `<start>`–`<end>` / `<location>`，要点 `<bullets>`。类型对吗（实习 / 工作 / 项目 / 竞赛 / 论文 / 志愿）？要点里的数字和时间都是简历原文吗？ |
| 字段路径 | `experience[]`：`kind`、`organisation`、`title`、`start`、`end`、`is_current`、`location`、`bullets[]`、`source="resume"`、`confirmed_by_user` |
| 允许答案 | `kind` ∈ `internship` / `job` / `project` / `competition` / `publication` / `volunteer` / `other`；`bullets[]` 每条 ≤ 600 字符，只能是简历原文或用户口述（`source="user_stated"`） |
| 默认值 | 解析值 |
| 可否跳过 | 单条可删除；不可跳过整节（至少确认 0 条也要明说） |
| 为什么问 | Workday / SuccessFactors / SmartRecruiters 结构化经历栏（各 playbook §5）；SmartRecruiters 会把项目误当雇佣经历（smartrecruiters.md §5），`kind` 必须准确；`bullets` 是 facts_card `experience` 类事实的来源。 |

### q1_7 技能与语言

| 项 | 内容 |
|---|---|
| 问题文案 | 简历上的语言能力、工具 / 技术、证书我读到的是 `<列表>`。语言水平请按母语 / 流利 / 专业工作 / 会话 / 基础标。要补充或删除吗？ |
| 字段路径 | `skills.languages_spoken[]`（`name`、`level`）、`skills.tools[]`、`skills.certifications[]`（`name`、`issuer`、`date`）、`skills.other[]` |
| 允许答案 | `level` ∈ `native` / `fluent` / `professional` / `conversational` / `basic` / `null` |
| 默认值 | 解析值；`level` 简历未写则 `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday Languages / Skills 下拉（workday.md §5）；Lever / LinkedIn Languages（lever.md §5、linkedin.md §5）。 |

### q1_8 技能年限与自评预设（可选）

| 项 | 内容 |
|---|---|
| 问题文案 | LinkedIn 等表单常问"你用 `<技能>` 几年"（只能填整数）或让你自评熟练度。要不要现在对简历上出现的技能预设？不预设的遇到就挂起问你。 |
| 字段路径 | `skills.years_by_skill{<技能>: 年限}` / `skills.proficiency{<技能>: 档位}` |
| 允许答案 | 年限为非负整数；自评用 `basic` / `intermediate` / `advanced` 或 `null`（schema 无 `none`，不预设则整键省略或值填 `null`） |
| 默认值 | 不预设（`null` → 挂起） |
| 可否跳过 | 是 |
| 为什么问 | linkedin.md §5 年限题只能填整数；greenhouse.md §5 / smartrecruiters.md §5 技能自评题，简历未声明的技能不得自评。 |

### q1_9 一致性门（R3，脚本执行，不是提问）

| 项 | 内容 |
|---|---|
| 动作 | q1_1–q1_4 确认后写 `resume_parse.json`，运行 `AA profile consistency --profile <id>`，读 `consistency_report.json`。 |
| 结果 `pass` / `info` | 不打断，继续第 2 轮。 |
| 结果 `warn` | 展示脱敏差异，问一句"知道了，继续吗？"；用户可改档案。 |
| 结果 `block` | 触发 `consistency_mismatch` 关口（`gates.md` §16），文案见 `resume_parse_guide.md` §6；用户三选一：① 以档案为准 → 写 `materials.resumes[].known_mismatches[]`；② 换简历 → 回 q0_3 重解析；③ 改档案 → 改后重跑。 |
| 字段路径 | `materials.resumes[].known_mismatches[]` |
| 为什么做 | 事故 I-03；P2 DoD "一致性门能抓出联系方式不一致"。 |

---

## 3. 轮 2 身份与工作许可（`status.*`、`identity.address`、`identity.date_of_birth`、`identity.gender`）

**目标**：把 ATS 反复问的工作授权题一次问清，拆成独立的三问。**本轮不收集任何证件号**；用户主动提供也不记录。

### q2_1 国籍

| 项 | 内容 |
|---|---|
| 问题文案 | 你的国籍是？（只记国家名，不记证件号。） |
| 字段路径 | `status.nationality` |
| 允许答案 | 国家名或 ISO 3166 代码；`null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Lever / LinkedIn 部分表单问 Nationality（lever.md §5、linkedin.md §5）；Workday Self Identify 步骤问国籍（workday.md §4 第 5 步）。 |

### q2_2 现居国家 / 城市与地址

| 项 | 内容 |
|---|---|
| 问题文案 | 现居国家和城市？部分表单必填街道地址和邮编，要现在给吗（只存本机，不写日志）？ |
| 字段路径 | `status.country_of_residence`；`identity.address.country` / `.city` / `.line1` / `.postal_code` |
| 允许答案 | 自由文本；`postal_code` ≤ 20 字符；`null` |
| 默认值 | `null` |
| 可否跳过 | 是（缺邮编时 Workday 部分租户会挂起） |
| 为什么问 | Workday 第 1 步地址与邮编必填（workday.md §4/§5）；Greenhouse Location、Lever Current location 自动完成控件（lever.md §5，事故 I-09）、SmartRecruiters City / Country。 |

### q2_3 当前在新加坡的身份

| 项 | 内容 |
|---|---|
| 问题文案 | 你现在在新加坡持什么身份？（不需要证件号。） |
| 字段路径 | `status.work_pass`；`other` 时补 `status.work_pass_other_label`；有效期 `status.work_pass_expiry` |
| 允许答案 | `citizen` / `permanent_resident` / `student_pass` / `employment_pass` / `s_pass` / `work_permit` / `dependant_pass` / `ltvp` / `training_employment_pass` / `work_holiday_pass` / `other` / `none` / `unknown` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Jobstreet 工作许可下拉（jobstreet.md §9）、SmartRecruiters "Current pass"（smartrecruiters.md §5）、Lever Visa status（lever.md §5）；D1 枚举覆盖所有国籍情形。 |

### q2_4 工作授权（第一问）

| 项 | 内容 |
|---|---|
| 问题文案 | 按你现在的身份，你是否可以合法在新加坡做你要投的这类工作（实习 / 全职）？ |
| 字段路径 | `status.authorised_to_work_in_sg` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null`（不从 `work_pass` 推断） |
| 可否跳过 | 是 |
| 为什么问 | "Are you legally authorized to work in Singapore" 出现在 Workday / Ashby / Workable / LinkedIn（各 playbook §5）。三问拆开是因为 Workday 把"现在或未来需要赞助"合成一题，Executor 需要分别知道。 |

### q2_5 工作授权（第二问）

| 项 | 内容 |
|---|---|
| 问题文案 | 就这份实习 / 工作本身，你**现在**是否需要雇主为你申请工作准证？ |
| 字段路径 | `status.requires_sponsorship_now` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Greenhouse DRW "实习期间 work pass"（greenhouse.md §5）、Lever "sponsorship during internship"（lever.md §5）、LinkedIn "need additional work pass"（linkedin.md §5）。 |

### q2_6 工作授权（第三问）

| 项 | 内容 |
|---|---|
| 问题文案 | 毕业后或将来，你是否需要雇主赞助工作准证？ |
| 字段路径 | `status.requires_sponsorship_future` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday "now or in the future require sponsorship"（未来需要即答 Yes，workday.md §5）；SmartRecruiters "after graduation"（smartrecruiters.md §5）。 |

### q2_7 实习性质

| 项 | 内容 |
|---|---|
| 问题文案 | 你要投的实习是哪种性质：学分实习、学校批准的非学分实习、假期实习、休学实习，还是不适用（投全职）？ |
| 字段路径 | `status.internship_nature` |
| 允许答案 | `credit_bearing` / `school_approved_non_credit` / `vacation` / `leave_of_absence` / `not_applicable` / `unknown` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | LinkedIn "school-recognised internship"（linkedin.md §5）、Ashby / Lever "credit-bearing"（ashby.md §5、lever.md §5）、Workable "Internship type"（workable.md §5）、SuccessFactors 学分实习题（successfactors.md §5）。 |

### q2_8 实习期是否免工作准证

| 项 | 内容 |
|---|---|
| 问题文案 | 据你了解，你的实习期间是否不需要另外的工作准证（例如学生准证下的学校批准实习）？不确定就说不确定，我不替你判断。 |
| 字段路径 | `status.work_pass_exempt_for_internship` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | 与 q2_5 配合回答"实习期间需要准证吗"类题；Agent 不解释移民规则，只记录用户的答案。 |

### q2_9 学校能否出实习信

| 项 | 内容 |
|---|---|
| 问题文案 | 学校能出实习信 / 批准函吗？ |
| 字段路径 | `status.school_can_issue_letter` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | 部分雇主筛选题要求；Content Agent 不引用，只供 Executor 答题。 |

### q2_10 出生日期（可选、敏感）

| 项 | 内容 |
|---|---|
| 问题文案 | 少数表单必填出生日期。要现在存吗？只存本机、只在表单必填时使用、不写日志。不存也可以，遇到时会挂起问你。 |
| 字段路径 | `identity.date_of_birth` |
| 允许答案 | `YYYY-MM-DD` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | LinkedIn Easy Apply 出现过 Date of birth（linkedin.md §5）；Workday 第 5 步年龄题（workday.md §4）；SECURITY §2 列为谨慎字段。 |

### q2_11 性别（可选）

| 项 | 内容 |
|---|---|
| 问题文案 | 表单里的性别栏你希望怎么填？这与 EEO 类问题的默认答法（第 6 轮）分开设置。 |
| 字段路径 | `identity.gender` |
| 允许答案 | `female` / `male` / `non_binary` / `prefer_not_to_say` / `other` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | 部分表单性别为普通必填栏而非 EEO 自愿栏；`policy.eeo_default` 只管 EEO 栏。 |

### q2_12 身份备注

| 项 | 内容 |
|---|---|
| 问题文案 | 关于身份或工作许可还有什么我该知道的（如准证申请中、身份即将变化）？ |
| 字段路径 | `status.notes` |
| 允许答案 | ≤ 1000 字符 / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | 供 Screening 与 Executor 阅读；不进 facts_card 除非用户在第 6 轮明确签字。 |

---

## 4. 轮 3 求职意向（`intent.*`）

### q3_1 岗位类型

| 项 | 内容 |
|---|---|
| 问题文案 | 投哪些类型：实习、全职、兼职、毕业生计划、合同工？可多选。 |
| 字段路径 | `intent.types[]` |
| 允许答案 | `internship` / `full_time` / `part_time` / `graduate_programme` / `contract`，至少 1 项 |
| 默认值 | 无 |
| 可否跳过 | 否 |
| 为什么问 | Sourcing 搜索过滤与 Screening 硬条件。 |

### q3_2 方向关键词

| 项 | 内容 |
|---|---|
| 问题文案 | 用 3–5 个关键词描述你要投的方向（如 data analyst、backend、product）。 |
| 字段路径 | `intent.keywords[]` |
| 允许答案 | 字符串数组 |
| 默认值 | `[]` |
| 可否跳过 | 是（跳过则 Sourcing 只消费用户清单，不自主搜索） |
| 为什么问 | R2 站内搜索词；Screening 匹配打分。 |

### q3_3 排除方向

| 项 | 内容 |
|---|---|
| 问题文案 | 哪些方向明确不投（如纯销售、客服、纯硬件）？ |
| 字段路径 | `intent.excluded_directions[]` |
| 允许答案 | 字符串数组 |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | Screening 排除；与第 5 轮岗位名排除（`rules.title_exclusions`）互补：这里是方向，那里是岗位名子串。 |

### q3_4 地点

| 项 | 内容 |
|---|---|
| 问题文案 | 工作地点接受哪些？默认只投新加坡。 |
| 字段路径 | `intent.locations[]` |
| 允许答案 | 字符串数组，至少 1 项 |
| 默认值 | `["Singapore"]`（用户确认） |
| 可否跳过 | 否 |
| 为什么问 | LinkedIn / Lever 地点硬规则：`Hong Kong / Taipei / Asia / APAC / Remote / Hybrid` 不等于新加坡（linkedin.md §9、lever.md §9）；Greenhouse 隐藏 `job_location` 字段核对（greenhouse.md §6）。 |

### q3_5 远程与外派

| 项 | 内容 |
|---|---|
| 问题文案 | 接受远程岗吗？接受外派到其他国家吗？ |
| 字段路径 | `intent.remote_ok` / `intent.relocation_ok` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | LinkedIn "On-site at <地点>?"（linkedin.md §5）；Remote 岗必须明确允许在新加坡工作（lever.md §9）。 |

### q3_6 实习 / 到岗窗口

| 项 | 内容 |
|---|---|
| 问题文案 | 你能工作的时间窗口是哪个月到哪个月？两端可以浮动几周？ |
| 字段路径 | `intent.window.start` / `.end` / `.flexibility_weeks` |
| 允许答案 | `YYYY-MM`；`flexibility_weeks` 0–52 整数 |
| 默认值 | `null` |
| 可否跳过 | 是（跳过则日期窗过滤不生效，风险自负） |
| 为什么问 | 硬边界"日期窗不符必跳过并记账"；事故 I-10（Grab 表单只给 2026 窗口）；Workday internship period、SmartRecruiters start / end、Ashby / Lever dates（各 playbook §5）。 |

### q3_7 最早到岗日期

| 项 | 内容 |
|---|---|
| 问题文案 | 最早哪一天可以到岗？至少精确到月；只知道月就填该月 1 日并说明。 |
| 字段路径 | `intent.earliest_start` |
| 允许答案 | `YYYY-MM-DD` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday "Available start date" 精确到月（workday.md §4 第 3 步）；Greenhouse "Earliest start date"、Ashby "Earliest available date"（各 playbook §5）。"能否立即到岗"类题默认仍由 Executor 按 `earliest_start` 与投递日比较如实回答；`false` 且题目必须 Yes → 跳过整岗（linkedin.md §11、smartrecruiters.md §5）。若用户想直接预设，写 `intent.can_start_immediately`（该字段已进 schema），Executor 优先读它，未设置时才按日期换算。 |

### q3_8 每周时数

| 项 | 内容 |
|---|---|
| 问题文案 | 每周能工作多少小时？全职按 40 左右；学期中与假期不同就分别说。 |
| 字段路径 | `intent.hours_per_week`；差异写 `intent.term_time_vs_vacation_notes` |
| 允许答案 | 1–80 整数 / `null`；备注自由文本 |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Lever "Hours per week"（lever.md §5）；"Full-time?" 类题默认仍由 Executor 按时数如实答；SmartRecruiters "Days per week"（smartrecruiters.md §5）同理按 `hours_per_week` 换算。若用户想直接预设，写 `intent.full_time` / `intent.days_per_week`（均已进 schema），Executor 优先读它们，未设置时才换算。 |

### q3_9 最短承诺时长

| 项 | 内容 |
|---|---|
| 问题文案 | 你能承诺的最短实习 / 工作时长是几个月？ |
| 字段路径 | `intent.min_commitment_months` |
| 允许答案 | ≥ 0 的数 / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | LinkedIn "Can you commit N months full-time?"（linkedin.md §5）；Ashby / Lever duration（ashby.md §5、lever.md §5）。 |

### q3_10 学历口径

| 项 | 内容 |
|---|---|
| 问题文案 | 投哪个学历口径的岗位：本科、硕士、博士、文凭，还是不限？ |
| 字段路径 | `intent.degree_level_targets[]` |
| 允许答案 | `diploma` / `bachelor` / `master` / `phd` / `any` |
| 默认值 | `[]`（= 不过滤，Screening 记警告） |
| 可否跳过 | 是 |
| 为什么问 | 硬边界"学历门槛不符必跳过"；Screening 过滤。 |

### q3_11 只招本科的岗位

| 项 | 内容 |
|---|---|
| 问题文案 | 岗位写明只招本科在读时，投不投？注意：硕士在读不能冒充本科在读，遇到"currently pursuing Bachelor's"必答题会跳过。 |
| 字段路径 | `intent.apply_to_bachelor_only_postings` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | successfactors.md §5（硕士在读不得冒充本科在读 → 跳过）。 |

---

## 5. 轮 4 薪资与条件（`salary.*`）

### q4_1 币种与周期

| 项 | 内容 |
|---|---|
| 问题文案 | 薪资按什么币种和周期谈？默认新币 / 月。 |
| 字段路径 | `salary.currency` / `salary.period` |
| 允许答案 | ISO 4217 三字母（如 `SGD`）；`month` / `day` / `hour` / `year` |
| 默认值 | `SGD` / `month`（用户确认） |
| 可否跳过 | 是 |
| 为什么问 | 后续数字的单位；Screening 换算比较。 |

### q4_2 期望区间

| 项 | 内容 |
|---|---|
| 问题文案 | 期望薪资区间是多少？表单问"期望薪资"时填区间下限。 |
| 字段路径 | `salary.expected_min` / `salary.expected_max` |
| 允许答案 | ≥ 0 的数 / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday / Jobstreet / Ashby "Expected salary"（各 playbook §5）；R10 复核"薪资"。 |

### q4_3 硬下限

| 项 | 内容 |
|---|---|
| 问题文案 | 低于多少明确不投？这是硬规则，岗位公开薪资低于它会直接跳过并记账。 |
| 字段路径 | `salary.hard_floor` |
| 允许答案 | ≥ 0 的数 / `null` |
| 默认值 | `null`（= 不按薪资过滤） |
| 可否跳过 | 是 |
| 为什么问 | 硬边界"薪资低于下限必跳过并记账"；jobstreet.md §11。 |

### q4_4 未披露薪资

| 项 | 内容 |
|---|---|
| 问题文案 | 岗位没写薪资，投不投？ |
| 字段路径 | `salary.apply_if_undisclosed` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Screening 硬条件。 |

### q4_5 无薪实习

| 项 | 内容 |
|---|---|
| 问题文案 | 无薪实习投不投？ |
| 字段路径 | `salary.allow_unpaid` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Screening 硬条件。 |

### q4_6 可否协商

| 项 | 内容 |
|---|---|
| 问题文案 | 表单有"可协商"选项时勾不勾？ |
| 字段路径 | `salary.negotiable` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Ashby 薪资区间可协商（ashby.md §5）。 |

### q4_7 现薪资与备注

| 项 | 内容 |
|---|---|
| 问题文案 | 表单问"现薪资"时怎么答（在读一般填 0 并注明学生）？其它薪资相关说明也写这里。 |
| 字段路径 | `salary.current`（数值，在读学生填 `0` 或 `null`）；其它薪资相关说明写 `salary.notes` |
| 允许答案 | `salary.current`：非负数 / `null`；`salary.notes`：自由文本 / `null` |
| 默认值 | `null`（→ 遇到必填时挂起） |
| 可否跳过 | 是 |
| 为什么问 | Workday 第 3 步 "Current salary"（workday.md §5）。 |

---

## 6. 轮 5 排除与策略（`rules.*`，R8 / D13）

**目标**：用户特别强调的一轮。每一条都直接变成 Screening 的过滤规则或 Executor 的节流参数。列表类问题允许用户一次给多条。

### q5_1 公司黑名单

| 项 | 内容 |
|---|---|
| 问题文案 | 哪些公司绝对不投？包括你已经投够、不想再投的公司。每家可以写原因和失效日期。 |
| 字段路径 | `rules.company_blacklist[]`：`name`、`reason`、`until` |
| 允许答案 | `name` 必填；`until` = `YYYY-MM-DD` 或 `null` |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | 硬边界"公司黑名单必跳过并记账"；R8。 |

### q5_2 行业排除

| 项 | 内容 |
|---|---|
| 问题文案 | 哪些行业不投（如博彩、烟草、军工、加密货币、其它）？ |
| 字段路径 | `rules.industry_exclusions[]` |
| 允许答案 | 字符串数组 |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | Screening 过滤；R8。 |

### q5_3 岗位名排除

| 项 | 内容 |
|---|---|
| 问题文案 | 岗位名里出现哪些词就不投（如 sales、telemarketing、driver）？ |
| 字段路径 | `rules.title_exclusions[]` |
| 允许答案 | 子串数组（不区分大小写） |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | Screening 岗位名过滤；与 q3_3 方向排除互补。 |

### q5_4 保留内推名单

| 项 | 内容 |
|---|---|
| 问题文案 | 哪些公司你打算走内推、不要自动投（自动投了可能挤掉内推名额）？每家可写原因和到期日。 |
| 字段路径 | `rules.reserve_for_referral[]`：`name`、`reason`、`until` |
| 允许答案 | 同 q5_1 |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | R8；硬边界"保留内推名单必跳过并记账"；Plan §1 用户原话（全球限额岗位与内推名额的关系）。 |

### q5_5 全球限额岗位规则

| 项 | 内容 |
|---|---|
| 问题文案 | 有些公司全球只给每人一个申请名额或一份考虑机会。遇到这类岗位怎么处理：忽略、只对保留内推名单里的公司跳过、还是全部跳过？ |
| 字段路径 | `rules.global_quota_rule.mode` / `.notes` |
| 允许答案 | `ignore` / `skip_if_in_reserve_list` / `skip_all_global_quota` |
| 默认值 | `null`（→ Screening 遇到限额岗位时并入母清单标风险，由用户批准时决定） |
| 可否跳过 | 是 |
| 为什么问 | R8；greenhouse.md §9（一份申请全局考虑）、§12（只能选一个岗位）；workday.md §12（每人只能投一份）。 |

### q5_6 同公司上限

| 项 | 内容 |
|---|---|
| 问题文案 | 同一家公司最多投几份？默认 3。 |
| 字段路径 | `rules.per_company_max`；公司级更严的上限（如某公司每人 1 份）用 `rules.company_caps[{company, max_applications}]` 覆盖，来自 playbook §12，不在本题问 |
| 允许答案 | 1–3 整数（schema `maximum` 已收紧为 3，对齐 SECURITY §7.2 硬上限） |
| 默认值 | `3`（D13） |
| 可否跳过 | 是（取默认） |
| 为什么问 | D13；事故 I-01 同公司重复。 |

### q5_7 每轮份数

| 项 | 内容 |
|---|---|
| 问题文案 | 每轮目标投几份？默认 10，上限 20。 |
| 字段路径 | `rules.per_round` |
| 允许答案 | 1–20 整数 |
| 默认值 | `10`（D13） |
| 可否跳过 | 是 |
| 为什么问 | D13；SECURITY §7.2 节流表。 |

### q5_8 每日份数

| 项 | 内容 |
|---|---|
| 问题文案 | 每天最多投几份（跨平台合计）？默认 20，这也是硬上限，只能调低。 |
| 字段路径 | `rules.per_day` |
| 允许答案 | 1–20 整数 |
| 默认值 | `20`（D13） |
| 可否跳过 | 是 |
| 为什么问 | D13；`quota_exhausted` 关口（gates.md §18）；ToS 风险（SECURITY §7）。 |

### q5_9 渠道优先级

| 项 | 内容 |
|---|---|
| 问题文案 | 同一岗位在多个渠道都能投时，优先走哪个？请排序。默认：公司官网 > LinkedIn > Jobstreet > MyCareersFuture > 邮件 > 其它。 |
| 字段路径 | `rules.channel_priority[]` |
| 允许答案 | `company_site` / `linkedin` / `jobstreet` / `mycareersfuture` / `email` / `other` 的有序子集 |
| 默认值 | `["company_site","linkedin","jobstreet","mycareersfuture","email","other"]`（用户确认） |
| 可否跳过 | 是 |
| 为什么问 | R1 同岗位只投一个渠道，渠道是属性不是键（事故 I-01）；R6 LinkedIn 配额满时按此顺序切换。 |

### q5_10 已有账号的平台

| 项 | 内容 |
|---|---|
| 问题文案 | 你已经有账号的求职平台 / ATS 有哪些？各用哪个邮箱登录？密码是否已存在 Chrome 密码管理器？（不要告诉我密码。） |
| 字段路径 | `rules.existing_accounts[]`：`platform`、`login_email`、`saved_in_browser`、`notes` |
| 允许答案 | `platform` ∈ `jobstreet` / `linkedin_easy_apply` / `linkedin_external` / `mycareersfuture` / `workday` / `successfactors` / `greenhouse` / `ashby` / `smartrecruiters` / `lever` / `workable` / `company_custom` / `email` / `other` / `unknown`；Workday / SuccessFactors 按公司租户各一条，`notes` 写公司名 |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | 避免重复注册（Workday 一邮箱一账号，workday.md §3）；`password_or_signup` 关口前判断走登录还是注册；onboarding 预注册清单（`onboarding_checklist.md` §5）。 |

### q5_11 已投过的岗位导入

| 项 | 内容 |
|---|---|
| 问题文案 | 之前投过的岗位有记录吗（旧台账 Markdown、表格、或一份公司+岗位清单）？给我路径，我导入后这些岗位会被查重拦下，不会重复投。 |
| 字段路径 | `rules.legacy_ledger_imported`（导入成功后置 `true`）；数据经 `AA ledger migrate-legacy <文件>` 进台账 |
| 允许答案 | 路径 / "没有" |
| 默认值 | `false` |
| 可否跳过 | 是 |
| 为什么问 | R1 去重；D17；P3 DoD "已投岗 100% 被查重拦下"。非四节格式的清单：Intake 先整理成四节格式 Markdown 再导入（格式见 ARCHITECTURE §5.6），整理结果给用户过目。 |

### q5_12 用户岗位清单 / 链接（母清单原料）

| 项 | 内容 |
|---|---|
| 问题文案 | 你有想投的岗位清单或链接吗？有的话给路径或直接贴链接。Sourcing 会先消费它们，再自主搜索。 |
| 字段路径 | `materials.job_list_paths[]`；每轮开始时也可直接给 Sourcing |
| 允许答案 | 路径 / URL 列表 / "没有" |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | R2 母清单优先（事故 I-02）。 |

### q5_13 岗位来源的其它约束

| 项 | 内容 |
|---|---|
| 问题文案 | 还有其它筛岗规则吗（如只投 JD 明确写新加坡的、不投中介发布的、不投要求立即到岗的）？ |
| 字段路径 | 能映射的写入对应字段（地点 → `intent.locations`；立即到岗 → `intent.earliest_start`）；其余不合适塞进具体字段的规则写 `rules.notes` |
| 允许答案 | 自由文本 |
| 默认值 | 无 |
| 可否跳过 | 是 |
| 为什么问 | 兜住用户强调而 schema 没有槽位的规则，避免丢失。 |

---

## 7. 轮 6 内容与声明（`policy.*`、facts_card）

**目标**：定开放题 / CL 策略；把 playbooks 里出现过的所有声明题一次预设为"本人预设答案"；生成并签字 facts_card。**未预设的声明题 = `null` = 投递时挂起问本人**（`personal_declaration` 关口，gates.md §7）。

### q6_1 求职信策略

| 项 | 内容 |
|---|---|
| 问题文案 | 求职信（cover letter）怎么处理：从不写、生成后你批准再填、还是自动填？只会引用你签字的事实卡。 |
| 字段路径 | `policy.cover_letter_policy` |
| 允许答案 | `never` / `approve` / `auto` |
| 默认值 | `approve`（D9） |
| 可否跳过 | 是（取默认） |
| 为什么问 | D9 / R9；`content_approval` 关口（gates.md §9）。 |

### q6_2 开放题策略

| 项 | 内容 |
|---|---|
| 问题文案 | 表单里的开放题（如 "Why us?"）怎么处理：跳过、生成后你批准再填、还是自动填？ |
| 字段路径 | `policy.open_question_policy` |
| 允许答案 | `skip` / `approve` / `auto` |
| 默认值 | `approve`（D9） |
| 可否跳过 | 是 |
| 为什么问 | 事故 I-12（Razer / PwC 必答开放题）；`skip` 遇必答题 → 跳过整岗并记账。 |

### q6_3 一句话自我介绍

| 项 | 内容 |
|---|---|
| 问题文案 | 允许依据事实卡生成一句话自我介绍（用于简短的 "About you" 栏）吗？ |
| 字段路径 | `policy.allow_ai_self_intro` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null`（= 不生成） |
| 可否跳过 | 是 |
| 为什么问 | SmartRecruiters "Hiring Team Message"（smartrecruiters.md §9）、Lever "Additional information"（lever.md §9）。 |

### q6_4 EEO 类默认答法

| 项 | 内容 |
|---|---|
| 问题文案 | 自愿披露类问题（性别 / 种族 / 残障 / 退伍）默认怎么答：一律 prefer not to say、按档案作答、还是每次问你？ |
| 字段路径 | `policy.eeo_default` |
| 允许答案 | `prefer_not_to_say` / `answer_from_profile` / `ask_me` |
| 默认值 | `prefer_not_to_say`（BRIEF §7） |
| 可否跳过 | 是 |
| 为什么问 | Workday 第 4 步 Voluntary Disclosures（workday.md §4）；`ask_me` → 每次触发 `personal_declaration`。 |

### q6_5 声明题：司法记录

| 项 | 内容 |
|---|---|
| 问题文案 | 表单问"是否有犯罪记录 / 待决指控"时，你的预设答案是什么？只记你的原话；不预设就每次问你。 |
| 字段路径 | `policy.declarations.criminal_record` |
| 允许答案 | ≤ 300 字符文本（通常 `No` / `Yes: <说明>`）/ `null` |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workable PRISM+ 司法记录题（workable.md §9）；Workday 第 5 步合规声明（workday.md §4）；硬边界"必须本人回答的声明题"。 |

### q6_6 声明题：破产

| 项 | 内容 |
|---|---|
| 问题文案 | "是否曾破产 / 有未清偿破产令"预设答案？ |
| 字段路径 | `policy.declarations.bankruptcy` |
| 允许答案 | 同 q6_5 |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | ARCHITECTURE §3.1 `personal_declaration` 列举项；金融类租户常见 `[未验证：具体平台]`。 |

### q6_7 声明题：疫苗

| 项 | 内容 |
|---|---|
| 问题文案 | "疫苗接种状态"预设答案？ |
| 字段路径 | `policy.declarations.vaccination_status` |
| 允许答案 | 同 q6_5 |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday Keppel Covid 疫苗题（workday.md §4 第 5 步、§9）。 |

### q6_8 声明题：亲属 / 关系人在该公司

| 项 | 内容 |
|---|---|
| 问题文案 | "是否有亲属、配偶或密切关系人在该公司任职（或与该公司有客户 / 业务关系）"预设答案？默认可以是"无，除非我在批准母清单时特别注明"。 |
| 字段路径 | `policy.declarations.relatives_in_company` |
| 允许答案 | 同 q6_5 |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday 第 3 步亲属 / 客户关系、第 5 步利益冲突（workday.md §4/§9）。 |

### q6_9 声明题：曾申请 / 曾任职于该公司

| 项 | 内容 |
|---|---|
| 问题文案 | "是否曾在该公司工作 / 曾申请过该公司"预设答案？如果有个别公司例外，把公司名写进答案。 |
| 字段路径 | `policy.declarations.previously_applied_or_employed` |
| 允许答案 | 同 q6_5（例：`No, except <公司>: worked 2025-06 to 2025-08`） |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | Workday 第 1 步 "Have you previously worked for X"、第 3 步"是否申请过本公司"（workday.md §4/§5）；台账里已投过的公司由 Executor 如实答"已申请"，不靠此项。 |

### q6_10 声明题：竞业限制

| 项 | 内容 |
|---|---|
| 问题文案 | "是否受竞业限制 / 保密协议约束"预设答案？ |
| 字段路径 | `policy.declarations.non_compete` |
| 允许答案 | 同 q6_5 |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | ARCHITECTURE §3.1 列举项；`[未验证：出现平台]`。 |

### q6_11 声明题：背景调查同意

| 项 | 内容 |
|---|---|
| 问题文案 | "同意雇主做背景调查"预设答案？ |
| 字段路径 | `policy.declarations.background_check_consent` |
| 允许答案 | 同 q6_5 |
| 默认值 | `null` |
| 可否跳过 | 是 |
| 为什么问 | ARCHITECTURE §3.1 列举项；SuccessFactors Singtel 成功前身份验证步骤（successfactors.md §9）`[未验证：是否为背景调查同意]`。 |

### q6_12 声明题：个人数据处理同意（PDPA / 隐私）

| 项 | 内容 |
|---|---|
| 问题文案 | 申请表末尾的"同意按隐私政策处理我的个人数据"勾选，预设为同意吗？不勾无法提交。 |
| 字段路径 | `policy.declarations.data_processing_consent` |
| 允许答案 | `Yes` / `null` |
| 默认值 | `null`（→ 每次挂起） |
| 可否跳过 | 是 |
| 为什么问 | Greenhouse 隐私 / PDPA 勾选（greenhouse.md §4/§5）；SECURITY §6。 |

### q6_13 其它声明题与固定选项题（逐条问，`declarations.other[]`）

每条一问，`question` 用第 10 节固定前缀，`answer` 为用户原话或 `null`。**只列 playbooks 出现过或 ARCHITECTURE 列举的题**；不在此表的题投递时挂起。

| 序 | 问题文案 | `question` 值 | 允许答案 | 默认值 | 为什么问 |
|---|---|---|---|---|---|
| a | "是否曾被解雇 / 被要求辞职"预设答案？ | `common:previously_dismissed` | 文本 / `null` | `null` | Workday 第 5 步（workday.md §4） |
| b | "本人或亲属是否为政府官员 / 政治公众人物"预设答案？ | `common:government_official_relative` | 文本 / `null` | `null` | Workday GSK / Micron（workday.md §9） |
| c | "是否存在利益冲突"预设答案？ | `common:conflict_of_interest` | 文本 / `null` | `null` | Workday 第 5 步 |
| d | "是否担任任何公司董事 / 外部职务"预设答案？ | `common:directorships` | 文本 / `null` | `null` | Workday Micron（workday.md §4） |
| e | "是否年满 18 岁"预设答案？（不问出生日期） | `common:age_18_plus` | `Yes` / `No` / `null` | `null` | Workday 年龄题（workday.md §4） |
| f | "兵役状态"预设答案（如不适用 / 已服 / 待服 / 豁免）？ | `common:military_service_status` | 文本 / `null` | `null` | Workday Micron 第 3 步（workday.md §4） |
| g | "是否由员工推荐 / 内推"默认答法？ | `common:employee_referral` | 文本 / `null`（例：`No unless noted at shortlist approval`） | `null` | Workday 第 3 步（workday.md §4） |
| h | "How did you hear about us" 固定答案？不固定则 Executor 按该岗位在台账中的实际来源渠道如实填（不是猜） | 写 `policy.source_channel_default`（不再暂存 `declarations.other[]`） | `$defs/channel` 枚举值（`company_site`/`linkedin`/`jobstreet`/`mycareersfuture`/`email`/`other`）/ `null` | `null` | Workday 第 1 步（workday.md §4/§5） |
| i | "接收招聘营销邮件 / 人才库"勾选？ | `common:marketing_consent` | `Yes` / `No` / `null` | `No`（策略默认：最少授权；用户可改） | 常见于 Greenhouse / Workday 提交前 `[未验证]` |
| j | "当前是否在职 / 离职通知期"固定答案？ | 写 `intent.notice_period`（不再暂存 `declarations.other[]`） | 文本 / `null`（例：`Not employed; available from <earliest_start>`） | `null` | Greenhouse "Notice period"（greenhouse.md §5） |
| k | Jobstreet 工作许可下拉**没有 Student's Pass 选项**，固定选项为：公民 / PR / 已有 EP·S Pass·Work Permit / Training Employment Pass·Work Permit / "I require sponsorship…"。你要固定选哪一项？不固定则每次挂起。Agent 不把 Student's Pass 映射为任何一项。 | 写 `policy.platform_option_overrides.jobstreet["work_rights_option"]`（不再暂存 `declarations.other[]`） | 上述选项原文 / `null` | `null` | jobstreet.md §9/§11 |
| l | Lever 部分表单 Visa status 选项（如"已持有相关签证"）你固定选哪项？ | `platform:lever:visa_status_option` | 选项原文 / `null` | `null` | lever.md §5 |
| m | 只能选一个岗位 / 一份申请全局考虑的公司，默认投哪个方向？ | `common:single_application_preference` | 文本 / `null` | `null` | greenhouse.md §9/§12；与 q5_5 配合 |

### q6_14 事实卡：动机与偏好事实

| 项 | 内容 |
|---|---|
| 问题文案 | 开放题常问"为什么选我们 / 为什么这个方向"。有哪些**你愿意让 AI 引用**的真实动机、偏好、经历感受？一句一条，不需要修辞。没有就说没有。 |
| 字段路径 | `facts_card.facts[]`，`category="motivation"`，`source.type="user_stated"`，`source.ref="intake:q6_14"` |
| 允许答案 | 每条 ≤ 600 字符 |
| 默认值 | 无 |
| 可否跳过 | 是（则开放题只能引用简历事实） |
| 为什么问 | D9 / R9：Content Agent 只能引用已签字事实；动机不在简历上，必须用户口述。 |

### q6_15 事实卡：禁止说法

| 项 | 内容 |
|---|---|
| 问题文案 | 有哪些说法绝对不能出现在你的求职信或开放题里（如"精通 X"、提及某雇主、任何夸大）？ |
| 字段路径 | `facts_card.forbidden_claims[]` |
| 允许答案 | 字符串数组 |
| 默认值 | `[]` |
| 可否跳过 | 是 |
| 为什么问 | facts_card.schema `forbidden_claims`；Content Agent 生成前逐条对照。 |

### q6_16 事实卡签字（逐条 + 整卡）

| 项 | 内容 |
|---|---|
| 动作 | Agent 按 `facts_card.template.md` 渲染 `facts_card.md`，逐类展示；用户回复"全部确认"或"f_003 改为…"/"f_007 删掉"；改动写回 `facts_card.json`（`status=edited/rejected`），重新渲染，直到用户说"整卡签字"。 |
| 字段路径 | `facts_card.facts[].status` / `.user_signature`；`facts_card.meta.signed_by_user` / `.signed_at` / `.resume_sha256[]` |
| 允许答案 | `confirmed` / `edited` / `rejected`（`draft` 不能留） |
| 默认值 | 无 |
| 可否跳过 | 否（未签字不能进入 `source`） |
| 为什么问 | D9 / R9；ARCHITECTURE §2.2 `intake` 退出条件。 |

---

## 8. 轮 7 授权与节奏（`policy.*`、`meta.intake_signed_at`）

### q7_1 提交模式

| 项 | 内容 |
|---|---|
| 问题文案 | 最终提交怎么处理？**confirm**：每份停在提交按钮前等你说"提交"。**autopilot**：复核通过后自动点提交，你事后看台账。选 autopilot 需要你写一句书面授权，并确认以下后果：(1) 提交的内容以你签字的档案和事实卡为准，错误由你承担；(2) 提交后不可撤回；(3) 关口（密码、验证码、证件号、未预设声明题）仍然会停；(4) 你随时可以改回 confirm。 |
| 字段路径 | `policy.submit_mode`；autopilot 时必须写 `policy.autopilot_consent.enabled_at` / `.statement` |
| 允许答案 | `confirm` / `autopilot`；`statement` ≥ 10 字符，必须是用户原话（Agent 不代拟） |
| 默认值 | `confirm`（D8） |
| 可否跳过 | 是（取默认） |
| 为什么问 | D8；`final_submit` 关口（gates.md §8）。 |

### q7_2 关口处理方式

| 项 | 内容 |
|---|---|
| 问题文案 | 遇到需要你出面的关口时：**interactive** = 你在场，当场问你；**batch** = 你不在，能挂起的都挂起、保存草稿、继续下一份，轮末给你一份待办清单。选哪种？无论哪种，最终提交（confirm 模式）、母清单批准、一致性不符、浏览器断连都会当场停。 |
| 字段路径 | `policy.gate_mode` |
| 允许答案 | `interactive` / `batch` |
| 默认值 | `interactive`（ARCHITECTURE §13 开放问题 2 的建议值，**待定**） |
| 可否跳过 | 是 |
| 为什么问 | gates.md §0 两种处理模式。 |

### q7_3 邮箱只读授权

| 项 | 内容 |
|---|---|
| 问题文案 | 允许我**只读**你的邮箱来查回执、状态邮件和验证码吗？只读、不发、不删、不改标签。走哪条路：运行时的邮箱连接器（你自己在设置里授权，推荐 Gmail / Outlook）、已登录 Chrome 里的网页邮箱、还是不授权？ |
| 字段路径 | `policy.mail_readonly_consent`；`policy.mail_backend_preference` |
| 允许答案 | `true` / `false`；`connector` / `webmail` / `none` |
| 默认值 | `null` / `null`（= 不追踪，报告标明） |
| 可否跳过 | 是 |
| 为什么问 | D10；SECURITY §8；`otp` 关口自动读码前提（gates.md §3）；连接器读取可能改变已读状态 `[未验证]`，需告知。 |

### q7_4 验证链接点击授权

| 项 | 内容 |
|---|---|
| 问题文案 | 注册 ATS 账号后的"邮箱激活链接"，允许我在核对发件域与链接域一致后代你点击吗？只限账号激活链接，不含改密 / 解绑 / 授权链接。 |
| 字段路径 | `policy.allow_verification_link_click` |
| 允许答案 | `true` / `false` / `null` |
| 默认值 | `null`（= 挂起交你点） |
| 可否跳过 | 是 |
| 为什么问 | `email_verification_link` 关口（gates.md §4）；事故 I-15（链接过期）。 |

### q7_5 汇报频率

| 项 | 内容 |
|---|---|
| 问题文案 | 每投几份汇报一次进度？默认 5。 |
| 字段路径 | `policy.report_every_n` |
| 允许答案 | 1–50 整数 |
| 默认值 | `5`（D13） |
| 可否跳过 | 是 |
| 为什么问 | D13；汇报只引用台账。 |

### q7_6 待办过期天数

| 项 | 内容 |
|---|---|
| 问题文案 | 挂起的待办项多少天没处理就作废（岗位标放弃、可复活）？默认 7 天。 |
| 字段路径 | `policy.pending_item_expiry_days` |
| 允许答案 | 1–90 整数 |
| 默认值 | `7` |
| 可否跳过 | 是 |
| 为什么问 | ARCHITECTURE §3.4 超时规则。 |

### q7_7 平台 ToS 免责（不重复问）

| 项 | 内容 |
|---|---|
| 动作 | 读 `onboarding.json.tos_acknowledged_at`；存在则写 `policy.platform_tos_acknowledged=true`；不存在则回到 onboarding 展示 SECURITY §7.3 文案，用户输入"我已了解并同意"后再继续。 |
| 字段路径 | `policy.platform_tos_acknowledged` |
| 允许答案 | `true` |
| 默认值 | 无 |
| 可否跳过 | 否 |
| 为什么问 | D13。 |

### q7_8 整体签字

| 项 | 内容 |
|---|---|
| 问题文案 | 档案摘要如下（不含联系方式明文）：`<意向 / 薪资 / 规则 / 策略 摘要>`。确认无误请回复"签字"；要改哪一项直接说。 |
| 字段路径 | `meta.intake_signed_at`；`meta.updated_at` |
| 允许答案 | "签字" / 修改指令 |
| 默认值 | 无 |
| 可否跳过 | 否 |
| 为什么问 | ARCHITECTURE §2.2 `intake` 退出条件；`validate profile` 通过后才写。 |

---

## 9. 每轮结束的固定动作

| 轮 | 结束时写入 | 校验 |
|---|---|---|
| 0 | `materials.*`、`meta.*`；`intake_state.round_done=0` | 文件存在、可读 |
| 1 | `identity.*`、`education[]`、`experience[]`、`skills.*`；`resume_parse.json`；`consistency_report.json`；`round_done=1` | `consistency` 非 `block`（或 `known_mismatches` 已记） |
| 2 | `status.*`、`identity.address`、`identity.date_of_birth`、`identity.gender`；`round_done=2` | — |
| 3 | `intent.*`；`round_done=3` | `intent.types`、`intent.locations` 非空 |
| 4 | `salary.*`；`round_done=4` | `hard_floor ≤ expected_min`（若两者都有，否则提示） |
| 5 | `rules.*`；旧台账导入；`round_done=5` | 黑名单与保留内推名单无重复公司 |
| 6 | `policy.cover_letter_policy` … `policy.declarations`；`facts_card.json` + `facts_card.md`（签字）；`round_done=6` | `validate facts_card` 退出码 0；`signed_by_user=true` |
| 7 | `policy.submit_mode` … `policy.pending_item_expiry_days`；`meta.intake_signed_at`；`round_done=7` | `validate profile` 退出码 0 |

---

## 10. `policy.declarations.other[].question` 命名约定（暂存位）

| 前缀 | 含义 | 示例 |
|---|---|---|
| `common:<key>` | 跨平台常见声明 / 固定答案题 | `common:previously_dismissed` |
| `platform:<platform>:<key>` | 某平台固定选项题的用户选择（仍无对应正式字段的） | `platform:lever:visa_status_option`（q6_13 l） |

Executor 按前缀精确匹配；找不到即 `null` 语义（挂起）。这些前缀是 schema 之外的约定，schema 新增对应字段后应迁移（见第 11 节）。**`skill_years:<skill>` / `skill_level:<skill>` 前缀已于 2026-09-05 废弃**——技能年限与自评现在直接写 `skills.years_by_skill` / `skills.proficiency`（q1_8），不再进 `declarations.other[]`。

---

## 11. 已实现的 schema 字段（原"建议新增"，2026-09-05 产品负责人已批准并进 schema）

以下字段此前只是"建议新增"、由本文各题暂存到 `declarations.other[]` / `notes` / `intake_state.json`（非契约）；`schemas/profile.schema.json` 已补齐，Intake 直接写正式路径，不再暂存。

| 字段 | 理由 | 对应问题 | 迁移前暂存位（已废弃） |
|---|---|---|---|
| `skills.years_by_skill{<skill>: int}` | LinkedIn 年限题只能整数（linkedin.md §5） | q1_8 | `declarations.other[]` `skill_years:*` |
| `skills.proficiency{<skill>: enum}` | Greenhouse / SmartRecruiters 自评题 | q1_8 | `declarations.other[]` `skill_level:*` |
| `intent.can_start_immediately: bool` | "立即到岗"类题必答 Yes 才能过（linkedin.md §11、smartrecruiters.md §5） | q3_7（未设置则由 `earliest_start` 换算） | 由 `earliest_start` 换算 |
| `intent.full_time: bool`、`intent.days_per_week: int` | Ashby / Lever / SmartRecruiters 直接问 | q3_8（未设置则由 `hours_per_week` 换算） | 由 `hours_per_week` 换算 |
| `intent.notice_period: string` | Greenhouse 问 | q6_13 j | `declarations.other[]` `common:notice_period` |
| `intent.work_mode: enum(onsite/hybrid/remote/any)` | LinkedIn "On-site at <地点>?" | 尚无专属题，Intake 可在 q3_* 追问后写入 | `remote_ok` 近似 |
| `salary.current: number` | Workday "Current salary" | q4_7 | `salary.notes` |
| `rules.company_caps[{company, max_applications}]` | 公司级更严上限（PwC 1 份，workday.md §12） | q5_6 附问 | 无（Screening 读 playbook） |
| `rules.notes: string` | 兜底自由规则 | q5_13 | `intake_state.json.free_rules[]`（待定） |
| `materials.job_list_paths[]` | R2 用户清单路径（事故 I-02） | q5_12 | `intake_state.json.user_job_lists[]`（待定） |
| `policy.source_channel_default`（`$defs/channel` 枚举） | Workday "How did you hear about us" | q6_13 h | `declarations.other[]` `common:source_channel` |
| `policy.platform_option_overrides.<platform>.<field_label>: string` | Jobstreet / Lever 固定选项题（jobstreet.md §9、lever.md §5） | q6_13 k | `declarations.other[]` `platform:*` |
| `rules.per_company_max` 的 `maximum` 由 50 改为 3 | 与 SECURITY §7.2 硬上限一致 | q5_6 | Intake 只写 ≤ 3（现由 schema 强制） |
| `intake_state.json` 增加 `skipped_questions[]` | 纪律第 3 条需要落盘 | 全程 | 待定（`user_job_lists[]`/`free_rules[]` 已随上表迁移，不再需要） |

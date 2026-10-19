# LinkedIn Easy Apply

> 证据充分度：**中高**（日配额、成功状态文案、题型有一手记录；弹窗分步的精确顺序未逐步记录）。来源缩写见 `README.md` §3。

## 1. 识别特征
- 岗位页 `https://www.linkedin.com/jobs/view/<id>`（含 `cn.linkedin.com`）；申请按钮文案 "Easy Apply"（中文界面"轻松申请"）。已验证（逐字稿 L3473、L4195、L7878）。
- 非 Easy Apply 的 "Apply" 按钮外跳公司 ATS → 重新识别平台。
- 追踪器页面显示"已申请 N / 进行中 M / 面试 K"。已验证（L4931、L4946）。

## 2. 登录态检测
- 必须使用用户已登录的 Chrome 会话（D4）；已验证（L4574 "Chrome连接已经恢复，而且LinkedIn登录状态正常"）。
- 2026-08 最大故障源不是登录，而是**扩展与运行时的连接超时**（L2252、L2842、L2912、L3139）。断连 = 挂起并记录，禁止假装完成（R4）。
- 无登录态时：Agent 不登录、不注册（D3）；挂起 `pending_user`。

## 3. 账号注册关口
- 不适用（用户必须自带 LinkedIn 账号，onboarding 检查项）。
- 运行时差异只引用 BRIEF D3。

## 4. 表单流程步骤
1. 岗位页确认 **官方地点**后再点 Easy Apply（见 §9 地点规则）。
2. 弹窗分步：联系信息（预填自账号）→ 简历（选已存或上传）→ 雇主筛选题（若干页）→ Review → Submit application。**精确页序未逐步记录（未验证）**。
3. 提交后弹窗/页面显示成功状态（§10）。
4. 每份提交后刷新岗位页核对状态标签（L4840 "刷新后页面明确显示"）。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| Email / Phone（预填） | `identity.email` / `identity.phone.*` | 核对而非重填 |
| Resume（已存列表） | `materials.resume_en_path` | 用户曾授权把简历上传到"求职申请设置"而非公开资料（L2645） |
| Years of experience with X | `skills.years_by_skill[X]` | **只能填整数**（L4586：Python 1、AI 1；L4758：C++ 0、Verilog 0） |
| Nationality / Current residence | `identity.nationality` / `identity.address.country` | L4816、L4766 |
| Date of birth | `identity.date_of_birth` | 出现过（L4816）；profile 未提供则挂起 |
| Available from / to；Can you commit N months full-time? | `intent.available_from` / `.available_to` / `.duration_months` / `.full_time` | L4758、L4824 |
| Can you start immediately? | `intent.start_immediately` | 为 false 且题目必答 Yes → **跳过整岗**（L4291、L4811、L4828、L4243） |
| Is this a school-recognised internship? / Is your school in Singapore? | `status.credit_bearing` / `status.school_in_singapore` | L4820 |
| Bachelor completed? / Master ongoing? | `education[]` 推导 | L4824 |
| Legally authorised to work for this internship / Need future sponsorship | `status.authorized_to_work_internship` / `status.requires_sponsorship_future` | L4832 |
| Need additional work pass? / On-site at <地点>? | `status.requires_sponsorship_internship` / `intent.work_mode` | L4844 |
| Region（Asia / South East Asia 等） | `intent.locations[]` | 只选含新加坡的选项 |
| Languages | `skills.languages[]` | L3895 |
| Motivation / 定制动机（自由文本） | Content Agent（D9） | L4816 |

## 6. 字符上限与控件坑
- 年限题为整数输入，不能填小数或文本（L4586）。
- 自由文本题上限**未验证**。
- 岗位标题/邮件中的"新加坡"标签不可信（§9）。

## 7. Save 草稿与超时策略
- 弹窗支持中途关闭保存草稿（追踪器"进行中"= 草稿/点过申请，L4946）。草稿不算投递。
- 每份 <5 分钟；断连后重开弹窗，先看追踪器是否已"已申请"。

## 8. 简历上传方式
- 优先用 LinkedIn 已存简历（"那里已经保存了你的候选资料和简历"，L5125），不依赖本地上传。
- 首次需把 profile 指定简历上传到 Easy Apply 简历库（需 file URL 权限或系统选择器；2026-08 因扩展故障未完成，L2681）。

## 9. 开放题与声明题出现的位置
- 筛选题位于弹窗中段；多为选择/整数题，少数自由文本"动机"题（L4816）→ Content Agent。
- **地点规则（硬）**：LinkedIn 标"新加坡"但官网写 Hong Kong/Hybrid 或 Asia/Remote（Binance 三岗，L7396-7398）；LinkedIn 确认邮件也标错地点（L7400）。→ 提交前必须打开公司官网 JD 核对；`Hong Kong / Taipei / Asia / APAC / Remote / Hybrid` 不等于新加坡；冲突以官网为准并跳过（L7405-7410）。
- 声明题（若有）只取 `policy.declarations.*`。

## 10. 成功页特征
- 岗位页刷新后显示"申请状态：申请已提交（现在）"（L4808、L4816、L4840、L4844）。
- 提交成功框"您的申请已发送给 <Company>"（L4586、L4758）；"已提交的简历"标签（L4582）。
- 追踪器"已申请"计数**只统计 LinkedIn 站内申请**，不含外部 ATS（L4778）；"进行中"≠雇主推进（L4946）。
- 回执邮件：LinkedIn 发申请确认邮件（地点字段可能错，L7400）。
- **不算**：草稿、"进行中"、职位推荐邮件（L765）、通知里的主页浏览/动态（L4742）。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 提示今日"领英申请"次数已达上限，只能明日继续（L4850、L5129） | 平台日配额 | 把候选存到次日队列（L5141）；自动切换到其他平台（R6） | `failed`（记原因）（quota） |
| 扩展连接超时/读不到标签页（L2252、L2842） | 通道故障 | 挂起；恢复后查追踪器再决定 | `failed` |
| 必答"能否立即开始"= Yes 才能过 | 日期不符 | 放弃草稿 | `skipped`（附 skip_reason_code） |
| 官网地点≠新加坡 | 地点冲突 | 跳过；已投的改标"地点冲突待确认" | `skipped`（附 skip_reason_code） / `location_conflict` |
| 同岗已在公司 ATS 投过（L4540） | 重复 | R1 去重键拦下 | `skipped`（already_applied） |
| 题目要求 profile 没有的事实（生日等） | 缺字段 | 挂起 | `pending_user` |

## 12. 配额与节流
- **日配额已验证存在**（L4850、L4909、L5129），触发后当日不可继续；具体数值和重置时间 **未验证**。
- 对策（R6）：Executor 记录 `linkedin_quota_hit_at`；同日不再排 Easy Apply；被拦岗位入次日队列并可点"保存"。
- 全局 D13 仍适用；同公司 ≤3。

## 13. 已知事故
- 事故 #4：扩展单点故障，LinkedIn 私信整批无法执行（L2842-2912）。
- 事故 #1 口径：官网 ATS + LinkedIn 各投一次导致重复计数（L4540）。
- 地点错投：Binance 三岗按 LinkedIn 标签投到 HK/Asia（L7396-7410）。
- 日配额触发（L4850、L5129）。

## 14. 未验证项
- Easy Apply 弹窗的精确页序与每页按钮文案（未验证）。
- 日配额数值、是否按自然日或 24h 滚动（未验证）。
- 自由文本题字符上限（未验证）。
- 简历上传到 Easy Apply 简历库的入口位置（未验证）。

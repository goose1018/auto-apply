# SmartRecruiters

> 证据充分度：**高**（NCS 30+ 份实投；4000 字符上限、折叠必答题、隐藏文件控件、解析超时、确认/拒信邮件均有一手记录）。来源缩写见 `README.md` §3。

## 1. 识别特征
- URL `https://jobs.smartrecruiters.com/<Company>/<19位数字>-<slug>`（NCS3：`…/NCS3/6000000001077122-ai-strategy-planning-intern`；Grab：`…/Grab/744000139499664-intern-strategy-analytics-transport`）。已验证（L6772、L362）。
- 页面特征：Jobstreet 上 NCS 的 Apply 外跳到此（逐字稿08-05 L814）；表单上传简历后自动解析出经历/教育；最后一页有折叠必答题（L58）；成功文案 "Application submitted!"（L4023）。
- Plan §1 归类：NCS、Bosch、Grab。

## 2. 登录态检测
- 公开表单，**无需账号**（L78 "公开 SmartRecruiters 表单"）。
- 无 OTP/验证码（2026-08 未遇到；未验证）。

## 3. 账号注册关口
- 不适用。运行时差异只引用 BRIEF D3。

## 4. 表单流程步骤
1. 第 1 页：姓名、邮箱 + 确认邮箱、城市、电话、简历上传（必填）、教育（必填）、给招聘团队留言（Hiring Team Message）、LinkedIn/个人网站（可选）。已验证（逐字稿08-05 L814-822、L941）。
2. 简历解析后自动展开工作经历/教育编辑态；需逐条核对（§6）。
3. "Next" → 第 2 页：**折叠的必答题**（实习起止日、每周天数、毕业年份、语言/技术熟练度、签证赞助、岗位特定筛选题）。已验证（L58-62、L3959、L3979、L4023、L4147）。
4. Submit → "Application submitted!"。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| First / Last name | `identity.given_name` / `identity.family_name` | |
| Email / Confirm email | `identity.email` | 两次一致 |
| City / Country | `identity.address.city` / `.country` | |
| Phone | `identity.phone.country_code` + `.number` | 解析器曾带入旧简历的旧区号（逐字稿08-05 L928）→ 复核 |
| Resume（必填） | `materials.resume_en_path` | |
| Education（必填） | `education[]` | 解析可能生成空白教育记录 → 删除（08-05 L997） |
| Experience（解析自动） | `experience[]` | 项目会被误当雇佣经历 → 取消（08-05 L981、L993） |
| Hiring Team Message | Content Agent（D9） | 曾用 2–3 句定制留言（08-05 L835） |
| LinkedIn / Website | `identity.linkedin_url` / `identity.portfolio_url` | 可选 |
| Internship start / end date | `intent.available_from` / `.available_to` | |
| Days per week | `intent.days_per_week` | |
| Graduation year | `education[0].graduation_date` | **易漂移**（L4043、L4047）必核 |
| Visa / sponsorship after graduation | `status.requires_sponsorship_future` | L3959、L3979 |
| Current pass（Student's Pass） | `status.visa_type` | L3959 |
| Skill proficiency（Python / JS-TS / AI security / Power Platform / SAP / OutSystems / Power BI…） | `skills.technical[]` + `skills.proficiency` | 无经验如实选"愿意学习/No"（L4023、L4051、L4155） |
| Field of study / currently enrolled | `education[0].major` / `status.enrollment_status` | L4031 |
| "Available immediately"（岗位正文或题目） | `intent.start_immediately` | 为 false → 跳过整岗（L4295） |

## 6. 字符上限与控件坑
- **单条经历描述 >4,000 字符**：Next 看似可点但不跳页、无红字（L31）。→ Content Agent 把 `experience[].description` 压缩到 ≤4,000（观察值；精确阈值未验证），只删不改事实。
- 解析器把项目当工作经历并在点 Next 时**自动重新展开**（08-05 L993）→ 保存前删除/改正。
- 文件控件隐藏在原生上传窗口里，自动化接口无法直接注入（L4183）→ 需 computer-use 选文件；Codex 内置浏览器不接受系统级点击，需切 Chrome（L4187）。
- 折叠题默认收起，漏答会阻塞提交（L58）→ 展开全部后逐题填。
- Grab 表单只提供 2026 年三个档期选项（L362）→ 日期不符跳过。

## 7. Save 草稿与超时策略
- 无显式 Save（未验证是否有"Save"）；页面停留过久或解析中断会**重置浏览器会话**（L3971、L4003）→ 重连后先看页面是否保留已填内容，再决定重填；未出现成功页一律不算提交。
- 单份 5–10 分钟；同公司批量时每份提交后立即写台账，避免会话重置后重复提交。

## 8. 简历上传方式
- 必填上传（L5068）。三条通道：① Chrome 扩展有 file URL 权限时直接上传；② 无权限 → 系统文件选择器（computer-use，L4183、L4199）；③ 内置浏览器上传（Codex 2026-08 用过，L78）。
- 上传控件打开时曾超时重置会话（L3971）；解析超时同理（L4003）。
- 上传后核对页面显示的文件名 == profile 文件名（08-05 L941 "文件名显示在下方"）。

## 9. 开放题与声明题出现的位置
- Hiring Team Message 在第 1 页（可选自由文本）。
- 折叠必答题在最后一页：日期、天数、毕业年份、技能熟练度、签证。NCS 各岗题面不同（L3979、L4023、L4031、L4147、L4155）。
- 未遇到司法/疫苗/EEO 声明题（**未验证**）；出现则只取 `policy.declarations.*`。

## 10. 成功页特征
- 文案 "Application submitted!"（L4023、L4039、L4147、L4191）/ "Application submitted"（L3959）/ 中文界面"申请已提交"（L4319）。
- 成功页 URL 模式 **未验证**。
- 回执邮件：SmartRecruiters 代发的正式确认邮件（L6816）；拒信同渠道（L6744）；主题模式未验证。
- NCS 首批成功页无确认邮件（L424 "1 份 NCS 有正式成功页面，但没有确认邮件"）→ 成功页截图即证据。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| Next 不跳页、无报错（L31） | 描述 >4000 字符 | 压缩后重试 | 继续 |
| 折叠题未展开导致提交失败（L58） | 漏答 | 展开逐题填 | 继续 |
| 上传/解析超时，会话重置（L3971、L4003） | 通道 | 重连，核对页面状态，未成功不算 | `failed` |
| 文件控件不可注入（L4183） | 上传通道 | computer-use 选文件；不可行则跳过 | `failed`（记原因） |
| 解析器生成错误经历/空教育（08-05 L981、L997） | 数据 | 删除/修正后再 Next | 继续 |
| 毕业年份落错（L4043） | 数据 | 提交前修正（R10） | 继续 |
| 岗位要求 Available immediately（L4295） | 日期 | 跳过 | `skipped`（附 skip_reason_code） |
| 档期选项只有 2026（Grab L362） | 日期 | 跳过 | `skipped`（附 skip_reason_code） |
| 同名岗位不同 ID（台账 §一 #25） | 去重 | R1 键=公司+岗位名 → 视为重复，除非用户明示 | `skipped`（already_applied） |

## 12. 配额与节流
- 平台无配额。NCS 一晚 30+ 份未被拦（L3959-4191），但用户规则"NCS 全线已覆盖不再新投"（台账 §一 #25、SKILL）；同公司 ≤3（D13）作为默认上限，用户可放宽。

## 13. 已知事故
- 4,000 字符卡 Next（L31）→ Plan §1 坑位表。
- 折叠必答题（L58）。
- 上传/解析超时重置会话（L3971、L4003、L4135）。
- Bosch 上传被扩展权限拦（L72）。
- NCS 官网 + LinkedIn 同名重复提交（台账 §一 #25；L4540）。
- 毕业年份两次误落 2027（L4043、L4047）。

## 14. 未验证项
- 4,000 是观察值，精确上限与是否按字节计（未验证）。
- 是否有 Save/草稿、CAPTCHA、声明题（未验证）。
- 成功页 URL、回执邮件主题（未验证）。
- Bosch/Grab 的具体表单字段（Bosch 只到上传步，Grab 只到档期题；未验证完整流程）。

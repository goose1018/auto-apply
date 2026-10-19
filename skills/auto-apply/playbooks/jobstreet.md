# Jobstreet / SEEK（新加坡站）

> 证据充分度：**高**（2026-08 主力渠道；成功页 URL、登录墙、外跳页、回执邮件均有一手记录）。来源缩写见 `README.md` §3。

## 1. 识别特征
- 岗位页 `https://sg.jobstreet.com/job/<数字id>`；申请页 `…/job/<id>/apply`；成功页 `…/job/<id>/apply/success`。已验证（台账 §一 SHOKZ；逐字稿08-13 rollout summary：`https://sg.jobstreet.com/job/93624878/apply/success`）。
- 外跳页 `…/job/<id>/apply/external`，标题 "Visited external site | Jobstreet" —— 这是**外部 ATS 入口**，不是申请。已验证（逐字稿08-13b L925；逐字稿 L256、L5039）。
- 登录墙：`https://login.seek.com/login?…&realm=Username-Password-Authentication&…nudge=apply%3A<jobid>`（Auth0，`redirect_uri=https://sg.jobstreet.com/oauth/callback/`）。已验证（逐字稿 L375、L3369）。
- 第三方站上的 "Apply with SEEK" 按钮（Bosch、CBRE）= OAuth 授权把 SEEK 已存简历带入对方表单。已验证（逐字稿 L74、L5149）。
- 岗位分两类：**Quick Apply**（站内一键）与普通 Apply（站内表单或外跳）。已验证（逐字稿08-05 L810：13 个收藏中 3 个 Quick Apply、10 个普通）。

## 2. 登录态检测
- 已登录：申请页能直接选已存简历、显示账号邮箱与手机号字段（逐字稿08-05 L1009）。
- 未登录：任何 Apply 都跳到 `login.seek.com`。已验证（逐字稿 L616 "NETS：Jobstreet 强制登录"）。
- 登录不一定是密码：出现过**强制向邮箱发一次性登录码**（逐字稿 L3805）；"Applied jobs" 状态页也会要求重新登录（L723）。→ 挂起 `pending_user`，或经用户授权后由 Tracker 从邮箱读码（D10 只读）。
- 内置/无登录态浏览器打开 Jobstreet 停在登录页，不能代替（L2567）；主通道必须是用户已登录的 Chrome（D4）。

## 3. 账号注册关口
- 2026-08 未在逐字稿中注册新 Jobstreet 账号（用户已有账号）。注册页字段 **未验证**。
- 运行时差异只引用 BRIEF D3。
- 账号资料页可由 Agent 维护的非密码项：默认简历、个人简介、教育、技能、语言；资料可见性建议保持 Hidden（雇主仅在申请时看到）。已验证（逐字稿08-05 L606、L646、L1106）。

## 4. 表单流程步骤（站内申请）
1. 岗位页点 "Apply"/"Quick apply"（若跳 `/apply/external` → 停止，改识别外部 ATS）。
2. **简历选择**：从已存简历中选（默认简历可能是旧版，见 §8）+ 手机号 + 求职信（可选，2026-08 全部选"无"）。已验证（逐字稿08-05 L1009-1013、L1101-1103）。
3. **雇主问题**（0–4 题不等；SHOKZ 4 题、SWAEN 2 题）：工作许可、学历、薪资等。已验证（逐字稿08-05 L1017、L1184）。
4. **资料补充页**：系统从简历自动识别经历/技能，询问是否加入 Jobstreet Profile；可取消不保存（不影响本次申请）。已验证（逐字稿08-05 L1085-1089）。
5. **最终核对页**：列出简历、手机号、账号邮箱、求职信、雇主问题答案、随附 Profile 摘要（经历数/技能数/教育）。按钮 "Submit application"。已验证（逐字稿08-05 L977、L1093-1106）。
6. 成功页（§10），并推荐更多岗位（L90）。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| 账号邮箱（不可在申请内改） | `identity.email` | 与简历 PDF 上的邮箱做一致性门（R3）；不一致先报警 |
| Phone | `identity.phone.country_code` + `.number` | |
| Resume（已存简历下拉） | `materials.resume_en_path` | 只选文件名匹配的那份；不匹配 → 先到资料页上传新简历 |
| Cover letter | `materials.cover_letter_policy` | 默认 none |
| 雇主问题：Right to work / work pass 类型 | `status.visa_type` → 选项映射 | **下拉无 Student's Pass**（见 §9）；无准确项 → 挂起 |
| 雇主问题：Expected salary | `salary.expected_min`（区间内） | 已验证按公开区间填 S$1,500/月（L88） |
| 雇主问题：Highest education | `education[0].degree` | |
| 雇主问题：Availability / 日期 | `intent.available_from` / `intent.available_to` | |
| Profile 补充（经历/技能） | `experience[]` / `skills.technical[]` | 默认不保存到公开 Profile，除非 `policy.update_platform_profile=true` |

## 6. 字符上限与控件坑
- 站内表单未遇到字符上限（**未验证**是否存在）。
- 资料补充页会打开长描述编辑器，保存会把描述同步到 Profile —— 默认取消（逐字稿08-05 L1089）。
- 浏览器自动化在"保存"时断连过一次，重连后页面状态仍在，需先读页面再决定是否重填（逐字稿08-05 L1013）。

## 7. Save 草稿与超时策略
- 站内申请无显式 Save；表单短（<5 分钟），断连后从第 1 步重来即可，但**先查该岗位是否已出现在 "Applied jobs"**，避免重复。
- 登录会话会过期（状态页要求重新登录，L723）；出现登录墙即挂起。

## 8. 简历上传方式
- 主路径：**平台已存简历**（下拉选择），不依赖本地文件上传，不受扩展 file URL 限制。已验证（L84 "使用已存的英文产品经理简历，不受本地上传权限影响"）。
- 风险：已存/默认简历可能是**改过名的旧文件**或旧版本。已验证（L1363：SHA-256 比对后确认内容相同仅改名；L5153：SEEK 默认简历是旧版，未点授权）。→ Executor 在选择前核对文件名；若 profile 文件名不在列表中，先上传新版并设为默认（需 file URL 权限或系统选择器）。
- "Apply with SEEK" 到第三方时同样带入默认简历，先核对再授权。

## 9. 开放题与声明题出现的位置
- 雇主问题在第 3 步。**工作许可题**固定选项：公民 / PR / 已有 EP·S Pass·Work Permit / Training Employment Pass·Work Permit / "I require sponsorship…"，**无 Student's Pass 选项**且强制必选。已验证（逐字稿08-05 L1017、L1071、rollout summary L63）。→ 规则：不得把 Student's Pass 映射为 "require sponsorship" 或"已有 S Pass"；`policy.jobstreet_work_rights_choice` 由用户在 Intake 一次性决定（2026-08 由用户本人手选，L44、L1081），未预设则挂起。
- 开放题：站内少见；求职信可选。
- 外跳 ATS 的声明题按目标平台 playbook。

## 10. 成功页特征
- URL `…/job/<id>/apply/success`；文案"申请已发送/已发送给 <雇主>"（中文界面）并附推荐岗位。已验证（L90、L100、L112；台账 §一）。
- 岗位卡片标签 `Applied on Jobstreet`。已验证（L2532）。
- 回执邮件：Jobstreet 自动"成功提交"回执（13 封，L716）；后续状态邮件："Reviewing applications"（L760）、"职位已停止接收新申请"（≠拒信，申请仍保留，L754-762）、"雇主已查看你的申请"（L865）。
- **不算**：`/apply/external` "访问了雇主申请网站"（L256、L5039：活动页 50 条中大量只是访问）、收藏（Saved）提醒邮件（L871）、职位推荐邮件（L765）。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 跳到 `login.seek.com` | 无登录态 / 会话过期 | 挂起；不在无登录态浏览器操作 | `pending_user` |
| 登录要求邮箱一次性码（L3805） | OTP 关口 | 挂起；或 Tracker 只读取码（需授权） | `pending_user` |
| Apply 跳 `/apply/external` | 外部 ATS | 重新识别平台，切换 playbook | 不记为申请 |
| 工作许可下拉无对应项（L1017） | 事实无法如实表达 | 取 `policy.jobstreet_work_rights_choice`，无则挂起 | `pending_user` |
| 默认简历文件名≠profile（L5153） | 版本漂移 | 不提交；上传新版或挂起 | `failed`（记原因） |
| Chrome 扩展断连（L2585） | 通道故障 | 挂起，恢复后先查 "Applied jobs" | `failed` |
| 薪资低于 `salary.floor` | 规则 | 跳过 | `skipped`（附 skip_reason_code） |

## 12. 配额与节流
- 未观察到 Jobstreet 站内日配额（**未验证**是否存在）。遵守全局 D13。
- 成功页推荐岗位是"偏离母清单"的主要诱因（L90-96 → 事故 #2）：推荐岗位一律回到 Sourcing 走母清单批准（D7），Executor 不得就地投。

## 13. 已知事故
- 事故 #3 简历版本漂移：Jobstreet 已存简历为改名副本（L1363）；SEEK 默认简历为旧版（L5153）。
- "访问了雇主网站"曾被误当投递（L256、L5039）→ BRIEF §3 已投标准。
- 工作许可题无 Student's Pass 选项，SHOKZ 停在该题等用户手选（逐字稿08-05 L1017-1081）。
- 从成功页推荐岗位凑数，被用户抓包（L90、L146）。

## 14. 未验证项
- 注册新账号的字段与流程（未验证）。
- 站内表单是否有字符上限（未验证）。
- 是否存在站内日申请配额（未验证）。
- "Apply with SEEK" OAuth 授权页的具体控件（未验证；2026-08 未点授权）。
- Jobstreet 账号邮箱能否在申请内更换（观察为不可，未验证）。

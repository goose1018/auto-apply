# Workday

> 证据充分度：**高**（Micron/PwC/GSK/VIAVI/MBS/HP/CapitaLand/Vopak 多家实投，步骤、声明题、成功页、重复提示均有一手记录）。来源缩写见 `README.md` §3。

## 1. 识别特征
- URL `https://<company>.wd<n>.myworkdayjobs.com/<locale>/<site>/job/<location>/<slug>_<ReqId>`，如 `micron.wd1…/External/job/…_JR106776`、`pwc.wd3…/Global_Campus_Careers/job/…_740967WD`、`gsk.wd5…/GSKCareers/job/…_444672`、`vopak.wd3…/CareersAtVopak/job/…_R0017370`。已验证（逐字稿 L2620、L2623、L2904-2906）。
- 页面特征：分步进度 "Step 2 of 6 / 3 of 6…"（L2846、L2858、L2905）；"Candidate Home"（L3264）；提交后弹窗 "Application Submitted"（L3171）。
- 公司自建域也可能是 Workday（Keppel、CapitaLand 未从 URL 核实，L3469、L5007）。

## 2. 登录态检测
- 已登录：右上账号菜单 / "Candidate Home" 可见，岗位页显示 "You've already applied for this job" 或申请状态（L3701、L3709）。
- 未登录：点击 Apply 后要求 "Create Account / Sign In"（L2591）。
- 部分租户允许**免账号申请**：Vopak 走"无需登录的手动申请"直接到成功页，成功页再提供可选建号（L2870、L3405）。→ Executor 先尝试 Apply，看是否弹登录墙。
- 账号邮箱验证不阻塞已完成的投递（L2904），但未激活账号下次登录可能被拒（Keppel 密码错误/锁定，L3469；GSK 再次要求登录，L3911、L4179）。

## 3. 账号注册关口
- 强制建号并设密码（Micron L2591、VIAVI L6986、P&G L7216、PwC L7372）。
- Agent 可预填：邮箱（`identity.email`）；必停：密码/确认密码；Verify 邮件由用户点或 Tracker 只读取链接。
- 运行时差异只引用 BRIEF D3。
- 账号创建 ≠ 已投（L5195 "账号创建不算投递成功"）。
- 一个邮箱在同一租户只能有一个账号；不要换邮箱重复建号（L3469）。

## 4. 表单流程步骤（典型 6 步，租户可增减）
1. **My Information**：姓名、邮箱、电话（区号下拉）、地址（含邮编/区域，Micron 必填，L186）、来源渠道、是否曾在该公司工作。
2. **My Experience**：简历上传 → 解析 → 工作经历 / 教育 / 语言 / 技能 / 网站（GitHub/作品集）。解析后**不一定自动展开**经历与教育（L3505），结构化栏可能为非必填 "No Response"（L3171）但复核页会显示空 → 按 profile 补齐（L2862-2866）。
3. **Application Questions**：工作授权、现在/未来签证赞助、是否申请过本公司、亲属/客户关系、可到岗日期、毕业日期（精确到月，L4999）、期望薪资/现薪资、学校绑定/员工亲属/内推、兵役（L2905、L3513）。
4. **Voluntary Disclosures**：性别/民族/残障/退伍（EEO 类）；GSK/Micron 在进入本步时触发过 Workday 服务错误并要求先建号（L3159、L3167）。
5. **Self Identify / 合规声明**：政府官员亲属、利益冲突、曾被解雇、董事职务、年龄、国籍（L2858、L2906-2907）、Covid 疫苗（Keppel，L150）。
6. **Review** → "Submit"。成功弹窗 + Candidate Home 状态。
- 按钮："Save and Continue"（未逐字验证按钮文案）；Review 页可返回第 1 步改旧资料（PwC 保留旧地址/电话需返工，L3151）。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| Legal First / Last Name | `identity.given_name` / `identity.family_name` | 按护照拆分（L3143） |
| Email / Phone Device Type / Country Phone Code / Number | `identity.email` / `identity.phone.country_code` / `.number` | 区号下拉曾自动切到中国区号，提交前复核（L2858） |
| Address / City / Postal Code / Country | `identity.address.*` | 缺邮编 → 挂起，不猜（L186） |
| How did you hear about us | `policy.source_channel_default` | |
| Have you previously worked for X | `policy.declarations.previously_worked_here` | |
| Work Experience: Job Title / Company / Location / From / To / Role Description | `experience[]` | 描述有字符校验（§6） |
| Education: School / Degree / Field of Study / From / To / GPA | `education[]` | 无 GPA 不填；"当前硕士成绩"无"尚无成绩"选项时不得编造（L3155） |
| Languages / Proficiency | `skills.languages[]` | |
| Skills（下拉搜索） | `skills.technical[]` | 下拉返回空则留空（L2866） |
| Websites | `identity.github_url` / `identity.portfolio_url` / `identity.linkedin_url` | |
| Resume/CV；Transcript（PwC 必传，L3657） | `materials.resume_en_path` / `materials.transcript_path` | |
| Are you legally authorized to work in SG / Will you now or in the future require sponsorship | `status.authorized_to_work_internship` / `status.requires_sponsorship_future` | "now or in the future" 题 = 未来需赞助则 Yes（L3143） |
| Available start date / Internship period | `intent.available_from` / `.available_to` | |
| Expected graduation (month/year) | `education[0].graduation_date` | 必核毕业年份（R10） |
| Expected salary / Current salary | `salary.expected_min` / `salary.current`（在读填 0 并注明，L3517） | |
| 声明题（解雇/董事/政府官员/利益冲突/疫苗/年龄） | `policy.declarations.*` | 未预设 → 挂起 |
| EEO（性别/种族/残障/退伍） | `policy.eeo_default`（默认 prefer not to say） | |

## 6. 字符上限与控件坑
- 经历描述有**非法字符校验**：直引号等符号被拦（CapitaLand，L4995）；VIAVI 也触发描述字符校验（L3260）。→ 提交前把 `experience[].description` 中的 `"`、`'`、特殊符号替换为纯 ASCII/全角安全字符，不删内容。
- 日期为**年/月分段控件**：直接键入会错解析（HP：2026/05 → 2005，L5199）→ 用日历控件逐段选。
- 简历解析污染：教育年份错、混入无关 URL（MBS，L3272）、项目被当第四段工作经历（PwC，L3457）→ 保存前逐项比对。
- 技能下拉可能无匹配项 → 留空（L2866）。
- Review 页 "No Response" 表示结构化栏为空（L2862）。
- 长度上限数值 **未验证**。

## 7. Save 草稿与超时策略
- Workday 会自动保存到 Candidate Home 的草稿（"PwC Cloud 另一岗已有草稿"，L3701）；重登后从草稿续填（**草稿续填流程未逐步验证**）。
- SKILL 经验：长表单单份 >20 分钟先 Save 一次（未在逐字稿中验证 Workday 的显式 Save 按钮）。
- 服务错误（L3159、L3167）、503/504（L3631）→ 刷新；若要求登录先建号/登录，再回到草稿，**不重填已保存页**。

## 8. 简历上传方式
- 页面文件控件；部分租户把 PDF 设为必填（Hitachi L5011、DuPont L5015）→ 无上传能力时跳过记账。
- HP 允许**不上传、纯在线填写**（L5195、L5203）。
- 登录后同一租户可复用已上传简历与作品集（Micron 自动带入，L3505）；复用前核对文件名。
- 系统文件选择器有时不把文件带回页面（HP L5195、MBS L3268）→ 重试一次，仍失败则改在线填写或跳过。
- Micron 的 Eightfold 入口不接受自动选文件 → 改走 Workday 入口（L3769）。

## 9. 开放题与声明题出现的位置
- 第 3 步（Application Questions）：签证/赞助、历史申请、亲属/客户关系（PwC L2905）；期望薪资/现薪资/兵役（Micron L3513）。
- 第 3–5 步：政府官员/利益冲突（GSK L2866）；年龄/离职记录/国籍/董事/政府任职（Micron L2858、L2907）；Covid 疫苗（Keppel L150）。
- 开放题 "Why PwC / Why this position" 在第 2 页必答（L3461）→ Content Agent（D9），未批准前不提交。
- 全部声明题只取 `policy.declarations.*`，未预设 → 挂起（BRIEF §3）。

## 10. 成功页特征
- 弹窗 "Application Submitted"（Micron L3171、L3521、L3749；CapitaLand L5007）；中文租户"您的申请已成功提交"（HP L5207）。
- Candidate Home 状态 `Application Submitted / In Progress`（VIAVI L3264、MBS L3280）或 `In Process`（Micron L3171、L3521）；HP 候选人主页"有效(N)"计数 +1（L5242、L5298）。
- PwC 状态 `Application Received` + 提交日期（L3155）；GSK 提交后直接进入 `Assessment` 并分配 "GSK Digital Assessment"（L3163、L3717；Agent 不代做测评）。
- Vopak 免账号流程成功文案 "Your application is now complete"（L2870）。
- 岗位页 "You've already applied for this job"（L3701、L3709、L3713、L5117）/ "您于<日期>申请了此职务"（L5314）= 历史已投证据，用于补记台账，不重复计数。
- 回执邮件：CapitaLand 提交后收到确认邮件（L5031）；主题模式 **未验证**。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| Apply 弹 Create Account 密码框 | 注册关口 | 预填邮箱后挂起 | `pending_user` |
| 账号锁定/密码错误（L3469）、要求重置 | 凭据问题 | 挂起，不换邮箱建号 | `pending_user` |
| Workday 服务错误后要求建号（L3159） | 会话丢失 | 建号/登录后从草稿恢复 | `failed` |
| 非法字符拦截（L4995） | 校验 | 清理符号后重试 | 继续 |
| 日期分段控件错解析（L5199） | 控件 | 日历逐段选 | 继续 |
| 解析器污染字段（L3272、L3457） | 数据 | 与 profile 逐项比对修正 | 继续 |
| 声明题未预设 | 关口 | 挂起，保留草稿 | `pending_user` |
| 缺高中成绩/证件号等未知事实（UBS 41%，L3689） | 不编造 | 保留草稿并跳过 | `skipped`（附 skip_reason_code） |
| PDF 必填且无法上传（L5011） | 通道 | 跳过 | `failed`（记原因） |
| "You've already applied" | 重复 | 查台账补记 | `skipped`（already_applied） |
| 503/504（L3631） | 平台故障 | 稍后重试 | `failed` |

## 12. 配额与节流
- 公司级规则：PwC 每人只能投一份，官网提示重复申请会拖慢处理（L3701、L7368）→ `rules.company_caps[PwC]=1`。
- 同一租户连续多投（HP 8 份、Micron 7 份）技术上可行，但受全局同公司 ≤3（D13）与用户规则约束。

## 13. 已知事故
- 声明题必须本人答：PwC 3/6、GSK、Micron 停在合规声明（L2858-2907）→ Intake 一次性预设（BRIEF §7 第 6 轮）。
- CapitaLand 非法字符拦截（L4995）；HP 日期控件错解析（L5199）。
- PwC 复核页残留旧地址/电话（L3151）→ R3/R10。
- Keppel 账号锁定（L3469）、验证链接超 24 小时失效（L721）。
- Micron Eightfold 入口不可上传，改走 Workday（L3769）。

## 14. 未验证项
- 各步按钮精确文案（"Save and Continue"/"Next"）与显式 Save 入口（未验证）。
- 草稿续填的精确路径（Candidate Home → 草稿）（未验证）。
- 描述字段字符数上限（未验证）。
- 回执邮件主题模式（未验证）。
- Keppel、CapitaLand 是否确为 Workday（逐字稿判断，未从 URL 核实）。

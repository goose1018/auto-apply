# SAP SuccessFactors（Career Site Builder / jobs2web）

> 证据充分度：**中**。登录墙、账号激活、CSRF 超时事故有一手记录；**完整走到成功页的只有 Singtel（平台归属由 Codex 判断、未从 URL 核实）**，字段级细节主要来自台账 Temasek 条目。来源缩写见 `README.md` §3。

## 1. 识别特征
- 公司品牌域 + `/job/<slug>/<10位数字>/`：`careers.nets.com.sg/job/Braddell-Data-Analytics-Intern/1361408966/`、`jobs.temasek.com.sg/job/…/1369200757/`、`groupcareers.singtel.com/job/…/1363401866/`。已验证（逐字稿 L363；逐字稿08-07b L340-353；逐字稿08-13b L1959、L2099）。
- 点 Apply 后跳转 `https://career<n>.successfactors.eu/careers?company=<tenant>`（Temasek `career2…company=temasekcapP2`，SAP `career5…company=SAP`），页面标题 **"Career Opportunities: Sign In"**，含 "Already have an account?" / "Forgot your password?" / "Not a registered user yet? Create an account"，URL 参数含 `career_ns=job_application&career_job_req_id=<id>&jobPipeline=JobStreet&clientId=jobs2web`。已验证（08-13b L2129、L4265）。
- Plan §1 归类：NETS、Temasek；逐字稿另判断 Singtel、EY 为同类（EY 未验证）。

## 2. 登录态检测
- 已登录：跳过 Sign In 直接进入申请表（**未验证**具体页面特征）。
- 未登录：必到 "Career Opportunities: Sign In"；**无免账号通道**（NETS L2500、L363；Temasek L4578）。
- 账号状态三种：① 不存在 → Create an account；② 已存在未激活 → 系统只允许"重发激活邮件"（NETS L3417、L3629；Temasek L5318、L5064）；③ 已激活但 Chrome 无登录态 → 需密码（L4578）。
- Singtel 走"招聘助手"式流程，要求邮箱 6 位验证码（L3425、L3621）。

## 3. 账号注册关口
- Create an account 页：Agent 可预填邮箱、姓名、电话（**字段清单未验证**）；必停：密码/确认密码。
- 注册后强制邮箱激活链接（Temasek "激活邮件已发送"，L5064；NETS L3284）；激活链接由用户点或 Tracker 只读取。台账 §二：Temasek 账号建在旧邮箱上，需本人激活。
- 运行时差异只引用 BRIEF D3。
- 一个邮箱一个账号；EY 出现"邮箱已注册、密码校验失败 → 需重置"（L4923，EY 平台未验证）→ 挂起，不重置密码。

## 4. 表单流程步骤
- 以 Temasek（台账 §四 2026-08-25）为样本：单页/分区长表单 → 简历上传 → 定制求职信 → 工作经历（4 段）→ 教育（2 段）→ 筛选题（6 题）→ **Save**（存草稿）→ **Apply**（正式提交）。
- Singtel："Apply now" → 官方招聘入口 → 身份验证（邮箱 6 位码）→ 表单 → 成功页（L3288-3292、L3425）。
- 精确分区名与按钮文案 **未验证**（Save / Apply 已验证存在，台账 §四）。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| Email（账号邮箱） | `identity.email` | 已有账号绑定旧邮箱则沿用（台账 §三） |
| Name / Phone | `identity.*` | |
| Resume / CV | `materials.resume_en_path` | |
| Cover letter | Content Agent（D9） | Temasek 用了定制 CL（台账 §四） |
| Work experience ×N | `experience[]` | |
| Education ×N | `education[]` | |
| 筛选题（约 6 题：日期、学分实习、签证、薪资等，具体题面未验证） | `intent.*` / `status.*` / `salary.*` | |
| 学历门槛 "currently pursuing Bachelor's" | `education[0].degree` 与 JD 比对 | 硕士在读不得冒充本科在读 → 跳过（08-13b L2045） |

## 6. 字符上限与控件坑
- 字符上限 **未验证**。
- 会话型坑见 §7（CSRF）。

## 7. Save 草稿与超时策略（本平台核心）
- **已验证事故**（台账 §四 2026-08-25 Temasek）：表单 100% 填完并 Save 成功；因填表超 30 分钟旧会话失效，点 Apply 时 CSRF 令牌失效 → 卡在 Loading，邮箱无回执 → 不计已投；处理 = 重新登录后打开草稿点 Apply。
- 规则（SKILL、R5）：① 进入表单先记 `form_opened_at`；② 每完成一个分区 Save 一次；③ 单份 >20 分钟强制 Save；④ 点 Apply 前若 `now - login_at > 20 min` 先刷新/重登再 Apply；⑤ Apply 后 Loading >60 s 无成功页 → 判会话失效，重登 → 草稿 → 再 Apply，**不重填**。
- 自动登出阈值：观察为 ~30 分钟（台账），精确值未验证。

## 8. 简历上传方式
- 页面文件控件（Temasek 上传成功，台账 §四）；扩展 file URL 权限前置。
- Singtel 上传曾被扩展权限拦（L3421）。
- 平台"已存简历"复用：**未验证**。

## 9. 开放题与声明题出现的位置
- 筛选题区（Temasek 6 题）；Singtel 在成功前有身份验证步骤。
- 声明题具体题面 **未验证**；一律只取 `policy.declarations.*`。
- 求职信为定制文本 → Content Agent。

## 10. 成功页特征
- Singtel："Your application has been sent. Thank you!"（L3292）；FDE 岗申请助手 "Thank you … for submitting your application"（L7332）。
- EY："Thank you for submitting your application!"（L158，EY 平台归属未验证）；EY 回执邮件"可进入候选人主页查看"（L718）。
- Temasek 成功页 **未拿到**（卡在 CSRF）；判定标准暂用：Apply 后出现确认页 + 邮箱回执，二者缺一先记 `draft_saved`。
- 回执邮件主题模式 **未验证**。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 跳到 `career*.successfactors.eu` Sign In | 无账号/未登录 | 有账号→挂起要密码；无账号→预填后挂起 | `pending_user` |
| "账号已存在但尚未激活"（L3417、L5318） | 激活关口 | 重发激活邮件后挂起；Tracker 找链接 | `pending_user` |
| 邮箱 6 位验证码（Singtel L3425） | OTP | 挂起或 Tracker 只读取码 | `pending_user` |
| Apply 后 Loading 卡死 / 页面登出（台账 §四） | CSRF/会话失效 | 重登 → 草稿 → Apply | `draft_saved` → 重试 |
| 密码校验失败要求重置（L4923） | 凭据 | 挂起，不重置 | `pending_user` |
| JD 要求本科在读（08-13b L2045） | 学历门槛 | 跳过 | `skipped`（附 skip_reason_code） |
| 申请入口异常跳回首页（Temasek L4223） | 平台故障 | 稍后重试 | `failed` |

## 12. 配额与节流
- 未观察到平台配额。Temasek 3 岗共用一个账号（L4578）；同公司 ≤3（D13）。

## 13. 已知事故
- Temasek CSRF/登出事故（台账 §四 2026-08-25；SKILL"防超时"条目）。
- NETS/Temasek 账号未激活循环（L3417、L3629、L5318）。
- Singtel 邮箱验证码阻塞（L3425、L3621）；后经用户在场完成投递（L3292、L7332）。
- Jobstreet 外跳带 `jobPipeline=JobStreet` 参数（08-13b L2129）：来源标记不影响流程，但说明 Jobstreet→SF 是常见路径。

## 14. 未验证项
- 已登录页面特征；Create an account 字段清单（未验证）。
- 表单分区名、按钮文案、字符上限（未验证）。
- 自动登出精确时长（观察 ~30 分钟）。
- Temasek 成功页文案/URL；回执邮件主题（未验证）。
- Singtel、EY、Keppel 是否确为 SuccessFactors（Singtel URL 形态符合，Codex 判断为 SF；EY/Keppel 未验证）。
- 平台已存简历复用（未验证）。

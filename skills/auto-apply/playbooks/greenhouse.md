# Greenhouse

> 证据充分度：**高**（StraitsX ×3、DRW、Workato、Marshall Wace、Citadel 实投；邮箱验证码、"Enter manually"、隐藏地点字段均有一手记录）。来源缩写见 `README.md` §3。

## 1. 识别特征
- 托管板 `https://job-boards.greenhouse.io/<company>/jobs/<数字id>`（StraitsX，L2622、L7761）；旧域 `boards.greenhouse.io/<company>/jobs/<id>`（**未在逐字稿出现，未验证**）。
- 公司自建域内嵌 Greenhouse 表单（Marshall Wace、Workato、DRW、Citadel、Jane Street 等，L7095-7212）：识别依据是简历控件 "Attach / Dropbox / Google Drive / Enter manually" 与提交前的 8 位邮箱验证码（**内嵌页 URL 未逐一核实**）。
- Plan §1 归类：StraitsX、DRW。

## 2. 登录态检测
- 无账号体系；申请**无需登录**（L2597 "申请无需账号"）。
- 提交前有**邮箱所有权验证**：向填写的邮箱发 8 位验证码，页面输入后才真正提交（L7027、L7095、L7115、L7131）。→ 不是登录，是 OTP 关口。

## 3. 账号注册关口
- 不适用。运行时差异只引用 BRIEF D3。
- 验证码来源：发到 `identity.email`；Tracker 可经邮箱连接器只读取码（已验证 Gmail 连接器读到并自动完成，L7143-7159）；无连接器 → 挂起让用户贴码（L7027-7035）。验证码只用一次不落盘。

## 4. 表单流程步骤（单页）
1. 基本信息：First/Last name、Email、Phone、Location/Address。
2. Resume/CV：Attach / Enter manually（L4866、L7017）。
3. 可选：Cover letter、LinkedIn、GitHub/Website。
4. 公司自定义题（见 §9）；隐私/PDPA 勾选（L6993）。
5. reCAPTCHA（部分租户，L4907、L3919）。
6. Submit application → 邮箱 8 位码验证 → 成功页（§10）。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| First / Last Name | `identity.given_name` / `identity.family_name` | |
| Email | `identity.email` | 验证码发此邮箱 |
| Phone | `identity.phone.country_code` + `.number` | |
| Location (City) / Address | `identity.address.city` / `identity.address.*` | |
| LinkedIn Profile（StraitsX 必填，L2622、L2597） | `identity.linkedin_url` | 无 → 挂起，不冒填 |
| GitHub / Website | `identity.github_url` / `identity.portfolio_url` | |
| Resume/CV | `materials.resume_en_path`；Enter manually → `materials.resume_text_en` | |
| Earliest start date / Notice period | `intent.available_from` / `intent.notice_period` | L2597 |
| Education: school / degree / start–end / expected graduation（DRW 精确日期，L7079） | `education[]` | 缺月份不猜 |
| Skill proficiency（如 C++ level，L7079） | `skills.proficiency[skill]` | 简历未声明的技能不自评 → 跳过该岗 |
| Work pass 两题（实习期间 / 毕业后，L7091） | `status.requires_sponsorship_internship` / `status.requires_sponsorship_future` | |
| GPA / Most recent employer / Preferred location / Availability windows（Citadel，L7212） | `education[].gpa` / `experience[0].company` / `intent.locations[]` / `intent.windows[]` | GPA 只填 profile 有的 |
| Role preference（Marshall Wace 只能选一个岗位，L7131） | `intent.role_preference` | |
| PDPA / privacy consent | `policy.consent_pdpa=true` | |
| 隐藏字段 `job_location`（Citadel，L7403） | 与 `intent.locations[]` 比对 | 值≠新加坡 → 跳过 |

## 6. 字符上限与控件坑
- 字符上限 **未验证**。
- Citadel 页面显示 "Hong Kong, Singapore" 但隐藏字段 `job_location=Hong Kong`（L7403）→ Executor 读 DOM 隐藏字段核地点。
- Optiver（平台未验证）表单要求中学考试类型与分数（L3919、L7208）→ profile 无此事实 → 跳过。

## 7. Save 草稿与超时策略
- 无草稿功能。表单短，但 8 位码等待期间标签页可能被断连**锁住**（Marshall Wace，L7147-7155）→ 处理：不抢占旧标签，新开同岗位重填；旧表单未过验证码即未提交，不会重复（L7155）。
- 验证码有时效（未验证时长）；新码会作废旧码（L7131 "又发了一组新的"）→ 取**最新**一封。

## 8. 简历上传方式
- "Attach" 按钮触发文件控件（L7017）；曾因扩展无 file URL 权限失败（L7003），开启后重试成功（L7021）。
- Citadel 的 Attach 调起 macOS 原生选择器 → 需 computer-use（L7210）。
- 备选 **"Enter manually"**：把 `materials.resume_text_en` 逐字粘贴（L4866；不改写不用旧版）。
- Workato 上传时扩展连接被文件选择器重置（L7111）→ 重连后先看页面是否已附件。

## 9. 开放题与声明题出现的位置
- 自定义题在简历之后、Submit 之前：签证两问（DRW）、技能自评（DRW C++）、教育精确日期、GPA、可实习窗口、地点偏好（Citadel）、"只能选一个岗位"（Marshall Wace）、PDPA。
- 开放题（自由文本）2026-08 未在 Greenhouse 遇到必答项（**未验证**是否存在）；有则 → Content Agent。
- 声明题只取 `policy.declarations.*`。
- Jane Street（平台未验证）："一份申请自动考虑全球其他岗位" → 只投一份（L7188）。
- Point72（平台未验证）页面明文禁止用生成式 AI 完成申请 → 跳过（L3705）。**任何页面出现此类声明一律跳过并记账**。

## 10. 成功页特征
- 文案："Thank you for applying. Your application has been received."（StraitsX，L7045）；"Thank you for applying / application has been received"（L3813）；"Your application has been received"（L7256）；"Thank you for applying."（Marshall Wace，L7159）；"Thank you for your application."（Citadel，L7212）。
- 成功页 URL 模式 **未验证**（内嵌页多为同 URL 内容替换）。
- 回执邮件：Greenhouse 代发的确认邮件（Jane Street 8 月 13 日确认收到简历、ShopBack 确认邮件，L7196）；主题模式未验证。
- **不算**：验证码邮件本身；填完但未过验证码的表单（L4907、L7095）。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 要求 8 位邮箱验证码（L7027） | OTP | Tracker 读最新码（连接器）或挂起 | `pending_user`（有连接器则自动） |
| reCAPTCHA（L4907、L3919） | CAPTCHA | 挂起给用户按 | `pending_user` |
| 必填 LinkedIn URL 而 profile 无（L2622） | 缺字段 | 挂起 | `pending_user` |
| 必填技能自评/中学成绩/精确日期，profile 无（L7079、L7208） | 不编造 | 跳过 | `skipped`（附 skip_reason_code） |
| 隐藏 `job_location`≠新加坡（L7403） | 地点 | 跳过 | `skipped`（附 skip_reason_code） |
| 页面声明禁止 AI 填写（L3705） | 合规 | 跳过 | `skipped`（附 skip_reason_code） |
| 提交返回系统错误（Jane Street，L7352） | 平台故障 | 不连续重试（避免风控），稍后一次 | `failed` |
| 标签页被旧会话锁住（L7151） | 通道 | 新开同岗位重填 | `failed` |
| 上传触发扩展重置（L7111） | 通道 | 重连后核对附件 | 继续 |

## 12. 配额与节流
- 平台无配额。公司级：Marshall Wace 只能选一个岗位（L7131）；Jane Street 一份全局考虑（L7188）；StraitsX 未见限制、可投多岗（L3815）。写入 `rules.company_caps`。

## 13. 已知事故
- 验证码人工转发 → 后改为 Gmail 连接器自动读取（L7135-7172）。
- StraitsX 停在 reCAPTCHA（L4907）后另一晚成功（L7045）：CAPTCHA 出现与否不稳定。
- Citadel 隐藏地点字段为 Hong Kong，提交前拦下（L7403）。
- Marshall Wace 标签页锁死后重开（L7147-7159）。

## 14. 未验证项
- `boards.greenhouse.io` 旧域是否仍在用（未验证）。
- 内嵌表单公司（Citadel、Jane Street、Marshall Wace、Workato、DRW、Optiver、Point72）是否全部为 Greenhouse（未从 URL 核实）。
- 字符上限、验证码时效、成功页 URL、回执主题（未验证）。
- 是否存在必答自由文本开放题（未验证）。

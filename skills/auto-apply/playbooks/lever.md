# Lever

> 证据充分度：**高**（ShopBack、Binance ×5、PatSnap 尝试；地点自动完成返空、解析清空地点、成功文案、地点错投均有一手记录）。来源缩写见 `README.md` §3。

## 1. 识别特征
- URL `https://jobs.lever.co/<company>/<uuid>`（`jobs.lever.co/shopback-2/…`、`jobs.lever.co/binance/…`）。已验证（L2621、L5669、L7396）。
- 页面特征：单页表单；"Current location" 自动完成控件；简历上传后解析（"解析已显示 Success"，L7067）；成功文案 "Application submitted!"（L3649、L3887）。
- Plan §1 归类：ShopBack；逐字稿另有 Binance、PatSnap。

## 2. 登录态检测
- 无账号体系，免登录（L3641 "标准附件上传，不需要账号或验证码"）。
- 无 OTP/CAPTCHA（2026-08 未遇到；未验证）。

## 3. 账号注册关口
- 不适用。运行时差异只引用 BRIEF D3。

## 4. 表单流程步骤（单页）
1. Resume/CV 上传（触发解析，自动填部分字段）。
2. Full name、Email、Phone、**Current location**（自动完成）、Current company（可选）。
3. Links：LinkedIn、GitHub、Portfolio。
4. 公司自定义题：签证/赞助、日期、全职时长、学分实习、学校、GPA/年级（可选）、居住地/国籍、区域、语言、每周小时数。
5. Additional information（自由文本，可选）。
6. Submit application → "Application submitted!"。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| Full name | `identity.full_name_en` | |
| Email / Phone | `identity.email` / `identity.phone.*` | |
| Current location（自动完成） | `identity.address.city` + `.country` | **必须从下拉选中候选**，否则隐藏值为空（§6） |
| LinkedIn / GitHub | `identity.linkedin_url` / `identity.github_url` | L7063 |
| University / School | `education[0].school` | L7063 |
| GPA / Year of study（非必填） | `education[0].gpa` / `.year` | 不猜、不填（L7059） |
| Internship duration / Full-time / Dates | `intent.duration_months` / `.full_time` / `.available_from` / `.available_to` | ShopBack H1 六个月全职（L7063） |
| Credit-bearing internship | `status.credit_bearing` | |
| Visa status（"已持有相关签证"类选项） | `status.visa_type` | Student's Pass 映射到"已持有相关签证"是 2026-08 的用户决定（L7063）；写入 `policy.lever_visa_choice`，否则挂起 |
| Sponsorship during internship / after | `status.requires_sponsorship_internship` / `.requires_sponsorship_future` | Binance 实习期间选 No（L3899） |
| Country of residence / Nationality | `identity.address.country` / `identity.nationality` | Binance（L4766） |
| Region（Asia / South East Asia…） | `intent.locations[]` | 只选含新加坡的选项，且先核官网地点（§9） |
| Hours per week | `intent.hours_per_week` | Binance 40h（L4766） |
| Languages | `skills.languages[]` | L3895 |
| Expected salary（若有） | `salary.expected_min` | |
| Additional information | Content Agent（D9） | 可选 |

## 6. 字符上限与控件坑
- **Current location 自动完成返空**：控件不返回任何地点候选 → 隐藏地点值为空 → 提交时字段被清空/提交失败（ShopBack L2675、L7075；PatSnap L3955）。
- **解析完成瞬间清空 Current location**（L7067）→ 顺序必须是：先上传简历等解析 Success，**再**填地点，再提交。
- 处理：输入城市名后等待下拉，键盘 ↓ + Enter 选中；仍无候选 → 换写法（"Singapore, Singapore"）；再失败 → 记 `failed`（记原因），稍后换浏览器通道重试。
- 字符上限 **未验证**。

## 7. Save 草稿与超时策略
- 无草稿；单页 <5 分钟。断连后重填，提交前查台账。
- 已填未提交的表单可留在标签页（L2675 "保留这张表"），但标签页断连后可能锁死（Greenhouse 案例同理）→ 新开重填。

## 8. 简历上传方式
- 页面文件控件；受扩展 file URL 权限约束（ShopBack 被拦，L4858）。
- 上传后解析，会覆盖/清空已填字段（§6）→ 先传后填。
- 平台已存简历：无。

## 9. 开放题与声明题出现的位置
- 自定义题在联系信息之后；Binance 有居住地/国籍/区域/语言/工时/赞助（L3887-3899、L4766）；ShopBack 有实习性质/签证/日期/学校（L7063）。
- 自由文本 "Additional information" 可选 → Content Agent。
- 未遇到司法/疫苗/EEO 声明题（**未验证**）。
- **地点硬规则**（L7396-7410）：Lever 岗位页顶部地点/区域是权威（Binance 官网写 Hong Kong·Hybrid / Asia·Remote 而 LinkedIn 标新加坡）；`Hong Kong / Taipei / Asia / APAC / Remote / Hybrid` 不等于新加坡；Remote 必须明确允许在新加坡工作。

## 10. 成功页特征
- 文案 "Application submitted!"（ShopBack L3649；Binance L3887、L3891、L3895）。
- 成功页 URL 模式 **未验证**。
- 回执邮件：ShopBack 有确认邮件（L7196）；主题模式未验证。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 地点下拉无候选（L2675、L3955） | 控件故障 | 换写法/换通道重试一次；仍失败保留待办 | `failed`（记原因） |
| 提交后地点被清空、未提交（L7067） | 解析覆盖 | 等解析 Success 后补地点再提交 | 继续 |
| 官网地点≠新加坡（L7396） | 地点冲突 | 跳过；已投改标 `location_conflict` | `skipped`（附 skip_reason_code） |
| 上传被扩展拦（L4858） | 通道 | `_template.md` §8 备选 | `failed`（记原因） |
| 岗位 Part Time（PatSnap L4130） | 筛岗 | 跳过 | `skipped`（附 skip_reason_code） |

## 12. 配额与节流
- 平台无配额；Binance 一晚 5 份未被拦（L3887-3899）。同公司 ≤3（D13）默认，用户可放宽。

## 13. 已知事故
- ShopBack 地点控件返空，两晚都未能提交（L2675、L7075）；另一次成功（L3649）→ 控件行为不稳定，与浏览器通道相关。
- Binance 三岗地点错投（L7396-7410）→ README §4 地点规则。
- PatSnap 同样地点返空（L3955）。

## 14. 未验证项
- 字符上限、CAPTCHA、声明题（未验证）。
- 成功页 URL、回执主题（未验证）。
- 地点控件返空的根因（内置浏览器 vs Chrome 扩展）（未验证）。
- Raine Group "Application submitted!"（L3681、L7364）平台归属未验证，未计入本 playbook 证据。

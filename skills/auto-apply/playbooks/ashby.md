# Ashby

> 证据充分度：**中高**（Bifrost、Venti ×3、Simular ×6 实投；成功文案、反垃圾拦截有一手记录；字段清单按公司差异大）。来源缩写见 `README.md` §3。

## 1. 识别特征
- URL `https://jobs.ashbyhq.com/<Company>/<uuid>/`（Bifrost、GoVenti、simular，L2616、L2699、L8943）；申请页 `…/<uuid>/application`（L2920）。
- 页面特征：单页表单；提交后文案 "Your application was successfully submitted"（L2607）。
- Plan §1 归类：Simular、Bifrost、Venti；"顺畅，通常无学历字段"（Plan §1，部分验证：Bifrost 无签证/国籍题，L2601）。

## 2. 登录态检测
- 无账号体系，免登录（L2601 "申请只要求姓名、邮箱和简历"）。
- 无 OTP/验证码（2026-08 未遇到；**未验证**是否存在租户级 CAPTCHA）。

## 3. 账号注册关口
- 不适用。运行时差异只引用 BRIEF D3。

## 4. 表单流程步骤（单页）
1. Name、Email（、Phone）。
2. Resume 上传（部分租户解析简历自动填充，未验证）。
3. 公司自定义题：工作授权/赞助、起止日期、全职/学分实习、薪资期望、LinkedIn/GitHub（Venti L2687-2699；Simular L7312）。
4. Submit → 成功文案。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| Name / Email / Phone | `identity.full_name_en` / `identity.email` / `identity.phone.*` | |
| Resume | `materials.resume_en_path` | |
| LinkedIn / GitHub / Portfolio | `identity.linkedin_url` / `identity.github_url` / `identity.portfolio_url` | 无则留空 |
| Are you authorized to work / need sponsorship | `status.authorized_to_work_internship` / `status.requires_sponsorship_*` | Simular 有此题（L7312）；Bifrost 无（L2601） |
| Start date / End date / Duration / Full-time | `intent.available_from` / `.available_to` / `.duration_months` / `.full_time` | Venti 按 6 个月全职填（L2687） |
| Internship type (credit-bearing) | `status.credit_bearing` | |
| Expected salary | `salary.expected_min`–`salary.expected_max` + `salary.negotiable` | Venti 填区间可协商（L2699） |
| Earliest available date（k-ID 只问此项，L3873） | `intent.available_from` | 标题年份≠可用年份时如实填，ATS 接受才计数 |
| Free-text（why us / relevant experience） | Content Agent（D9） | Simular GTM 岗用了真实项目描述（L3843） |

## 6. 字符上限与控件坑
- 字符上限 **未验证**。
- 反垃圾：连续多岗快速提交后出现 "couldn't submit"（Simular People & Ops，L7324）→ 判为速率/反垃圾拦截；不连续重试，换公司后稍后复查。
- 同公司多岗共用同一表单模板，答案可复用但每岗仍需逐题核对（Simular 6 岗，L3831-3847）。

## 7. Save 草稿与超时策略
- 无草稿；单页 <5 分钟。断连后重开页面重填，提交前先查台账。

## 8. 简历上传方式
- 页面文件控件；受扩展 file URL 权限约束（同 `_template.md` §8）。
- 2026-08 在 Ashby 上传未见失败记录（L2607、L2699 均带最新版简历）。
- 平台已存简历：无（免登录）。

## 9. 开放题与声明题出现的位置
- 自定义题在简历之后；是否有开放题取决于租户（Simular GTM 岗有描述性问题，L3843）。
- 未遇到司法/疫苗/EEO 类声明题（**未验证**是否存在）；出现则只取 `policy.declarations.*`。
- 硬条件不满足（如要求现成社群/设计作品集，L3867）→ 不投。

## 10. 成功页特征
- 文案 "Your application was successfully submitted"（Bifrost L2607、Venti L2699、Simular L7320）；变体 "Success — application was successfully submitted"（L3835）。
- 成功页 URL 模式 **未验证**（可能仍在 `/application` 路径下内容替换）。
- 回执/后续邮件由 Ashby 代发（Simular 面试邀请来自 "Simular 的 Ashby 招聘系统"，DKIM 通过，L8925）；主题模式未验证。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| "couldn't submit"（L7324） | 反垃圾/速率 | 停止该公司当轮；间隔后复查一次 | `failed`（rate） |
| 必填字段 profile 无 | 缺字段 | 挂起 | `pending_user` |
| 岗位硬条件不符（L3867） | 筛岗 | 跳过 | `skipped`（附 skip_reason_code） |
| 上传被扩展拦 | 通道 | 按 `_template.md` §8 备选 | `failed`（记原因） |

## 12. 配额与节流
- 平台反垃圾阈值 **未验证**；2026-08 在 Simular 连续第 7 份左右被拦（L3831-3847、L7320-7324）。建议同公司 Ashby 岗位间隔 ≥2 分钟且同公司 ≤3（D13）。

## 13. 已知事故
- Simular People & Operations 被反垃圾拦截（L7324）。
- k-ID 岗位标题写 2026 但表单只问最早可开始日期，如实填 2027 并成功（L3873-3877）。

## 14. 未验证项
- 是否存在 CAPTCHA、字符上限、简历解析自动填充（未验证）。
- 成功页 URL、回执邮件主题（未验证）。
- 反垃圾触发阈值（未验证）。
- "通常无学历字段"仅在 Bifrost/Venti 验证，其他租户未验证。

# MyCareersFuture（MCF，新加坡政府求职平台）

> 证据充分度：**低**。2026-08 只打开过岗位页，**没有任何一份在 MCF 上完成的申请**；申请流程各节多为未验证，需产品负责人试跑一份补证。来源缩写见 `README.md` §3。

## 1. 识别特征
- 岗位页 `https://www.mycareersfuture.gov.sg/job/<category>/<slug>-<32位hash>`（可带 `?source=MCF&event=RecommendedJobJD`）。已验证（逐字稿08-13b L4829、L4943）。
- 岗位编号格式 `MCF-<yyyy>-<n>`（如 `MCF-2026-1311005`）。已验证（08-13b L4900 附近）。
- 页面特征：顶部 "A Singapore Government Agency Website"；导航 "Search Jobs / Gain Insights / Explore Paths / Join Events / Apply Scheme"；右上 **"Log In"** 按钮；岗位卡显示薪资区间、"N applications"、"Typically Replies in 30 Days"、多语言机器翻译（Microsoft Translator）；页脚 "Powered by X0PA AI"。已验证（08-13b L4860-4950）。
- 雇主端 `employer.mycareersfuture.gov.sg`（已验证，L4876）。
- Jobstreet 上 PSA 的 "Apply" 外跳到 MCF（已验证，逐字稿08-05 L1207、L1233）。

## 2. 登录态检测
- 已登录特征：**未验证**（推测顶栏显示用户名代替 "Log In"）。
- 无登录态：页面显示 "Log In" 按钮（已验证）。MCF 求职者登录走 **Singpass**（未验证，常识）。→ 若为 Singpass：属于"密码/证件级"关口，Agent 永不操作（等同 BRIEF §3 密码/OTP），挂起 `pending_user`，由用户本人在同一 Chrome 完成登录后说"继续"。

## 3. 账号注册关口
- MCF 无独立注册，账号与 Singpass 绑定（未验证）。Agent 可预填字段：无。必停：整个登录过程。
- 运行时差异只引用 BRIEF D3；对 Singpass 两运行时一致：**都不碰**。
- Student's Pass 持有者是否能激活 Singpass 并使用 MCF 申请：逐字稿只提到"拿到数字 STP 后可以激活 Singpass"（逐字稿08-05 L678），MCF 侧未验证。

## 4. 表单流程步骤
- **未验证**。推测：岗位页 "Apply Now" → 登录 → 选择/上传简历 → 可选求职信/筛选题 → 提交。需试跑补证。
- 已知：2026-08-05 打开 PSA 岗位后"未进入可预填的申请表"，即未登录状态下看不到表单（逐字稿08-05 L1207）。

## 5. 字段映射
| 表单字段（推测） | profile 字段 | 备注 |
|---|---|---|
| 简历 | `materials.resume_en_path` | 未验证 |
| 求职信/附言 | `materials.cover_letter_policy` | 未验证 |
| 期望薪资 | `salary.expected_min` | 岗位页有薪资区间（已验证），表单是否问薪资未验证 |
| 联系方式 | `identity.email` / `identity.phone.*` | 若来自 Singpass MyInfo 则不可改（未验证） |

## 6. 字符上限与控件坑
- 未验证。

## 7. Save 草稿与超时策略
- 未验证。默认按 `_template.md` §7 落盘草稿。

## 8. 简历上传方式
- 未验证。默认按 `_template.md` §8 优先级；若 MCF 有"已存简历"，先核对文件名。

## 9. 开放题与声明题出现的位置
- 未验证。声明题一律只取 `policy.declarations.*`。

## 10. 成功页特征
- **未验证**。在拿到一手证据前，MCF 的"已投"证据只认：① 用户本人截图的提交成功页；② MCF/雇主回执邮件。
- 岗位卡的 "N applications" 计数不是个人证据。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 页面只有 "Log In"，无表单（08-05 L1207） | 未登录 | 挂起，用户自行 Singpass 登录 | `pending_user` |
| Jobstreet 外跳到 MCF | 平台切换 | 切本 playbook；不算 Jobstreet 申请 | — |
| 岗位薪资区间低于 `salary.floor`（岗位页已验证展示薪资） | 规则 | 跳过 | `skipped`（附 skip_reason_code） |
| 任何未验证控件报错 | 未知平台行为 | 走 `_template.md` §11 + 记 INCIDENTS | `failed`（记原因） |

## 12. 配额与节流
- 未验证。遵守全局 D13。

## 13. 已知事故
- PSA 经 Jobstreet 外跳 MCF 后停在入口，未开始表单（逐字稿08-05 L1207、L1233；Codex 记忆 "PSA redirected to MyCareersFuture"）。

## 14. 未验证项（本 playbook 大部分）
- 登录方式是否为 Singpass、Student's Pass 持有者能否使用（未验证）。
- 申请表字段、步骤、按钮文案（未验证）。
- 成功页 URL/文案、回执邮件主题（未验证）。
- 是否有已存简历库、字符上限、草稿保存（未验证）。
- **需要产品负责人补充**：在已登录 Chrome 里投一份 MCF 岗位到成功页，把 URL/文案/回执主题回填本文件 §4、§5、§10。

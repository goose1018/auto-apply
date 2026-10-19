# Workable

> 证据充分度：**中低**（EPOS 一份成功回执；PRISM+、Decathlon 卡在声明题/上传；URL 模式与完整字段未验证）。来源缩写见 `README.md` §3。

## 1. 识别特征
- URL 模式 `https://apply.workable.com/<company>/j/<id>/`：**未验证**（逐字稿未记录 Workable URL，仅按常识推断）。
- 已验证特征：官方回执文案 "Your application has been submitted successfully."（L276）；Jobstreet 外跳"直达雇主 Workable 表单"（PRISM+，L3393）。
- Plan §1 未单列；台账 §一 EPOS（Workable 回执）。

## 2. 登录态检测
- 免登录（EPOS "正式申请页不需要新建账号"，L272）。
- 无 OTP/CAPTCHA（2026-08 未遇到；未验证）。

## 3. 账号注册关口
- 不适用。运行时差异只引用 BRIEF D3。

## 4. 表单流程步骤（单页，推断）
1. Personal information：姓名、邮箱、电话、地址。
2. Resume 上传（部分租户必填：Decathlon，L5072）；可能带解析。
3. Cover letter / Summary（可选）。
4. 公司自定义题：工作授权、实习类型、司法记录声明（PRISM+，L2500、L304）。
5. Submit → 回执文案。
- 精确页序与按钮文案 **未验证**。

## 5. 字段映射
| 表单字段 | profile 字段 | 备注 |
|---|---|---|
| First / Last name / Email / Phone | `identity.*` | |
| Address | `identity.address.*` | 未验证是否必填 |
| Resume | `materials.resume_en_path` | Decathlon 必填（L5072） |
| Legally authorised to work in Singapore | `status.authorized_to_work_internship` | EPOS 记录填 Yes（L729-731） |
| Internship type（自由文本） | `status.credit_bearing` + `intent.full_time` → 文本 | EPOS 填"full-time, credit-bearing internship"（L729） |
| Criminal record declaration（PRISM+） | `policy.declarations.criminal_record` | 未预设 → 挂起（L2500） |
| Cover letter | Content Agent（D9） | |

## 6. 字符上限与控件坑
- 字符上限 **未验证**。
- PRISM+ 表单**残留旧简历**（Chrome 已挂旧文件），且新上传被扩展权限拦（L2500、L3397）→ 必须核对附件文件名，不用旧版硬投。

## 7. Save 草稿与超时策略
- 无草稿（未验证）；单页短表。断连后重填，提交前查台账。

## 8. 简历上传方式
- 页面文件控件；受扩展 file URL 权限约束（PRISM+ L3397、Decathlon L5072）。
- 曾出现"第二次 Workable 上传未确认"（Codex 记忆 MEMORY L1127）→ 上传后必须核对显示的文件名。
- 平台已存简历：无。

## 9. 开放题与声明题出现的位置
- 自定义题在简历之后：工作授权（EPOS）、**司法记录**（PRISM+，L2500）→ 只取 `policy.declarations.criminal_record`，未预设挂起。
- 开放题未遇到（未验证）。

## 10. 成功页特征
- 回执文案 "Your application has been submitted successfully."（EPOS，L276）。
- 回执邮件：EPOS 收到"确认提交，正在审核"自动邮件（L708、L718）——属自动回执，不是进展。
- 成功页 URL **未验证**。

## 11. 失败模式与处理
| 现象 | 判断 | 动作 | 记账 |
|---|---|---|---|
| 司法记录必答且未预设（L2500） | 声明关口 | 挂起 | `pending_user` |
| 附件为旧简历且无法替换（L2500、L3397） | 版本 | 不提交；开权限后重传 | `failed`（记原因） |
| Resume 必填而无法上传（L5072） | 通道 | 跳过 | `failed`（记原因） |
| 简历 PDF 联系方式与表单不一致（L288，PRISM+ 暂停） | R3 一致性门 | 挂起报警 | `pending_user` |

## 12. 配额与节流
- 未观察到配额。全局 D13。

## 13. 已知事故
- PRISM+：司法记录题 + 旧简历残留 + 上传被拦，三重阻塞（L2500、L3393-3397、L304）。
- PRISM+ 提交前发现 PDF 上的联系方式是旧的，与表单不一致 → 暂停（逐字稿08-07b L288）→ R3 由此而来。
- Decathlon Resume 必填上传阻塞（L5072）。

## 14. 未验证项
- URL 模式 `apply.workable.com/...`（未验证）。
- 表单页序、字段清单、字符上限、CAPTCHA（未验证）。
- 成功页 URL、回执邮件主题（未验证）。
- 是否有简历解析自动填充（未验证）。

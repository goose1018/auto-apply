# playbooks/ — 平台识别与使用说明

> 每个 ATS 一份 playbook（BRIEF R5、D5）。结构统一见 `_template.md`。
> Executor 在打开 `apply_url` 后，先按下表识别平台 → 加载对应 playbook → 按 14 节执行；识别不到则走 `_template.md` 通用流程并记 INCIDENTS。

## 1. 平台识别表（URL 模式 → playbook）

| 平台 | URL 模式（按优先级匹配） | 页面特征 | playbook | 证据 |
|---|---|---|---|---|
| Jobstreet / SEEK | `sg.jobstreet.com/job/<id>`；申请页 `…/job/<id>/apply`；成功页 `…/job/<id>/apply/success`；外跳页 `…/job/<id>/apply/external`（标题 "Visited external site \| Jobstreet"）；登录 `login.seek.com/login?…realm=Username-Password-Authentication…`（Auth0） | "Quick apply" / "Apply" 按钮；成功页带推荐岗位 | `jobstreet.md` | 已验证（台账 §一；逐字稿 L375；逐字稿08-13b L925） |
| LinkedIn Easy Apply | `linkedin.com/jobs/view/<id>`、`linkedin.com/jobs/…`；申请弹窗内标题 "Easy Apply" | 站内弹窗分步表单；"Applied"/"已申请" 追踪器 | `linkedin.md` | 已验证（逐字稿 L4195、L4778、L4850） |
| MyCareersFuture | `www.mycareersfuture.gov.sg/job/<category>/<slug>-<hash>`；岗位编号 `MCF-<yyyy>-<n>`；雇主端 `employer.mycareersfuture.gov.sg` | 政府站头 "A Singapore Government Agency Website"；"Log In" 按钮；页脚 "Powered by X0PA AI" | `mycareersfuture.md` | 已验证（逐字稿08-13b L4829-4950） |
| Workday | `<company>.wd<n>.myworkdayjobs.com/<locale>/<site>/job/<location>/<slug>_<ReqId>`（如 `wd1` `wd3` `wd5`） | 分步进度 "1/6…6/6"；"Candidate Home"；提交后弹 "Application Submitted" | `workday.md` | 已验证（逐字稿 L2620、L2846、L3171、L3264） |
| SuccessFactors | 公司品牌域 + `/job/<slug>/<10位数字>/`（如 `careers.nets.com.sg/job/…/1361408966/`、`jobs.temasek.com.sg/job/…/1369200757/`、`groupcareers.singtel.com/job/…/1363401866/`）；登录跳转 `career<n>.successfactors.eu/careers?company=<id>`（标题 "Career Opportunities: Sign In"，参数含 `clientId=jobs2web`） | "Already have an account?" + "Create an account" | `successfactors.md` | 已验证（逐字稿 L363；逐字稿08-07b L340-353；逐字稿08-13b L2129、L4265） |
| Greenhouse | `job-boards.greenhouse.io/<company>/jobs/<id>`、`boards.greenhouse.io/<company>/jobs/<id>`；公司自建域嵌入 Greenhouse 表单（如 Citadel/Marshall Wace/Workato/DRW，未从 URL 逐一核实） | "Attach / Enter manually" 简历控件；提交前邮箱 8 位验证码 | `greenhouse.md` | 已验证（逐字稿 L2622、L4866、L7027） |
| Ashby | `jobs.ashbyhq.com/<company>/<uuid>`；申请页 `…/<uuid>/application` | 单页表单；成功文案 "Your application was successfully submitted" | `ashby.md` | 已验证（逐字稿 L2616、L2699、L2920） |
| SmartRecruiters | `jobs.smartrecruiters.com/<Company>/<19位数字>-<slug>` | 简历解析后自动展开经历/教育；最后一页折叠必答题；成功文案 "Application submitted!" | `smartrecruiters.md` | 已验证（逐字稿 L362、L6772、L4023） |
| Lever | `jobs.lever.co/<company>/<uuid>` | 单页表单；"Current location" 自动完成；成功文案 "Application submitted!" | `lever.md` | 已验证（逐字稿 L2621、L2675、L3649、L3887） |
| Workable | `apply.workable.com/<company>/j/<id>`（URL 模式未验证，仅推断）；已验证特征为回执文案 | 回执 "Your application has been submitted successfully." | `workable.md` | 文案已验证（逐字稿 L276）；URL 未验证 |

**识别顺序建议**：先匹配 URL 主域 → 再看页面标题/品牌 → 最后看控件文案。Jobstreet 的 "Apply" 经常外跳到公司 ATS（`/apply/external`），外跳后必须**重新识别**目标平台（已验证：PSA→MyCareersFuture、Singtel→官方站、NCS→SmartRecruiters，逐字稿08-05 L814、L1207）。

## 2. 遇到未知平台怎么办
1. 不要硬填。先按 `_template.md` §1 记录识别字段（域名、标题、步骤数、是否强制登录、是否要上传简历）。
2. 走 `_template.md` 通用流程：登录态检测 → 注册关口 → 分步填表 → 声明题只取 `policy.declarations.*` → 成功页证据。
3. 提交前复核清单（`checklists/pre_submit.md`）照常执行；缺证据不得记 `applied`（须有合格证据，否则 `submitted_unverified`）。
4. 由 Orchestrator 向 `INCIDENTS.md` 追加一条：平台识别字段 + 卡点 + 成功页特征（若拿到）。累计 ≥2 家公司同平台 → 立项写新 playbook。
5. 2026-08 遇到过、但**不在 v1 平台集**的自建/其他 ATS（仅供识别参考，不写 playbook）：Apple Jobs（需 Apple Account + 2FA）、Bank of America（`bankcampuscareers.tal.net`，CAPTCHA + APAC 每季 ≤2 份）、Shopee 官方站（成功文案 "Successfully submitted!"）、Infineon 官方站（成功文案 "Thank you for your application, <FirstName>!"，需成绩单）、StarHub "Skye" 流程、InternSG 表单（reCAPTCHA）、Micron Eightfold 入口（不接受自动选文件；改走 Workday）、Schneider 官方表（hCaptcha；地址校验故障）、Optiver/Jane Street 自建表单、京东校招。来源：逐字稿 L2886、L3175、L3453、L3677、L5056、L5060、L3769、L5191、L7232、L3919。

## 3. 证据来源缩写（各 playbook 通用）
| 缩写 | 文件 |
|---|---|
| 逐字稿 L#### | `~/codex-chat-export/2026-08-07/16-24-12 继续投递简历 [57727641e3e8].md`（9003 行主逐字稿） |
| 逐字稿08-05 L#### | `~/codex-chat-export/2026-08-05/13-48-41 简历与英文面试准备 [38a8e289250d].md` |
| 逐字稿08-07b L#### | `~/codex-chat-export/2026-08-07/18-38-30 目前应该是要继续帮我投简历 但是一直没动几个 [93d91d0951b6].md` |
| 逐字稿08-13b L#### | `~/codex-chat-export/2026-08-13/11-52-58 The following is the Codex agent history … [58607a90487a].md` |
| 台账 §n | `~/Documents/Codex/投递台账.md`（§一 已确认 / §二 中间状态 / §三 规则 / §四 状态表） |
| Plan §1 | `~/Documents/Codex/2026-09-04/自动投递工作流_Plan与需求确认_v0.md` §1 平台坑位表 |
| SKILL | `~/.claude/skills/job-apply/SKILL.md` |

## 4. 跨平台共性规则（各 playbook 默认继承）
- **签证三问拆分**（已验证，逐字稿 L2651-2657、L2703-2706）：`status.authorized_to_work_internship` / `status.requires_sponsorship_internship` / `status.requires_sponsorship_future` 是三个独立字段；下拉无对应项时挂起，不选近似项（已验证：Jobstreet 无 Student's Pass 选项，逐字稿08-05 L1017）。
- **地点以公司官网为准**（已验证，逐字稿 L7396-7410）：LinkedIn/聚合站标"Singapore"不算数；隐藏字段 `job_location` 也要读（Citadel 案例）。`Hong Kong / Taipei / Asia / APAC / Remote / Hybrid` 不自动等于新加坡。
- **简历版本核对**（已验证，逐字稿 L1363、L5153、L7272）：平台已存简历常是旧文件名/旧版本；上传或复用前比对 `materials.resume_en_path` 文件名（可选哈希）。
- **解析器污染**（已验证，逐字稿 L3272、L3457、L3505）：简历解析常把项目当工作经历、把年份填错、混入无关 URL；保存前逐项与 profile 比对。
- **毕业年份漂移**（已验证，逐字稿 L4043、L4047；SKILL）：系统常把毕业年份落到错误年份，提交前必核（R10）。
- **上传通道**：见 `_template.md` §8；Chrome 扩展 "Allow access to file URLs" 是 2026-08 最频繁的单点故障（逐字稿 L72、L2545、L4862、L7003）。
- **"已投"证据**：只认职位级成功页 / 候选人主页状态 / 雇主·ATS 回执邮件（BRIEF §3）。

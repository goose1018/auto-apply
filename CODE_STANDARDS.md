# CODE_STANDARDS — 代码与文档规范

> 适用范围：`~/cursor/auto-apply/` 全部代码与文档。状态：Phase 1 初版，2026-09-05。
> 与 `BRIEF.md` 冲突以 BRIEF 为准；包与目录的具体布局以 `ARCHITECTURE.md` 为准，本文只规定"怎么写"。
> 继承 `~/cursor/PROJECT_PLAYBOOK.md` 的精神（不验证不算完成 / 真实链路零 mock / 密钥不进仓库 / fail loud），但技术栈不同：Python 标准库、无服务器、无 npm、无 API key、无第三方依赖。

---

## 0. 五条硬规则（凌驾本文其余内容）

1. **不验证不算完成。** 每个功能对应一个 `scripts/verify/<功能>.py`；"功能完成" = 它的 verify 脚本存在且通过。
2. **真实链路零 mock。** 假数据只允许出现在 `tests/fixtures/` 与 verify 脚本自建的临时目录里；`skills/auto-apply/` 下不得有任何示例值、占位值、硬编码个人信息。
3. **个人数据永不进仓库、日志、截图、会话。** 详见 `SECURITY.md`。
4. **Fail loud。** 关键数据缺失、schema 不合、证据不足时抛异常并以非零退出码结束；禁止静默降级、禁止"先默认一个值"。
5. **诚实标灰。** 文档里任何"支持 / 已完成 / 可用"必须带验证方式；没有就写 `[未验证]`。禁止假绿、假数据、假装闭环。

---

## 1. 语言与运行环境

- Python **3.9+**，**仅标准库**。常用：`argparse` `dataclasses` `json` `sqlite3` `pathlib` `logging` `re` `datetime` `typing` `unittest` `tempfile` `hashlib` `shutil` `textwrap` `html.parser`。
- 禁止：任何 pip 依赖；`requests` / `playwright` / `selenium` / `bs4`；任何对 ATS 或招聘平台的 HTTP 直连（BRIEF D15）。Python 只做确定性工作：校验、查重、台账、导出、运行状态、自检。浏览器操作全部由会话内 Agent 通过运行时工具完成。
- **版本底线定为 3.9（非 3.11）**：目标用户是学生，macOS 自带 `/usr/bin/python3` 就是 3.9.6，D12「用户零安装」的前提就是不强制用户装新解释器；3.9 已足以满足本项目全部语法与标准库需求。**版本门必须显式写，且没有覆盖变量**：每个可执行入口第一件事是：

  ```python
  import sys
  if sys.version_info < (3, 9):
      sys.exit("auto-apply 需要 Python 3.9+，当前 %d.%d" % sys.version_info[:2])
  ```

- **新代码禁止使用 3.10+ 专有语法**：`match` 语句、运行时求值的 `X | Y` 类型联合（`isinstance`/默认值等位置）、`dataclass(slots=True)`、`itertools.pairwise`、`tomllib`、`typing.Self` 等。类型注解一律配 `from __future__ import annotations`，用 `Optional[X]` / `Union[X, Y]`（而非 `X | Y`）书写注解本体；`from __future__ import annotations` 下注解不在运行时求值，但仍写 3.9 兼容形式以防未来有代码读取 `__annotations__` 或用 `typing.get_type_hints()`。
- 开发辅助工具（pytest / mypy / ruff）可选，不得成为运行依赖；verify 脚本与 tests 不得假设它们已安装。
- 文件编码 UTF-8，换行 LF，4 空格缩进，行宽建议 100。

---

## 2. 模块分层（禁止反向依赖）

Python 包位于 `skills/auto-apply/scripts/autoapply/`，模块清单与 CLI verb 由 `ARCHITECTURE.md` §1.3 定义（扁平布局，统一入口 `AA <verb>`）。本节把这些模块分成三层；层是**角色**不是子包，`layering.py` 用显式的"模块 → 层"映射表检查。

| 层 | 模块（ARCHITECTURE §1.3 名） | 职责 | 允许 import | 禁止 |
|---|---|---|---|---|
| **入口层** | `__main__.py`（argparse 分发） | 解析参数、经 `paths` 取路径、调业务层、打印结果、退出码 | 业务层、工具层 | 写业务规则；直接开 SQLite |
| **业务层** | `validate` `dedup` `ledger` `export_md` `runstate` `pending` `evidence` `consistency` `presubmit` `quota` `selfcheck` `migrate_legacy_ledger` `report` | 校验、查重、台账、证据判定、状态机、配额、导出 | 工具层；同层之间只允许 `ledger` / `runstate` / `pending` 被其他业务模块 import（防环） | `print()`；`os.environ`；读 `secrets.env`；import 入口层 |
| **工具层** | `paths` `schema` `normalize` `redact`（及架构后续新增的纯工具） | 路径解析、JSON Schema 校验器、规范化、脱敏 | 仅标准库 | import 业务层或入口层；除 `paths` 外读 `os.environ` |

- 依赖方向只能是 入口 → 业务 → 工具。
- `os.environ` 只允许出现在 `paths.py`（数据目录解析）与 `__main__.py`；其他模块通过参数拿 `Path`。
- `scripts/verify/*.py` 与 `tests/*.py` 可以 import 任意层，但**不得被任何层 import**。
- 每个 verb 失败时 stderr 输出**一行 JSON**（`{"error": "<code>", "detail": "<不含个人数据的说明>"}`），退出码见 §5（ARCHITECTURE §1.3）。
- **强制执行**：`scripts/verify/layering.py` 按映射表扫描 `import` 与 `os.environ`，违规即 FAIL；架构新增模块必须同时加进映射表，否则按"未知模块"FAIL。

---

## 3. 命名

| 对象 | 规则 | 例 |
|---|---|---|
| 模块 / 函数 / 变量 | `snake_case`，动词开头的函数 | `normalize_company()`, `record_application()` |
| 类 | `PascalCase`；数据记录用 `@dataclass(frozen=True)` | `ApplicationRecord`, `GateEvent` |
| 常量 | `UPPER_SNAKE` | `DAILY_CAP_DEFAULT = 20` |
| 台账 / schema 字段 | 英文 `snake_case`，与 `schemas/*.json` 及 ARCHITECTURE §9 DDL 一字不差 | `company_norm`, `title_norm`, `evidence_type` |
| 状态枚举 | 小写英文字符串，只用 ARCHITECTURE §9 的枚举值，集中定义在一处，禁止散落字面量 | `"applied"`, `"pending_user"`, `"skipped"` |
| 用户可见文案 | 走 i18n 表（工具层模块，架构未命名，建议 `i18n.py` 并加入 §2 映射表；zh / en 两列），代码里不出现裸中文/英文提示 | `t("gate.password_required", lang)` |
| verify 脚本 | `scripts/verify/<功能名>.py`，功能名与 DoD 条目对应 | `ledger_dedupe.py`, `screening_hard_filters.py` |
| 测试文件 | `tests/test_<模块>.py` | `tests/test_normalize.py` |
| run_id / app_id / job_id | 以 ARCHITECTURE §5.1 为准（`run_<YYYYMMDD>_<HHMMSS>`、`app_<YYYYMMDD>_<6hex>`、`job_<12hex>`） | `run_20260905_140211` |

布尔值命名要能读成问句：`is_duplicate`, `has_evidence`, `needs_user_action`。

---

## 4. 类型注解

- 所有公开函数、方法、dataclass 字段必须有类型注解；模块顶部 `from __future__ import annotations`。
- JSON 结构用 `TypedDict` 或 `dataclass` 描述，不用裸 `dict[str, Any]` 穿透多层。
- 返回 `None` 表示"不存在"的地方必须写 `-> X | None`，调用方必须处理 `None` 分支（否则违反 fail loud）。
- `Any` 只允许出现在 JSON 解析的边界函数内部，出边界前必须校验并收窄。
- mypy 若本机可用，`mypy --strict skills/auto-apply/scripts/autoapply` 应零错误；不可用时不阻塞，但评审者可要求作者说明。

---

## 5. 错误处理：fail loud

- 异常层级集中定义：`AutoApplyError` → `ProfileError` / `SchemaError` / `LedgerError` / `EvidenceError` / `GateError` / `ConfigError`。异常消息**不得包含个人数据**（写字段名，不写字段值）。
- 禁止裸 `except:` 与 `except Exception: pass`。捕获后要么重新抛出，要么转换为上述异常并保留 `from e`。
- 关键数据缺失（profile 必填字段、简历路径、台账文件、schema 文件）= 抛异常，不默认、不猜、不跳过。
- 证据不足时**禁止**写入 `applied` 状态：`ledger upsert-app --status applied` 在没有 `evidence.qualifies=1` 记录时必须抛 `EvidenceError` 并以退出码 3 结束（ARCHITECTURE §7.1 / §9 `applied-has-evidence` 断言；这是 BRIEF 硬边界"已投标准"在代码层的落点）。`qualifies` 只能由 `evidence.py` 判定写入，Agent 不得手写 1。
- 退出码约定（入口层统一）：

  | 码 | 含义 |
  |---|---|
  | 0 | 成功 / verify PASS |
  | 1 | verify FAIL 或业务断言失败 |
  | 2 | 用法 / 配置错误（缺参数、缺环境、Python 版本不够、非法状态转移） |
  | 3 | 数据完整性错误（schema 不合、台账损坏、`applied` 无合格证据、`ledger assert` 失败） |

- 用户可见的错误提示写"发生了什么 + 下一步做什么"，不写堆栈；堆栈进日志文件。

---

## 6. 日志与脱敏

### 6.1 去向
- 标准库 `logging`；一个工具层模块（架构未命名，建议 `logging_setup.py`，加入 §2 映射表）提供 `get_logger(name)`，所有模块只用它；handler 输出 JSON 行并在写出前调用 `redact()`。
- 日志文件只写到 `~/auto-apply-data/<profile_id>/runs/<run_id>/log.jsonl`（ARCHITECTURE §5.3），**永不**写入仓库目录。
- 默认 INFO。DEBUG 也**不得**打印表单值、页面 HTML、cookie、带 token 的 URL。

### 6.2 记录什么
一行一个 JSON 事件（`log.jsonl`），键名与 `events` 表对齐（`at` / `kind` / `actor` / `run_id` / `app_id` / `payload`，`kind` 只用 ARCHITECTURE §9 枚举），例：

```
{"at":"2026-09-05T14:02:11+08:00","level":"INFO","kind":"applied","actor":"qa","run_id":"run_20260905_140000","app_id":"app_20260905_a1b2c3","payload":{"company":"Example Robotics","title":"Data Intern","platform":"greenhouse","evidence_type":"success_page"}}
{"at":"2026-09-05T14:05:40+08:00","level":"WARN","kind":"gate_opened","actor":"executor","run_id":"run_20260905_140000","app_id":"app_20260905_d4e5f6","payload":{"gate_type":"captcha","company":"Example Robotics"}}
```

公司名、岗位名、平台、状态、run_id、证据类型可以进日志；用户的姓名、邮箱、手机、地址、任何声明题答案不进日志。

### 6.3 脱敏函数（`redact.py`，全项目唯一实现）

| 函数 | 输入 | 输出 |
|---|---|---|
| `mask_email(s)` | `alex.tan@example.com` | `a***@example.com` |
| `mask_phone(s)` | `+65 0000 1234` | `+65 ****1234`（保留区号 + 末 4 位） |
| `mask_name(s)` | `Alex Tan` / `李明` | `A** T**` / `李*`（每个词保留首字符） |
| `redact(text)` | 任意字符串 | 用正则替换其中的邮箱 / 手机 / NRIC-FIN 模式（`[STFGM]\d{7}[A-Z]`）为 `[REDACTED:<kind>]` |

- 任何要进日志、异常消息、导出摘要、汇报文案的字符串，若可能含用户输入，必须先过 `redact()`。
- `redact()` 检测到 NRIC/FIN 或疑似密码键（`password=`、`JOB_ACCOUNT_PASSWORD=`）时，除替换外还要 `logger.error("redaction hit kind=nric")` 并抛 `RedactionError` —— 出现这种值本身就是 bug，不能静默放过。异常消息只写 kind，不写值。
- 汇报（Reporter）给用户看的内容可以显示用户自己的姓名邮箱，但导出到 `exports/` 的 Markdown 台账默认不含联系方式。

### 6.4 禁止事项
- 禁止 `print(profile)`、`logger.debug(form_data)` 之类整对象输出。
- 禁止把页面截图路径以外的页面内容写日志。
- 禁止在日志里记录 `secrets.env` 是否存在以外的任何信息；Python 包**永不读取** `secrets.env`（BRIEF D3：只有 Codex 运行时适配层在填密码框那一步读取，且不回显）。

---

## 7. SQLite 与数据文件

- 只用 `sqlite3`。连接时 `PRAGMA foreign_keys = ON`、`PRAGMA journal_mode = WAL`；写操作走事务，异常回滚。
- DDL 以 ARCHITECTURE §9 为准；schema 版本存 `meta.schema_version`。表结构变更 = 编号迁移文件 `migrations/NNN_<说明>.sql`，由 `ledger.py` 按版本顺序执行；禁止在代码里 `ALTER TABLE` 散写。
- 时间戳统一 ISO-8601 含时区偏移（`2026-09-05T14:02:11+08:00`），存字符串，不存本地时间无偏移。
- `jobs.dedup_key`（`normalize(company)|normalize(title)`，BRIEF R1 / ARCHITECTURE §6）是 `UNIQUE` 约束，不只靠应用层判断。
- `status='applied'` 必须有 ≥ 1 条 `evidence.qualifies=1`（跨表，CHECK 表达不了）：`ledger upsert-app` 写入前强制跑 `applied-has-evidence` 断言，失败拒写、退出码 3（BRIEF §3 硬边界"已投标准"）；verify 脚本断言违规写入必失败。ARCHITECTURE §9 的另外三条断言（`unique-vs-actions`、`no-secrets`、`per-company-cap`）同样要有 verify。
- 所有数据文件只在 `AUTO_APPLY_DATA_DIR` 下；代码里禁止出现 `~/Documents`、`/Users/...` 之类绝对路径。

---

## 8. verify 脚本规范

### 8.1 每个脚本
- 路径 `scripts/verify/<功能>.py`，可直接 `python3` 执行，顶部版本门（§1）。
- **打真实文件、真实 SQLite**：在 `tempfile.TemporaryDirectory()` 里设置 `AUTO_APPLY_DATA_DIR`，走与生产完全相同的代码路径建库、写入、导出；不 mock 函数、不 monkeypatch。
- **永不**触碰用户真实数据目录：脚本开头强制覆盖 `os.environ["AUTO_APPLY_DATA_DIR"]` 为临时目录；若检测到它仍指向 `~/auto-apply-data`，直接 FAIL。
- 覆盖：**主成功路径 + 至少一个失败/边界路径**（例：同岗两渠道只计 1；无证据写 submitted 必须抛错；缺必填字段必须抛错）。
- 输出契约：最后一行是 `PASS <功能>: <一句话说明验证了什么>` 或 `FAIL <功能>: <原因>`；退出码 0 / 1。既没有 PASS 也没有 FAIL 行 = 视为 FAIL。
- 一个断言失败立即停止，不"继续跑完再总结"（fail loud）。
- 可重复执行、不依赖网络、不依赖浏览器、单个脚本 120 秒内完成。

### 8.2 骨架

```python
#!/usr/bin/env python3
"""verify: ledger_dedupe — 去重键与计数口径（BRIEF R1）。
主路径：同一 company+title 经两个渠道记录，去重岗位数=1，提交动作数=2。
失败路径：无 qualifies=1 证据却写 applied → 必须被拒绝（退出码 3）。
"""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit("需要 Python 3.9+")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "auto-apply" / "scripts"))
NAME = "ledger_dedupe"

def check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL {NAME}: {msg}")
        sys.exit(1)

def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["AUTO_APPLY_DATA_DIR"] = td
        # ... 走真实代码路径建库、写入、查询 ...
        check(True, "示例断言")
    print(f"PASS {NAME}: 去重键生效，无合格证据写 applied 被拒绝")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 8.3 `scripts/verify/all.py`
- 枚举 `scripts/verify/*.py`（排除 `all.py` 与 `_` 开头文件），按文件名排序，用**当前解释器**逐个 `subprocess.run`，单个超时 120 秒。
- 打印表格：脚本名 / PASS|FAIL|TIMEOUT|NO-VERDICT / 耗时 / 最后一行。
- 任一非 PASS → 退出码 1，并在末尾列出失败脚本清单。禁止 `--skip-failed` 之类开关。
- 末行固定格式：`SUMMARY passed=<n> failed=<m> total=<t>`，供评审引用。

### 8.4 必须存在的基础 verify（Phase 1）
| 脚本 | 断言 |
|---|---|
| `layering.py` | 按 §2 映射表：无反向 import；业务层 / 工具层无 `print`；`os.environ` 只在 `paths.py` 与 `__main__.py`；未知模块 FAIL |
| `no_pii_in_repo.py` | 仓库内无邮箱（除 `example.com/.sg/.org`）、无 `+65`/`+86` 手机（虚构号段 `+65 0000 xxxx` 白名单）、无 NRIC/FIN 模式、无 `JOB_ACCOUNT_PASSWORD=` 带值、代码中无读取 `secrets.env`、无 `~/auto-apply-data` 之外的真实数据路径 |
| `schema_examples.py` | `examples/*.json` 全部通过对应 schema；且不含真实个人数据模式 |
| `ledger_applied_has_evidence.py` | 无 `qualifies=1` 证据写 `applied` 被拒（退出码 3）；有合格证据成功；`unique-vs-actions` / `no-secrets` / `per-company-cap` 三条断言各有主路径 + 失败路径 |
| `docs_status_tags.py` | 所有 `*.md` 中每个"已验证"标签同一行必须带来源或验证方式（两种写法见 §10.1）；`agents/`、`playbooks/` 每个文件头部有状态 / 置信度行；playbook 含 ARCHITECTURE §10.2 要求的章节 |

---

## 9. 测试约定

- 框架：标准库 `unittest`（`python3 -m unittest discover -s tests -v`）。pytest 若本机有也能跑，但仓库不依赖它。
- 单测面向工具层与业务层的纯函数（normalize、redact、筛选规则、去重键）；跨文件、跨 SQLite 的行为放 verify 脚本，两者不重复。
- `tests/fixtures/`：假 ATS 页面文本片段、虚构 profile、虚构简历解析结果。**人物、邮箱、电话一律虚构**：姓名如 `Alex Tan` / `Priya Nair` / `李明`，邮箱只用 `example.com` / `example.sg`，电话只用 `+65 0000 xxxx` 这类明显无效号段，公司用 `Example Robotics Pte Ltd` 之类。真实公司名只允许出现在 playbooks 与 INCIDENTS（那是平台事实，不是个人数据）。
- 每个 fixture 文件头部一行注释说明来源与脱敏方式（"手写虚构" / "从 2026-08 真实页面结构改写，已去除全部个人字段"）。
- 测试不写用户真实数据目录；需要目录就 `tempfile`。

---

## 10. Markdown 文档约定

- 中文为主；README 含英文安装段；SECURITY 关键段附英文；用户可见问诊文件 `.zh.md` / `.en.md` 成对。
- 每个文档以引用块开头：适用范围 / 状态 / 日期 / 上位文件（冲突以谁为准）。
- 标题层级：`#` 文件名级标题一个；`##` 编号章节；`###` 小节。列表能用表格就用表格。
- 术语固定：母清单、台账、关口、挂起、证据、去重岗位、提交动作、运行时（Claude Code / Codex）、profile、facts_card。不要同义词混用。
- 中文标点在中文句子里；平台名、控件名、字段名保留原文（Easy Apply、Workday、`Current location`）。
- 数字口径必须写清"数什么"：`去重岗位 92 / 提交动作 102`，禁止裸写"投了 100 份"。

### 10.1 状态标签（全项目统一、可被脚本检查）

| 标签 | 含义 | 要求 |
|---|---|---|
| `[已验证 <方式>]` | 有可重跑的证明 | 同一行必须有 `验证: <命令或路径>` |
| `[部分验证]` | 主路径有证据、边界没有 | 写明哪部分没验 |
| `[未验证]` | 设计了、没跑过，或平台行为只是听说 | 默认值：拿不准就用它 |
| `[需你出面]` | 人机关口，Agent 必须停 | 写明停在哪、用户做什么 |
| `[不做]` | 明确 scope 外 | 写明原因或 BRIEF 决策号 |

不用颜色、不用 emoji 表达状态；只用上述文字标签。

两种等价写法都接受，脚本都识别：方括号式 `[已验证 verify ledger_dedupe.py]` / `[未验证]`（规范类文档），或 `playbooks/` 现行的加粗式 **已验证（逐字稿 L2675）** / **未验证**（来源缩写见 `skills/auto-apply/playbooks/README.md` §3）。共同底线：出现"已验证"三个字的那一行必须能找到来源或验证方式，否则 `docs_status_tags.py` FAIL。

### 10.2 证据引用格式

```
证据：台账 2026-08-25 Temasek / Generative AI Citizen Developer Intern
证据：codex-export 2026-08-07/16-24-12 继续投递简历 :L2675
证据：evidence/app_20260905_a1b2c3/01_success_page.png（本机，不在仓库）
证据：scripts/verify/ledger_dedupe.py -> PASS（2026-09-05）
```

平台行为的描述必须带**观察日期 + 运行时**：`（观察 2026-08-07，Codex 内置浏览器）`。没有观察记录就 `[未验证]`。

---

## 11. `agents/*.md` 与 `playbooks/*.md` 写作规范

结构由架构定义：agents 固定 7 个二级标题（职责 / 输入 / 输出 / 可用工具 / 关口 / 禁止 / 完成标准，ARCHITECTURE §10.1）；playbooks 以 ARCHITECTURE §10.2 与 `playbooks/_template.md` 为准（截至 2026-09-05 两者分别为 15 节与 14 节，尚未对齐，以产品负责人裁定为准）。本节只规定怎么填。

### 11.1 语气
- 祈使句、短句、平实。写给一个要照着执行的 Agent 看，不是写给用户看的宣传。
- 禁止修饰词："轻松""强大""智能地""完美""无缝""一键"；禁止感叹号；禁止表演式热情。
- 平台行为不用"总是 / 永远 / 一定"，用"观察到（日期）"。
- 数量（每轮 10 份、每日 20、同公司 3）只从 BRIEF D13 引用并标注来源，不自创。

### 11.2 agents/*.md 必须满足
- **可用工具**段里每个工具都能对应到 `runtime/claude-code.md` 或 `runtime/codex.md` 的映射，脚本 verb 与 ARCHITECTURE §1.3 一致；没有映射的写 `[未验证]`。
- **关口**段列出：停下的触发条件 → 写入 `pending_actions.md` 的字段 → 恢复条件。不得写"必要时请用户处理"这种模糊句。
- **禁止**段至少复述与本 Agent 直接相关的硬边界原文（BRIEF §3）和 SECURITY 条款编号，不能只写"见 SECURITY.md"。
- **完成标准**必须是可检查的事实：某文件存在、台账某行状态、某 verify 通过。"用户满意"不是完成标准。
- 示例一律虚构人物（§9），不出现产品负责人或任何真实个人的信息。
- 头部状态行：`状态：[未验证] | [部分验证] | [已验证 <方式>]`，Phase 1 一律 `[未验证]`。

### 11.3 playbooks/*.md 必须满足
- 头部引用块：适用公司示例 / 最后核实日期 / 核实人 / 置信度或证据充分度（ARCHITECTURE §10.2 与 `_template.md` 的头部格式）；观察时的运行时写在证据来源里。
- 三个必填章节，不知道就写"未验证"，不得留空或猜：**字符上限与控件坑**、**Save 与超时策略**、**成功页特征**（QA 可判定的具体文本或 URL 模式，并写明对应 `evidence_type`；"通常会显示成功"不合格）。
- 状态词只用 ARCHITECTURE §9 的 `applications.status` / `skip_reason_code` / `gate_type` 枚举；playbook 里出现的任何其他状态词视为未对齐，评审 FAIL。
- 每个"坑"固定五行：现象 / 触发条件 / 对策 / 证据（§10.2 格式）/ 状态标签。
- `INCIDENTS.md` 中标 R5 的每条事故，对应 playbook 的"已知事故"章节必须引用其编号，反向亦然（verify `docs_status_tags.py` 可扩展检查）。运行时遇到的新坑先写在 `runs/<run_id>/` 的脱敏记录里，经 PR 进 playbook 与 INCIDENTS；不由 Agent 在用户机器上直接改仓库文件。
- 回写流程：用户踩坑 → 脱敏证据（页面文本片段或打码截图） → PR。PR 中不得含任何个人数据，评审者按 §13 检查。

---

## 12. Conventional Commits（供产品负责人使用；Agent 不 commit）

```
<type>(<scope>): <subject>

<body：做了什么 / 为什么；关联 BRIEF 决策或 R 编号>

验证: python3 scripts/verify/all.py -> SUMMARY passed=12 failed=0 total=12
```

- type：`feat` `fix` `docs` `refactor` `test` `verify` `chore` `playbook` `security`。
- scope：`intake` `sourcing` `screening` `executor` `content` `qa` `tracker` `reporter` `ledger` `schema` `install` `docs` `playbook-<平台>`。
- subject ≤ 72 字符，中英皆可，不加句号。
- 动了 `schemas/` 或迁移文件：`feat(schema)!:` 并在 body 写迁移编号。
- 没有 `验证:` 行的功能提交视为不合规（docs 类除外）。

---

## 13. 独立评审协议

**评审者只读**：不改文件、不跑会改用户数据的命令；可跑 verify（它们只写临时目录）。

**输入包（作者必须给全，缺一项评审者直接退回）**
1. 任务目标与对应的 BRIEF 决策 / R 编号
2. 变更文件清单
3. 跑过的命令与**原始输出**（不是"都过了"）
4. 作者自认的风险点
5. 未验证项清单（作者自己先标灰）

**六个维度按序过**
1. 正确性：主路径、空值、重复、超长、并发写台账
2. 安全与隐私：个人数据有没有进仓库/日志/异常消息；`secrets.env` 有没有被 Python 读
3. 真实性：有没有 mock / 假数据 / 硬编码混进 `skills/auto-apply/`；有没有"未验证却标绿"
4. 事实性：平台行为、数量、限制有没有证据引用；没有的是否标了 `[未验证]`
5. 一致性：分层、命名、术语、与 BRIEF/ARCHITECTURE 是否一致
6. 可回滚：动了 schema / 迁移 / 台账格式吗；旧数据怎么办

**输出格式固定**

```
结论: PASS | CONDITIONAL | FAIL
阻塞项:
1. <文件:行> <问题> -> 违反 <规则编号> -> <需要的修复>
非阻塞建议:
- ...
复跑验证: <命令> -> <原始最后一行>
```

**硬 FAIL 条件**（任一命中即 FAIL，不得 CONDITIONAL）：任一 verify 失败；仓库含个人数据或密码；"已完成"无验证方式；违反 BRIEF 决策 / 硬边界；平台事实无证据且未标 `[未验证]`；Agent 自行 commit。

评审者不因作者解释改结论；作者修复后重新提交完整输入包。

---

## 14. DoD 模板（复制到任务汇报末尾，逐项填）

```
## DoD — <功能名>（对应 BRIEF <D/R 编号> / Phase <n>）
- [ ] 代码放在正确分层，无反向 import（verify layering.py PASS）
- [ ] verify 脚本存在：scripts/verify/<功能>.py，含主路径 + 失败路径
- [ ] python3 scripts/verify/all.py -> SUMMARY passed=<n> failed=0
- [ ] python3 -m unittest discover -s tests -> OK
- [ ] 全文搜 mock|demo|fake|TODO|FIXME|占位|hardcode，skills/ 下无残留
- [ ] no_pii_in_repo.py PASS；日志/异常消息不含个人数据
- [ ] 文档更新：相关 agents/ playbooks/ README 状态标签正确，未验证项已标灰
- [ ] 独立评审结论 PASS（附评审输出）
- [ ] HISTORY.md 当天追加：做了什么 / 为什么 / 坑
- [ ] 未 commit、未 push（交产品负责人）
未验证项：
- ...
```

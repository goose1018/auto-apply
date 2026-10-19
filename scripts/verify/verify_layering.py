#!/usr/bin/env python3
"""verify: layering — CODE_STANDARDS §2 module layers for skills/auto-apply/scripts/autoapply.
entry (cli, __main__) -> business -> tools; tools import stdlib + tools only; business may import tools and the
shared business modules {ledger, runstate, gates(pending), dedup}; no print() outside the entry layer;
os.environ only in paths.py and cli.py; nothing reads secrets.env; only standard-library imports anywhere.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SCRIPTS_DIR, Checker, version_gate  # noqa: E402

version_gate()

NAME = "layering"
c = Checker(NAME)
PKG = SCRIPTS_DIR / "autoapply"

ENTRY = {"cli", "__main__"}
BUSINESS = {"ledger", "evidence", "runstate", "gates", "queue_build", "dedup", "profile_check", "facts_render",
            "export_md", "migrate_legacy", "report", "selfcheck", "presubmit"}
TOOLS = {"enums", "errors", "paths", "ids", "redact", "normalize", "schema_validate", "i18n", "__init__"}
SHARED_BUSINESS = {"ledger", "runstate", "gates", "dedup"}
STDLIB = {
    "argparse", "ast", "dataclasses", "datetime", "difflib", "hashlib", "json", "logging", "os", "pathlib", "re",
    "secrets", "shutil", "sqlite3", "stat", "sys", "tempfile", "textwrap", "typing", "unicodedata", "subprocess",
    "time", "collections", "functools", "itertools", "io", "math", "string", "enum", "abc",
}


def imports_of(tree: ast.AST) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append((a.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            out.append((node.module or "", node.lineno))
    return out


def main() -> int:
    files = sorted(p for p in PKG.glob("*.py"))
    names = {p.stem for p in files}
    unknown = names - ENTRY - BUSINESS - TOOLS
    c.check(not unknown, "modules not in the layer map (add them to verify_layering.py): %s" % sorted(unknown))
    missing = (ENTRY | BUSINESS | TOOLS) - names
    c.check(not missing, "modules in the layer map but missing on disk: %s" % sorted(missing))
    for p in files:
        mod = p.stem
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src, str(p))
        layer = "entry" if mod in ENTRY else "business" if mod in BUSINESS else "tools"
        for imp, line in imports_of(tree):
            top = imp.split(".")[0]
            if top == "autoapply":
                target = imp.split(".")[1] if "." in imp else None
                if target is None:
                    # `from autoapply import x, y` -> names are in node.names; handled below
                    continue
                if layer == "tools":
                    c.check(target in TOOLS, "%s (tools) imports %s (line %d)" % (mod, target, line))
                elif layer == "business":
                    c.check(target in TOOLS or target in SHARED_BUSINESS, "%s (business) imports %s (line %d)" % (mod, target, line))
                    c.check(target not in ENTRY, "%s imports entry layer (line %d)" % (mod, line))
            elif top == "__future__":
                continue
            else:
                c.check(top in STDLIB, "%s imports non-stdlib or unknown module %r (line %d) — add to STDLIB if it is standard" % (mod, top, line))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "autoapply":
                for a in node.names:
                    target = a.name
                    if layer == "tools":
                        c.check(target in TOOLS, "%s (tools) imports %s (line %d)" % (mod, target, node.lineno))
                    elif layer == "business":
                        c.check(target in TOOLS or target in SHARED_BUSINESS, "%s (business) imports %s (line %d)" % (mod, target, node.lineno))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print" and layer != "entry":
                c.check(False, "%s uses print() at line %d (only the entry layer prints)" % (mod, node.lineno))
            if isinstance(node, ast.Attribute) and node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id == "os":
                c.check(mod in ("paths", "cli"), "%s reads os.environ at line %d (only paths.py / cli.py may)" % (mod, node.lineno))
        c.check("secrets.env" not in src or mod in ("paths", "selfcheck", "__init__"), "%s mentions secrets.env" % mod)
        if mod == "selfcheck":
            c.check(".read_text(" not in src.split("secrets_env")[-1][:400] and "open(" not in src.split("secrets_env")[-1][:400],
                    "selfcheck must not read secrets.env")
        c.check("from __future__ import annotations" in src or mod == "__main__", "%s lacks `from __future__ import annotations`" % mod)
        c.check("~/Documents" not in src and "/Users/" not in src, "%s contains a user absolute path" % mod)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                c.check(False, "%s has a bare except at line %d" % (mod, node.lineno))
            if isinstance(node, ast.ExceptHandler) and node.body and isinstance(node.body[0], ast.Pass):
                c.check(False, "%s swallows an exception at line %d" % (mod, node.lineno))
    return c.done("entry->business->tools only; stdlib only; no print/os.environ/secrets.env outside allowed modules")


if __name__ == "__main__":
    sys.exit(main())

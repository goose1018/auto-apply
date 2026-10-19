"""Hand-written JSON Schema validator (ARCHITECTURE §11 keyword subset) + hard-coded forbidden-key scan.

Supported: type (incl. list form), properties, required, additionalProperties (false | schema), enum,
const, items, minItems, maxItems, minimum, maximum, minLength, maxLength, pattern (Python re.search),
$ref (local "#/..." pointers only), $defs, not, anyOf, allOf, oneOf, uniqueItems,
exclusiveMinimum/exclusiveMaximum. Annotation keywords are ignored silently; anything else is
recorded as a warning (never an error).

scan_forbidden(instance) rejects any password / national-ID / bank field anywhere in an instance,
independent of the schema (SECURITY §2). It also rejects string values that look like NRIC/FIN or
password assignments.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autoapply.errors import SchemaError
from autoapply.redact import find_secret_hits

ANNOTATION_KEYWORDS: frozenset[str] = frozenset({
    "title", "description", "default", "examples", "$schema", "$id", "$comment", "$defs", "definitions",
    "deprecated", "readOnly", "writeOnly",
})
SUPPORTED_KEYWORDS: frozenset[str] = frozenset({
    "type", "properties", "required", "additionalProperties", "enum", "const", "items", "minItems",
    "maxItems", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength",
    "pattern", "$ref", "not", "anyOf", "allOf", "oneOf", "uniqueItems",
})

# Hard-coded, schema-independent. Keys are compared lower-cased with "-"/" " folded to "_".
FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "password", "passwords", "password_hash", "passwd", "pwd", "pin",
    "nric", "nric_no", "nric_number", "fin", "fin_no", "fin_number", "passport", "passport_number",
    "passport_no", "id_number", "national_id", "identity_card", "ic_number", "ssn", "tax_id", "tin",
    "bank", "bank_account", "bank_account_number", "bank_name", "iban", "swift", "paynow",
    "card_number", "credit_card", "credit_card_number", "cvv", "cvc",
    "secret", "secrets", "api_key", "apikey", "token", "access_token", "refresh_token",
    "session_token", "cookie", "cookies", "otp", "one_time_password",
})


def _fold_key(key: str) -> str:
    return re.sub(r"[\s\-]+", "_", key.strip().lower())


def scan_forbidden(instance: Any, path: str = "$") -> list[str]:
    """Return JSON paths of forbidden keys / secret-looking values. Empty list == clean."""
    problems: list[str] = []
    if isinstance(instance, dict):
        for k, v in instance.items():
            p = "%s.%s" % (path, k)
            if _fold_key(str(k)) in FORBIDDEN_KEYS:
                problems.append("%s: forbidden key" % p)
            problems.extend(scan_forbidden(v, p))
    elif isinstance(instance, list):
        for i, v in enumerate(instance):
            problems.extend(scan_forbidden(v, "%s[%d]" % (path, i)))
    elif isinstance(instance, str):
        hits = find_secret_hits(instance)
        if hits:
            problems.append("%s: value looks like %s" % (path, ",".join(hits)))
    return problems


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_integer(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return True
    return isinstance(v, float) and v.is_integer()


def _is_number(v: Any) -> bool:
    return (isinstance(v, (int, float))) and not isinstance(v, bool)


def _type_ok(v: Any, t: str) -> bool:
    if t == "null":
        return v is None
    if t == "boolean":
        return isinstance(v, bool)
    if t == "integer":
        return _is_integer(v)
    if t == "number":
        return _is_number(v)
    if t == "string":
        return isinstance(v, str)
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    return False


def _strict_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if _is_number(a) and _is_number(b):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_strict_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_strict_equal(a[k], b[k]) for k in a)
    return bool(a == b)


class Validator:
    def __init__(self, schema: dict[str, Any], name: str = "schema") -> None:
        if not isinstance(schema, dict):
            raise SchemaError("schema 顶层必须是对象 / schema root must be an object", {"schema": name})
        self.schema = schema
        self.name = name
        self.load_warnings: list[str] = []
        self._ref_cache: dict[str, Any] = {}
        self._scan_keywords(schema, "#")

    # -- loading -----------------------------------------------------------------------------------
    @classmethod
    def from_file(cls, path: Path) -> "Validator":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SchemaError("schema 文件无法读取或不是合法 JSON / cannot read schema", {"path": str(path)}) from e
        return cls(data, path.name)

    def _scan_keywords(self, node: Any, where: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k not in SUPPORTED_KEYWORDS and k not in ANNOTATION_KEYWORDS and not self._inside_properties(where):
                    self.load_warnings.append("%s: unsupported keyword '%s' ignored (%s)" % (where, k, self.name))
                if k in ("properties", "$defs", "definitions") and isinstance(v, dict):
                    for pk, pv in v.items():
                        self._scan_keywords(pv, "%s/%s/%s" % (where, k, pk))
                elif isinstance(v, (dict, list)):
                    self._scan_keywords(v, "%s/%s" % (where, k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self._scan_keywords(v, "%s/%d" % (where, i))

    @staticmethod
    def _inside_properties(where: str) -> bool:
        # direct children of properties/$defs are property names, not keywords
        parts = where.split("/")
        return len(parts) >= 2 and parts[-2] in ("properties", "$defs", "definitions")

    # -- $ref --------------------------------------------------------------------------------------
    def _resolve_ref(self, ref: str) -> Any:
        if ref in self._ref_cache:
            return self._ref_cache[ref]
        if not ref.startswith("#"):
            raise SchemaError("只支持本地 $ref / only local $ref supported", {"ref": ref, "schema": self.name})
        node: Any = self.schema
        pointer = ref[1:]
        if pointer.startswith("/"):
            for part in pointer[1:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(node, dict) and part in node:
                    node = node[part]
                elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                    node = node[int(part)]
                else:
                    raise SchemaError("$ref 无法解析 / unresolvable $ref", {"ref": ref, "schema": self.name})
        elif pointer:
            raise SchemaError("$ref 无法解析 / unresolvable $ref", {"ref": ref, "schema": self.name})
        self._ref_cache[ref] = node
        return node

    # -- validation --------------------------------------------------------------------------------
    def validate(self, instance: Any) -> ValidationResult:
        result = ValidationResult(warnings=list(self.load_warnings))
        self._validate(instance, self.schema, "$", result.errors)
        return result

    def _validate(self, inst: Any, schema: Any, path: str, errors: list[str]) -> None:
        if schema is True:
            return
        if schema is False:
            errors.append("%s: schema false (no value allowed)" % path)
            return
        if not isinstance(schema, dict):
            errors.append("%s: invalid schema node" % path)
            return
        if "$ref" in schema:
            self._validate(inst, self._resolve_ref(str(schema["$ref"])), path, errors)
            rest = {k: v for k, v in schema.items() if k != "$ref"}
            if rest:
                self._validate(inst, rest, path, errors)
            return

        t = schema.get("type")
        if t is not None:
            types = t if isinstance(t, list) else [t]
            if not any(_type_ok(inst, str(x)) for x in types):
                errors.append("%s: expected type %s, got %s" % (path, "|".join(map(str, types)), _typename(inst)))
                return  # further keyword checks are meaningless on a wrong type

        if "enum" in schema:
            if not any(_strict_equal(inst, e) for e in schema["enum"]):
                errors.append("%s: value not in enum %s" % (path, _short_enum(schema["enum"])))
        if "const" in schema and not _strict_equal(inst, schema["const"]):
            errors.append("%s: value must equal const %r" % (path, schema["const"]))

        if isinstance(inst, str):
            if "minLength" in schema and len(inst) < int(schema["minLength"]):
                errors.append("%s: shorter than minLength %s" % (path, schema["minLength"]))
            if "maxLength" in schema and len(inst) > int(schema["maxLength"]):
                errors.append("%s: longer than maxLength %s" % (path, schema["maxLength"]))
            if "pattern" in schema and not re.search(str(schema["pattern"]), inst):
                errors.append("%s: does not match pattern %s" % (path, schema["pattern"]))

        if _is_number(inst):
            if "minimum" in schema and inst < schema["minimum"]:
                errors.append("%s: below minimum %s" % (path, schema["minimum"]))
            if "maximum" in schema and inst > schema["maximum"]:
                errors.append("%s: above maximum %s" % (path, schema["maximum"]))
            if "exclusiveMinimum" in schema and inst <= schema["exclusiveMinimum"]:
                errors.append("%s: must be > %s" % (path, schema["exclusiveMinimum"]))
            if "exclusiveMaximum" in schema and inst >= schema["exclusiveMaximum"]:
                errors.append("%s: must be < %s" % (path, schema["exclusiveMaximum"]))

        if isinstance(inst, list):
            if "minItems" in schema and len(inst) < int(schema["minItems"]):
                errors.append("%s: fewer than minItems %s" % (path, schema["minItems"]))
            if "maxItems" in schema and len(inst) > int(schema["maxItems"]):
                errors.append("%s: more than maxItems %s" % (path, schema["maxItems"]))
            if schema.get("uniqueItems"):
                seen: list[Any] = []
                for i, v in enumerate(inst):
                    if any(_strict_equal(v, s) for s in seen):
                        errors.append("%s[%d]: duplicate item (uniqueItems)" % (path, i))
                    seen.append(v)
            if "items" in schema:
                for i, v in enumerate(inst):
                    self._validate(v, schema["items"], "%s[%d]" % (path, i), errors)

        if isinstance(inst, dict):
            props = schema.get("properties", {})
            for req in schema.get("required", []):
                if req not in inst:
                    errors.append("%s: missing required property '%s'" % (path, req))
            for k, v in inst.items():
                if k in props:
                    self._validate(v, props[k], "%s.%s" % (path, k), errors)
                else:
                    ap = schema.get("additionalProperties", True)
                    if ap is False:
                        errors.append("%s: additional property '%s' not allowed" % (path, k))
                    elif isinstance(ap, dict):
                        self._validate(v, ap, "%s.%s" % (path, k), errors)

        if "allOf" in schema:
            for i, sub in enumerate(schema["allOf"]):
                self._validate(inst, sub, path, errors)
        if "anyOf" in schema:
            branches: list[list[str]] = []
            for sub in schema["anyOf"]:
                sub_err: list[str] = []
                self._validate(inst, sub, path, sub_err)
                if not sub_err:
                    break
                branches.append(sub_err)
            else:
                errors.append("%s: no anyOf branch matched (%s)" % (path, "; ".join(b[0] for b in branches if b)))
        if "oneOf" in schema:
            matched = 0
            for sub in schema["oneOf"]:
                sub_err: list[str] = []
                self._validate(inst, sub, path, sub_err)
                if not sub_err:
                    matched += 1
            if matched != 1:
                errors.append("%s: oneOf matched %d branches" % (path, matched))
        if "not" in schema:
            sub_err_not: list[str] = []
            self._validate(inst, schema["not"], path, sub_err_not)
            if not sub_err_not:
                errors.append("%s: matches forbidden schema (not)" % path)


def _typename(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


def _short_enum(values: list[Any]) -> str:
    text = json.dumps(values, ensure_ascii=False)
    return text if len(text) <= 120 else text[:117] + "..."


class SchemaSet:
    """Loads the six schemas once; validate(kind, instance) raises SchemaError on failure."""

    KINDS: tuple[str, ...] = ("profile", "facts_card", "job", "application", "run_state", "pending_action")

    def __init__(self, schema_dir: Path) -> None:
        self.schema_dir = schema_dir
        self._validators: dict[str, Validator] = {}

    def get(self, kind: str) -> Validator:
        if kind not in self.KINDS:
            raise SchemaError("未知 schema 类型 / unknown schema kind", {"kind": kind})
        if kind not in self._validators:
            self._validators[kind] = Validator.from_file(self.schema_dir / ("%s.schema.json" % kind))
        return self._validators[kind]

    def check(self, kind: str, instance: Any, *, forbid_secrets: bool = True) -> ValidationResult:
        res = self.get(kind).validate(instance)
        if forbid_secrets:
            res.errors.extend(scan_forbidden(instance))
        return res

    def require(self, kind: str, instance: Any, what: str = "") -> ValidationResult:
        res = self.check(kind, instance)
        if not res.ok:
            raise SchemaError(
                "%s 不符合 %s schema / schema validation failed" % (what or kind, kind),
                {"kind": kind, "errors": res.errors[:50], "error_count": len(res.errors)},
            )
        return res

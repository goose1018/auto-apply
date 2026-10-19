"""R1 dedup key normalisation (ARCHITECTURE §6.2 / §6.3 / §6.4). Pure functions, tool layer.

dedup_key = normalize_company(company) + "|" + normalize_title(title)
job_id    = "job_" + sha256(dedup_key)[:12]
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from autoapply.enums import DEDUP_JACCARD_THRESHOLD
from autoapply.errors import UsageError
from autoapply.ids import job_id_from_key

_BRACKET_MAP = {
    "（": "(", "）": ")", "【": "[", "】": "]", "「": "(", "」": ")", "『": "(", "』": ")",
    "〔": "(", "〕": ")",
}
_CJK_RE = re.compile(r"[㐀-鿿]")

# ---- company -------------------------------------------------------------------------------------
_COMPANY_PAREN_DROP_RE = re.compile(
    r"^\s*(?:(?:singapore|sg|asia|apac|pte|ltd|group|holdings|s\.?e\.?a\.?|international)\s*[.,]?\s*)+$",
    re.IGNORECASE,
)
_COMPANY_PUNCT_RE = re.compile(r"[.,'\"’/\-_]")
# multi-token suffixes first so "pte ltd" is stripped as a unit
COMPANY_SUFFIXES: tuple[tuple[str, ...], ...] = (
    ("pte", "ltd"), ("sdn", "bhd"), ("asia", "pacific"),
    ("pte",), ("ltd",), ("limited",), ("inc",), ("incorporated",), ("llc",), ("llp",), ("plc",),
    ("co",), ("corp",), ("corporation",), ("company",), ("gmbh",), ("ag",), ("sa",), ("bv",), ("nv",),
    ("bhd",), ("pvt",), ("private",), ("holdings",), ("holding",), ("group",), ("international",),
    ("global",), ("singapore",), ("sg",), ("apac",), ("asia",), ("sea",),
)
COMPANY_CJK_SUFFIXES: tuple[str, ...] = ("股份有限公司", "私人有限公司", "有限公司", "集团", "公司", "新加坡")


def _nfkc(s: str) -> str:
    out = unicodedata.normalize("NFKC", s)
    for k, v in _BRACKET_MAP.items():
        out = out.replace(k, v)
    return out


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_company(raw: str, aliases: dict[str, str] | None = None) -> str:
    if not raw or not raw.strip():
        raise UsageError("公司名为空 / empty company name")
    s = _collapse(_nfkc(raw))

    def _paren(m: re.Match[str]) -> str:
        inner = m.group(1)
        return " " if _COMPANY_PAREN_DROP_RE.match(inner) else " %s " % inner

    s = re.sub(r"[\(\[]([^()\[\]]*)[\)\]]", _paren, s)
    s = s.lower()
    s = s.replace("&", " and ")
    s = _COMPANY_PUNCT_RE.sub(" ", s)
    s = _collapse(s)
    if s.startswith("the "):
        s = s[4:]
    # CJK suffixes (no whitespace tokenisation)
    changed = True
    while changed:
        changed = False
        for suf in COMPANY_CJK_SUFFIXES:
            if s.endswith(suf) and len(s) > len(suf):
                s = s[: -len(suf)].strip()
                changed = True
    tokens = s.split()
    changed = True
    while changed and len(tokens) > 1:
        changed = False
        for suf in COMPANY_SUFFIXES:
            n = len(suf)
            if len(tokens) > n and tuple(tokens[-n:]) == suf:
                tokens = tokens[:-n]
                changed = True
                break
    if len(tokens) > 1 and tokens[-1] == "and":
        tokens = tokens[:-1]
    s = " ".join(tokens)
    if aliases:
        s = aliases.get(s, s)
    s = _collapse(s)
    if not s:
        raise UsageError("公司名规范化后为空 / company normalises to empty")
    return s


# ---- title ---------------------------------------------------------------------------------------
_REQ_SEGMENT_RE = re.compile(r"^(jr|req|hrc|uni|r|id|job|ref|no)?\s*[-#]?\s*\d{3,}[a-z]?$")
_MONTH_WORD = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_TIME_SEGMENT_RE = re.compile(
    r"20\d\d|\b" + _MONTH_WORD + r"\b|\b(?:spring|summer|fall|autumn|winter|h1|h2|q[1-4]|batch|intake|cohort|cycle|off\s*cycle|term)\b"
)
_LOC_WORDS = r"(?:singapore|sg|remote|hybrid|onsite|on\s*site|apac|asia|sea|global|regional)"
_LOC_SEGMENT_RE = re.compile(r"^\s*" + _LOC_WORDS + r"(?:\s*[,/&]?\s*" + _LOC_WORDS + r")*\s*$")
_AUD_WORDS = r"(?:uni|university|student|undergraduate|graduate|postgraduate|penultimate|final\s*year|masters?|phd|m\s*/\s*f\s*/\s*d|f\s*/\s*m\s*/\s*x)"
_AUD_SEGMENT_RE = re.compile(r"^\s*" + _AUD_WORDS + r"(?:\s*[,/&]?\s*" + _AUD_WORDS + r")*\s*$")
_TITLE_SEP_RE = re.compile(r"[/|–—\-_:,•]")
_REQ_TOKEN_RE = re.compile(r"^(jr|req|hrc|uni)?\d{4,}$")
_YEAR_TOKEN_RE = re.compile(r"^20\d\d$")
_MONTH_TOKEN_RE = re.compile(r"^" + _MONTH_WORD + r"$")

EDGE_STRIP_TOKENS: frozenset[str] = frozenset({
    "spring", "summer", "fall", "autumn", "winter", "h1", "h2", "q1", "q2", "q3", "q4", "batch",
    "intake", "cohort", "cycle", "off", "offcycle", "term",
    "singapore", "sg", "remote", "hybrid", "onsite", "on", "site", "apac", "asia", "sea", "global", "regional",
    "uni", "university", "student", "undergraduate", "graduate", "postgraduate", "penultimate", "final",
    "year", "master", "masters", "phd",
    "to", "till", "until", "through", "thru",
})

# 泛化残根：边缘剥离（season/degree/地域等）后只剩这些通用词时，去重键会把本质不同的岗位撞到一起
# （如 "Summer Intern" 与 "PhD Intern" 都 -> "intern"）。命中这里的标题不做硬拦，降级为 dedup_review。
# Generic stubs: when edge-stripping leaves only one of these, an exact key match is downgraded to review.
GENERIC_TITLE_STUBS: frozenset[str] = frozenset({
    "intern", "internship", "analyst", "engineer", "associate", "trainee", "assistant",
    "developer", "consultant", "specialist", "officer", "executive", "manager", "scientist",
    "researcher", "designer", "coordinator", "programme", "program",
})


def is_generic_title(title_norm: str) -> bool:
    """规范化标题是否只剩通用残根 / True when the normalised title is only a generic stub."""
    return title_norm.strip() in GENERIC_TITLE_STUBS


TITLE_SYNONYMS: dict[str, str] = {
    "internship": "intern", "interns": "intern", "internships": "intern",
    "swe": "software engineer",
    "ml": "machine learning",
    "sr": "senior", "snr": "senior",
    "jr": "junior",
    "mgr": "manager",
    "eng": "engineer",
    "genai": "generative ai",
    "asst": "assistant",
}

TITLE_FILLERS: frozenset[str] = frozenset({
    "a", "an", "the", "of", "for", "in", "at", "and", "with", "to", "position", "role", "opening",
    "program", "programme",
})


def _segment_should_drop(inner: str) -> bool:
    seg = _collapse(inner.lower())
    if not seg:
        return True
    if _REQ_SEGMENT_RE.match(seg):
        return True
    if _TIME_SEGMENT_RE.search(seg):
        return True
    if _LOC_SEGMENT_RE.match(seg):
        return True
    if _AUD_SEGMENT_RE.match(seg):
        return True
    return False


def _is_edge_token(tok: str) -> bool:
    return tok in EDGE_STRIP_TOKENS or bool(_YEAR_TOKEN_RE.match(tok)) or bool(_MONTH_TOKEN_RE.match(tok))


def normalize_title(raw: str) -> str:
    if not raw or not raw.strip():
        raise UsageError("岗位名为空 / empty title")
    s = _collapse(_nfkc(raw)).lower()

    def _bracket(m: re.Match[str]) -> str:
        inner = m.group(1)
        return " " if _segment_should_drop(inner) else " %s " % inner

    for _ in range(3):  # nested brackets, a few passes
        s = re.sub(r"[\(\[]([^()\[\]]*)[\)\]]", _bracket, s)
    s = s.replace("&", " and ")
    s = _TITLE_SEP_RE.sub(" ", s)
    tokens = [t for t in s.split() if t]
    if not tokens:
        raise UsageError("岗位名规范化后为空 / title normalises to empty")
    # edge stripping (ARCHITECTURE §6.3 step 3)
    stripped = list(tokens)
    while stripped and _is_edge_token(stripped[0]):
        stripped.pop(0)
    while stripped and _is_edge_token(stripped[-1]):
        stripped.pop()
    if not stripped:
        stripped = list(tokens)
    # step 4: req tokens / year tokens anywhere
    stripped = [t for t in stripped if not _REQ_TOKEN_RE.match(t) and not _YEAR_TOKEN_RE.match(t)]
    if not stripped:
        stripped = list(tokens)
    # step 5: synonyms
    expanded: list[str] = []
    for t in stripped:
        expanded.extend(TITLE_SYNONYMS.get(t, t).split())
    # step 6: fillers
    final = [t for t in expanded if t not in TITLE_FILLERS]
    if not final:
        final = expanded or stripped
    out = _collapse(" ".join(final))
    if not out:
        raise UsageError("岗位名规范化后为空 / title normalises to empty")
    return out


# ---- keys & similarity ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DedupKey:
    company_raw: str
    title_raw: str
    company_norm: str
    title_norm: str

    @property
    def key(self) -> str:
        return "%s|%s" % (self.company_norm, self.title_norm)

    @property
    def job_id(self) -> str:
        return job_id_from_key(self.key)


def make_dedup_key(company_raw: str, title_raw: str, aliases: dict[str, str] | None = None) -> DedupKey:
    return DedupKey(
        company_raw=company_raw.strip(),
        title_raw=title_raw.strip(),
        company_norm=normalize_company(company_raw, aliases),
        title_norm=normalize_title(title_raw),
    )


def jaccard(a: str, b: str) -> float:
    sa, sb = set(a.split()), set(b.split())
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / float(len(sa | sb))


def is_contiguous_subsequence(a: str, b: str) -> bool:
    ta, tb = a.split(), b.split()
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    n = len(short)
    return any(long_[i:i + n] == short for i in range(len(long_) - n + 1))


def title_similarity(a: str, b: str) -> float:
    """Score in [0,1]: 1.0 for exact / contiguous-subsequence, else Jaccard."""
    if a == b or is_contiguous_subsequence(a, b):
        return 1.0
    return jaccard(a, b)


def is_suspected_duplicate(title_norm_a: str, title_norm_b: str) -> bool:
    """ARCHITECTURE §6.4: same company_norm assumed; Jaccard >= 0.8 or contiguous subsequence."""
    if title_norm_a == title_norm_b:
        return True
    return jaccard(title_norm_a, title_norm_b) >= DEDUP_JACCARD_THRESHOLD or is_contiguous_subsequence(
        title_norm_a, title_norm_b
    )


def fuzzy_ratio(a: str, b: str) -> float:
    """Loose text similarity for evidence matching (job_title_seen vs job title)."""
    na, nb = _collapse(_nfkc(a).lower()), _collapse(_nfkc(b).lower())
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    seq = SequenceMatcher(None, na, nb).ratio()
    tok = jaccard(na, nb)
    return max(seq, tok)


def has_cjk(s: str) -> bool:
    return bool(_CJK_RE.search(s))

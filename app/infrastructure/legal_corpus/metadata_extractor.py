"""
Rule-based metadata extraction from Vietnamese legal document text.
No LLM/API required. Ported from EONSR_CAND helpers/metadata_extractor.py
adapted for ContractLens schema (effectivity chunks instead of enforcement section_type).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

_DOC_NUMBER_RE = r"\d{1,4}(?:/[A-ZĐa-zđ0-9\-]+)*(?:/[A-ZĐa-zđ]+)*"

_EFFECTIVE_KEYWORDS = [
    "có hiệu lực thi hành",
    "hiệu lực thi hành",
    "có hiệu lực kể từ ngày",
    "có hiệu lực từ ngày",
    "có hiệu lực sau",
    "có hiệu lực vào",
    "kể từ ngày ký",
    "kể từ ngày ký ban hành",
    "kể từ ngày ban hành",
    "bắt đầu có hiệu lực",
    "bắt đầu thi hành",
    "thi hành kể từ ngày",
    "thi hành từ ngày",
]

_EXPIRY_KEYWORDS = [
    "hết hiệu lực",
    "đến hết ngày",
]

_SIGNING_DATE_EFFECTIVE_PATTERNS = [
    r"có\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?kể\s+từ\s+ngày\s+ký",
    r"có\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?từ\s+ngày\s+ký",
    r"hiệu\s+lực\s+thi\s+hành\s+kể\s+từ\s+ngày\s+ký",
    r"có\s+hiệu\s+lực\s+kể\s+từ\s+ngày\s+ban\s+hành",
    r"có\s+hiệu\s+lực\s+từ\s+ngày\s+ban\s+hành",
    r"có\s+hiệu\s+lực\s+thi\s+hành\s+kể\s+từ\s+ngày\s+ban\s+hành",
    r"có\s+hiệu\s+lực\s+thi\s+hành\s+từ\s+ngày\s+ban\s+hành",
]

_DATE_PATTERNS = [
    r"(?:ngày\s+)?(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
    r"(\d{4})-(\d{1,2})-(\d{1,2})",
]

_AFTER_KW_PATTERNS = [
    r"có\s+hiệu\s+lực\s+thi\s+hành\s+kể\s+từ\s+ngày\s+([^.;]+)",
    r"có\s+hiệu\s+lực\s+thi\s+hành\s+từ\s+ngày\s+([^.;]+)",
    r"có\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?(?:kể\s+từ\s+|từ\s+|vào\s+)?ngày\s+([^.;]+)",
    r"hiệu\s+lực\s+thi\s+hành\s+(?:kể\s+từ\s+|từ\s+)?ngày\s+([^.;]+)",
    r"thi\s+hành\s+(?:kể\s+từ\s+|từ\s+)?ngày\s+([^.;]+)",
]

_EXPIRY_STRICT_PATTERNS = [
    r"hết\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?(?:kể\s+từ\s+)?ngày\s+(\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{4})",
    r"hết\s+hiệu\s+lực\s+(?:thi\s+hành\s+)?(?:kể\s+từ\s+)?ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    r"hết\s+hiệu\s+lực\s+vào\s+ngày\s+(\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{4})",
    r"hết\s+hiệu\s+lực\s+vào\s+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
]

_EXPIRY_NARROW_PATTERNS = _EXPIRY_STRICT_PATTERNS + [
    r"đến\s+hết\s+ngày\s+(\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{4})",
    r"đến\s+hết\s+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
]

_TITLE_DOC_TYPE_PATTERNS = [
    (r"\bHiến\s*pháp\b", "Hiến pháp"),
    (r"\bBộ\s*luật\b", "Bộ luật"),
    (r"\bLuật\b(?!.*\bBộ\s*luật\b)", "Luật"),
    (r"\bNghị\s*quyết\b", "Nghị quyết"),
    (r"\bNghị\s*định\b", "Nghị định"),
    (r"\bQuyết\s*định\b", "Quyết định"),
    (r"\bThông\s*tư\b", "Thông tư"),
    (r"\bChỉ\s*thị\b", "Chỉ thị"),
    (r"\bPháp\s*lệnh\b", "Pháp lệnh"),
    (r"\bQuy\s*chuẩn\b", "Quy chuẩn"),
    (r"\bVăn\s+bản\s+hợp\s+nhất\b", "Văn bản hợp nhất"),
]

_ISSUED_DATE_PATTERNS = [
    r"(?:ngày|số)\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+(\d{4})",
    r"năm\s+(\d{4})",
]


def parse_vietnamese_date(text: str) -> Optional[str]:
    """Parse Vietnamese date string → YYYY-MM-DD."""
    if not text:
        return None
    for pat in _DATE_PATTERNS:
        m = re.search(pat, text)
        if not m:
            continue
        try:
            groups = m.groups()
            if len(groups) == 3:
                if len(groups[0]) == 4:
                    y, mo, d = groups
                else:
                    d, mo, y = groups
                d, mo, y = int(d), int(mo), int(y)
                if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
                    return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, IndexError):
            continue
    return None


def _normalize_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    date_str = date_str.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    m = re.match(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$", date_str)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return parse_vietnamese_date(date_str)


def _find_effective_article(content: str) -> Optional[str]:
    """Find 'Hiệu lực thi hành' article in content."""
    if not content:
        return None
    _header_re = re.compile(r"Điều\s+[\dIVXLCH]+\s*[\.:]", re.IGNORECASE)
    matches = []
    for m in _header_re.finditer(content):
        start = m.start()
        if start > 0 and content[start - 1].isalpha():
            continue
        matches.append(start)
    if not matches:
        return None

    def _collect(s: int) -> Optional[str]:
        end = len(content)
        for ms in matches:
            if ms > s:
                end = ms
                break
        seg = content[s:end].strip()
        return seg or None

    for s in matches:
        if re.search(r"hiệu\s+lực", content[s : s + 100], re.I):
            return _collect(s)
    for s in matches:
        if re.search(r"có\s+hiệu\s+lực|hiệu\s+lực\s+thi\s+hành", content[s : s + 400], re.I):
            return _collect(s)
    return None


def extract_effective_date_section(content: str) -> str:
    """Find enforcement section from document tail."""
    if not content:
        return ""
    paragraphs = re.split(r"\n\s*\n", content)
    for para in reversed(paragraphs):
        para_s = para.strip()
        if not para_s:
            continue
        for kw in _EFFECTIVE_KEYWORDS:
            if kw in para_s.lower():
                if len(para_s) > 2000:
                    narrowed = _find_effective_article(para_s)
                    if narrowed:
                        return narrowed
                return para_s
    return ""


def is_effective_from_signing(content: str) -> bool:
    if not content:
        return False
    text_lower = content.lower()
    for pat in _SIGNING_DATE_EFFECTIVE_PATTERNS:
        if re.search(pat, text_lower):
            return True
    return False


def _calc_signing_delay(content: str, issued_date: Optional[str]) -> Optional[str]:
    if not content or not issued_date:
        return None
    m = re.search(r"sau\s+(\d+)\s+ngày\s+kể\s+từ\s+ngày\s+ký", content.lower())
    if not m:
        return None
    days = int(m.group(1))
    iso = _normalize_date(issued_date)
    if not iso:
        return None
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        return (dt + timedelta(days=days)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def find_cross_ref_doc_number(text: str) -> Optional[str]:
    if not text:
        return None
    cross_pats = [
        rf"kể\s+từ\s+ngày\s+(?:[\wĐđ]+\s+){{1,5}}số\s+({_DOC_NUMBER_RE})\s+.*?có\s+hiệu\s+lực",
        rf"từ\s+ngày\s+(?:[\wĐđ]+\s+){{1,5}}số\s+({_DOC_NUMBER_RE})\s+.*?có\s+hiệu\s+lực",
    ]
    for pat in cross_pats:
        m = re.search(pat, text.lower())
        if m:
            ref = m.group(1).strip().rstrip("-/")
            if ref and len(ref) >= 5:
                return ref
    return None


def _extract_effective_from_segments(text: str) -> Optional[str]:
    if not text:
        return None
    segments = re.split(r"\n\s*(?:\d+[\.\)]|[a-zđ][\.\)]|[-–•])\s*", text)
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        if is_effective_from_signing(seg):
            continue
        if find_cross_ref_doc_number(seg):
            continue
        for pat in _AFTER_KW_PATTERNS:
            m = re.search(pat, seg.lower())
            if m:
                parsed = parse_vietnamese_date(m.group(1)[:80])
                if parsed:
                    return parsed
    return None


def extract_effective_date(
    content: str,
    issued_date: Optional[str] = None,
) -> Optional[str]:
    """Extract effective_date (YYYY-MM-DD) from document text.

    Priority:
    1. Enforcement article → pattern match
    2. Enforcement section fallback
    3. 'kể từ ngày ký' → issued_date
    4. 'sau X ngày' → issued_date + X
    """
    article = _find_effective_article(content)
    section = extract_effective_date_section(content)

    for source in [article, section]:
        if source:
            parsed = _extract_effective_from_segments(source)
            if parsed:
                return parsed
            if is_effective_from_signing(source):
                return _normalize_date(issued_date)
            delay = _calc_signing_delay(source, issued_date)
            if delay:
                return delay

    if is_effective_from_signing(content):
        return _normalize_date(issued_date)
    delay = _calc_signing_delay(content, issued_date)
    if delay:
        return delay
    return None


def _extract_expiry_from_section(section: str, enforcement_context: bool = False) -> Optional[str]:
    if not section:
        return None
    section_lower = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", section.lower())
    doc_num_pat = re.compile(rf"số\s+{_DOC_NUMBER_RE}", re.I)
    _list_other = re.compile(
        r"(?:các|những)\s+(?:quy[ếe]t\s*đ[ịi]nh|v[ăa]n\s*b[ảa]n|ngh[ịi]\s*đ[ịi]nh|th[ôo]ng\s*t[ưu])\s+sau\s+đ[âa]y\s+h[ếe]t\s+hi[ệe]u\s+l[ựư]c",
        re.I,
    )

    lines = section_lower.split("\n")
    paragraphs = []
    cur = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^(?:\d+|điều\s+\d+)[\.\)]\s", line, re.I):
            if cur.strip():
                paragraphs.append(cur.strip())
            cur = line + "\n"
        else:
            cur += line + "\n"
    if cur.strip():
        paragraphs.append(cur.strip())
    if not paragraphs:
        paragraphs = [section_lower]

    patterns = list(_EXPIRY_STRICT_PATTERNS)
    if enforcement_context:
        patterns += _EXPIRY_NARROW_PATTERNS[len(_EXPIRY_STRICT_PATTERNS):]

    for para in paragraphs:
        if _list_other.search(para):
            continue
        other_positions = [m.start() for m in doc_num_pat.finditer(para)] if doc_num_pat.search(para) else []
        for pat in patterns:
            for m in re.finditer(pat, para):
                if other_positions and any(m.start() > op for op in other_positions):
                    continue
                groups = m.groups()
                if len(groups) == 1:
                    parsed = parse_vietnamese_date(groups[0].replace(" ", ""))
                else:
                    parsed = parse_vietnamese_date(f"ngày {groups[0]} tháng {groups[1]} năm {groups[2]}")
                if parsed:
                    return parsed
    return None


def extract_expiry_date(content: str, enf_text: Optional[str] = None) -> Optional[str]:
    """Extract expiry_date ONLY from enforcement text (avoid false positives)."""
    source = enf_text or ""
    if not source:
        source = _find_effective_article(content) or ""

    if not source:
        return None

    enf_lower = source.lower()
    has_kw = any(kw in enf_lower for kw in ("hiệu lực", "hết hiệu lực", "có hiệu lực", "thi hành"))
    return _extract_expiry_from_section(source, enforcement_context=has_kw)


def validate_expiry_against_effective(expiry: str, effective: str) -> Optional[str]:
    if expiry[:10] < effective[:10]:
        return None
    return expiry


def detect_doc_type_from_title(title: str) -> str:
    if not title:
        return "Unknown"
    clean = re.sub(r"\s+", " ", title.strip())
    for pat, label in _TITLE_DOC_TYPE_PATTERNS:
        if re.search(pat, clean, re.IGNORECASE):
            return label
    return "Unknown"


def extract_issued_date(content: str) -> Optional[str]:
    """Extract issued_date from header section."""
    if not content:
        return None
    header_end = min(len(content), 1200)
    header = content[:header_end]
    for pat in _ISSUED_DATE_PATTERNS:
        m = re.search(pat, header, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 1900 <= year <= date.today().year + 5:
                return f"{year:04d}-01-01"
    return None


def extract_doc_metadata(
    title: str,
    content: str,
    issued_date: Optional[str] = None,
    enf_texts: Optional[list[str]] = None,
) -> dict:
    """Extract all metadata from document text + enforcement chunks.

    Returns dict with: effective_date, expiry_date, doc_type, issued_date.
    """
    enf_combined = " ".join(enf_texts) if enf_texts else None
    doc_type = detect_doc_type_from_title(title)

    eff = extract_effective_date(content, issued_date=issued_date)
    expiry = extract_expiry_date(content, enf_text=enf_combined)
    if expiry and eff:
        expiry = validate_expiry_against_effective(expiry, eff)

    if not issued_date:
        issued = extract_issued_date(content)
    else:
        issued = _normalize_date(issued_date)

    return {
        "effective_date": eff,
        "expiry_date": expiry,
        "doc_type": doc_type,
        "issued_date": issued or issued_date,
    }

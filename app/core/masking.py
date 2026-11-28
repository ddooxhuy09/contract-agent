"""Mask personal data before text leaves for an LLM (OWASP LLM02:2025) or a log line (OWASP A09:2021).

``PiiVault`` swaps each value for a token like ``[CCCD_1]`` (same value, same token) and puts the
originals back in the model's reply. One vault per LLM call; it is never stored.
Kept visible on purpose: salary, dates other than birth dates, percentages, company names,
the last two parts of an address (district and province decide the minimum-wage region),
and the year of birth (age rules).

shortcut: regex only, so a bare name with no label ("Ông", "Bà", "Họ và tên") is not masked;
add NER if contracts with unlabelled names show up.
"""

from __future__ import annotations

import re

_UP = "A-ZĐÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ"
_SEP = r"\s*(?:số)?\s*[:：]?\s*"

# (token kind, pattern). Only the named group ``v`` is replaced, so labels stay readable.
# Labelled patterns run before bare ones: a 10-digit tax code must not end up as a phone number.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"(?P<v>[\w.+-]+@[\w-]+(?:\.[\w-]+)+)")),
    # Word boundaries around the label: "CÔNG TY" / "BÀN GIAO" contain ÔNG / BÀ.
    ("HO_TEN", re.compile(rf"(?<!\w)(?:[Hh]ọ (?:và )?tên|HỌ (?:VÀ )?TÊN|Ông|Bà|ÔNG|BÀ)(?:\s*/\s*(?:Ông|Bà|ÔNG|BÀ))?(?!\w)\s*[:：]?\s*"
                          rf"(?P<v>[{_UP}][\w]*(?:[ \t]+[{_UP}][\w]*){{1,5}})")),
    ("CCCD", re.compile(r"(?i:CCCD|CMND|CMTND|căn cước(?: công dân)?|chứng minh (?:nhân dân|thư)|số định danh(?: cá nhân)?)"
                        rf"{_SEP}(?P<v>\d{{12}}|\d{{9}})(?!\d)")),
    ("HO_CHIEU", re.compile(rf"(?i:hộ chiếu){_SEP}(?P<v>[A-Z]\d{{7,8}})\b")),
    ("MST", re.compile(rf"(?i:mã số thuế|MST|mã số doanh nghiệp){_SEP}(?P<v>\d{{10}}(?:-\d{{3}})?)(?!\d)")),
    ("BHXH", re.compile(rf"(?i:(?:mã số |số )?sổ BHXH|mã số BHXH|sổ bảo hiểm xã hội|mã số bảo hiểm xã hội){_SEP}(?P<v>\d{{10}})(?!\d)")),
    ("STK", re.compile(rf"(?i:số tài khoản|STK|tài khoản ngân hàng){_SEP}(?P<v>\d[\d .-]{{5,22}}\d)")),
    ("NGAY_THANG_SINH", re.compile(r"(?i:ngày,? tháng,? năm sinh|ngày sinh|sinh ngày)\s*[:：]?\s*"
                                   r"(?P<v>\d{1,2}[/.-]\d{1,2})(?=[/.-]\d{4})")),
    ("DIA_CHI", re.compile(r"(?i:địa chỉ(?: thường trú| liên hệ| tạm trú| cư trú)?|thường trú|tạm trú|"
                           r"nơi (?:ở|cư trú)(?: hiện (?:nay|tại))?|chỗ ở(?: hiện (?:nay|tại))?)\s*[:：]\s*"
                           r"(?P<v>[^\n;]{3,200})")),
    # Not part of a longer number such as 1.000.000.000.000 (a "." or "," between digits).
    ("CCCD", re.compile(r"(?<!\d)(?<!\d[.,])(?P<v>\d{12})(?!\d)(?![.,]\d)")),
    ("SDT", re.compile(r"(?<!\d)(?<!\d[.,])(?P<v>(?:\+84|0)(?:[ .-]?\d){9})(?!\d)(?![.,]\d)")),
]


def _split_address(value: str) -> tuple[str, str]:
    """('house, street, ward', ', district, province'): only the detailed part is masked."""
    parts = value.rstrip(" .").split(",")
    if len(parts) < 3:
        return value, ""
    return ",".join(parts[:-2]), "," + ",".join(parts[-2:])


class PiiVault:
    def __init__(self) -> None:
        self._token_of: dict[tuple[str, str], str] = {}
        self._value_of: dict[str, str] = {}

    def _token(self, kind: str, value: str) -> str:
        key = (kind, value)
        if key not in self._token_of:
            n = sum(1 for k, _ in self._token_of if k == kind) + 1
            token = f"[{kind}_{n}]"
            self._token_of[key] = token
            self._value_of[token] = value
        return self._token_of[key]

    def mask(self, text: str) -> str:
        if not text:
            return text
        for kind, pattern in _PATTERNS:
            text = pattern.sub(lambda m, k=kind: self._replace(m, k), text)
        return text

    def _replace(self, m: re.Match[str], kind: str) -> str:
        value = m.group("v")
        tail = ""
        if kind == "DIA_CHI":
            value, tail = _split_address(value)
        start, end = m.start("v") - m.start(), m.end("v") - m.start()
        whole = m.group(0)
        return whole[:start] + self._token(kind, value.strip()) + tail + whole[end:]

    def unmask(self, text: str) -> str:
        if not isinstance(text, str) or not self._value_of:
            return text
        for token, value in self._value_of.items():
            text = text.replace(token, value)
        return text


def mask_for_log(value: object, limit: int = 500) -> str:
    """Log-safe text: personal data replaced by tokens (never restored), then cut to ``limit``."""
    return PiiVault().mask(str(value))[:limit]

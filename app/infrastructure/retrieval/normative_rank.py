"""Normative hierarchy rank for Vietnamese legal instruments (no fixed doc numbers)."""

from __future__ import annotations

import re
import unicodedata

# Higher = preferred. Order follows Luật Ban hành VBQPPL (rút gọn theo yêu cầu sản phẩm):
# Hiến pháp → Bộ luật/Luật → Nghị quyết → Pháp lệnh → Lệnh/Quyết định
# → Nghị định → Thông tư → Thông tư liên tịch → khác.
# Patterns are longest-first.
_DOC_TYPE_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"hi[eế]n\s*ph[aá]p", re.I), 1.00),
    (re.compile(r"b[oộ]\s*lu[aậ]t", re.I), 0.95),
    (re.compile(r"\blu[aậ]t\b", re.I), 0.92),
    (re.compile(r"ngh[iị]\s*quy[eế]t", re.I), 0.84),
    (re.compile(r"ph[aá]p\s*l[eệ]nh", re.I), 0.78),
    (re.compile(r"\bl[eệ]nh\b", re.I), 0.72),
    (re.compile(r"quy[eế]t\s*đ[iị]nh", re.I), 0.68),
    (re.compile(r"ngh[iị]\s*đ[iị]nh", re.I), 0.60),
    (re.compile(r"th[oô]ng\s*t[uư]\s*li[eê]n\s*t[iị]ch", re.I), 0.40),
    (re.compile(r"th[oô]ng\s*t[uư]", re.I), 0.48),
    (re.compile(r"ch[iỉ]\s*th[iị]", re.I), 0.30),
    (re.compile(r"quy\s*chu[aẩ]n", re.I), 0.28),
]

_DEFAULT_RANK = 0.25


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def normative_rank(doc_type: str | None = None, title: str | None = None) -> float:
    """Score by instrument level; never by a fixed số hiệu."""
    blob = _nfc(f"{doc_type or ''} {title or ''}")
    if not blob.strip():
        return _DEFAULT_RANK
    for pat, rank in _DOC_TYPE_PATTERNS:
        if pat.search(blob):
            return rank
    return _DEFAULT_RANK

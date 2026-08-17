"""Detect sector-specific legal docs that do not apply to the contract context.

Only keep industry-scoped instruments when the contract itself mentions that
sector. Otherwise drop them so general Bộ luật / Luật / Nghị định rank higher.

Never treat broad labor instruments (BLLĐ, NĐ xử phạt lĩnh vực lao động, …) as
sector-only — their titles often *list* niche domains without being niche.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Titles that apply across ordinary HĐLĐ — never drop as sector-mismatch.
_GENERAL_LABOR = re.compile(
    r"Bộ\s*luật\s*Lao\s*động|"
    r"xử\s*phạt\s*vi\s*phạm\s*hành\s*chính\s*trong\s*lĩnh\s*vực\s*lao\s*động|"
    r"Nghị\s*định\s+số\s+\d+/\d+/NĐ-CP[^\n]{0,80}lĩnh\s*vực\s*lao\s*động|"
    r"Thông\s*tư\s+số\s+\d+/\d+/TT-BLĐTBXH[^\n]{0,60}hợp\s*đồng\s*lao\s*động|"
    r"nội\s*dung\s*(?:chủ\s*yếu\s*)?(?:của\s*)?hợp\s*đồng\s*lao\s*động",
    re.IGNORECASE,
)

# (law_title_pattern, contract_must_match_to_keep).
_SECTOR_SCOPES: list[tuple[re.Pattern[str], re.Pattern[str]]] = [
    (
        re.compile(
            r"dầu\s*khí|thăm\s*dò|khai\s*thác\s*dầu|lọc\s*dầu|lọc\s*hóa|"
            r"trên\s*biển|giàn\s*khoan|offshore|xăng\s*dầu|"
            r"đường\s*ống.*khí|công\s*trình\s*khí|phân\s*phối\s*khí",
            re.IGNORECASE,
        ),
        re.compile(
            r"dầu\s*khí|thăm\s*dò|giàn\s*khoan|offshore|khoan\s*biển|"
            r"khai\s*thác\s*dầu|lọc\s*dầu|lọc\s*hóa|trên\s*biển|xăng\s*dầu|"
            r"đường\s*ống|công\s*trình\s*khí|khí\s*đốt",
            re.IGNORECASE,
        ),
    ),
    (
        re.compile(r"hầm\s*lò|khai\s*thác\s*mỏ|than\s*hầm", re.I),
        re.compile(r"hầm\s*lò|mỏ\s*than|khai\s*thác\s*mỏ", re.I),
    ),
    (
        re.compile(
            r"giúp\s*việc\s*gia\s*đình|người\s*giúp\s*việc|lao\s*động\s*là\s*người\s*giúp\s*việc",
            re.I,
        ),
        re.compile(r"giúp\s*việc|ô\s*sin|domestic\s*worker", re.I),
    ),
    (
        # Primary topic = NLĐ đi nước ngoài / xuất khẩu LĐ — NOT a trailing
        # clause in multi-domain titles like NĐ 12/2022 (lao động, BHXH, NLĐ NN).
        re.compile(
            r"Luật\s+Người\s+lao\s+động\s+Việt\s+Nam\s+đi\s+làm\s+việc|"
            r"xuất\s*khẩu\s*lao\s*động|"
            r"đưa\s*người\s*lao\s*động\s*đi\s*làm\s*việc|"
            r"cung\s*ứng\s*lao\s*động\s*(?:ra\s*)?nước\s*ngoài",
            re.I,
        ),
        re.compile(
            r"xuất\s*khẩu\s*lao\s*động|làm\s*việc\s*ở\s*nước\s*ngoài|"
            r"đi\s*làm\s*việc\s*ở\s*nước\s*ngoài|người\s*lao\s*động\s*việt\s*nam\s*đi",
            re.I,
        ),
    ),
    (
        re.compile(r"quân\s*đội|quân\s*nhân|sĩ\s*quan|nghĩa\s*vụ\s*quân\s*sự|BQP\b", re.I),
        re.compile(r"quân\s*đội|quân\s*nhân|sĩ\s*quan|nghĩa\s*vụ\s*quân|quân\s*sự", re.I),
    ),
    (
        re.compile(r"công\s*an\s*nhân\s*dân|lực\s*lượng\s*công\s*an|BCA\b", re.I),
        re.compile(r"công\s*an|cảnh\s*sát\s*nhân\s*dân|lực\s*lượng\s*công\s*an", re.I),
    ),
    (
        re.compile(r"hàng\s*không|tiếp\s*viên\s*hàng\s*không|phi\s*công", re.I),
        re.compile(r"hàng\s*không|sân\s*bay|phi\s*công|tiếp\s*viên", re.I),
    ),
    (
        re.compile(r"đường\s*sắt|ga\s*đường\s*sắt", re.I),
        re.compile(r"đường\s*sắt|ga\s*tàu", re.I),
    ),
    (
        re.compile(r"hàng\s*hải|thuyền\s*viên|tàu\s*biển", re.I),
        re.compile(r"hàng\s*hải|thuyền\s*viên|tàu\s*biển|cảng\s*biển", re.I),
    ),
]


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def contract_context(*parts: str | None) -> str:
    return _nfc(" ".join(p for p in parts if p and str(p).strip()))


def doc_scope_text(meta: dict[str, Any] | None, content: str | None = None) -> str:
    meta = meta or {}
    bits = [
        str(meta.get("title") or ""),
        str(meta.get("doc_number") or ""),
        str(meta.get("doc_type") or ""),
    ]
    # Prefer title/doc_number for sector scope — body text can mention unrelated
    # industries and false-trigger filters.
    if content and not bits[0]:
        bits.append(str(content)[:400])
    return _nfc(" ".join(bits))


def is_general_labor_instrument(doc_text: str) -> bool:
    return bool(_GENERAL_LABOR.search(_nfc(doc_text)))


def is_sector_mismatch(doc_text: str, contract_text: str) -> bool:
    """True when the legal source is sector-scoped and the contract is not."""
    law = _nfc(doc_text)
    contract = _nfc(contract_text)
    if not law:
        return False
    if is_general_labor_instrument(law):
        return False
    for law_pat, contract_pat in _SECTOR_SCOPES:
        if law_pat.search(law) and not contract_pat.search(contract):
            return True
    return False


def filter_sector_mismatches(
    chunks: list[Any],
    contract_text: str,
    *,
    content_attr: str = "content",
) -> tuple[list[Any], list[Any]]:
    kept: list[Any] = []
    dropped: list[Any] = []
    for ch in chunks:
        if isinstance(ch, dict):
            meta = dict(ch.get("metadata") or ch)
            content = ch.get("content") or ch.get("page_content") or ""
        else:
            meta = dict(getattr(ch, "metadata", None) or {})
            content = getattr(ch, content_attr, None) or getattr(ch, "page_content", "") or ""
        if is_sector_mismatch(doc_scope_text(meta, str(content)), contract_text):
            meta = dict(meta)
            meta["note"] = "sector_scope_mismatch"
            if hasattr(ch, "metadata"):
                ch.metadata = meta
            dropped.append(ch)
        else:
            kept.append(ch)
    return kept, dropped

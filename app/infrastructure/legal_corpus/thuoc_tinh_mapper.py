"""Map crawler thuoc_tinh.json → IngestLegalDocument dict."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_STATUS_CODE_MAP = {
    "CHL": 1,  # Còn hiệu lực
    "HHL": 2,  # Hết hiệu lực
    "BB": 2,  # Bãi bỏ
    "CHUA_HL": 3,
    "CHHL": 3,  # Chưa có hiệu lực
    "SD": 4,  # Sửa đổi một phần
}


def normalize_doc_num(doc_num: str | None) -> str | None:
    if not doc_num:
        return None
    text = unicodedata.normalize("NFC", str(doc_num)).strip().upper()
    text = text.replace("Đ", "D")
    text = re.sub(r"\s+", "", text)
    return text or None


def status_flag_from_thuoc_tinh(data: dict[str, Any]) -> int:
    if data.get("status_flag") is not None:
        try:
            return int(data["status_flag"])
        except (TypeError, ValueError):
            pass
    code = (data.get("eff_status_code") or "").strip().upper()
    if code in _STATUS_CODE_MAP:
        return _STATUS_CODE_MAP[code]
    status = (data.get("eff_status") or "").lower()
    if "bãi" in status or "hết hiệu lực" in status:
        return 2
    if "chưa" in status:
        return 3
    if "sửa" in status:
        return 4
    if "còn hiệu lực" in status:
        return 1
    return 1


def map_thuoc_tinh(raw: dict[str, Any], full_text: str | None = None) -> dict[str, Any]:
    doc_id = str(raw["doc_id"])
    doc_num = str(raw.get("doc_num") or "")
    return {
        "doc_id": doc_id,
        "doc_num": doc_num,
        "doc_num_norm": raw.get("doc_num_norm") or normalize_doc_num(doc_num),
        "title": str(raw.get("title") or ""),
        "doc_type": str(raw.get("doc_type") or "Unknown"),
        "majors": list(raw.get("majors") or []),
        "fields": list(raw.get("fields") or []),
        "issue_date": raw.get("issue_date"),
        "eff_from": raw.get("eff_from"),
        "eff_to": raw.get("eff_to"),
        "eff_status": raw.get("eff_status"),
        "eff_status_code": raw.get("eff_status_code"),
        "status_flag": status_flag_from_thuoc_tinh(raw),
        "agency": raw.get("agency"),
        "signers": list(raw.get("signers") or []),
        "source_url": raw.get("source_url"),
        "full_text": full_text if full_text is not None else raw.get("full_text"),
    }

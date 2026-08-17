"""Map crawler thuoc_tinh.json → IngestLegalDocument dict."""

from __future__ import annotations

from typing import Any

# Canonical eff_flag labels (9 values from crawl / post-update)
EFF_CHUA_XAC_DINH = "Chưa xác định"
EFF_CON = "Còn hiệu lực"
EFF_HET_TOAN_BO = "Hết hiệu lực toàn bộ"
EFF_HET_MOT_PHAN = "Hết hiệu lực một phần"
EFF_CHUA_HL = "Chưa có hiệu lực"
EFF_NGUNG = "Ngưng hiệu lực"
EFF_NGUNG_MOT_PHAN = "Ngưng hiệu lực một phần"
EFF_KHONG_PHU_HOP = "Không còn phù hợp"
EFF_CON_MOT_PHAN = "Có hiệu lực một phần"

CANONICAL_EFF_FLAGS = frozenset(
    {
        EFF_CHUA_XAC_DINH,
        EFF_CON,
        EFF_HET_TOAN_BO,
        EFF_HET_MOT_PHAN,
        EFF_CHUA_HL,
        EFF_NGUNG,
        EFF_NGUNG_MOT_PHAN,
        EFF_KHONG_PHU_HOP,
        EFF_CON_MOT_PHAN,
    }
)

# Grouped operational flag used by RAG / triggers
_EFF_FLAG_TO_STATUS: dict[str, int] = {
    EFF_CHUA_XAC_DINH: 0,
    EFF_CON: 1,
    EFF_HET_TOAN_BO: 2,
    EFF_NGUNG: 2,
    EFF_KHONG_PHU_HOP: 2,
    EFF_CHUA_HL: 3,
    EFF_HET_MOT_PHAN: 4,
    EFF_NGUNG_MOT_PHAN: 4,
    EFF_CON_MOT_PHAN: 5,
}

_STATUS_TO_EFF_FLAG: dict[int, str] = {
    0: EFF_CHUA_XAC_DINH,
    1: EFF_CON,
    2: EFF_HET_TOAN_BO,
    3: EFF_CHUA_HL,
    4: EFF_HET_MOT_PHAN,
    5: EFF_CON_MOT_PHAN,
}

_CODE_TO_EFF_FLAG: dict[str, str] = {
    "CHL": EFF_CON,
    "HHL": EFF_HET_TOAN_BO,
    "HHL1P": EFF_HET_MOT_PHAN,
    "BB": EFF_HET_TOAN_BO,
    "CHUA_HL": EFF_CHUA_HL,
    "CHHL": EFF_CHUA_HL,
    "SD": EFF_HET_MOT_PHAN,
}

# Exact / normalized label aliases → canonical
_LABEL_ALIASES: dict[str, str] = {
    "chưa xác định": EFF_CHUA_XAC_DINH,
    "còn hiệu lực": EFF_CON,
    "hết hiệu lực toàn bộ": EFF_HET_TOAN_BO,
    "hết hiệu lực": EFF_HET_TOAN_BO,
    "hết hiệu lực một phần": EFF_HET_MOT_PHAN,
    "hết hiệu lực 1 phần": EFF_HET_MOT_PHAN,
    "chưa có hiệu lực": EFF_CHUA_HL,
    "chưa hiệu lực": EFF_CHUA_HL,
    "sắp có hiệu lực": EFF_CHUA_HL,
    "ngưng hiệu lực": EFF_NGUNG,
    "ngưng hiệu lực một phần": EFF_NGUNG_MOT_PHAN,
    "không còn phù hợp": EFF_KHONG_PHU_HOP,
    "có hiệu lực một phần": EFF_CON_MOT_PHAN,
    "bãi bỏ": EFF_HET_TOAN_BO,
}


def status_flag_from_eff_flag(eff_flag: str | None) -> int:
    if not eff_flag:
        return 0
    return _EFF_FLAG_TO_STATUS.get(eff_flag, 0)


def eff_flag_for_status(status_flag: int) -> str:
    return _STATUS_TO_EFF_FLAG.get(int(status_flag), EFF_CHUA_XAC_DINH)


def normalize_eff_flag(data: dict[str, Any]) -> str:
    """Resolve crawl fields (eff_flag / eff_status / code) → one of 9 canonical labels."""
    direct = (data.get("eff_flag") or "").strip()
    if direct in CANONICAL_EFF_FLAGS:
        return direct

    # Legacy crawl keys still accepted at ingest boundary
    for key in ("eff_flag", "eff_status"):
        label = (data.get(key) or "").strip()
        if not label:
            continue
        if label in CANONICAL_EFF_FLAGS:
            return label
        aliased = _LABEL_ALIASES.get(label.lower())
        if aliased:
            return aliased

    code = (data.get("eff_status_code") or data.get("eff_code") or "").strip().upper()
    if code in _CODE_TO_EFF_FLAG:
        return _CODE_TO_EFF_FLAG[code]

    # Fuzzy fallback on free text
    text = (data.get("eff_flag") or data.get("eff_status") or "").strip().lower()
    if text:
        if "không còn phù hợp" in text:
            return EFF_KHONG_PHU_HOP
        if "ngưng" in text and "một phần" in text:
            return EFF_NGUNG_MOT_PHAN
        if "ngưng" in text:
            return EFF_NGUNG
        if "có hiệu lực một phần" in text:
            return EFF_CON_MOT_PHAN
        if "một phần" in text and ("hết" in text or "sửa" in text):
            return EFF_HET_MOT_PHAN
        if "bãi" in text or "hết hiệu lực" in text:
            return EFF_HET_TOAN_BO
        if "chưa xác định" in text:
            return EFF_CHUA_XAC_DINH
        if "chưa" in text:
            return EFF_CHUA_HL
        if "còn hiệu lực" in text:
            return EFF_CON

    return EFF_CHUA_XAC_DINH


def status_flag_from_thuoc_tinh(data: dict[str, Any]) -> int:
    """Backward-compatible: prefer explicit status_flag, else derive from eff_flag."""
    if data.get("status_flag") is not None:
        try:
            return int(data["status_flag"])
        except (TypeError, ValueError):
            pass
    return status_flag_from_eff_flag(normalize_eff_flag(data))


def _first_signer(raw: dict[str, Any]) -> tuple[str | None, str | None]:
    if raw.get("signer_name") or raw.get("signer_title"):
        return (
            (str(raw["signer_name"]).strip() or None) if raw.get("signer_name") else None,
            (str(raw["signer_title"]).strip() or None) if raw.get("signer_title") else None,
        )
    signers = raw.get("signers") or []
    if not signers:
        return None, None
    first = signers[0] if isinstance(signers[0], dict) else {}
    name = first.get("name") or first.get("personName")
    title = first.get("title") or first.get("jobTitleName")
    return (
        str(name).strip() if name else None,
        str(title).strip() if title else None,
    )


def map_thuoc_tinh(raw: dict[str, Any], full_text: str | None = None) -> dict[str, Any]:
    doc_id = str(raw["doc_id"])
    doc_num = str(raw.get("doc_num") or "")
    eff_flag = normalize_eff_flag(raw)
    status_flag = status_flag_from_thuoc_tinh({**raw, "eff_flag": eff_flag})
    signer_name, signer_title = _first_signer(raw)
    return {
        "doc_id": doc_id,
        "doc_num": doc_num,
        "title": str(raw.get("title") or ""),
        "doc_type": str(raw.get("doc_type") or "Unknown"),
        "majors": list(raw.get("majors") or []),
        "fields": list(raw.get("fields") or []),
        "issue_date": raw.get("issue_date"),
        "eff_from": raw.get("eff_from"),
        "eff_to": raw.get("eff_to"),
        "eff_flag": eff_flag,
        "status_flag": status_flag,
        "agency": raw.get("agency"),
        "signer_name": signer_name,
        "signer_title": signer_title,
        "source_url": raw.get("source_url"),
        "full_text": full_text if full_text is not None else raw.get("full_text"),
    }

"""Shared document effectivity checks (status_flag 0..5 + date window).

Used by preamble «Căn cứ…», red-flag hydrate, completeness, and GraphRAG
grounding so every citation either proves it is ok to rely on as of the
contract date, or is explicitly marked unverified / not citable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.agents.labor_code_resolver import _parse_as_of

_STATUS_LABEL = {
    0: "Chưa xác định",
    1: "Còn hiệu lực",
    2: "Hết hiệu lực toàn bộ",
    3: "Chưa có hiệu lực",
    4: "Hết hiệu lực một phần",
    5: "Có hiệu lực một phần",
}


@dataclass(frozen=True, slots=True)
class Effectivity:
    """Result of checking one legal_documents row against an analysis date."""

    ok_to_cite: bool
    """False → do not rely on this instrument when drafting / judging."""

    verified: bool
    """True when checked against a DB row + as_of (not a blind fallback)."""

    status_label: str
    """Short label for UI (citation.status)."""

    detail: str
    """Human reason (for risk reasons / citation.summary notes)."""

    status_flag: int = 0


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def evaluate_document_effectivity(
    row: dict[str, Any] | None,
    as_of: str | date | None = None,
) -> Effectivity:
    """Decide whether a document may be used as a living legal basis on ``as_of``."""
    as_of_d = _parse_as_of(as_of)
    as_of_s = as_of_d.isoformat()

    if not row:
        return Effectivity(
            ok_to_cite=False,
            verified=False,
            status_label="Chưa đối chiếu kho",
            detail=(
                f"Chưa tra được văn bản trong kho pháp điển tại ngày {as_of_s} "
                "— không xác nhận được hiệu lực để nêu làm căn cứ soạn hợp đồng."
            ),
            status_flag=0,
        )

    sf = int(row.get("status_flag") or 0)
    cached = (row.get("eff_flag") or _STATUS_LABEL.get(sf, "Chưa xác định")).strip()
    eff_from = _as_date(row.get("eff_from"))
    eff_to = _as_date(row.get("eff_to"))
    doc = str(row.get("doc_num") or row.get("title") or "VB").strip()

    if sf == 2:
        return Effectivity(
            ok_to_cite=False,
            verified=True,
            status_label="Hết hiệu lực",
            detail=f"{doc}: hết hiệu lực toàn bộ ({cached}) — không dùng làm căn cứ tại {as_of_s}.",
            status_flag=sf,
        )
    if sf == 3 or (eff_from and eff_from > as_of_d):
        return Effectivity(
            ok_to_cite=False,
            verified=True,
            status_label="Chưa có hiệu lực",
            detail=f"{doc}: chưa có hiệu lực tại {as_of_s} ({cached}).",
            status_flag=sf,
        )
    if eff_to and eff_to <= as_of_d:
        return Effectivity(
            ok_to_cite=False,
            verified=True,
            status_label="Hết hiệu lực",
            detail=(
                f"{doc}: đã hết hiệu lực theo eff_to={eff_to.isoformat()} "
                f"(ngày phân tích {as_of_s})."
            ),
            status_flag=sf,
        )
    if sf == 4:
        return Effectivity(
            ok_to_cite=True,
            verified=True,
            status_label=f"Đã đối chiếu · Còn hiệu lực (có sửa đổi) · {as_of_s}",
            detail=(
                f"{doc}: còn áp dụng tại {as_of_s} nhưng đã hết hiệu lực một phần — "
                "khi nêu làm căn cứ soạn HĐ, đối chiếu điều còn hiệu lực / văn bản sửa đổi."
            ),
            status_flag=sf,
        )
    if sf in (1, 5):
        part = " (một phần)" if sf == 5 else ""
        return Effectivity(
            ok_to_cite=True,
            verified=True,
            status_label=f"Đã đối chiếu · Còn hiệu lực{part} · {as_of_s}",
            detail=f"{doc}: còn hiệu lực tại {as_of_s} ({cached}).",
            status_flag=sf,
        )
    # sf == 0 or unknown — soft-allow but mark uncertainty
    return Effectivity(
        ok_to_cite=True,
        verified=True,
        status_label=f"Đã đối chiếu · Chưa rõ trạng thái · {as_of_s}",
        detail=f"{doc}: trạng thái kho chưa xác định ({cached}) tại {as_of_s} — cần rà soát thêm.",
        status_flag=sf,
    )


def citation_status_for_labor(
    labor: dict[str, Any] | None,
    as_of: str | date | None = None,
) -> Effectivity:
    """Effectivity of the resolved Bộ luật Lao động used to ground red-flags."""
    return evaluate_document_effectivity(labor, as_of)

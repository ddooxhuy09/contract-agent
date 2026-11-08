"""Shared document effectivity checks (status_flag 0..5 + date window).

Used by preamble «Căn cứ…», red-flag hydrate, completeness, and GraphRAG
grounding so every citation either proves it is ok to rely on as of the
contract date, or is explicitly marked unverified / not citable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.core.dates import parse_as_of

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
    as_of_d = parse_as_of(as_of)
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


# ---------------------------------------------------------------------------
# Which date the law is judged at (signing vs today) — made explicit in the report
# ---------------------------------------------------------------------------

_BASIS_LABEL = {
    "ngay_ky": "ngày ký",
    "ngay_bat_dau": "ngày bắt đầu hiệu lực",
    "hom_nay": "ngày phân tích",
}


def legal_timeline(
    execution_date: str | None,
    start_date: str | None,
    end_date: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """The date legal grounds are checked at, why, and whether the law moved since.

    Contract terms are judged under the law in force when they were agreed (signing date,
    else start date, else today). Today's date is reported next to it, and the Labor Code
    status is compared at both dates so a later change is called out instead of silent.
    """
    from app.core.dates import parse_vn_date

    today = today or date.today()
    signing, start = parse_vn_date(execution_date), parse_vn_date(start_date)
    basis, as_of = ("ngay_ky", signing) if signing else ("ngay_bat_dau", start) if start else ("hom_nay", today)
    out: dict[str, Any] = {
        "ngay_doi_chieu": as_of.isoformat(),
        "co_so": basis,
        "ngay_ky": signing.isoformat() if signing else None,
        "ngay_bat_dau": start.isoformat() if start else None,
        "ngay_ket_thuc": (parse_vn_date(end_date).isoformat() if parse_vn_date(end_date) else None),
        "ngay_phan_tich": today.isoformat(),
        "thay_doi_sau_ky": None,
    }
    note = f"Căn cứ pháp luật được đối chiếu tại {_BASIS_LABEL[basis]} ({as_of.isoformat()})"
    if basis == "hom_nay":
        note += " vì không đọc được ngày ký / ngày bắt đầu của hợp đồng"
    out["ghi_chu"] = note + f"; báo cáo được lập ngày {today.isoformat()}."
    if as_of != today:
        out["thay_doi_sau_ky"] = _law_change_note(as_of, today)
    return out


def _law_change_note(then: date, now: date) -> str | None:
    try:
        from app.agents.labor_code_resolver import resolve_labor_code_document

        a, b = resolve_labor_code_document(then), resolve_labor_code_document(now)
    except Exception:
        return None
    if not a or not b:
        return None
    if (a["doc_id"], a["status_flag"]) == (b["doc_id"], b["status_flag"]):
        return (
            f"Bộ luật Lao động {a['doc_num']} giữ nguyên trạng thái giữa {then.isoformat()} và {now.isoformat()} "
            "trong kho pháp điển. Nội dung điều khoản được trích là bản còn hiệu lực hiện tại."
        )
    return (
        f"Văn bản đối chiếu đã thay đổi: tại {then.isoformat()} là {a['doc_num']} "
        f"({_STATUS_LABEL.get(a['status_flag'], '?')}), tại {now.isoformat()} là {b['doc_num']} "
        f"({_STATUS_LABEL.get(b['status_flag'], '?')}) — cần rà soát lại các điều khoản trích dẫn."
    )


def stamp_legal_basis(risks: list, timeline: dict[str, Any]) -> list:
    """Make every citation status say which date it was checked at («· tại ngày ký 2026-07-15»)."""
    iso, label = timeline["ngay_doi_chieu"], _BASIS_LABEL[timeline["co_so"]]
    old, new = f"· {iso}", f"· tại {label} {iso}"

    def fix(text):
        return text.replace(old, new) if isinstance(text, str) and old in text and new not in text else text

    def fix_cites(cites):
        return [c.model_copy(update={"status": fix(c.status)}) for c in cites] if cites else cites

    out = []
    for r in risks:
        upd: dict[str, Any] = {"legal_basis": fix(r.legal_basis), "legal_citations": fix_cites(r.legal_citations)}
        if r.findings:
            upd["findings"] = [f.model_copy(update={"legal_citations": fix_cites(f.legal_citations)}) for f in r.findings]
        out.append(r.model_copy(update=upd))
    return out

"""Validate the contract preamble «Căn cứ …» citations against legal_documents.

Looks up each cited số hiệu, checks status_flag (0..5) as of analysis date,
and flags missing / expired / not-yet-effective / date mismatches.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.agents.effectivity import Effectivity, evaluate_document_effectivity
from app.agents.labor_code_resolver import _parse_as_of
from app.core.logging import logger
from app.schemas.contract import LegalCitation, RiskItem

_DOC_NUM = re.compile(
    r"(?<!\d)(\d{1,4}/\d{4}/[A-ZĐ0-9.\-]+)",
    re.IGNORECASE,
)
_PREFIX = (
    r"(?:Thông\s*tư\s*liên\s*tịch|Thông\s*tư|Nghị\s*định|Quyết\s*định|"
    r"Bộ\s*luật|Luật|Pháp\s*lệnh|Nghị\s*quyết|Chỉ\s*thị|Lệnh)"
)
_CAN_CU_LINE = re.compile(
    rf"(?:^|\n)\s*[-•*]?\s*Căn\s*cứ\s+({_PREFIX}[^;\n]{{0,200}})",
    re.IGNORECASE,
)
_DATE_VN = re.compile(
    r"ngày\s+(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})"
    r"|ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
    re.IGNORECASE,
)
# Stop preamble once body starts
_BODY_START = re.compile(
    r"(?:^|\n)\s*(?:Hôm\s*nay\s*ngày|Người\s*sử\s*dụng\s*lao\s*động|Điều\s*1\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PreambleCite:
    raw: str
    doc_num: str | None
    name_hint: str | None
    cited_date: date | None


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _parse_vn_date(text: str) -> date | None:
    m = _DATE_VN.search(text or "")
    if not m:
        return None
    if m.group(1):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        d, mo, y = int(m.group(4)), int(m.group(5)), int(m.group(6))
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def extract_preamble(text: str) -> str:
    body = _nfc(text)
    m = _BODY_START.search(body)
    return body[: m.start()] if m else body[:2500]


def parse_can_cu_citations(text: str) -> list[PreambleCite]:
    """Parse «Căn cứ Bộ luật … số X/Y/… ngày …» from the contract header."""
    preamble = extract_preamble(text)
    out: list[PreambleCite] = []
    seen: set[str] = set()
    for m in _CAN_CU_LINE.finditer(preamble):
        raw = m.group(1).strip().rstrip(".;,")
        # Skip non-instrument boilerplate
        if re.search(r"^vào\s+nhu\s*cầu|^thỏa\s*thuận|^khả\s*năng", raw, re.I):
            continue
        num_m = _DOC_NUM.search(raw)
        doc_num = num_m.group(1).upper().replace("Đ", "Đ") if num_m else None
        if doc_num:
            # Normalize Đ in doc nums carefully — keep as written for DB match variants
            doc_num = num_m.group(1)
        name_hint = None
        pref = re.match(_PREFIX, raw, re.I)
        if pref:
            after = raw[pref.end() :].strip()
            if doc_num and "số" in after.lower():
                name_hint = re.split(r"\bsố\b", after, maxsplit=1, flags=re.I)[0].strip(" ,.-")
            else:
                name_hint = after[:80].strip(" ,.-")
        key = (doc_num or raw).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            PreambleCite(
                raw=raw,
                doc_num=doc_num,
                name_hint=name_hint or None,
                cited_date=_parse_vn_date(raw),
            )
        )
    return out


def _lookup_doc(doc_num: str) -> dict[str, Any] | None:
    try:
        from app.infrastructure.db.connection import get_db
    except Exception as e:
        logger.warning("preamble lookup: no DB (%s)", e)
        return None
    variants = list(
        dict.fromkeys(
            [
                doc_num,
                doc_num.upper(),
                doc_num.replace("Đ", "D").replace("đ", "d"),
                doc_num.replace("D", "Đ"),
            ]
        )
    )
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT doc_id, doc_num, title, doc_type, status_flag, eff_flag,
                           eff_from, eff_to, issue_date, source_url
                    FROM legal_documents
                    WHERE UPPER(REPLACE(doc_num, 'Đ', 'D')) = ANY(%s)
                       OR doc_num = ANY(%s)
                    ORDER BY
                      CASE status_flag
                        WHEN 1 THEN 0 WHEN 5 THEN 1 WHEN 4 THEN 2 WHEN 0 THEN 3 ELSE 9
                      END
                    LIMIT 1
                    """,
                    (
                        [v.upper().replace("Đ", "D").replace("đ", "d") for v in variants],
                        variants,
                    ),
                )
                row = cur.fetchone()
    except Exception as e:
        logger.warning("preamble lookup failed for %s: %s", doc_num, e)
        return None
    if not row:
        return None
    return {
        "doc_id": row[0],
        "doc_num": row[1],
        "title": row[2],
        "doc_type": row[3],
        "status_flag": int(row[4] if row[4] is not None else 0),
        "eff_flag": row[5],
        "eff_from": row[6],
        "eff_to": row[7],
        "issue_date": row[8],
        "source_url": row[9],
    }


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _effective_on(row: dict[str, Any], as_of: date) -> Effectivity:
    return evaluate_document_effectivity(row, as_of)


def _dates_match(cited: date | None, issue: date | None) -> bool:
    if not cited or not issue:
        return True
    return cited == issue


def check_preamble_citations(
    text: str,
    *,
    as_of_date: str | date | None = None,
) -> list[RiskItem]:
    cites = parse_can_cu_citations(text)
    if not cites:
        return []

    as_of = _parse_as_of(as_of_date)
    problems: list[str] = []
    citations: list[LegalCitation] = []
    severity = "warning"
    soft_notes: list[str] = []

    for cite in cites:
        if not cite.doc_num:
            problems.append(
                f"Câu căn cứ «{cite.raw[:80]}» không có số hiệu văn bản để đối chiếu trong kho."
            )
            continue
        row = _lookup_doc(cite.doc_num)
        if not row:
            problems.append(
                f"Không tìm thấy văn bản số {cite.doc_num} trong kho pháp điển "
                f"(căn cứ: «{cite.raw[:100]}»)."
            )
            severity = "warning"
            continue

        eff = _effective_on(row, as_of)
        citations.append(
            LegalCitation(
                title=str(row.get("title") or cite.raw),
                summary=eff.detail,
                doc_number=str(row.get("doc_num") or cite.doc_num),
                source_url=row.get("source_url"),
                status=eff.status_label,
            )
        )

        if not eff.ok_to_cite:
            problems.append(
                f"{cite.doc_num} — {row.get('title') or ''}: {eff.detail} "
                f"Không nên nêu làm căn cứ còn hiệu lực khi soạn / ký hợp đồng tại {as_of.isoformat()}."
            )
            if eff.status_flag == 2 or "hết hiệu lực" in eff.detail.lower():
                severity = "critical"
        elif eff.status_flag == 4:
            soft_notes.append(eff.detail)
        elif "chưa rõ" in eff.status_label.lower():
            soft_notes.append(eff.detail)

        issue = _as_date(row.get("issue_date"))
        if cite.cited_date and issue and not _dates_match(cite.cited_date, issue):
            problems.append(
                f"{cite.doc_num}: ngày ghi trên HĐ ({cite.cited_date.isoformat()}) "
                f"không khớp issue_date trong kho ({issue.isoformat()})."
            )

        # Soft check: name hint vs title
        if cite.name_hint and row.get("title"):
            hint = cite.name_hint.lower()
            title = str(row["title"]).lower()
            tokens = [t for t in re.split(r"\s+", hint) if len(t) > 3]
            if tokens and not any(t in title for t in tokens[:3]):
                problems.append(
                    f"{cite.doc_num}: tên gọi trên HĐ («{cite.name_hint}») "
                    f"không khớp tiêu đề trong kho («{row['title'][:80]}»)."
                )

    # Partial-effect instruments are still citable but must be called out for drafters
    problems.extend(soft_notes)

    if not problems:
        return []

    # Soft-only notes (status 4) stay warning; hard expire stays critical if set
    if soft_notes and not any("Không nên nêu" in p or "không tìm thấy" in p.lower() for p in problems):
        severity = "warning"

    return [
        RiskItem(
            clause_ref="Phần căn cứ (đầu hợp đồng)",
            title="Căn cứ pháp lý đầu HĐ cần rà soát",
            issue=(
                "Các văn bản nêu tại mục «Căn cứ…» đã được đối chiếu với kho pháp điển "
                f"tại ngày {as_of.isoformat()}. Phát hiện vấn đề về hiệu lực / số hiệu / ngày ban hành "
                "— cần xác nhận trước khi dùng làm căn cứ soạn hợp đồng."
            ),
            severity=severity,
            summary_topics=["Căn cứ pháp lý", "Hiệu lực văn bản", "Preamble"],
            reasons=problems,
            impact=[
                "Căn cứ sai hoặc hết hiệu lực làm suy giảm giá trị đối chiếu khi tranh chấp / thanh tra.",
                "Nên thay bằng văn bản còn hiệu lực (hoặc bản sửa đổi, bổ sung đang áp dụng).",
            ],
            actions=[
                "Tra cứu lại từng số hiệu trong mục Căn cứ và cập nhật bản còn hiệu lực.",
                "Sửa ngày ban hành / tên văn bản cho khớp văn bản chính thức.",
                "Với VB hết hiệu lực một phần: chỉ nêu điều còn áp dụng hoặc dẫn bản sửa đổi.",
            ],
            legal_basis="; ".join(
                f"{c.doc_number or c.title}: {c.status or c.summary}" for c in citations
            )
            or None,
            legal_citations=citations or None,
            recommendation="\n".join(f"- {p}" for p in problems),
            confidence=0.8 if citations else 0.55,
        )
    ]

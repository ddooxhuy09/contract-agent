"""Employment-contract completeness vs Bộ luật Lao động Điều 21 (mandatory contents).

Also extracts job/workplace text used for sector-scope RAG (only focus industry
circulars when the contract's job section mentions that sector).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.agents.labor_code_resolver import (
    fetch_article_21_snippet,
    resolve_labor_code_document,
)
from app.schemas.contract import ContractAnalysis, LegalCitation, RiskItem

_STATUS_LABEL = {
    0: "Chưa xác định",
    1: "Còn hiệu lực",
    2: "Hết hiệu lực toàn bộ",
    3: "Chưa có hiệu lực",
    4: "Hết hiệu lực một phần",
    5: "Có hiệu lực một phần",
}


@dataclass(frozen=True, slots=True)
class MandatoryField:
    key: str
    label: str
    patterns: tuple[re.Pattern[str], ...]
    severity: str = "warning"  # missing content → warning (critical if clearly illegal omission of BH)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _pat(*alts: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{a})" for a in alts), re.IGNORECASE)


# Khoản 1 Điều 21 BLLĐ 2019 — nội dung chủ yếu
_MANDATORY: tuple[MandatoryField, ...] = (
    MandatoryField(
        "employer_identity",
        "Thông tin NSDLĐ (tên, địa chỉ, người giao kết + chức danh)",
        (
            _pat(r"người\s*sử\s*dụng\s*lao\s*động", r"NSDLĐ", r"công\s*ty"),
            _pat(r"địa\s*chỉ", r"MST|mã\s*số\s*doanh\s*nghiệp"),
            _pat(r"đại\s*diện|giám\s*đốc|chức\s*vụ|chức\s*danh"),
        ),
    ),
    MandatoryField(
        "employee_identity",
        "Thông tin NLĐ (họ tên, ngày sinh, giới tính, nơi cư trú, CCCD/CMND/hộ chiếu)",
        (
            _pat(r"người\s*lao\s*động", r"\bNLĐ\b"),
            _pat(r"ngày\s*sinh|sinh\s*ngày"),
            _pat(r"CCCD|CMND|căn\s*cước|hộ\s*chiếu"),
        ),
    ),
    MandatoryField(
        "job_and_workplace",
        "Công việc và địa điểm làm việc",
        (
            _pat(r"công\s*việc|chức\s*danh|chức\s*vụ|nội\s*dung\s*công\s*việc"),
            _pat(r"địa\s*điểm\s*làm\s*việc|đơn\s*vị\s*làm\s*việc|nơi\s*làm\s*việc|phòng\s+"),
        ),
    ),
    MandatoryField(
        "term",
        "Thời hạn hợp đồng lao động",
        (_pat(r"thời\s*hạn|xác\s*định\s*thời\s*hạn|không\s*xác\s*định\s*thời\s*hạn|từ\s*ngày.+đến"),),
    ),
    MandatoryField(
        "wage",
        "Mức lương, hình thức / thời hạn trả lương, phụ cấp và khoản bổ sung",
        (
            _pat(r"mức\s*lương|tiền\s*lương|lương\s*cơ\s*bản|\d[\d\.,]*\s*(?:VNĐ|đồng)"),
            _pat(r"hình\s*thức\s*trả\s*lương|trả\s*lương|thời\s*hạn\s*trả\s*lương|ngày\s*trả\s*lương"),
        ),
    ),
    MandatoryField(
        "pay_raise",
        "Chế độ nâng bậc, nâng lương",
        (_pat(r"nâng\s*bậc|nâng\s*lương|xét\s*nâng\s*lương|điều\s*chỉnh\s*lương"),),
    ),
    MandatoryField(
        "working_hours_rest",
        "Thời giờ làm việc, thời giờ nghỉ ngơi",
        (
            _pat(r"thời\s*giờ\s*làm\s*việc|giờ\s*làm\s*việc|\d+\s*tiếng\s*/\s*ngày"),
            _pat(r"nghỉ\s*ngơi|nghỉ\s*tuần|nghỉ\s*giữa\s*giờ|ngày\s*nghỉ"),
        ),
    ),
    MandatoryField(
        "ppe",
        "Trang bị bảo hộ lao động",
        (_pat(r"bảo\s*hộ\s*lao\s*động|trang\s*bị\s*bảo\s*hộ|phương\s*tiện\s*bảo\s*vệ"),),
    ),
    MandatoryField(
        "social_insurance",
        "Bảo hiểm xã hội, bảo hiểm y tế và bảo hiểm thất nghiệp",
        (_pat(r"bảo\s*hiểm\s*xã\s*hội|BHXH|bảo\s*hiểm\s*y\s*tế|BHYT|bảo\s*hiểm\s*thất\s*nghiệp|BHTN"),),
        severity="warning",
    ),
    MandatoryField(
        "training",
        "Đào tạo, bồi dưỡng, nâng cao trình độ, kỹ năng nghề",
        (_pat(r"đào\s*tạo|bồi\s*dưỡng|nâng\s*cao\s*trình\s*độ|kỹ\s*năng\s*nghề"),),
    ),
)


def is_labor_contract(analysis: ContractAnalysis | None, text: str) -> bool:
    blob = _nfc(f"{(analysis.contract_type if analysis else '') or ''} {text[:2000]}")
    return bool(
        re.search(r"hợp\s*đồng\s*lao\s*động|\bHĐLĐ\b|người\s*sử\s*dụng\s*lao\s*động", blob, re.I)
    )


def extract_job_context(text: str, analysis: ContractAnalysis | None = None) -> str:
    """Pull job / workplace wording for sector-scope (AI, dầu khí, quân đội, …)."""
    parts: list[str] = []
    if analysis and analysis.contract_type:
        parts.append(analysis.contract_type)
    body = _nfc(text)
    # Prefer Điều về công việc / thời hạn (tolerate **Điều 1:** markdown).
    m = re.search(
        r"(?:\*{0,2}\s*)?Điều\s*1\b[^\n]{0,120}(?:công\s*việc|thời\s*hạn)"
        r"[\s\S]{0,1500}?(?=\n\s*(?:\*{0,2}\s*)?Điều\s*2\b|\Z)",
        body,
        re.I,
    )
    if m:
        parts.append(m.group(0))
    else:
        for clause in (analysis.clauses if analysis else []) or []:
            title = (clause.title or "").lower()
            if any(k in title for k in ("công việc", "thời hạn", "chức danh")):
                parts.append(f"{clause.title or ''} {clause.summary or ''}")
    # Identity lines often carry company industry hint
    m2 = re.search(r"công\s*ty[^\n]{5,160}", body, re.I)
    if m2:
        parts.append(m2.group(0))
    # Harvest distinctive workplace tokens even if Điều 1 regex misses.
    for pat in (
        r"\bAI\b",
        r"MLOps",
        r"Vision\s*Transformers?",
        r"Phòng\s+Nghiên\s*cứu[^\n.]{0,80}",
        r"Thực\s*tập\s*sinh[^\n.]{0,40}",
    ):
        hit = re.search(pat, body, re.I)
        if hit:
            parts.append(hit.group(0))
    return _nfc(" ".join(dict.fromkeys(p for p in parts if p)))[:1500]


def field_is_covered(text: str, field: MandatoryField) -> bool:
    body = _nfc(text)
    # Each entry in patterns is an OR-group; every group must hit.
    for group in field.patterns:
        if not group.search(body):
            return False
    return True


def missing_mandatory_fields(text: str) -> list[MandatoryField]:
    return [f for f in _MANDATORY if not field_is_covered(text, f)]


def check_labor_completeness(
    text: str,
    analysis: ContractAnalysis | None = None,
    *,
    as_of_date: str | None = None,
) -> list[RiskItem]:
    """Emit risk items for Điều 21 mandatory contents that are absent."""
    if not is_labor_contract(analysis, text):
        return []

    missing = missing_mandatory_fields(text)
    if not missing:
        return []

    labor = resolve_labor_code_document(as_of_date)
    snippet = fetch_article_21_snippet(labor["doc_id"]) if labor else None
    doc_num = (labor or {}).get("doc_num") or "45/2019/QH14"
    doc_title = (labor or {}).get("title") or "Bộ luật Lao động"
    sf = int((labor or {}).get("status_flag") or 1)
    status_label = (labor or {}).get("eff_flag") or _STATUS_LABEL.get(sf, "Chưa xác định")

    citations = [
        LegalCitation(
            title=f"Điều 21 {doc_title}",
            summary=(snippet or "Nội dung chủ yếu bắt buộc của hợp đồng lao động.")[:500],
            doc_number=str(doc_num),
            article="Điều 21",
            quote=(snippet or "")[:280] or None,
            source_url=(labor or {}).get("source_url"),
            status=status_label,
        )
    ]

    labels = [f.label for f in missing]
    bullets = [f"- {f.label}" for f in missing]
    return [
        RiskItem(
            clause_ref="Hợp đồng (toàn văn)",
            title="Thiếu nội dung chủ yếu bắt buộc của HĐLĐ",
            issue=(
                "Hợp đồng lao động chưa thể hiện đủ các nội dung chủ yếu theo Điều 21 Bộ luật Lao động "
                f"({len(missing)} mục thiếu). Các mục sau không tìm thấy hoặc không đủ rõ trong văn bản."
            ),
            severity="warning",
            summary_topics=["Thiếu nội dung bắt buộc", "Điều 21 BLLĐ", "HĐLĐ"],
            reasons=labels,
            impact=[
                "Hợp đồng có nguy cơ bị coi là không đầy đủ nội dung chủ yếu theo pháp luật lao động.",
                "Rủi ro khi thanh tra / tranh chấp về quyền lợi NLĐ chưa được thỏa thuận rõ.",
            ],
            actions=[
                "Bổ sung từng mục còn thiếu theo Điều 21 khoản 1 Bộ luật Lao động.",
                "Đối chiếu Thông tư hướng dẫn nội dung HĐLĐ (nếu áp dụng) để ghi đủ thông tin định danh và chế độ.",
            ],
            legal_basis=f"Điều 21 Bộ luật Lao động ({doc_num}) — {status_label}",
            legal_citations=citations,
            recommendation="\n".join(bullets),
            confidence=0.75 if labor else 0.55,
        )
    ]

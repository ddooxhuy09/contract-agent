"""Employment-contract completeness vs Bộ luật Lao động Điều 21 (mandatory contents).

Also extracts job/workplace text used for sector-scope RAG (only focus industry
circulars when the contract's job section mentions that sector).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.agents.labor_code_resolver import resolve_labor_code_document
from app.schemas.contract import ContractAnalysis, LegalCitation, RiskItem


CO, CHUA_DAY_DU, THIEU, KHONG_AP_DUNG = "co", "chua_day_du", "thieu", "khong_ap_dung"


@dataclass(frozen=True, slots=True)
class Part:
    """One sub-requirement of a mandatory item (e.g. «giới tính» inside «thông tin NLĐ»)."""

    label: str
    pattern: re.Pattern[str]
    # The item is mentioned but only to exclude it («không tham gia đóng BHXH») → not present.
    negate: re.Pattern[str] | None = None


@dataclass(frozen=True, slots=True)
class MandatoryField:
    key: str
    label: str
    point: str  # điểm of Điều 21 khoản 1 (matches the corpus path leaf: a b c d dd e g h i k)
    parts: tuple[Part, ...]
    severity: str = "warning"  # missing content → warning
    # Job contexts where the item can legitimately be stated as «không áp dụng».
    na_when: re.Pattern[str] | None = None
    na_unless: re.Pattern[str] | None = None

    @property
    def law_ref(self) -> str:
        shown = "đ" if self.point == "dd" else self.point
        return f"Điều 21 khoản 1 điểm {shown}"


@dataclass(frozen=True, slots=True)
class FieldAssessment:
    field: MandatoryField
    status: str  # co | chua_day_du | thieu | khong_ap_dung
    found: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    note: str = ""


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _pat(*alts: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{a})" for a in alts), re.IGNORECASE)


_OFFICE_JOB = _pat(
    r"\bAI\b", r"MLOps", r"phần\s*mềm", r"lập\s*trình", r"nghiên\s*cứu", r"văn\s*phòng",
    r"hành\s*chính", r"kế\s*toán", r"nhân\s*sự",
)
_HAZARD_JOB = _pat(
    r"nặng\s*nhọc", r"độc\s*hại", r"nguy\s*hiểm", r"hóa\s*chất", r"công\s*trường",
    r"vận\s*hành\s*máy", r"xưởng",
)

# Khoản 1 Điều 21 BLLĐ 2019 — nội dung chủ yếu, split into the sub-items the law lists.
_MANDATORY: tuple[MandatoryField, ...] = (
    MandatoryField(
        "employer_identity",
        "Thông tin NSDLĐ (tên, địa chỉ, người giao kết + chức danh)",
        "a",
        (
            Part("Tên người sử dụng lao động", _pat(r"người\s*sử\s*dụng\s*lao\s*động", r"NSDLĐ", r"công\s*ty")),
            Part("Địa chỉ người sử dụng lao động", _pat(r"địa\s*chỉ", r"MST|mã\s*số\s*doanh\s*nghiệp")),
            Part("Họ tên, chức danh người giao kết", _pat(r"đại\s*diện|giám\s*đốc|chức\s*vụ|chức\s*danh")),
        ),
    ),
    MandatoryField(
        "employee_identity",
        "Thông tin NLĐ (họ tên, ngày sinh, giới tính, CCCD/CMND/hộ chiếu)",
        "b",
        (
            Part("Họ tên người lao động", _pat(r"(?:ông|bà)\s+\S+", r"họ\s*(?:và\s*)?tên")),
            Part("Ngày sinh", _pat(r"ngày\s*sinh|sinh\s*ngày")),
            Part("Giới tính", _pat(r"giới\s*tính")),
            Part("Số CCCD/CMND/hộ chiếu", _pat(r"CCCD|CMND|căn\s*cước|hộ\s*chiếu")),
        ),
    ),
    MandatoryField(
        "employee_residence",
        "Nơi cư trú / địa chỉ hiện tại của NLĐ",
        "b",
        (
            # Không dùng bare "địa chỉ" — sẽ khớp địa chỉ NSDLĐ trên cùng văn bản.
            Part(
                "Nơi cư trú của người lao động",
                _pat(
                    r"nơi\s*cư\s*trú",
                    r"địa\s*chỉ\s*hiện\s*tại",
                    r"địa\s*chỉ\s*thường\s*trú",
                    r"địa\s*chỉ\s*tạm\s*trú",
                    r"chỗ\s*ở\s*(?:hiện\s*tại|thường\s*trú)",
                    r"thường\s*trú\s*:",
                    r"tạm\s*trú\s*:",
                ),
            ),
        ),
    ),
    MandatoryField(
        "job_and_workplace",
        "Công việc và địa điểm làm việc",
        "c",
        (
            Part("Công việc phải làm", _pat(r"công\s*việc|chức\s*danh|chức\s*vụ|nội\s*dung\s*công\s*việc")),
            # «Đơn vị / phòng» là bộ phận, không phải địa điểm làm việc cụ thể.
            Part("Địa điểm làm việc cụ thể", _pat(r"địa\s*điểm\s*làm\s*việc|nơi\s*làm\s*việc")),
        ),
    ),
    MandatoryField(
        "term",
        "Thời hạn hợp đồng lao động",
        "d",
        (
            Part("Loại hợp đồng", _pat(r"xác\s*định\s*thời\s*hạn|loại\s*hợp\s*đồng")),
            Part("Thời hạn / ngày bắt đầu – kết thúc", _pat(r"thời\s*hạn|từ\s*ngày.+đến")),
        ),
    ),
    MandatoryField(
        "wage",
        "Mức lương, hình thức / thời hạn trả lương, phụ cấp và khoản bổ sung",
        "dd",
        (
            Part("Mức lương", _pat(r"mức\s*lương|lương\s*cơ\s*bản|\d[\d\.,]*\s*(?:VNĐ|đồng)\s*/\s*(?:tháng|giờ|ngày)|\d[\d\.,]*\s*(?:VNĐ|đồng)")),
            Part("Hình thức trả lương", _pat(r"hình\s*thức\s*trả\s*lương|trả\s*lương\s*(?:bằng|qua)|chuyển\s*khoản|tiền\s*mặt")),
            Part("Thời hạn trả lương", _pat(r"thời\s*hạn\s*trả\s*lương|ngày\s*trả\s*lương|trả\s*lương\s*(?:vào|định\s*kỳ|hằng\s*tháng|hàng\s*tháng)")),
            Part("Phụ cấp và các khoản bổ sung", _pat(r"phụ\s*cấp|khoản\s*bổ\s*sung|tiền\s*thưởng|thưởng\s")),
        ),
    ),
    MandatoryField(
        "pay_raise",
        "Chế độ nâng bậc, nâng lương",
        "e",
        (Part("Chế độ nâng bậc, nâng lương", _pat(r"nâng\s*bậc|nâng\s*lương|xét\s*nâng\s*lương|điều\s*chỉnh\s*lương")),),
    ),
    MandatoryField(
        "working_hours_rest",
        "Thời giờ làm việc, thời giờ nghỉ ngơi",
        "g",
        (
            Part("Thời giờ làm việc", _pat(r"thời\s*giờ\s*làm\s*việc|giờ\s*làm\s*việc|\d+\s*tiếng\s*/\s*ngày|\d+\s*giờ\s*/\s*(?:ngày|tuần)")),
            # «ngày nghỉ cuối tuần» trong câu bắt làm thêm giờ không phải chế độ nghỉ ngơi.
            Part(
                "Thời giờ nghỉ ngơi",
                _pat(
                    r"thời\s*giờ\s*nghỉ\s*ngơi", r"nghỉ\s*ngơi", r"nghỉ\s*giữa\s*(?:giờ|ca)",
                    r"nghỉ\s*(?:hằng|hàng)\s*tuần", r"nghỉ\s*phép", r"nghỉ\s*hằng\s*năm", r"nghỉ\s*lễ",
                ),
            ),
        ),
    ),
    MandatoryField(
        "ppe",
        "Trang bị bảo hộ lao động",
        "h",
        (Part("Trang bị bảo hộ lao động", _pat(r"bảo\s*hộ\s*lao\s*động|trang\s*bị\s*bảo\s*hộ|phương\s*tiện\s*bảo\s*vệ")),),
        na_when=_OFFICE_JOB,
        na_unless=_HAZARD_JOB,
    ),
    MandatoryField(
        "social_insurance",
        "Bảo hiểm xã hội, bảo hiểm y tế và bảo hiểm thất nghiệp",
        "i",
        (
            Part(
                "Bảo hiểm xã hội, y tế, thất nghiệp",
                _pat(r"bảo\s*hiểm\s*xã\s*hội|BHXH|bảo\s*hiểm\s*y\s*tế|BHYT|bảo\s*hiểm\s*thất\s*nghiệp|BHTN"),
                negate=_pat(r"không\s*tham\s*gia\s*(?:đóng\s*)?Bảo\s*hiểm", r"không\s*đóng\s*(?:BHXH|BHYT)"),
            ),
        ),
    ),
    MandatoryField(
        "training",
        "Đào tạo, bồi dưỡng, nâng cao trình độ, kỹ năng nghề",
        "k",
        # «Chi phí đào tạo» trong điều khoản bồi thường không phải chế độ đào tạo.
        (Part("Chế độ đào tạo, bồi dưỡng, nâng cao kỹ năng", _pat(r"chế\s*độ\s*đào\s*tạo|được\s*đào\s*tạo|bồi\s*dưỡng|nâng\s*cao\s*trình\s*độ|kỹ\s*năng\s*nghề")),),
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


def assess_mandatory_fields(text: str, analysis: ContractAnalysis | None = None) -> list[FieldAssessment]:
    """Per Điều 21 item: co / chua_day_du / thieu / khong_ap_dung, with what was found."""
    body = _nfc(text)
    job = f"{extract_job_context(body, analysis)} {body[:4000]}"
    out: list[FieldAssessment] = []
    for field in _MANDATORY:
        found: list[str] = []
        missing: list[str] = []
        for part in field.parts:
            if not part.pattern.search(body):
                missing.append(part.label)
            elif part.negate is not None and part.negate.search(body):
                missing.append(f"{part.label} (hợp đồng chỉ nêu việc không tham gia — xem cảnh báo riêng)")
            else:
                found.append(part.label)
        if not missing:
            status = CO
        elif found:
            status = CHUA_DAY_DU
        elif field.na_when is not None and field.na_when.search(job) and not (
            field.na_unless is not None and field.na_unless.search(job)
        ):
            status = KHONG_AP_DUNG
        else:
            status = THIEU
        note = "Công việc văn phòng/nghiên cứu: có thể ghi rõ «không áp dụng» trong hợp đồng." if status == KHONG_AP_DUNG else ""
        out.append(FieldAssessment(field, status, tuple(found), tuple(missing), note))
    return out


def required_content_table(assessments: list[FieldAssessment]) -> list[dict]:
    """JSON-friendly checklist stored on ``ContractAnalysis.required_content``."""
    return [
        {
            "key": a.field.key,
            "noi_dung": a.field.label,
            "can_cu": a.field.law_ref,
            "trang_thai": a.status,
            "da_co": list(a.found),
            "con_thieu": list(a.missing),
            "ghi_chu": a.note or None,
        }
        for a in assessments
    ]


def field_is_covered(text: str, field: MandatoryField) -> bool:
    return next((a.status == CO for a in assess_mandatory_fields(text) if a.field is field), False)


def missing_mandatory_fields(text: str) -> list[MandatoryField]:
    """Items that are absent or only partly present (not «không áp dụng»)."""
    return [a.field for a in assess_mandatory_fields(text) if a.status in (THIEU, CHUA_DAY_DU)]


def _reason(a: FieldAssessment) -> str:
    if a.status == THIEU:
        excluded = next((m for m in a.missing if "xem cảnh báo" in m), None)
        return f"[Thiếu hoàn toàn] {a.field.label} ({a.field.law_ref})." + (
            " Hợp đồng chỉ nêu việc không tham gia đóng — xem cảnh báo riêng." if excluded else ""
        )
    return (
        f"[Chưa đầy đủ] {a.field.label} ({a.field.law_ref}) — đã có: {'; '.join(a.found)}; "
        f"còn thiếu: {'; '.join(a.missing)}."
    )


def check_labor_completeness(
    text: str,
    analysis: ContractAnalysis | None = None,
    *,
    as_of_date: str | None = None,
) -> list[RiskItem]:
    """Emit one risk item for Điều 21 mandatory contents that are absent or incomplete."""
    if not is_labor_contract(analysis, text):
        return []

    assessments = assess_mandatory_fields(text, analysis)
    gaps = [a for a in assessments if a.status in (THIEU, CHUA_DAY_DU)]
    if not gaps:
        return []
    not_applicable = [a for a in assessments if a.status == KHONG_AP_DUNG]

    labor = resolve_labor_code_document(as_of_date)
    doc_num = (labor or {}).get("doc_num") or "45/2019/QH14"
    doc_title = (labor or {}).get("title") or "Bộ luật Lao động"

    from app.agents.effectivity import citation_status_for_labor
    from app.agents.labor_code_resolver import fetch_provision
    from app.agents.legal_citations import evidence_confidence, format_path_location

    eff = citation_status_for_labor(labor, as_of_date)
    citations: list[LegalCitation] = []
    if not labor or eff.ok_to_cite:
        # One citation per affected điểm — exactly that điểm, not the whole Điều 21.
        for point in dict.fromkeys(a.field.point for a in gaps):
            prov = fetch_provision(labor["doc_id"], 21, 1, point) if labor else None
            loc = format_path_location(prov["path"]) if prov else {}
            shown = "đ" if point == "dd" else point
            citations.append(
                LegalCitation(
                    title=f"Điều 21 khoản 1 điểm {shown} — {doc_title}",
                    summary="" if prov else "Điều 21 khoản 1: nội dung chủ yếu bắt buộc của hợp đồng lao động.",
                    doc_number=str(doc_num),
                    article=loc.get("article") or "Điều 21",
                    clause=loc.get("clause") or "Khoản 1",
                    point=loc.get("point"),
                    location=loc.get("location"),
                    quote=prov["quote"] if prov else None,
                    evidence_path=prov["path"] if prov else None,
                    source_url=(labor or {}).get("source_url"),
                    status=eff.status_label if labor else "Chưa đối chiếu kho — chưa xác nhận hiệu lực",
                )
            )

    residence_gap = any(a.field.key == "employee_residence" for a in gaps)
    topic_labels = [a.field.label.split("(")[0].strip() for a in gaps]
    if residence_gap:
        # Put residence first so the list card surfaces it
        topic_labels = [
            "Thiếu địa chỉ / nơi cư trú NLĐ",
            *[t for t in topic_labels if "cư trú" not in t.lower() and "địa chỉ" not in t.lower()],
        ]
    n_missing = sum(a.status == THIEU for a in gaps)
    n_partial = len(gaps) - n_missing
    bullets = [f"- {_reason(a)}" for a in gaps]
    bullets += [f"- [Không áp dụng — nên ghi rõ] {a.field.label}." for a in not_applicable]
    # Regex checks can miss unusual phrasing, so absence is never certain: cap at 0.8.
    conf, notes = evidence_confidence(citations, 0.8)
    if not labor or not eff.verified:
        conf = min(conf, 0.55)
    return [
        RiskItem(
            clause_ref="Hợp đồng (toàn văn)",
            title=(
                "Thiếu địa chỉ / nơi cư trú NLĐ và nội dung bắt buộc khác"
                if residence_gap
                else "Thiếu nội dung chủ yếu bắt buộc của HĐLĐ"
            ),
            issue=(
                "Hợp đồng lao động chưa thể hiện đủ các nội dung chủ yếu theo Điều 21 khoản 1 Bộ luật Lao động "
                f"({n_missing} mục thiếu hoàn toàn, {n_partial} mục chưa đầy đủ). "
                + ("Đặc biệt: chưa ghi nơi cư trú / địa chỉ hiện tại của NLĐ. " if residence_gap else "")
                + "Các mục sau không tìm thấy hoặc chưa đủ rõ trong văn bản."
            ),
            severity="warning",
            summary_topics=["Thiếu nội dung bắt buộc", "Điều 21 BLLĐ", *topic_labels[:4]],
            reasons=[_reason(a) for a in gaps],
            impact=[
                "Hợp đồng có nguy cơ bị coi là không đầy đủ nội dung chủ yếu theo pháp luật lao động.",
                "Rủi ro khi thanh tra / tranh chấp về quyền lợi NLĐ chưa được thỏa thuận rõ.",
            ],
            actions=[
                "Bổ sung nơi cư trú / địa chỉ hiện tại của NLĐ (nếu đang thiếu).",
                "Bổ sung từng mục còn thiếu / chưa đầy đủ theo Điều 21 khoản 1 Bộ luật Lao động.",
                "Đối chiếu Thông tư hướng dẫn nội dung HĐLĐ (nếu áp dụng) để ghi đủ thông tin định danh và chế độ.",
            ],
            legal_basis=f"Điều 21 khoản 1 Bộ luật Lao động ({doc_num}) — {eff.status_label}",
            legal_citations=citations or None,
            recommendation="\n".join(bullets),
            confidence=round(conf, 2),
            confidence_notes=notes or ["Phát hiện thiếu dựa trên đối chiếu mẫu câu, có thể bỏ sót cách diễn đạt khác."],
        )
    ]

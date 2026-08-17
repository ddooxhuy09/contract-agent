"""Deterministic red-flag patterns for common illegal HĐLĐ clauses.

Complements GraphRAG + LLM judging: when retrieval is empty or noisy, these
still catch obvious violations on crafted / abusive contracts.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.agents.labor_code_resolver import resolve_labor_code_document
from app.agents.labor_completeness import is_labor_contract
from app.schemas.contract import ContractAnalysis, LegalCitation, RiskItem


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


@dataclass(frozen=True, slots=True)
class RedFlag:
    key: str
    clause_hint: str  # Điều N if known
    title: str
    severity: str
    topics: tuple[str, ...]
    pattern: re.Pattern[str]
    reason: str
    impact: str
    action: str
    article_hint: str  # e.g. "Điều 98" for legal_basis line


_FLAGS: tuple[RedFlag, ...] = (
    RedFlag(
        key="ot_unpaid",
        clause_hint="Điều 2",
        title="Làm thêm giờ không trả lương / bắt buộc OT",
        severity="critical",
        topics=("Làm thêm giờ", "Tiền lương OT"),
        pattern=re.compile(
            r"(không\s*được\s*tính\s*thêm\s*tiền\s*lương\s*làm\s*thêm|"
            r"không\s*trả\s*(?:thêm\s*)?(?:tiền\s*)?lương\s*làm\s*thêm|"
            r"làm\s*thêm\s*giờ[^\n.]{0,120}không\s*được\s*tính|"
            r"trách\s*nhiệm\s*làm\s*thêm\s*giờ[^\n.]{0,80}bất\s*cứ\s*khi\s*nào)",
            re.I,
        ),
        reason="Hợp đồng bắt làm thêm và/hoặc tuyên bố không trả lương làm thêm giờ.",
        impact="Vi phạm quy định về làm thêm giờ và trả lương; rủi ro thanh tra / bồi thường.",
        action="Bỏ thỏa thuận OT không lương; OT phải có thỏa thuận và trả đúng hệ số theo BLLĐ.",
        article_hint="Điều 98, Điều 107 BLLĐ",
    ),
    RedFlag(
        key="no_bhxh",
        clause_hint="Điều 3",
        title="Thỏa thuận không đóng BHXH / BHYT bắt buộc",
        severity="critical",
        topics=("Bảo hiểm xã hội", "BHYT"),
        pattern=re.compile(
            r"không\s*tham\s*gia\s*đóng\s*Bảo\s*hiểm\s*Xã\s*hội|"
            r"không\s*đóng\s*(?:BHXH|BHYT)|"
            r"không\s*tham\s*gia\s*(?:đóng\s*)?Bảo\s*hiểm\s*Y\s*tế\s*bắt\s*buộc",
            re.I,
        ),
        reason="Hai bên thỏa thuận Công ty không đóng BHXH/BHYT bắt buộc.",
        impact="Vi phạm nghĩa vụ tham gia BHXH bắt buộc; xử phạt và truy thu.",
        action="Xóa thỏa thuận miễn đóng; thực hiện đóng BHXH/BHYT theo luật.",
        article_hint="Điều 21 BLLĐ; Luật BHXH",
    ),
    RedFlag(
        key="retain_id_papers",
        clause_hint="Điều 3",
        title="Giữ bản gốc giấy tờ tùy thân / bằng cấp của NLĐ",
        severity="critical",
        topics=("Giấy tờ tùy thân", "CCCD"),
        pattern=re.compile(
            r"bàn\s*giao\s*bản\s*gốc\s*(?:Căn\s*cước|CCCD|CMND|bằng\s*cấp)|"
            r"giữ\s*(?:bản\s*gốc|CCCD|CMND|giấy\s*tờ)|"
            r"lưu\s*giữ[^\n.]{0,40}(?:CCCD|Căn\s*cước|bằng\s*cấp)",
            re.I,
        ),
        reason="Hợp đồng yêu cầu NLĐ giao bản gốc CCCD/bằng cấp cho Công ty giữ.",
        impact="Vi phạm cấm giữ giấy tờ gốc của NLĐ.",
        action="Xóa quy định giữ bản gốc; chỉ được yêu cầu bản sao khi cần thiết.",
        article_hint="Điều 17 BLLĐ",
    ),
    RedFlag(
        key="forfeit_wage_quit",
        clause_hint="Điều 3",
        title="Tước lương tháng cuối khi NLĐ đơn phương chấm dứt",
        severity="critical",
        topics=("Tiền lương", "Chấm dứt HĐLĐ"),
        pattern=re.compile(
            r"không\s*(?:những\s*)?không\s*được\s*nhận\s*lương|"
            r"không\s*được\s*nhận\s*lương\s*của\s*tháng\s*cuối|"
            r"tước\s*(?:quyền\s*)?lương|không\s*trả\s*lương\s*tháng\s*cuối",
            re.I,
        ),
        reason="Điều khoản tước lương tháng cuối khi NLĐ chấm dứt trước hạn.",
        impact="Không được giữ lương đã làm việc; rủi ro tranh chấp và xử phạt.",
        action="Xóa quy định tước lương; chỉ được thỏa thuận bồi thường đào tạo đúng luật (nếu có).",
        article_hint="Điều 94, Điều 96 BLLĐ",
    ),
    RedFlag(
        key="fine_deduct_wage",
        clause_hint="Điều 4",
        title="Kỷ luật phạt tiền / khấu trừ lương",
        severity="critical",
        topics=("Kỷ luật lao động", "Khấu trừ lương"),
        pattern=re.compile(
            r"kỷ\s*luật\s*phạt\s*tiền|phạt\s*tiền[^\n.]{0,60}khấu\s*trừ|"
            r"khấu\s*trừ\s*trực\s*tiếp\s*vào\s*tiền\s*lương|"
            r"hình\s*thức\s*kỷ\s*luật\s*phạt\s*tiền",
            re.I,
        ),
        reason="Công ty tự đặt hình thức kỷ luật phạt tiền và khấu trừ lương.",
        impact="Phạt tiền không phải hình thức kỷ luật hợp pháp; khấu trừ lương bị hạn chế chặt.",
        action="Xóa phạt tiền/khấu trừ kỷ luật; chỉ áp dụng hình thức kỷ luật theo BLLĐ.",
        article_hint="Điều 127, Điều 129 BLLĐ",
    ),
    RedFlag(
        key="terminate_pregnancy",
        clause_hint="Điều 4",
        title="Đơn phương chấm dứt HĐLĐ vì kết hôn / mang thai",
        severity="critical",
        topics=("Bảo vệ lao động nữ", "Đơn phương chấm dứt"),
        pattern=re.compile(
            r"chấm\s*dứt[^\n.]{0,80}(?:kết\s*hôn|mang\s*thai)|"
            r"(?:kết\s*hôn|mang\s*thai)[^\n.]{0,80}chấm\s*dứt|"
            r"đơn\s*phương\s*chấm\s*dứt[^\n.]{0,100}(?:kết\s*hôn|mang\s*thai)",
            re.I,
        ),
        reason="Cho phép NSDLĐ đơn phương chấm dứt khi NLĐ kết hôn hoặc mang thai.",
        impact="Phân biệt đối xử / vi phạm bảo vệ thai sản; điều khoản vô hiệu, rủi ro bồi thường.",
        action="Xóa toàn bộ lý do chấm dứt liên quan kết hôn/mang thai.",
        article_hint="Điều 137, Điều 141 BLLĐ",
    ),
    RedFlag(
        key="ban_lawsuit",
        clause_hint="Điều 5",
        title="Cấm NLĐ khởi kiện ra Tòa án",
        severity="critical",
        topics=("Giải quyết tranh chấp", "Quyền khởi kiện"),
        pattern=re.compile(
            r"không\s*được\s*(?:quyền\s*)?khởi\s*kiện|"
            r"không\s*được\s*kiện\s*ra\s*Tòa|"
            r"quyết\s*định\s*cuối\s*cùng[^\n.]{0,80}không\s*được|"
            r"Giám\s*đốc[^\n.]{0,60}quyết\s*định\s*cuối\s*cùng",
            re.I,
        ),
        reason="Hạn chế quyền khởi kiện / trao quyền quyết định tranh chấp một phía cho Giám đốc.",
        impact="Điều khoản vô hiệu; NLĐ vẫn có quyền khởi kiện theo pháp luật.",
        action="Sửa điều khoản tranh chấp: thương lượng, hòa giải, Tòa án theo BLLĐ/BLTTDS.",
        article_hint="Điều 179, Điều 187 BLLĐ",
    ),
)


def check_labor_red_flags(
    text: str,
    analysis: ContractAnalysis | None = None,
    *,
    as_of_date: str | None = None,
) -> list[RiskItem]:
    if not is_labor_contract(analysis, text):
        return []
    body = _nfc(text)
    labor = resolve_labor_code_document(as_of_date)
    doc_num = (labor or {}).get("doc_num") or "45/2019/QH14"
    doc_title = (labor or {}).get("title") or "Bộ luật Lao động"
    status = (labor or {}).get("eff_flag") or "Còn hiệu lực"

    out: list[RiskItem] = []
    for flag in _FLAGS:
        if not flag.pattern.search(body):
            continue
        cite = LegalCitation(
            title=f"{flag.article_hint} — {doc_title}",
            summary=flag.reason,
            doc_number=str(doc_num),
            article=flag.article_hint.split(",")[0].strip(),
            status=status,
            source_url=(labor or {}).get("source_url"),
        )
        out.append(
            RiskItem(
                clause_ref=flag.clause_hint,
                title=flag.title,
                issue=flag.reason,
                severity=flag.severity,
                summary_topics=list(flag.topics),
                reasons=[flag.reason],
                impact=[flag.impact],
                actions=[flag.action],
                legal_basis=f"{flag.article_hint} ({doc_num})",
                legal_citations=[cite],
                recommendation=flag.action,
                confidence=0.9,
            )
        )
    return out

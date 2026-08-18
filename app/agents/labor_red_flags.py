"""Deterministic red-flag patterns for common illegal HĐLĐ clauses.

Runs *before* per-clause LLM judging so covered Điều can skip Gemini/RAG.
Merges all hits on the same contract Điều into one RiskItem with a single
revised_clause that fixes every flagged issue (no extra LLM).
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from app.agents.effectivity import citation_status_for_labor
from app.agents.labor_code_resolver import (
    fetch_article_meta,
    resolve_labor_code_document,
)
from app.agents.labor_completeness import is_labor_contract
from app.agents.legal_citations import format_path_location
from app.schemas.contract import ContractAnalysis, LegalCitation, RiskItem


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


@dataclass(frozen=True, slots=True)
class RedFlag:
    key: str
    clause_hint: str
    title: str
    severity: str
    topics: tuple[str, ...]
    pattern: re.Pattern[str]
    reason: str
    impact: str
    action: str
    article_hint: str
    article_nums: tuple[int, ...]
    # Persuasive statutory wording when DB quote is thin/missing (not a substitute for SoT).
    law_blurb: str
    # (regex, replacement) applied in order on original_clause to build revised_clause.
    revise_ops: tuple[tuple[re.Pattern[str], str], ...] = ()


def _rx(pat: str) -> re.Pattern[str]:
    return re.compile(pat, re.I | re.DOTALL)


_FLAGS: tuple[RedFlag, ...] = (
    RedFlag(
        key="ot_unpaid",
        clause_hint="Điều 2",
        title="Làm thêm giờ không trả lương / bắt buộc OT",
        severity="critical",
        topics=("Làm thêm giờ", "Tiền lương OT"),
        pattern=_rx(
            r"(không\s*được\s*tính\s*thêm\s*tiền\s*lương\s*làm\s*thêm|"
            r"không\s*trả\s*(?:thêm\s*)?(?:tiền\s*)?lương\s*làm\s*thêm|"
            r"làm\s*thêm\s*giờ[^\n.]{0,120}không\s*được\s*tính|"
            r"trách\s*nhiệm\s*làm\s*thêm\s*giờ[^\n.]{0,80}bất\s*cứ\s*khi\s*nào)"
        ),
        reason="Hợp đồng bắt làm thêm và/hoặc tuyên bố không trả lương làm thêm giờ.",
        impact="Vi phạm quy định về làm thêm giờ và trả lương; rủi ro thanh tra / bồi thường.",
        action="Bỏ thỏa thuận OT không lương; OT phải có thỏa thuận và trả đúng hệ số theo BLLĐ.",
        article_hint="Điều 98, Điều 107 BLLĐ",
        article_nums=(98, 107),
        law_blurb=(
            "Điều 98 & 107 BLLĐ. Người sử dụng lao động phải trả lương làm thêm giờ theo hệ số quy định; "
            "tổ chức làm thêm giờ phải bảo đảm giới hạn thời gian và có sự đồng ý của người lao động theo luật."
        ),
        revise_ops=(
            (
                _rx(
                    r"[^.]*?(?:trách\s*nhiệm\s*làm\s*thêm|làm\s*thêm\s*giờ)"
                    r"[\s\S]{0,200}?(?:không\s*được\s*tính|không\s*trả)"
                    r"[\s\S]{0,80}?lương\s*làm\s*thêm\s*giờ\.?"
                ),
                " Việc làm thêm giờ (nếu có) chỉ thực hiện khi có thỏa thuận và được trả lương "
                "làm thêm giờ theo đúng hệ số quy định của Bộ luật Lao động. ",
            ),
            (
                _rx(r"không\s*được\s*tính\s*thêm\s*tiền\s*lương\s*làm\s*thêm\s*giờ"),
                "được trả lương làm thêm giờ theo quy định pháp luật",
            ),
        ),
    ),
    RedFlag(
        key="no_bhxh",
        clause_hint="Điều 3",
        title="Thỏa thuận không đóng BHXH / BHYT bắt buộc",
        severity="critical",
        topics=("Bảo hiểm xã hội", "BHYT"),
        pattern=_rx(
            r"không\s*tham\s*gia\s*đóng\s*Bảo\s*hiểm\s*Xã\s*hội|"
            r"không\s*đóng\s*(?:BHXH|BHYT)|"
            r"không\s*tham\s*gia\s*(?:đóng\s*)?Bảo\s*hiểm\s*Y\s*tế\s*bắt\s*buộc"
        ),
        reason="Hai bên thỏa thuận Công ty không đóng BHXH/BHYT bắt buộc.",
        impact="Vi phạm nghĩa vụ tham gia BHXH bắt buộc; xử phạt và truy thu.",
        action="Xóa thỏa thuận miễn đóng; thực hiện đóng BHXH/BHYT theo luật.",
        article_hint="Điều 21 BLLĐ; Luật BHXH",
        article_nums=(21,),
        law_blurb=(
            "Điều 21 BLLĐ. Nội dung chủ yếu của hợp đồng lao động phải có chế độ bảo hiểm xã hội "
            "và bảo hiểm y tế. Nghĩa vụ tham gia BHXH/BHYT bắt buộc không thể thỏa thuận loại trừ."
        ),
        revise_ops=(
            (
                _rx(
                    r"(?:Nhằm[^.]*?,\s*)?hai\s*bên\s*thống\s*nhất\s*Công\s*ty\s*sẽ\s*"
                    r"không\s*tham\s*gia\s*đóng\s*Bảo\s*hiểm[\s\S]{0,120}?bắt\s*buộc\.?"
                ),
                "Công ty thực hiện đóng BHXH, BHYT, BHTN bắt buộc theo quy định pháp luật.",
            ),
            (
                _rx(
                    r"Thay\s*vào\s*đó,\s*Công\s*ty\s*sẽ\s*hỗ\s*trợ\s*một\s*khoản\s*"
                    r"tương\s*đương[\s\S]{0,160}?tiền\s*lương\s*hàng\s*tháng\s*của\s*NLĐ\.?"
                ),
                "",
            ),
        ),
    ),
    RedFlag(
        key="retain_id_papers",
        clause_hint="Điều 3",
        title="Giữ bản gốc giấy tờ tùy thân / bằng cấp của NLĐ",
        severity="critical",
        topics=("Giấy tờ tùy thân", "CCCD"),
        pattern=_rx(
            r"bàn\s*giao\s*bản\s*gốc\s*(?:Căn\s*cước|CCCD|CMND|bằng\s*cấp)|"
            r"giữ\s*(?:bản\s*gốc|CCCD|CMND|giấy\s*tờ)|"
            r"lưu\s*giữ[^\n.]{0,40}(?:CCCD|Căn\s*cước|bằng\s*cấp)"
        ),
        reason="Hợp đồng yêu cầu NLĐ giao bản gốc CCCD/bằng cấp cho Công ty giữ.",
        impact="Vi phạm cấm giữ giấy tờ gốc của NLĐ.",
        action="Xóa quy định giữ bản gốc; chỉ được yêu cầu bản sao khi cần thiết.",
        article_hint="Điều 17 BLLĐ",
        article_nums=(17,),
        law_blurb=(
            "Điều 17 BLLĐ. Người sử dụng lao động không được giữ bản chính giấy tờ tùy thân, "
            "văn bằng, chứng chỉ của người lao động khi giao kết hoặc thực hiện hợp đồng lao động."
        ),
        revise_ops=(
            (
                _rx(
                    r"(?:Để\s*đảm\s*bảo[\s\S]{0,80}?,\s*)?NLĐ\s*đồng\s*ý\s*bàn\s*giao\s*bản\s*gốc"
                    r"[\s\S]{0,200}?lưu\s*giữ[\s\S]{0,120}?hợp\s*đồng\s*này\.?"
                ),
                "Công ty không giữ bản gốc giấy tờ tùy thân hay bằng cấp của NLĐ; "
                "chỉ yêu cầu bản sao khi cần thiết theo quy định.",
            ),
        ),
    ),
    RedFlag(
        key="forfeit_wage_quit",
        clause_hint="Điều 3",
        title="Tước lương tháng cuối khi NLĐ đơn phương chấm dứt",
        severity="critical",
        topics=("Tiền lương", "Chấm dứt HĐLĐ"),
        pattern=_rx(
            r"không\s*(?:những\s*)?không\s*được\s*nhận\s*lương|"
            r"không\s*được\s*nhận\s*lương\s*của\s*tháng\s*cuối|"
            r"tước\s*(?:quyền\s*)?lương|không\s*trả\s*lương\s*tháng\s*cuối"
        ),
        reason="Điều khoản tước lương tháng cuối khi NLĐ chấm dứt trước hạn.",
        impact="Không được giữ lương đã làm việc; rủi ro tranh chấp và xử phạt.",
        action="Xóa quy định tước lương; chỉ được thỏa thuận bồi thường đào tạo đúng luật (nếu có).",
        article_hint="Điều 94, Điều 96 BLLĐ",
        article_nums=(94, 96),
        law_blurb=(
            "Điều 94 & 96 BLLĐ. Người lao động được trả đủ lương đúng hạn cho thời gian đã làm việc. "
            "Không được tự ý giữ hoặc tước lương tháng cuối vì lý do đơn phương chấm dứt hợp đồng."
        ),
        revise_ops=(
            (
                _rx(
                    r"Trường\s*hợp\s*NLĐ\s*đơn\s*phương\s*chấm\s*dứt[\s\S]{0,200}?"
                    r"không\s*(?:những\s*)?không\s*được\s*nhận\s*lương[\s\S]{0,80}?\.?"
                ),
                "Khi chấm dứt hợp đồng, Công ty thanh toán đầy đủ tiền lương và các khoản "
                "NLĐ được hưởng theo pháp luật.",
            ),
        ),
    ),
    RedFlag(
        key="fine_deduct_wage",
        clause_hint="Điều 4",
        title="Kỷ luật phạt tiền / khấu trừ lương",
        severity="critical",
        topics=("Kỷ luật lao động", "Khấu trừ lương"),
        pattern=_rx(
            r"kỷ\s*luật\s*phạt\s*tiền|phạt\s*tiền[^\n.]{0,60}khấu\s*trừ|"
            r"khấu\s*trừ\s*trực\s*tiếp\s*vào\s*tiền\s*lương|"
            r"hình\s*thức\s*kỷ\s*luật\s*phạt\s*tiền"
        ),
        reason="Công ty tự đặt hình thức kỷ luật phạt tiền và khấu trừ lương.",
        impact="Phạt tiền không phải hình thức kỷ luật hợp pháp; khấu trừ lương bị hạn chế chặt.",
        action="Xóa phạt tiền/khấu trừ kỷ luật; chỉ áp dụng hình thức kỷ luật theo BLLĐ.",
        article_hint="Điều 127, Điều 129 BLLĐ",
        article_nums=(127, 129),
        law_blurb=(
            "Điều 127 BLLĐ. Nghiêm cấm phạt tiền, cắt lương thay thế việc xử lý kỷ luật lao động. "
            "Hình thức kỷ luật chỉ gồm khiển trách, kéo dài thời hạn nâng lương / cách chức, sa thải (Điều 124)."
        ),
        revise_ops=(
            (
                _rx(
                    r"(?:Nếu\s*NLĐ[\s\S]{0,120}?,\s*)?Công\s*ty\s*có\s*quyền\s*áp\s*dụng\s*"
                    r"hình\s*thức\s*kỷ\s*luật\s*phạt\s*tiền[\s\S]{0,220}?"
                    r"tiền\s*lương\s*hàng\s*tháng\.?"
                ),
                "Việc xử lý kỷ luật lao động (nếu có) chỉ áp dụng các hình thức theo Bộ luật Lao động; "
                "không dùng phạt tiền hay khấu trừ lương thay thế kỷ luật.",
            ),
        ),
    ),
    RedFlag(
        key="terminate_pregnancy",
        clause_hint="Điều 4",
        title="Đơn phương chấm dứt HĐLĐ vì kết hôn / mang thai",
        severity="critical",
        topics=("Bảo vệ lao động nữ", "Đơn phương chấm dứt"),
        pattern=_rx(
            r"chấm\s*dứt[^\n.]{0,80}(?:kết\s*hôn|mang\s*thai)|"
            r"(?:kết\s*hôn|mang\s*thai)[^\n.]{0,80}chấm\s*dứt|"
            r"đơn\s*phương\s*chấm\s*dứt[^\n.]{0,100}(?:kết\s*hôn|mang\s*thai)"
        ),
        reason="Cho phép NSDLĐ đơn phương chấm dứt khi NLĐ kết hôn hoặc mang thai.",
        impact="Phân biệt đối xử / vi phạm bảo vệ thai sản; điều khoản vô hiệu, rủi ro bồi thường.",
        action="Xóa toàn bộ lý do chấm dứt liên quan kết hôn/mang thai.",
        article_hint="Điều 137, Điều 141 BLLĐ",
        article_nums=(137, 141),
        law_blurb=(
            "Điều 137 & 141 BLLĐ. Người sử dụng lao động không được sa thải hoặc đơn phương chấm dứt "
            "hợp đồng lao động đối với lao động nữ vì lý do kết hôn, mang thai, nghỉ thai sản."
        ),
        revise_ops=(
            (
                _rx(
                    r"Công\s*ty\s*có\s*quyền\s*đơn\s*phương\s*chấm\s*dứt[\s\S]{0,220}?"
                    r"(?:kết\s*hôn|mang\s*thai)[\s\S]{0,120}?hợp\s*đồng\.?"
                ),
                "Công ty không đơn phương chấm dứt hợp đồng vì lý do kết hôn, mang thai hoặc nghỉ thai sản.",
            ),
        ),
    ),
    RedFlag(
        key="ban_lawsuit",
        clause_hint="Điều 5",
        title="Cấm NLĐ khởi kiện ra Tòa án",
        severity="critical",
        topics=("Giải quyết tranh chấp", "Quyền khởi kiện"),
        pattern=_rx(
            r"không\s*được\s*(?:quyền\s*)?khởi\s*kiện|"
            r"không\s*được\s*kiện\s*ra\s*Tòa|"
            r"quyết\s*định\s*cuối\s*cùng[^\n.]{0,80}không\s*được|"
            r"Giám\s*đốc[^\n.]{0,60}quyết\s*định\s*cuối\s*cùng"
        ),
        reason="Hạn chế quyền khởi kiện / trao quyền quyết định tranh chấp một phía cho Giám đốc.",
        impact="Điều khoản vô hiệu; NLĐ vẫn có quyền khởi kiện theo pháp luật.",
        action="Sửa điều khoản tranh chấp: thương lượng, hòa giải, Tòa án theo BLLĐ/BLTTDS.",
        article_hint="Điều 179, Điều 187 BLLĐ",
        article_nums=(179, 187),
        law_blurb=(
            "Điều 179 & 187 BLLĐ. Tranh chấp lao động được giải quyết theo thương lượng, hòa giải và Tòa án. "
            "Không được thỏa thuận tước quyền khởi kiện của người lao động."
        ),
        revise_ops=(
            (
                _rx(
                    r"Mọi\s*tranh\s*chấp[\s\S]{0,200}?"
                    r"(?:quyết\s*định\s*cuối\s*cùng|không\s*được\s*(?:quyền\s*)?khởi\s*kiện)"
                    r"[\s\S]{0,120}?Tòa\s*án\.?"
                ),
                "Mọi tranh chấp phát sinh từ Hợp đồng này được giải quyết trước hết bằng thương lượng; "
                "nếu không được thì thông qua hòa giải hoặc Tòa án có thẩm quyền theo pháp luật Việt Nam.",
            ),
        ),
    ),
)


def clause_number_from_ref(ref: str | None) -> str:
    m = re.search(r"(\d+)", str(ref or ""))
    return m.group(1) if m else ""


def extract_clause_excerpt(text: str, clause_number: str | int) -> str | None:
    """Pull Điều N body from full contract text (until next Điều)."""
    n = str(clause_number).strip()
    if not n.isdigit():
        return None
    body = _nfc(text)
    pat = re.compile(
        rf"(?:\*{{0,2}}\s*)?Điều\s*{n}\b[\s\S]*?"
        rf"(?=(?:\n\s*(?:\*{{0,2}}\s*)?Điều\s*{int(n) + 1}\b)|\Z)",
        re.I,
    )
    m = pat.search(body)
    if not m:
        return None
    excerpt = re.sub(r"\s+", " ", m.group(0)).strip()
    return excerpt[:2500] if excerpt else None


def _hydrate_citation(
    flag: RedFlag,
    *,
    labor: dict | None,
    doc_num: str,
    doc_title: str,
    as_of_date: str | None = None,
) -> LegalCitation | None:
    """Build a citation only when the Labor Code is ok to rely on (or mark unverified).

    Returns None when the resolved document is expired / not yet effective — never
    present a dead instrument as living grounds for drafting.
    """
    eff = citation_status_for_labor(labor, as_of_date)
    if labor and not eff.ok_to_cite:
        return None

    quotes: list[str] = []
    path = None
    article = None
    location = None
    for num in flag.article_nums:
        meta = fetch_article_meta((labor or {}).get("doc_id"), num, limit=4) if labor else None
        if not meta:
            continue
        q = (meta.get("quote") or "").strip()
        if q:
            quotes.append(q)
        if not path and meta.get("path"):
            path = meta["path"]
            loc = format_path_location(path)
            location = loc.get("location")
            article = loc.get("article") or f"Điều {num}"
    db_quote = "\n\n".join(quotes).strip() if quotes else ""
    has_verbatim = len(db_quote) >= 80
    if has_verbatim:
        quote = db_quote[:2800]
        summary = ""
        blurb = (flag.law_blurb or "").strip()
        if blurb and blurb not in quote and quote[:60] not in blurb:
            summary = blurb if len(blurb) <= 180 else blurb[:177] + "…"
    else:
        quote = flag.law_blurb
        summary = ""

    if not article and flag.article_nums:
        article = f"Điều {flag.article_nums[0]}"
    title = f"{article or flag.article_hint.split(',')[0].strip()} — {doc_title}"
    status = eff.status_label if labor else "Chưa đối chiếu kho — chưa xác nhận hiệu lực"
    return LegalCitation(
        title=title,
        summary=summary or (eff.detail if labor and eff.status_flag == 4 else ""),
        doc_number=str(doc_num),
        location=location,
        article=article,
        quote=quote,
        evidence_path=path,
        status=status,
        source_url=(labor or {}).get("source_url") if labor else None,
    )


def revise_clause_text(original: str | None, flag_keys: list[str]) -> str | None:
    """Apply deterministic edits for every flag on this Điều → one revised clause."""
    if not original or not flag_keys:
        return None
    text = _nfc(original)
    key_to_flag = {f.key: f for f in _FLAGS}
    for key in flag_keys:
        flag = key_to_flag.get(key)
        if not flag:
            continue
        for pat, repl in flag.revise_ops:
            text = pat.sub(repl, text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    # If edits barely changed text, append a compliant closing note
    if text == _nfc(original).strip() or len(text) < 40:
        bullets = []
        for key in flag_keys:
            flag = key_to_flag.get(key)
            if flag:
                bullets.append(f"- {flag.action}")
        return (
            f"{_nfc(original).strip()}\n\n"
            f"[Đề xuất chỉnh sửa bắt buộc]\n" + "\n".join(bullets)
        )
    return text


def _short_title(flag: RedFlag) -> str:
    """Compact label for list headers when several flags share one Điều."""
    shorts = {
        "ot_unpaid": "OT không lương / bắt buộc OT",
        "no_bhxh": "Không đóng BHXH/BHYT",
        "retain_id_papers": "Giữ CCCD / bằng cấp gốc",
        "forfeit_wage_quit": "Tước lương tháng cuối",
        "fine_deduct_wage": "Phạt tiền / khấu trừ lương",
        "terminate_pregnancy": "Chấm dứt vì kết hôn / mang thai",
        "ban_lawsuit": "Cấm khởi kiện ra Tòa",
    }
    return shorts.get(flag.key) or (flag.topics[0] if flag.topics else flag.title)


def _merge_clause_hits(
    hits: list[tuple[RedFlag, LegalCitation, str | None]],
) -> list[RiskItem]:
    """One RiskItem per contract Điều — combined reasons/actions/cites + revised_clause."""
    by_num: dict[str, list[tuple[RedFlag, LegalCitation, str | None]]] = defaultdict(list)
    for item in hits:
        num = clause_number_from_ref(item[0].clause_hint) or "?"
        by_num[num].append(item)

    out: list[RiskItem] = []
    for num in sorted(by_num.keys(), key=lambda x: int(x) if x.isdigit() else 99):
        group = by_num[num]
        flags = [g[0] for g in group]
        cites = [g[1] for g in group if g[1] is not None]
        original = next((g[2] for g in group if g[2]), None)
        keys = [f.key for f in flags]
        shorts = [_short_title(f) for f in flags]
        title = shorts[0] if len(shorts) == 1 else " · ".join(shorts)
        if len(title) > 100:
            title = title[:97].rstrip(" ·") + "…"
        reasons = [f.reason for f in flags]
        actions = list(dict.fromkeys(f.action for f in flags))
        impact = list(dict.fromkeys(f.impact for f in flags))
        # Topic chips = short violation labels (what was violated), not filler tags
        topics = list(dict.fromkeys(shorts))
        revised = revise_clause_text(original, keys)
        rec_parts = [f"- {a}" for a in actions]
        if revised:
            rec_parts.append(f"«{revised}»")
        severity = "critical" if any(f.severity == "critical" for f in flags) else "warning"
        basis = "; ".join(dict.fromkeys(f.article_hint for f in flags))
        out.append(
            RiskItem(
                clause_ref=f"Điều {num}",
                title=title,
                issue=" ".join(reasons),
                severity=severity,
                summary_topics=topics,
                reasons=reasons,
                impact=impact,
                actions=actions,
                legal_basis=basis,
                legal_citations=cites,
                recommendation="\n".join(rec_parts),
                original_clause=original,
                revised_clause=revised,
                confidence=0.9,
            )
        )
    return out


def check_labor_red_flags(
    text: str,
    analysis: ContractAnalysis | None = None,
    *,
    as_of_date: str | None = None,
    contract_id: str | None = None,
) -> list[RiskItem]:
    if not is_labor_contract(analysis, text):
        return []
    body = _nfc(text)
    labor = resolve_labor_code_document(as_of_date)
    doc_num = (labor or {}).get("doc_num") or "45/2019/QH14"
    doc_title = (labor or {}).get("title") or "Bộ luật Lao động"

    chunk_repo = None
    if contract_id:
        try:
            from app.infrastructure.retrieval.context import get_contract_chunks

            chunk_repo = get_contract_chunks()
        except Exception:
            chunk_repo = None

    hits: list[tuple[RedFlag, LegalCitation, str | None]] = []
    for flag in _FLAGS:
        if not flag.pattern.search(body):
            continue
        cite = _hydrate_citation(
            flag,
            labor=labor,
            doc_num=doc_num,
            doc_title=doc_title,
            as_of_date=as_of_date,
        )
        num = clause_number_from_ref(flag.clause_hint)
        original = None
        if chunk_repo is not None and num and contract_id:
            try:
                original = chunk_repo.get_text_by_clause(contract_id, num)
            except Exception:
                original = None
        if not original and num:
            original = extract_clause_excerpt(body, num)
        if not original and analysis:
            for cl in analysis.clauses or []:
                if str(cl.clause_number) == num:
                    original = (cl.summary or "").strip() or None
                    break
        hits.append((flag, cite, original))

    return _merge_clause_hits(hits)


def skip_llm_clause_numbers(red_flag_risks: list[RiskItem]) -> list[str]:
    """Clause numbers that already have critical deterministic coverage → skip Gemini."""
    skip: set[str] = set()
    for r in red_flag_risks:
        if (r.severity or "") != "critical":
            continue
        n = clause_number_from_ref(r.clause_ref)
        if n:
            skip.add(n)
    return sorted(skip, key=lambda x: int(x) if x.isdigit() else 0)


def matching_law_blurbs(text: str, *, limit: int = 4) -> list[str]:
    """Deterministic BLLĐ blurbs for QA when vector retrieval latches onto the wrong act.

    Matches the same red-flag patterns used in risk analysis against question +
    contract excerpts. Prefixed so the LLM treats them as legal grounding.
    """
    body = _nfc(text)
    if not body:
        return []
    out: list[str] = []
    for flag in _FLAGS:
        if not flag.pattern.search(body):
            # Also accept topic words without the full illegal contract phrasing
            # when the user asks about legality of pregnancy termination, etc.
            soft = False
            if flag.key == "terminate_pregnancy" and re.search(
                r"(?:mang\s*thai|thai\s*sản).{0,80}(?:chấm\s*dứt|sa\s*thải)|"
                r"(?:chấm\s*dứt|sa\s*thải).{0,80}(?:mang\s*thai|thai\s*sản)",
                body,
                re.I | re.DOTALL,
            ):
                soft = True
            if not soft:
                continue
        label = flag.article_hint or flag.title
        out.append(f"[BLLĐ · {label}] {flag.law_blurb}")
        if len(out) >= limit:
            break
    return out



def topic_keys_for_risks(red_flag_risks: list[RiskItem]) -> dict[str, set[str]]:
    """Map clause number → red-flag keys inferred from reasons/titles."""
    out: dict[str, set[str]] = {}
    for r in red_flag_risks:
        n = clause_number_from_ref(r.clause_ref)
        if not n:
            continue
        blob = f"{r.title or ''} {' '.join(r.reasons or [])}".lower()
        keys: set[str] = set()
        for f in _FLAGS:
            if f.title.lower() in blob or f.reason.lower() in blob:
                keys.add(f.key)
            elif any(t.lower() in blob for t in f.topics):
                # weak match — only if clause_hint matches
                if clause_number_from_ref(f.clause_hint) == n:
                    keys.add(f.key)
        if keys:
            out.setdefault(n, set()).update(keys)
    return out

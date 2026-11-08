"""Deterministic red-flag patterns for common illegal HĐLĐ clauses.

Runs *before* per-clause LLM judging so covered Điều can skip Gemini/RAG.
Each flag is one independent violation with its own provision references
(Điều + khoản, fetched exactly from the corpus), its own contract sentence and
its own confidence. Flags that fall in the same contract Điều are merged into one
RiskItem whose ``revised_clause`` is rebuilt sentence by sentence and then
re-checked, so a half-fixed or still-illegal rewrite is never shown.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import NamedTuple

from app.agents.clause_text import (
    join_segments,
    lead_marker,
    sentences_matching,
    split_segments,
    strip_signature_block,
)
from app.agents.effectivity import citation_status_for_labor
from app.agents.labor_code_resolver import fetch_provision, resolve_labor_code_document
from app.agents.labor_completeness import is_labor_contract
from app.agents.legal_citations import (
    build_source_deep_link,
    evidence_confidence,
    extract_article_title,
    format_path_location,
)
from app.document.chunker import find_headings
from app.schemas.contract import ContractAnalysis, LegalCitation, RiskFinding, RiskItem


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


class Ref(NamedTuple):
    """One cited provision: Điều ``article`` [khoản ``khoan`` [điểm ``point``]]."""

    article: int
    khoan: int | None
    support: str  # regex the fetched quote must match, else it does not support the finding
    point: str | None = None


@dataclass(frozen=True, slots=True)
class RedFlag:
    key: str
    clause_hint: str  # fallback only — the Điều is located from the contract text
    title: str
    severity: str
    topics: tuple[str, ...]
    pattern: re.Pattern[str]
    reason: str
    impact: str
    action: str
    refs: tuple[Ref, ...]
    # Persuasive statutory wording used for QA grounding and when the corpus is unreachable.
    law_blurb: str
    # Compliant wording that replaces every contract sentence matching ``pattern``.
    replacement: str
    # Companion sentences deleted whenever this flag fires (e.g. the «thay vào đó» offset).
    drop: tuple[re.Pattern[str], ...] = ()
    ceiling: float = 0.9  # max confidence: lower when legality depends on facts outside the text

    @property
    def hint(self) -> str:
        return ", ".join(_ref_label(r) for r in self.refs) + " BLLĐ"


def _ref_label(ref: Ref) -> str:
    out = f"Điều {ref.article}"
    if ref.khoan:
        out += f" khoản {ref.khoan}"
    return out


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
        action="Bỏ thỏa thuận OT không lương; OT phải có sự đồng ý của NLĐ và trả đúng hệ số theo BLLĐ.",
        refs=(
            Ref(98, 1, r"150\s*%|làm\s*thêm\s*giờ"),
            Ref(107, 2, r"đồng\s*ý|làm\s*thêm\s*giờ"),
        ),
        law_blurb=(
            "Điều 98 khoản 1 & Điều 107 khoản 2 BLLĐ. Người sử dụng lao động phải trả lương làm thêm giờ "
            "theo hệ số quy định; chỉ được yêu cầu làm thêm giờ khi có sự đồng ý của người lao động."
        ),
        replacement=(
            "Việc làm thêm giờ (nếu có) chỉ thực hiện khi có sự đồng ý của NLĐ và được trả lương "
            "làm thêm giờ theo đúng hệ số quy định của Bộ luật Lao động."
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
        action="Xóa thỏa thuận miễn đóng; thực hiện đóng BHXH/BHYT/BHTN theo luật.",
        refs=(Ref(168, 1, r"bảo\s*hiểm\s*xã\s*hội"),),
        law_blurb=(
            "Điều 168 khoản 1 BLLĐ. Người sử dụng lao động, người lao động phải tham gia bảo hiểm xã hội "
            "bắt buộc, bảo hiểm y tế, bảo hiểm thất nghiệp; không thể thỏa thuận loại trừ."
        ),
        replacement="Chế độ Bảo hiểm: Công ty thực hiện đóng BHXH, BHYT, BHTN bắt buộc theo quy định pháp luật.",
        drop=(_rx(r"Thay\s*vào\s*đó[^.]{0,60}hỗ\s*trợ"),),
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
        refs=(Ref(17, 1, r"giữ\s*bản\s*chính"),),
        law_blurb=(
            "Điều 17 khoản 1 BLLĐ. Người sử dụng lao động không được giữ bản chính giấy tờ tùy thân, "
            "văn bằng, chứng chỉ của người lao động khi giao kết hoặc thực hiện hợp đồng lao động."
        ),
        replacement=(
            "Công ty không giữ bản gốc giấy tờ tùy thân hay bằng cấp của NLĐ; "
            "chỉ yêu cầu bản sao khi cần thiết theo quy định."
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
        impact="Không được giữ lương đã làm việc; mức bồi thường khi chấm dứt trái luật đã bị luật giới hạn.",
        action="Xóa quy định tước lương; chỉ áp dụng nghĩa vụ khi chấm dứt trái luật theo Điều 40 BLLĐ.",
        refs=(
            Ref(94, 1, r"đầy\s*đủ"),
            Ref(40, 2, r"nửa\s*tháng\s*tiền\s*lương"),
        ),
        law_blurb=(
            "Điều 94 khoản 1 & Điều 40 BLLĐ. Người lao động được trả đủ lương đúng hạn cho thời gian đã làm việc; "
            "khi chấm dứt trái luật chỉ phải bồi thường nửa tháng lương và tiền lương những ngày không báo trước."
        ),
        replacement=(
            "Khi chấm dứt hợp đồng, Công ty thanh toán đầy đủ tiền lương và các khoản NLĐ được hưởng theo pháp luật."
        ),
    ),
    RedFlag(
        key="training_cost_flat",
        clause_hint="Điều 3",
        title="Bồi thường chi phí đào tạo bằng số tháng lương cố định",
        severity="critical",
        topics=("Chi phí đào tạo", "Bồi thường"),
        pattern=_rx(
            r"bồi\s*thường[^.]{0,80}chi\s*phí\s*đào\s*tạo|"
            r"chi\s*phí\s*đào\s*tạo[^.]{0,60}tương\s*đương\s*\d+\s*tháng"
        ),
        reason=(
            "Buộc NLĐ bồi thường «chi phí đào tạo» bằng số tháng lương cố định, không gắn với hợp đồng đào tạo "
            "nghề và chi phí thực tế có chứng từ."
        ),
        impact="Mức bồi thường tự áp đặt trái quy định; điều khoản có nguy cơ vô hiệu và bị khiếu nại.",
        action=(
            "Chỉ quy định hoàn trả chi phí đào tạo khi đã ký hợp đồng đào tạo nghề và theo chi phí thực tế "
            "có chứng từ hợp lệ."
        ),
        refs=(
            Ref(62, 1, r"hợp\s*đồng\s*đào\s*tạo"),
            Ref(62, 3, r"chứng\s*từ\s*hợp\s*lệ"),
            Ref(40, 3, r"chi\s*phí\s*đào\s*tạo"),
        ),
        law_blurb=(
            "Điều 62 & Điều 40 khoản 3 BLLĐ. Chi phí đào tạo chỉ hoàn trả khi hai bên đã ký hợp đồng đào tạo nghề "
            "và gồm các khoản chi có chứng từ hợp lệ."
        ),
        replacement=(
            "Việc hoàn trả chi phí đào tạo (nếu có) chỉ áp dụng khi hai bên đã ký hợp đồng đào tạo nghề "
            "theo Điều 62 Bộ luật Lao động và theo chi phí thực tế có chứng từ hợp lệ."
        ),
        ceiling=0.85,
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
        refs=(
            Ref(127, 2, r"phạt\s*tiền"),
            Ref(102, 1, r"khấu\s*trừ"),
        ),
        law_blurb=(
            "Điều 127 khoản 2 BLLĐ. Nghiêm cấm phạt tiền, cắt lương thay việc xử lý kỷ luật lao động. "
            "Hình thức kỷ luật chỉ gồm khiển trách, kéo dài thời hạn nâng lương, cách chức, sa thải (Điều 124)."
        ),
        replacement=(
            "Việc xử lý kỷ luật lao động (nếu có) chỉ áp dụng các hình thức theo Bộ luật Lao động; "
            "không dùng phạt tiền hay khấu trừ lương thay thế kỷ luật."
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
        refs=(
            Ref(137, 3, r"kết\s*hôn|mang\s*thai"),
            Ref(8, 1, r"phân\s*biệt\s*đối\s*xử"),
        ),
        law_blurb=(
            "Điều 137 khoản 3 BLLĐ. Người sử dụng lao động không được sa thải hoặc đơn phương chấm dứt "
            "hợp đồng lao động vì lý do kết hôn, mang thai, nghỉ thai sản, nuôi con dưới 12 tháng tuổi."
        ),
        replacement="Công ty không đơn phương chấm dứt hợp đồng vì lý do kết hôn, mang thai hoặc nghỉ thai sản.",
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
        refs=(
            Ref(179, 1, r"tranh\s*chấp\s*lao\s*động"),
            Ref(187, 3, r"Tòa\s*án"),
        ),
        law_blurb=(
            "Điều 179 khoản 1 & Điều 187 khoản 3 BLLĐ. Tranh chấp lao động cá nhân do hòa giải viên, "
            "hội đồng trọng tài hoặc Tòa án giải quyết; không thể thỏa thuận tước quyền khởi kiện."
        ),
        replacement=(
            "Mọi tranh chấp phát sinh từ Hợp đồng này được giải quyết trước hết bằng thương lượng; "
            "nếu không được thì thông qua hòa giải hoặc Tòa án có thẩm quyền theo pháp luật Việt Nam."
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
    excerpt = strip_signature_block(m.group(0).replace("**", ""))
    excerpt = re.sub(r"\s+", " ", excerpt).strip()
    return excerpt[:2500] if excerpt else None


def _locate_clause(flag: RedFlag, body: str) -> str:
    """Number of the contract Điều whose text actually triggers ``flag`` (hint as fallback)."""
    heads = find_headings(body)
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        if flag.pattern.search(body[h.start() : end]):
            return h.group(1)
    return clause_number_from_ref(flag.clause_hint)


def _violates(flag: RedFlag, segment: str) -> bool:
    """``flag`` fires on ``segment`` unless the match is negated («không dùng phạt tiền…»)."""
    for m in flag.pattern.finditer(segment):
        if not re.search(r"\b(?:không|cấm|nghiêm\s*cấm)\b", segment[max(0, m.start() - 30) : m.start()], re.I):
            return True
    return False


def rewrite_clause(original: str, flags: list[RedFlag]) -> str:
    """Replace each violating *sentence* with compliant wording; everything else stays verbatim."""
    out: list[tuple[str, str]] = []
    emitted: set[str] = set()
    for seg, sep in split_segments(_nfc(original)):
        hit = [f for f in flags if f.pattern.search(seg)]
        dropped = any(d.search(seg) for f in flags for d in f.drop)
        if not hit and not dropped:
            out.append((seg, sep))
            continue
        reps = [f.replacement for f in hit if f.replacement not in emitted]
        emitted.update(reps)
        if reps:
            out.append((lead_marker(seg) + " ".join(reps), sep))
    return re.sub(r"[ \t]{2,}", " ", join_segments(out))


def revised_clause_problems(original: str | None, revised: str | None, *, check_facts: bool = True) -> list[str]:
    """Re-check a rewritten clause (deterministic or LLM): empty list = safe to show.

    ``check_facts`` also requires amounts/dates outside the violating sentences to survive;
    it is for our own sentence-level rewrite (an LLM may legitimately change figures).
    """
    if not revised or not revised.strip():
        return ["Không có điều khoản sửa đổi."]
    orig, rev = _nfc(original or ""), _nfc(revised)
    problems: list[str] = []
    if orig and re.sub(r"\s+", "", orig) == re.sub(r"\s+", "", rev):
        problems.append("Điều khoản sửa đổi không khác bản gốc.")
    orig_segs = {re.sub(r"\s+", " ", s).strip() for s, _ in split_segments(orig)}
    prev = ""
    for seg, _ in split_segments(rev):
        text = re.sub(r"\s+", " ", seg).strip()
        for f in _FLAGS:
            if _violates(f, text):
                problems.append(f"Còn nội dung vi phạm «{f.key}»: «{text[:90]}»")
        body = text[len(lead_marker(text)) :].lstrip("*_ ")
        # A lowercase start is a fragment unless the previous segment ended mid-sentence («;» «,» «:»).
        if text not in orig_segs and body and body[0].islower() and (not prev or prev[-1] in ".!?"):
            problems.append(f"Câu bị cắt dở / sai ngữ pháp: «{text[:70]}»")
        prev = text
    # Lawful facts (amounts, dates) outside the violating sentences must survive the rewrite.
    for seg, _ in split_segments(orig) if check_facts else []:
        if any(f.pattern.search(seg) for f in _FLAGS):
            continue
        for num in re.findall(r"\d[\d./,]*\d|\d", seg):
            if num not in rev:
                problems.append(f"Mất nội dung hợp pháp ngoài phạm vi cần sửa: «{num}»")
                break
    return list(dict.fromkeys(problems))


def revise_clause_text(original: str | None, flag_keys: list[str]) -> str | None:
    """Rewrite ``original`` for the given flags; ``None`` when the result fails re-validation."""
    if not original or not flag_keys:
        return None
    by_key = {f.key: f for f in _FLAGS}
    flags = [by_key[k] for k in flag_keys if k in by_key]
    revised = rewrite_clause(original, flags)
    return None if revised_clause_problems(original, revised) else revised


def _short_title(flag: RedFlag) -> str:
    """Compact label for list headers when several flags share one Điều."""
    shorts = {
        "ot_unpaid": "OT không lương / bắt buộc OT",
        "no_bhxh": "Không đóng BHXH/BHYT",
        "retain_id_papers": "Giữ CCCD / bằng cấp gốc",
        "forfeit_wage_quit": "Tước lương tháng cuối",
        "training_cost_flat": "Bồi thường chi phí đào tạo cố định",
        "fine_deduct_wage": "Phạt tiền / khấu trừ lương",
        "terminate_pregnancy": "Chấm dứt vì kết hôn / mang thai",
        "ban_lawsuit": "Cấm khởi kiện ra Tòa",
    }
    return shorts.get(flag.key) or (flag.topics[0] if flag.topics else flag.title)


def _hydrate_citation(
    flag: RedFlag,
    ref: Ref,
    *,
    labor: dict | None,
    doc_num: str,
    doc_title: str,
    as_of_date: str | None = None,
) -> tuple[LegalCitation | None, list[str]]:
    """Cite exactly ``ref`` from the corpus; return (citation, problems).

    ``None`` when the resolved document is expired / not yet effective — never
    present a dead instrument as living grounds for drafting.
    """
    eff = citation_status_for_labor(labor, as_of_date)
    if labor and not eff.ok_to_cite:
        return None, []

    label = _ref_label(ref)
    prov = fetch_provision(labor.get("doc_id"), ref.article, ref.khoan, ref.point) if labor else None
    status = eff.status_label if labor else "Chưa đối chiếu kho — chưa xác nhận hiệu lực"
    title = f"{label} — {doc_title}"
    if not prov:
        note = f"{label}: không tìm thấy bản còn hiệu lực trong kho pháp điển — chỉ có tóm tắt, chưa đối chiếu nguyên văn."
        return (
            LegalCitation(
                title=title,
                summary=flag.law_blurb if ref is flag.refs[0] else f"{label} BLLĐ (chưa đối chiếu nguyên văn).",
                doc_number=str(doc_num),
                article=f"Điều {ref.article}",
                clause=f"Khoản {ref.khoan}" if ref.khoan else None,
                status=status,
                source_url=(labor or {}).get("source_url"),
            ),
            [note],
        )

    loc = format_path_location(prov["path"])
    problems: list[str] = []
    if ref.support and not re.search(ref.support, prov["quote"], re.I):
        problems.append(f"{label}: nội dung trích không nêu rõ căn cứ cho kết luận.")
    source_url = (labor or {}).get("source_url")
    return (
        LegalCitation(
            title=title,
            doc_number=str(doc_num),
            location=loc["location"],
            article=loc["article"],
            clause=loc["clause"],
            point=loc["point"],
            quote=prov["quote"],
            evidence_path=prov["path"],
            status=status,
            source_url=source_url,
            deep_link=build_source_deep_link(source_url, None, extract_article_title(prov["quote"]) or prov["quote"]),
        ),
        problems,
    )


def _build_item(
    num: str,
    group: list[tuple[RedFlag, list[LegalCitation], list[str], list[str]]],
    original: str | None,
) -> RiskItem:
    """One RiskItem per contract Điều: merged view + one RiskFinding per violation."""
    flags = [g[0] for g in group]
    shorts = [_short_title(f) for f in flags]
    title = shorts[0] if len(shorts) == 1 else " · ".join(shorts)
    if len(title) > 100:
        title = title[:97].rstrip(" ·") + "…"

    findings: list[RiskFinding] = []
    cites_all: list[LegalCitation] = []
    notes_all: list[str] = []
    for flag, cites, problems, violated in group:
        conf, cnotes = evidence_confidence(cites, flag.ceiling)
        notes = list(dict.fromkeys([*problems, *cnotes]))
        conf = max(0.3, conf - 0.1 * len(problems))
        findings.append(
            RiskFinding(
                key=flag.key,
                title=_short_title(flag),
                severity=flag.severity,
                reason=flag.reason,
                violated_text=" … ".join(violated) or None,
                legal_citations=cites or None,
                confidence=round(conf, 2),
                confidence_notes=notes or None,
            )
        )
        for c in cites:
            if not any(c.title == x.title for x in cites_all):
                cites_all.append(c)
        notes_all += [f"{_short_title(flag)}: {n}" for n in notes]

    revised = rewrite_clause(original, flags) if original else None
    rproblems = revised_clause_problems(original, revised) if original else ["Không có văn bản gốc."]
    if rproblems:
        notes_all.append("Điều khoản sửa đổi tự động không qua kiểm tra nên không hiển thị: " + "; ".join(rproblems))
        revised = None

    actions = list(dict.fromkeys(f.action for f in flags))
    rec_parts = [f"- {a}" for a in actions]
    rec_parts.append(f"«{revised}»" if revised else "- Cần soạn lại điều khoản này thủ công theo các căn cứ trên.")
    reasons = [f.reason for f in flags]
    return RiskItem(
        clause_ref=f"Điều {num}",
        title=title,
        issue=" ".join(reasons),
        severity="critical" if any(f.severity == "critical" for f in flags) else "warning",
        summary_topics=list(dict.fromkeys(shorts)),
        reasons=reasons,
        impact=list(dict.fromkeys(f.impact for f in flags)),
        actions=actions,
        legal_basis="; ".join(dict.fromkeys(f.hint for f in flags)),
        legal_citations=cites_all or None,
        recommendation="\n".join(rec_parts),
        original_clause=original,
        revised_clause=revised,
        confidence=min(f.confidence for f in findings if f.confidence is not None),
        confidence_notes=list(dict.fromkeys(notes_all)) or None,
        findings=findings,
    )


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

    by_num: dict[str, list[tuple[RedFlag, list[LegalCitation], list[str], list[str]]]] = defaultdict(list)
    originals: dict[str, str | None] = {}
    for flag in _FLAGS:
        if not flag.pattern.search(body):
            continue
        num = _locate_clause(flag, body) or "?"
        if num not in originals:
            original = None
            if chunk_repo is not None and num.isdigit() and contract_id:
                try:
                    original = chunk_repo.get_text_by_clause(contract_id, num)
                except Exception:
                    original = None
            if not original and num.isdigit():
                original = extract_clause_excerpt(body, num)
            if not original and analysis:
                original = next(
                    ((cl.summary or "").strip() or None for cl in analysis.clauses or [] if str(cl.clause_number) == num),
                    None,
                )
            originals[num] = strip_signature_block(original) if original else None
        cites: list[LegalCitation] = []
        problems: list[str] = []
        for ref in flag.refs:
            cite, probs = _hydrate_citation(
                flag, ref, labor=labor, doc_num=doc_num, doc_title=doc_title, as_of_date=as_of_date
            )
            if cite is not None:
                cites.append(cite)
            problems += probs
        violated = sentences_matching(originals[num] or body, flag.pattern)
        by_num[num].append((flag, cites, problems, violated))

    return [
        _build_item(num, by_num[num], originals[num])
        for num in sorted(by_num, key=lambda x: int(x) if x.isdigit() else 99)
    ]


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
        out.append(f"[BLLĐ · {flag.hint}] {flag.law_blurb}")
        if len(out) >= limit:
            break
    return out

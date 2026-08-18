"""Rule-based query rewrite for legal retrieval (no extra LLM hop)."""

from __future__ import annotations

import re
import unicodedata

from langchain_core.messages import BaseMessage

_FILLER = re.compile(
    r"\b(các|của|và|hoặc|một|những|này|đó|the|and|or|a|an|to|of|for|with|"
    r"quy định|theo|về|trong|khi|nếu|sẽ|được|phải|có)\b",
    re.IGNORECASE,
)

_LEGALITY_FOLLOWUP = re.compile(
    r"(đúng\s*luật|hợp\s*pháp|trái\s*luật|vi\s*phạm|"
    r"có\s*(?:được|sao)\s*không|có\s*ổn\s*không|"
    r"như\s*vậy\s*(?:có|thì)|vậy\s*thì)",
    re.IGNORECASE,
)

# Combined patterns → retrieval boosts (prefer BLLĐ over tangential instruments).
_TOPIC_BOOSTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:(?:mang\s*thai|thai\s*sản|kết\s*hôn).{0,60}(?:chấm\s*dứt|sa\s*thải|đuổi)|"
            r"(?:chấm\s*dứt|sa\s*thải|đuổi).{0,60}(?:mang\s*thai|thai\s*sản|kết\s*hôn))",
            re.I | re.DOTALL,
        ),
        "cấm đơn phương chấm dứt hợp đồng lao động nữ mang thai kết hôn Bộ luật Lao động",
    ),
    (
        re.compile(r"nghỉ\s*thai\s*sản|chế\s*độ\s*thai\s*sản|thời\s*gian\s*nghỉ\s*sinh", re.I),
        "nghỉ thai sản thời gian nghỉ sinh Bộ luật Lao động Luật bảo hiểm xã hội",
    ),
    (
        re.compile(
            r"(?:làm\s*thêm|OT).{0,40}(?:không\s*(?:trả|tính)|không\s*lương)|"
            r"không\s*(?:trả|tính).{0,40}(?:làm\s*thêm|lương\s*làm\s*thêm)",
            re.I | re.DOTALL,
        ),
        "làm thêm giờ trả lương hệ số Bộ luật Lao động",
    ),
    (
        re.compile(
            r"(?:không\s*(?:đóng|tham\s*gia).{0,20})?(?:BHXH|BHYT|bảo\s*hiểm\s*xã\s*hội)",
            re.I,
        ),
        "bảo hiểm xã hội bảo hiểm y tế bắt buộc Bộ luật Lao động",
    ),
    (
        re.compile(
            r"(?:giữ|lưu\s*giữ|bàn\s*giao).{0,40}(?:CCCD|CMND|bản\s*gốc|bằng\s*cấp)",
            re.I | re.DOTALL,
        ),
        "không được giữ bản chính giấy tờ tùy thân Bộ luật Lao động",
    ),
    (
        re.compile(r"phạt\s*tiền|khấu\s*trừ\s*(?:lương|tiền\s*lương)|kỷ\s*luật\s*phạt", re.I),
        "cấm phạt tiền cắt lương kỷ luật lao động Bộ luật Lao động",
    ),
    (
        re.compile(r"(?:không\s*được\s*)?khởi\s*kiện|kiện\s*ra\s*Tòa|tranh\s*chấp\s*lao\s*động", re.I),
        "giải quyết tranh chấp lao động Tòa án Bộ luật Lao động",
    ),
)

_TOPIC_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"mang\s*thai|thai\s*sản|kết\s*hôn", re.I), "mang thai thai sản"),
    (re.compile(r"đơn\s*phương|chấm\s*dứt|sa\s*thải", re.I), "đơn phương chấm dứt sa thải"),
    (re.compile(r"nghỉ\s*thai\s*sản", re.I), "nghỉ thai sản"),
    (re.compile(r"làm\s*thêm|overtime|\bOT\b", re.I), "làm thêm giờ"),
    (re.compile(r"BHXH|BHYT|bảo\s*hiểm", re.I), "bảo hiểm xã hội"),
    (re.compile(r"CCCD|bản\s*gốc|giấy\s*tờ", re.I), "giấy tờ tùy thân"),
    (re.compile(r"phạt\s*tiền|khấu\s*trừ|kỷ\s*luật", re.I), "kỷ luật phạt tiền"),
    (re.compile(r"khởi\s*kiện|Tòa\s*án|tranh\s*chấp", re.I), "tranh chấp khởi kiện"),
)


def rewrite_qa_query(question: str, max_chars: int = 400) -> str:
    """Free, rule-based query expansion for ad-hoc QA questions.

    Strips Vietnamese/English filler tokens and punctuation so the vector & FTS
    queries hit exact legal/clause wording instead of diluted question text.
    Returns the original question unchanged if stripping would leave nothing.
    """
    text = unicodedata.normalize("NFC", question or "")
    text = re.sub(r"[!?.,;:()\"'«»–—]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    tokens = []
    for tok in text.split(" "):
        t = tok.strip()
        if not t or len(t) <= 1:
            continue
        if _FILLER.fullmatch(t):
            continue
        tokens.append(t)
    rewritten = " ".join(tokens) if tokens else text
    return rewritten[:max_chars]


def expand_legal_topic_query(query: str, max_chars: int = 420) -> str:
    """Append BLLĐ-oriented keywords when the question matches known labor topics.

    Stops retrieval from latching onto tangential instruments (e.g. BHXH leave
    timing) when the user is really asking about termination-for-pregnancy.
    """
    text = unicodedata.normalize("NFC", query or "").strip()
    if not text:
        return text
    boosts: list[str] = []
    for pat, boost in _TOPIC_BOOSTS:
        if pat.search(text):
            boosts.append(boost)
    # Split-term fallback: pregnancy + legality/termination without adjacent match
    has_preg = bool(re.search(r"mang\s*thai|thai\s*sản|kết\s*hôn", text, re.I))
    has_term = bool(
        re.search(r"chấm\s*dứt|sa\s*thải|đuổi|đúng\s*luật|hợp\s*pháp|vi\s*phạm", text, re.I)
    )
    if has_preg and has_term:
        boosts.append(
            "cấm đơn phương chấm dứt hợp đồng lao động nữ mang thai Bộ luật Lao động"
        )
    if not boosts:
        return rewrite_qa_query(text, max_chars=max_chars)
    merged = f"{text} {' '.join(dict.fromkeys(boosts))}"
    return re.sub(r"\s+", " ", merged).strip()[:max_chars]


def _extract_topic_labels(blob: str) -> list[str]:
    out: list[str] = []
    for pat, label in _TOPIC_LABELS:
        if pat.search(blob) and label not in out:
            out.append(label)
    return out


def _strip_answer_prose(text: str) -> str:
    """Drop 'Kết luận:' / 'Căn cứ:' scaffolding so it doesn't dominate FTS."""
    t = text or ""
    t = re.sub(r"(?i)kết\s*luận\s*:\s*", " ", t)
    t = re.sub(r"(?i)căn\s*cứ\s*:\s*", " ", t)
    t = re.sub(r"(?i)khuyến\s*nghị\s*:\s*", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def augment_qa_retrieval_query(
    question: str,
    history: list[BaseMessage] | list | None,
    *,
    max_chars: int = 420,
) -> str:
    """Resolve follow-ups without dumping prior answer prose into the legal search.

    Old behaviour concatenated the last AI answer (incl. 'Kết luận: HĐ không quy định
    nghỉ thai sản') onto 'đúng luật không?', so retrieval stayed on BHXH leave timing
    instead of BLLĐ termination-for-pregnancy. We now pull topic keywords + Điều refs.
    """
    q = unicodedata.normalize("NFC", (question or "").strip())
    if not history:
        return expand_legal_topic_query(q, max_chars=max_chars)

    prior_parts: list[str] = []
    for m in history[-4:]:
        content = getattr(m, "content", None)
        if content:
            prior_parts.append(_strip_answer_prose(str(content)))
    prior = " ".join(prior_parts)

    clause_nums = re.findall(r"(?i)Điều\s*(\d+)", prior)
    topics = _extract_topic_labels(f"{prior} {q}")
    short_or_deictic = len(q) < 48 or bool(_LEGALITY_FOLLOWUP.search(q))

    if short_or_deictic and (topics or clause_nums):
        parts: list[str] = ["Bộ luật Lao động", *topics]
        if clause_nums:
            parts.append(f"Điều {clause_nums[-1]} hợp đồng")
        # Prefer the legal issue in prior human turns over AI conclusion prose
        for m in history[-4:]:
            name = type(m).__name__
            if name == "HumanMessage":
                hc = _strip_answer_prose(str(getattr(m, "content", "") or ""))
                if hc:
                    parts.append(hc[:160])
                    break
        parts.append(q)
        return expand_legal_topic_query(" ".join(parts), max_chars=max_chars)

    if topics:
        return expand_legal_topic_query(f"{' '.join(topics)} {q}", max_chars=max_chars)
    return expand_legal_topic_query(q, max_chars=max_chars)


def rewrite_legal_query(
    title: str | None,
    summary: str | None,
    contract_type: str | None = None,
    max_chars: int = 400,
) -> str:
    """Build retrieval query from clause context — no fixed số hiệu bias.

    Ranking by Bộ luật/Luật → … → Thông tư happens later in GraphRAG ordering.
    """
    parts = []
    ct = (contract_type or "").strip()
    if ct:
        # Collapse noisy headers like "Hợp đồng LAO ĐỘNG Số: 204/2026/HĐLĐ …"
        if re.search(r"hợp\s*đồng\s*lao\s*động|\bHĐLĐ\b", ct, re.I):
            parts.append("Hợp đồng lao động")
        else:
            # Drop contract serial numbers that dilute FTS/vector
            ct = re.sub(r"Số\s*:\s*\S+", " ", ct, flags=re.I)
            ct = re.sub(r"\b\d{1,4}/\d{4}/[A-ZĐ0-9.-]+\b", " ", ct)
            parts.append(re.sub(r"\s+", " ", ct).strip()[:80])
    if title:
        parts.append(title.strip())
    # Guard: title and summary often carry the SAME text from callers that pass
    # the question to both slots. Duplicating bloats the FTS query (ts_rank_cd is
    # length-normalised) and drops retrieval quality.
    if summary and summary.strip() != (title or "").strip():
        # Prefer clause body; strip job_context noise already folded by caller
        # but keep legal keywords (làm thêm, BHXH, kỷ luật, …).
        parts.append(summary.strip())
    text = " ".join(parts)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Drop very short filler tokens but keep legal/number tokens
    tokens = []
    for tok in text.split(" "):
        if len(tok) <= 1:
            continue
        if _FILLER.fullmatch(tok):
            continue
        tokens.append(tok)
    rewritten = " ".join(tokens) if tokens else text
    # Topic boosts also help clause-risk GraphRAG (pregnancy fire, OT unpaid…).
    return expand_legal_topic_query(rewritten, max_chars=max_chars)

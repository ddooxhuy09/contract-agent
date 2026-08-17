"""Rule-based query rewrite for legal retrieval (no extra LLM hop)."""

import re
import unicodedata

_FILLER = re.compile(
    r"\b(các|của|và|hoặc|một|những|này|đó|the|and|or|a|an|to|of|for|with|"
    r"quy định|theo|về|trong|khi|nếu|sẽ|được|phải|có)\b",
    re.IGNORECASE,
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
    return rewritten[:max_chars]

"""Rule-based query rewrite for legal retrieval (no extra LLM hop)."""

import re
import unicodedata

_FILLER = re.compile(
    r"\b(các|của|và|hoặc|một|những|này|đó|the|and|or|a|an|to|of|for|with|"
    r"quy định|theo|về|trong|khi|nếu|sẽ|được|phải|có)\b",
    re.IGNORECASE,
)


def rewrite_legal_query(
    title: str | None,
    summary: str | None,
    contract_type: str | None = None,
    max_chars: int = 400,
) -> str:
    parts = []
    if contract_type:
        parts.append(contract_type.strip())
    if title:
        parts.append(title.strip())
    if summary:
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

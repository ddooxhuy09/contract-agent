"""Prompt-injection guard for uploaded contract text (OWASP LLM01:2025).

The contract author is often the other party, so its text is untrusted. Two layers:
``fence`` marks the text as data inside the prompt (rule in ``prompts.GLOBAL_UNTRUSTED_DATA``),
and ``looks_like_prompt_injection`` catches text that talks to the AI, so that clause is
reported to the user instead of being judged by the model it is trying to steer.
"""

from __future__ import annotations

import re

DATA_TAG = "du_lieu_nguoi_dung"
_TAG_RE = re.compile(rf"</?\s*{DATA_TAG}\s*>", re.I)

# Phrases a real contract has no reason to contain. Matched on lower-cased text.
_INJECTION_RE = re.compile(
    "|".join([
        r"(?:bỏ qua|phớt lờ|quên|không (?:cần )?tuân theo)\s+(?:mọi|tất cả|toàn bộ|các)?\s*"
        r"(?:hướng dẫn|chỉ dẫn|chỉ thị|lệnh|quy tắc|prompt)\s*(?:trước(?: đó)?|ở trên|phía trên|hệ thống|của hệ thống)",
        r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|rules?)",
        r"\bsystem prompt\b|lời nhắc hệ thống",
        r"\bbạn là (?:một )?(?:ai|trợ lý(?: ai)?|mô hình|chatbot|llm)\b",
        r"\byou are (?:now )?(?:an? )?(?:ai|assistant|language model|chatbot)\b",
        r"(?:gửi|dành cho|lưu ý cho|chú ý|nói với)\s+(?:các |bất kỳ )?(?:trợ lý ai|mô hình ai|mô hình ngôn ngữ|hệ thống ai|llm|chatgpt|gemini|chatbot)\b",
        r"(?:hãy|phải|cần)\s+(?:đánh giá|kết luận|trả lời|xếp loại|chấm)\b[^.\n]{0,60}\b(?:severity|là ok|không có (?:rủi ro|vấn đề|vi phạm))",
        r"[\"']?severity[\"']?\s*[:=]",
    ]),
    re.I,
)


def fence(text: str | None) -> str:
    """Wrap untrusted text in the data tag; tags inside the text are removed so it cannot close it early."""
    return f"<{DATA_TAG}>\n{_TAG_RE.sub('', text or '')}\n</{DATA_TAG}>"


def looks_like_prompt_injection(text: str | None) -> bool:
    return bool(text) and _INJECTION_RE.search(text.lower()) is not None

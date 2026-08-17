import json
import re
from typing import Optional

from app.core.logging import logger

_COMMON_FIXES = [
    (re.compile(r"}\s*,\s*([}\]])"), r"}\1"),
    (re.compile(r",\s*(?=[}\]])"), r""),
    (re.compile(r"\u201c|\u201d"), '"'),
    (re.compile(r"\u2018|\u2019"), "'"),
]


def _repair_json(text: str) -> str:
    for pattern, replacement in _COMMON_FIXES:
        text = pattern.sub(replacement, text)
    return text


def parse_json_object(raw: str) -> Optional[dict]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    result = _try_parse(text)
    if result is not None:
        return result

    json_block = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_block:
        result = _try_parse(json_block.group(0))
        if result is not None:
            return result

    logger.warning("QA JSON parse failed. Raw LLM output (first 500 chars): %s", raw[:500])
    return None


def _try_parse(text: str) -> Optional[dict]:
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    else:
        return result if isinstance(result, dict) else None

    repaired = _repair_json(text)
    try:
        result = json.loads(repaired)
    except (json.JSONDecodeError, TypeError):
        return None
    return result if isinstance(result, dict) else None

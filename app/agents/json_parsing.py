import json
import re
from typing import Optional


def parse_json_object(raw: str) -> Optional[dict]:
    """Extract a single JSON object from an LLM response, tolerating ```json fences."""
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return result if isinstance(result, dict) else None

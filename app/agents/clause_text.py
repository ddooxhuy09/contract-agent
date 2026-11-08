"""Sentence-level helpers shared by field extraction and clause rewriting.

Contract text often arrives with a whole Điều on one line (DOCX paragraphs), so
line-based snippets drag unrelated sentences along. These helpers cut at the
real boundaries: sentence ends, list markers ``(i)`` / ``3.2.`` and Điều headings.
"""

from __future__ import annotations

import re
from collections.abc import Callable

# Boundary = the whitespace between two segments. A '.' right after a digit is not a
# sentence end ("3.2.", "8.500.000"), and a list marker starts a new segment.
_BOUNDARY = re.compile(
    r"(?<=[;!?])\s+"
    r"|(?<=[^\d\s]\.)\s+"
    r"|\s+(?=\((?:[ivxIVX]+|[a-z]|\d+)\)\s)"
    r"|\s+(?=(?:\d{1,2}\.){2,3}\s)"
    r"|\s+(?=\*{0,2}Điều\s+\d+\s*[:.])"
    r"|\n+"
)
_MARKER = re.compile(r"^(?:\((?:[ivxIVX]+|[a-z]|\d+)\)|(?:\d{1,2}\.){1,3}|\**Điều\s+\d+\s*[:.]\**)\s*")
_SIGNATURE = re.compile(
    r"\**\s*(?:NGƯỜI\s+LAO\s+ĐỘNG|NGƯỜI\s+SỬ\s+DỤNG\s+LAO\s+ĐỘNG|ĐẠI\s+DIỆN[^\n(*]{0,30})\**\s*_?\(?\s*[Kk]ý"
)


def split_segments(text: str) -> list[tuple[str, str]]:
    """``[(segment, trailing_separator)]`` — joining ``seg + sep`` rebuilds ``text``."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _BOUNDARY.finditer(text):
        if m.start() > pos:
            out.append((text[pos : m.start()], m.group(0)))
            pos = m.end()
    if pos < len(text):
        out.append((text[pos:], ""))
    return out


def join_segments(segments: list[tuple[str, str]]) -> str:
    return "".join(seg + sep for seg, sep in segments).strip()


def lead_marker(segment: str) -> str:
    """The list marker a segment starts with, e.g. ``(iii)`` or ``3.2.`` (else '')."""
    m = _MARKER.match(segment)
    return m.group(0) if m else ""


def strip_signature_block(text: str) -> str:
    """Drop the trailing «NGƯỜI LAO ĐỘNG (Ký tên…)» block that follows the last Điều."""
    m = _SIGNATURE.search(text)
    return text[: m.start()].rstrip() if m and m.start() > 0 else text


def sentences_matching(
    text: str,
    pattern: str | re.Pattern[str],
    accept: Callable[[str], bool] | None = None,
) -> list[str]:
    """Segments of ``text`` matching ``pattern`` (and ``accept``), whitespace-normalised."""
    rx = re.compile(pattern, re.I) if isinstance(pattern, str) else pattern
    out: list[str] = []
    for seg, _ in split_segments(text):
        clean = re.sub(r"\s+", " ", seg).strip()
        if clean and rx.search(clean) and (accept is None or accept(clean)):
            out.append(clean)
    return out

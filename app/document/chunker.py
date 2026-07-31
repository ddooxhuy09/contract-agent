import re
import unicodedata
from typing import List

from langchain_core.documents import Document

from app.core.config import CHUNK_OVERLAP, MAX_CHUNK_SIZE

_SEPARATORS = ["\n\n", "\n", ".", " ", ""]
# Split on Điều only — Khoản stays inside the same Điều chunk unless over budget.
_ARTICLE_PATTERN = re.compile(
    r"(?:(?:Điều|ĐIỀU)\s+(\d+)[\.:\-\)]\s*)",
)


def _split_text(text: str, chunk_size: int, chunk_overlap: int, separators: List[str] = None) -> List[str]:
    """Recursively split text on the first separator that fits, applying overlap between chunks."""
    if len(text) <= chunk_size:
        return [text] if text else []

    separators = _SEPARATORS if separators is None else separators
    sep = separators[0]
    rest = separators[1:]
    parts = text.split(sep) if sep else list(text)

    chunks, current = [], ""
    for part in parts:
        candidate = current + sep + part if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part) > chunk_size and rest:
                chunks.extend(_split_text(part, chunk_size, chunk_overlap, rest))
                current = ""
            else:
                current = part
    if current:
        chunks.append(current)

    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            overlapped.append(chunks[i - 1][-chunk_overlap:] + chunks[i])
        return overlapped
    return chunks


def _emit_article_parts(
    documents: list,
    contract_id: str,
    clause_number: str,
    chunk_text: str,
    chunk_index: int,
) -> int:
    """Append one or more chunks for a Điều; keep clause_number stable across parts."""
    if len(chunk_text) <= MAX_CHUNK_SIZE:
        chunk_index += 1
        documents.append(
            Document(
                page_content=chunk_text,
                metadata={
                    "contract_id": contract_id,
                    "clause_number": clause_number,
                    "chunk_index": chunk_index,
                    "part": 1,
                },
            )
        )
        return chunk_index

    parts = _split_text(chunk_text, MAX_CHUNK_SIZE, CHUNK_OVERLAP)
    for part_i, chunk in enumerate(parts, start=1):
        chunk_index += 1
        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "contract_id": contract_id,
                    "clause_number": clause_number,
                    "chunk_index": chunk_index,
                    "part": part_i,
                },
            )
        )
    return chunk_index


def chunk_by_clause(text: str, contract_id: str) -> List[Document]:
    """Chunk contract text by Điều (article). Khoản stays inside the Điều unit."""
    text = unicodedata.normalize("NFC", text)
    documents: List[Document] = []
    chunk_index = 0

    matches = list(_ARTICLE_PATTERN.finditer(text))
    if not matches:
        for idx, chunk in enumerate(_split_text(text, MAX_CHUNK_SIZE, CHUNK_OVERLAP)):
            if chunk.strip():
                documents.append(
                    Document(
                        page_content=chunk.strip(),
                        metadata={
                            "contract_id": contract_id,
                            "clause_number": str(idx + 1),
                            "chunk_index": idx + 1,
                            "part": 1,
                        },
                    )
                )
        return documents

    # Preamble before first Điều
    preamble = text[: matches[0].start()].strip()
    if preamble:
        chunk_index = _emit_article_parts(
            documents, contract_id, "Preamble", preamble, chunk_index
        )

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk_text = text[start:end].strip()
        if not chunk_text:
            continue
        clause_number = m.group(1)
        chunk_index = _emit_article_parts(
            documents, contract_id, clause_number, chunk_text, chunk_index
        )

    return documents

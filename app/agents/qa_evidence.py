"""Topic-guided statute lookup; retrieves evidence without deciding a verdict."""
from __future__ import annotations

import re
import unicodedata

from langchain_core.documents import Document

from app.agents.effectivity import evaluate_document_effectivity
from app.agents.labor_code_resolver import resolve_labor_code_document
from app.agents.legal_citations import trim_to_provision
from app.infrastructure.retrieval.context import get_legal_chunks, get_legal_docs

# BLLĐ 2019 topic index, checked against the official consolidated 125/VBHN-VPQH.
# These select provisions for compliant and violating text alike, never a label.
_TOPICS = (
    (r"giấy\s*tờ|căn\s*cước|CCCD|CMND|hộ\s*chiếu|văn\s*bằng|bằng\s*cấp|chứng\s*chỉ|đặt\s*cọc", (17,)),
    (r"kỷ\s*luật|phạt\s*tiền|khấu\s*trừ|trừ\s*(?:\d[\d.,]*\s*đồng|lương)|chấm\s*công|đi\s*muộn", (127, 102, 124)),
    (r"đào\s*tạo|học\s*nghề|hoàn\s*trả.{0,30}học\s*phí", (62, 40)),
    (r"làm\s*thêm|tăng\s*ca|overtime|\bOT\b", (98, 107)),
    (r"bảo\s*hiểm|BHXH|BHYT", (168,)),
    (r"thai\s*sản|mang\s*thai|lao\s*động\s*nữ|kết\s*hôn|sinh\s*con", (137, 138, 34)),
    (r"tranh\s*chấp|khởi\s*kiện|khiếu\s*nại|tòa\s*án", (190, 187, 188)),
    (r"chấm\s*dứt|thôi\s*việc|nghỉ\s*việc|tịch\s*thu|giữ.{0,30}lương|lương.{0,30}(?:tháng\s*cuối|kỳ\s*cuối)", (94, 48, 40)),
    (r"nội\s*dung\s*(?:chủ\s*yếu|bắt\s*buộc)|thông\s*tin\s*các\s*bên", (21,)),
    (r"thử\s*việc", (24, 25, 26)),
    (r"nghỉ\s*phép|nghỉ\s*hằng\s*năm|nghỉ\s*không\s*hưởng\s*lương", (113, 115)),
)


def topic_articles(text: str) -> tuple[int, ...]:
    text = unicodedata.normalize("NFC", text)
    heading = text.splitlines()[0] if text else ""
    # A heading identifies the main issue; incidental words in the body do not.
    for blob in (heading, text):
        for pattern, articles in _TOPICS:
            if re.search(pattern, blob, re.I):
                return articles
    return ()


def _article_text(rows: list[tuple]) -> str:
    lines = []
    seen = set()
    for text, path in sorted(rows, key=lambda r: re.sub(r"\d+", lambda m: m.group().zfill(6), r[1])):
        for line in trim_to_provision(text, max_chars=12000).splitlines():
            if line not in seen:
                seen.add(line)
                lines.append(line)
    return "\n".join(lines)


def _exact_documents(repo, law, articles):
    result = []
    for article in articles:
        chunks = repo.find_article_chunks(law["doc_id"], rf"\.D{article}(\.|$)", 64)
        content = _article_text(chunks)
        if content:
            result.append(Document(page_content=content, metadata={
                **law, "doc_number": law["doc_num"], "path": chunks[0][1],
                "article": article, "role": "topic_anchor", "evidence_paths": [x[1] for x in chunks],
            }))
    return result


def augment_legal_evidence(docs: list[Document], focus: str, as_of_date: str | None, *, contract_context: str = "") -> list[Document]:
    if not re.search(r"lao\s*động|\bNLĐ\b|\bNSDLĐ\b|\bHĐLĐ\b|BHXH|BHYT", f"{focus}\n{contract_context}", re.I):
        return docs
    articles = topic_articles(focus)
    if not articles:
        return docs
    law = resolve_labor_code_document(as_of_date)
    # Article numbers differ in earlier codes; retain normal retrieval for them.
    if not law or law["doc_num"] != "45/2019/QH14" or not evaluate_document_effectivity(law, as_of_date).ok_to_cite:
        return docs
    repo = get_legal_chunks()
    if repo is None:
        return docs
    exact = _exact_documents(repo, law, articles)
    if not exact:
        return docs
    if articles == (190, 187, 188):
        documents = get_legal_docs()
        row = documents.find_row_by_doc_num(["92/2015/QH13"]) if documents else None
        if row:
            civil = dict(zip(("doc_id", "doc_num", "title", "doc_type", "status_flag", "eff_flag", "eff_from", "eff_to", "issue_date", "source_url"), row))
            if evaluate_document_effectivity(civil, as_of_date).ok_to_cite:
                exact = _exact_documents(repo, civil, (4, 9)) + exact
    elif articles in ((62, 40), (113, 115)):
        exact += _exact_documents(repo, law, (4, 15))
    # Once direct provisions exist, unrelated vector passages only add scope noise.
    return exact[:5]

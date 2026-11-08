"""Build an offline QA benchmark and legal-corpus gap reports.

The source dataset is a legal single-hop QA set.  Its ``context`` column is
kept as the reference evidence; it is not treated as an LLM-generated gold
answer.  This makes the benchmark deterministic and safe to run in CI.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from collections.abc import Iterable


DOC_ID_RE = re.compile(r"^(?P<source>[^+]+?)(?:\+(?P<element>[^+]+))?$")
ARTICLE_RE = re.compile(r"(?i)\bĐiều\s+(\d+)")


def _normalise_source(value: str) -> str:
    """Use a stable, case-insensitive key while preserving legal punctuation."""
    return re.sub(r"\s+", "", (value or "").strip()).lower()


def _display_doc_number(value: str) -> str:
    parts = (value or "").strip().split("/")
    if len(parts) >= 3:
        return "/".join([parts[0], parts[1], "/".join(parts[2:]).upper()])
    return value.strip().upper()


def _parse_doc_id(doc_id: str) -> tuple[str, str]:
    match = DOC_ID_RE.match((doc_id or "").strip())
    if not match:
        return (doc_id or "").strip(), ""
    return match.group("source"), match.group("element") or ""


def _article_ref(title: str, context: str, element: str) -> str:
    # The CSV stores the article heading in ``title`` and only the body in
    # ``context``.  Searching the body first can pick up a cross-reference to
    # a different article (for example, "theo khoản 3 Điều 10").
    match = ARTICLE_RE.search(title or "") or ARTICLE_RE.search(context or "")
    if match:
        return match.group(1)
    element_match = re.search(r"\d+", element or "")
    return element_match.group(0) if element_match else ""


def _document_type(source: str) -> str:
    suffix = source.rsplit("/", 1)[-1].lower()
    if suffix.startswith("nd-") or suffix.startswith("nđ-") or suffix in {"nd-cp", "nđ-cp"}:
        return "Nghị định"
    if suffix.startswith("ttlt-"):
        return "Thông tư liên tịch"
    if suffix.startswith("tt-"):
        return "Thông tư"
    if suffix.startswith("qh"):
        return "Văn bản Quốc hội"
    return "Khác"


def read_dataset(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(10 * 1024 * 1024)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _iter_metadata_files(corpus_root: Path) -> Iterable[Path]:
    if not corpus_root.exists():
        return
    yield from corpus_root.rglob("thuoc_tinh.json")


def read_corpus_documents(corpus_root: Path) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for metadata_path in _iter_metadata_files(corpus_root):
        relative_parts = {part.lower() for part in metadata_path.relative_to(corpus_root).parts}
        if "tests" in relative_parts or "schemas" in relative_parts:
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        doc_num = str(metadata.get("doc_num") or "").strip()
        if doc_num:
            documents[_normalise_source(doc_num)] = {
                "doc_num": _display_doc_number(doc_num),
                "title": metadata.get("title") or "",
                "doc_id": str(metadata.get("doc_id") or ""),
                "status": metadata.get("eff_status") or "",
                "path": str(metadata_path.parent),
            }
    return documents


def normalise_cases(rows: list[dict[str, str]], corpus: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        source, element = _parse_doc_id(row.get("doc_id", ""))
        article = _article_ref(row.get("title", ""), row.get("context", ""), element)
        source_display = _display_doc_number(source)
        corpus_doc = corpus.get(_normalise_source(source))
        cases.append(
            {
                "case_id": f"{row.get('qid', '').strip()}-{index:04d}",
                "qid": row.get("qid", "").strip(),
                "source_doc": source_display,
                "source_doc_key": _normalise_source(source),
                "element_id": element,
                "article": article,
                "expected_citation": f"Điều {article}" if article else None,
                "question": row.get("question", "").strip(),
                "reference_context": row.get("context", "").strip(),
                "answerability": "answerable" if row.get("context", "").strip() else "unanswerable",
                "corpus_status": "available" if corpus_doc else "missing",
                "corpus_title": corpus_doc.get("title") if corpus_doc else None,
            }
        )
    return cases


def build_missing_rows(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for case in cases:
        key = case["source_doc_key"]
        item = grouped.setdefault(
            key,
            {
                "source_doc": case["source_doc"],
                "document_type": _document_type(case["source_doc"]),
                "question_count": 0,
                "element_ids": set(),
                "sample_qids": [],
                "sample_questions": [],
            },
        )
        item["question_count"] += 1
        if case["element_id"]:
            item["element_ids"].add(case["element_id"])
        if len(item["sample_qids"]) < 3:
            item["sample_qids"].append(case["qid"])
            item["sample_questions"].append(case["question"])

    rows = []
    for item in grouped.values():
        item["element_count"] = len(item.pop("element_ids"))
        item["sample_qids"] = "; ".join(item["sample_qids"])
        item["sample_questions"] = " | ".join(item["sample_questions"])
        item["status"] = "missing_from_local_corpus"
        item["next_action"] = "Crawl/ingest metadata, toàn văn và mục lục; kiểm tra hiệu lực trước khi bật truy hồi."
        rows.append(item)
    return sorted(rows, key=lambda row: (-row["question_count"], row["source_doc"]))


def write_jsonl(path: Path, cases: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_doc",
        "document_type",
        "question_count",
        "element_count",
        "sample_qids",
        "sample_questions",
        "status",
        "next_action",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_coverage(
    path: Path,
    cases: list[dict[str, Any]],
    missing: list[dict[str, Any]],
    corpus: dict[str, dict[str, Any]],
) -> None:
    questions = Counter(case["question"] for case in cases)
    qids = Counter(case["qid"] for case in cases)
    source_counts = Counter(case["source_doc"] for case in cases)
    available_cases = sum(case["corpus_status"] == "available" for case in cases)
    duplicate_questions = sum(count > 1 for count in questions.values())
    type_counts = Counter(row["document_type"] for row in missing)
    top_sources = source_counts.most_common(10)

    lines = [
        "# QA Benchmark Coverage",
        "",
        "## Dataset",
        "",
        f"- Số mẫu: **{len(cases)}**",
        f"- Số văn bản nguồn: **{len(source_counts)}**",
        f"- Câu hỏi xuất hiện từ hai lần trở lên: **{duplicate_questions}**",
        f"- QID xuất hiện từ hai lần trở lên: **{sum(count > 1 for count in qids.values())}**",
        f"- Mẫu có context tham chiếu: **{sum(bool(case['reference_context']) for case in cases)}**",
        "",
        "## Corpus Coverage",
        "",
        f"- Metadata văn bản tìm thấy trong local corpus: **{len(corpus)}**",
        f"- Mẫu có văn bản local tương ứng: **{available_cases}**",
        f"- Văn bản nguồn còn thiếu: **{len(missing)}**",
        "",
        "`missing_from_local_corpus` chỉ phản ánh các file corpus trong repository. Nếu database đang chạy có dump riêng, cần chạy kiểm tra bổ sung trên database.",
        "",
        "## Missing By Type",
        "",
    ]
    for doc_type, count in sorted(type_counts.items(), key=lambda pair: (-pair[1], pair[0])):
        lines.append(f"- {doc_type}: **{count}**")
    lines.extend(["", "## Top Source Documents By Question Count", ""])
    for source, count in top_sources:
        lines.append(f"- `{source}`: {count} mẫu")
    lines.extend(
        [
            "",
            "## Project-Critical Gaps",
            "",
            "- `45/2019/QH14` - Bộ luật Lao động: bắt buộc bổ sung cho `labor_code_resolver`, red flags và QA hợp đồng lao động.",
            "- `91/2015/QH13` - Bộ luật Dân sự: xuất hiện trong hợp đồng mẫu và dataset nhưng chưa có local corpus.",
            "- Nhóm văn bản về BHXH, BHYT, BHTN: cần crawl và xác định văn bản hiện hành theo ngày phân tích trước khi dùng làm căn cứ.",
            "- Các nghị định/thông tư xử phạt và hướng dẫn chuyên ngành: chỉ ingest khi có nhu cầu nghiệp vụ tương ứng; không dùng làm căn cứ chung cho mọi hợp đồng.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    rows = read_dataset(args.dataset)
    corpus = read_corpus_documents(args.corpus_root)
    cases = normalise_cases(rows, corpus)
    missing = build_missing_rows(cases)
    write_jsonl(args.fixture, cases)
    write_csv(args.missing_report, missing)
    write_coverage(args.coverage, cases, missing, corpus)
    print(
        f"Built {len(cases)} cases, {len(missing)} missing source documents, "
        f"and found {len(corpus)} local corpus documents."
    )


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=root / "data" / "dataset.csv")
    parser.add_argument("--corpus-root", type=Path, default=root / "data" / "legal_corpus_samples")
    parser.add_argument("--fixture", type=Path, default=root / "tests" / "fixtures" / "legal_qa.jsonl")
    parser.add_argument("--missing-report", type=Path, default=root / "evaluation_results" / "reports" / "missing_legal_documents.csv")
    parser.add_argument("--coverage", type=Path, default=root / "evaluation_results" / "reports" / "qa_coverage.md")
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())

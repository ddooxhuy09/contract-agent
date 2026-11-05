"""Independent benchmark/data audit and read-only corpus coverage inspection."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import date

from evaluation.runtime_adapter import BENCHMARK, BASELINE_RUN, error_info
from evaluation.run_benchmark import write_json, now


def load(name):
    return json.loads((BENCHMARK / name).read_text(encoding="utf-8"))


def norm_law(value):
    text = unicodedata.normalize("NFD", str(value or "").upper().replace("Đ", "D"))
    return re.sub(r"[^A-Z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)))


def audit_benchmark():
    bundle = load("MIXED_34_TEST_CASES_V04.json")
    cases, questions = bundle["test_cases"], load("QUESTIONS_ONLY_NO_GOLD.json")
    lines = [json.loads(line) for line in (BENCHMARK / "MIXED_34_TEST_CASES_V04.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    provisions = load("LEGAL_PROVISIONS.json")
    docs = load("LEGAL_DOCUMENTS_STATUS.json")
    relations = load("LEGAL_RELATION_GRAPH.json")
    timeline = load("PROVISION_VERSION_TIMELINE.json")
    corpus = [json.loads(line) for line in (BENCHMARK / "RETRIEVAL_CORPUS_MIXED_UNLABELED.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    errors, warnings = [], []
    ids = [c["id"] for c in cases]
    if len(cases) != 34 or len(set(ids)) != 34:
        errors.append("Expected 34 unique test case IDs.")
    if cases != lines:
        errors.append("JSON and JSONL case payloads differ.")
    if {c["id"] for c in questions} != set(ids):
        errors.append("Questions-only case IDs do not match gold cases.")
    qmap = {c["id"]: c for c in questions}
    pmap = {p["provision_id"]: p for p in provisions}
    emap = {e["edge_id"]: e for e in relations}
    doc_ids = {d["id"] for d in docs}
    case_warnings = {}
    for c in cases:
        cw = ["Synthetic draft; independent legal review pending."]
        for field in ("input", "difficulty", "gold", "scoring"):
            if field not in c:
                errors.append(f"{c['id']}: missing {field}")
        if c["difficulty"].get("level") not in ("easy", "medium", "hard", "expert"):
            errors.append(c["id"] + ": invalid difficulty")
        if qmap[c["id"]]["question"] != c["input"]["question"]:
            errors.append(c["id"] + ": questions-only text differs")
        for key in ("as_of_date", "transaction_date"):
            if c["input"].get(key):
                try:
                    date.fromisoformat(c["input"][key])
                except ValueError:
                    errors.append(f"{c['id']}: invalid {key}")
        asof, trans = c["input"].get("as_of_date"), c["input"].get("transaction_date")
        if asof and trans and trans > asof:
            cw.append("transaction_date is later than as_of_date; examine scenario.")
        for pid in c["gold"].get("required_provision_ids", []):
            if pid not in pmap:
                errors.append(f"{c['id']}: undefined required provision {pid}")
            elif pmap[pid]["law_number"] not in doc_ids:
                cw.append(f"Required law {pmap[pid]['law_number']} is absent from LEGAL_DOCUMENTS_STATUS metadata.")
        for edge in c.get("expected_legal_graph", {}).get("required_relation_edge_ids", []):
            if edge not in emap:
                errors.append(f"{c['id']}: undefined required edge {edge}")
        if c["task"] == "risk" and not c["gold"].get("risk_severity"):
            cw.append("Risk task has no gold risk_severity in repository label space; severity scoring unavailable.")
        if c["id"] in ("TEMP-010", "TEMP-011", "TEMP-012", "TEMP-013"):
            cw.append("Provision-version full text is incomplete/unverified; exact historical-text and current post-2025 applicability claims require review.")
        case_warnings[c["id"]] = cw
    for e in relations:
        if e["source_law_id"] not in doc_ids or e["target_law_id"] not in doc_ids:
            errors.append(e["edge_id"] + ": undefined document endpoint")
        for pid in e.get("basis_provision_ids", []):
            if pid not in pmap:
                errors.append(e["edge_id"] + ": undefined basis provision " + pid)
    for v in timeline:
        if v.get("effective_until_exclusive") and v["effective_from"] >= v["effective_until_exclusive"]:
            errors.append(v["version_id"] + ": invalid effective interval")
        if v.get("modifying_edge_id") and v["modifying_edge_id"] not in emap:
            errors.append(v["version_id"] + ": unknown modifying edge")
    contract_checks = []
    from app.document.parser import parse_docx
    for contract in bundle["contracts"]:
        path = BENCHMARK / contract["document_path"]
        actual = parse_docx(str(path)) if path.exists() else None
        normalize = lambda s: re.sub(r"\s+", " ", s or "").strip()
        match = normalize(actual) == normalize(contract["text"])
        body_contained = normalize(contract["text"]) in normalize(actual)
        if not match:
            warnings.append(contract["contract_id"] + (": DOCX contains the reference body plus additional title/disclaimer text." if body_contained else ": DOCX body differs from embedded reference text; retain actual parser output."))
        missing_text = not (BENCHMARK / contract["text_path"]).exists()
        if missing_text:
            warnings.append(contract["contract_id"] + ": declared .txt artifact absent; DOCX exists and is used.")
        contract_checks.append({"id": contract["contract_id"], "docx_exists": path.exists(), "docx_matches_embedded_text": match, "docx_contains_reference_body": body_contained, "declared_txt_missing": missing_text})
        for c in cases:
            if c["input"].get("contract_id") == contract["contract_id"] and c["input"].get("contract_excerpt_span"):
                span = c["input"]["contract_excerpt_span"]
                if contract["text"][span["start"]:span["end"]] != c["input"].get("clause_text"):
                    warnings.append(c["id"] + ": annotated span does not exactly equal clause_text.")
    omitted_docs = sorted({p["law_number"] for p in provisions} - doc_ids)
    if omitted_docs:
        warnings.append("Provision laws omitted from status manifest: " + ", ".join(omitted_docs))
    return {"generated_at": now(), "schema_valid": not errors, "errors": errors, "warnings": warnings,
            "case_count": len(cases), "difficulty_counts": dict(Counter(c["difficulty"]["level"] for c in cases)),
            "task_counts": dict(Counter(c["task"] for c in cases)), "provision_count": len(provisions),
            "document_status_count": len(docs), "unique_laws_in_provisions": len({norm_law(p['law_number']) for p in provisions}),
            "relation_count": len(relations), "version_count": len(timeline), "retrieval_fixture_chunks": len(corpus),
            "verification_levels": dict(Counter(p.get("verification_level", "unspecified") for p in provisions)),
            "all_cases_independently_legally_verified": False, "case_warnings": case_warnings,
            "contracts": contract_checks, "unverified_version_rows": [v for v in timeline if not v.get("full_text_available")],
            "statute_status_manifest_omissions": omitted_docs}


def inspect_corpus():
    import psycopg2
    from neo4j import GraphDatabase
    from app.core.settings import get_settings
    s = get_settings()
    provisions, laws, edges = load("LEGAL_PROVISIONS.json"), load("LEGAL_DOCUMENTS_STATUS.json"), load("LEGAL_RELATION_GRAPH.json")
    requested = sorted({p["law_number"] for p in provisions} | {d["id"] for d in laws})
    conn = psycopg2.connect(s.database_url, connect_timeout=5)
    result = {"snapshot_at": now(), "requested_laws": requested, "documents": [], "provisions": [], "graph_coverage": []}
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute("SELECT count(*) FROM legal_documents")
            result["document_metadata_rows"] = cur.fetchone()[0]
            cur.execute("SELECT count(DISTINCT doc_id),count(*),count(*) FILTER(WHERE embedding IS NOT NULL),count(*) FILTER(WHERE is_effective) FROM legal_embeddings")
            result["documents_with_chunks"], result["chunk_count"], result["embedded_chunk_count"], result["effective_chunk_count"] = cur.fetchone()
            cur.execute("SELECT doc_id,doc_num,title,eff_from,eff_to,status_flag FROM legal_documents WHERE regexp_replace(upper(replace(doc_num,'Đ','D')),'[^A-Z0-9]','','g')=ANY(%s)", ([norm_law(n) for n in requested],))
            for row in cur.fetchall():
                result["documents"].append(dict(zip(("doc_id", "doc_num", "title", "eff_from", "eff_to", "status_flag"), row)))
            docmap = {}
            for d in result["documents"]:
                docmap.setdefault(norm_law(d["doc_num"]), []).append(d["doc_id"])
            ids = [d["doc_id"] for d in result["documents"]]
            cur.execute("SELECT doc_id,count(*),count(*)FILTER(WHERE is_effective),count(*)FILTER(WHERE embedding IS NOT NULL) FROM legal_embeddings WHERE doc_id=ANY(%s) GROUP BY doc_id", (ids,))
            counts = {r[0]: {"chunks": r[1], "effective_chunks": r[2], "embedded_chunks": r[3]} for r in cur.fetchall()}
            for d in result["documents"]:
                d.update(counts.get(d["doc_id"], {"chunks": 0, "effective_chunks": 0, "embedded_chunks": 0}))
            for p in provisions:
                docids = docmap.get(norm_law(p["law_number"]), [])
                article_pattern = r"(^|\.)D" + re.escape(str(p["article"])) + r"(\.|$)"
                filters, values = ["doc_id=ANY(%s)", "path::text ~ %s"], [docids, article_pattern]
                if p.get("clause"):
                    filters.append("path::text ~ %s")
                    values.append(r"\.K" + re.escape(str(p["clause"])) + r"(\.|$)")
                if p.get("point"):
                    filters.append("path::text ~ %s")
                    values.append(r"\." + re.escape(str(p["point"]).lower()) + r"(\.|$)")
                cur.execute("SELECT count(*),count(*)FILTER(WHERE is_effective),min(path::text) FROM legal_embeddings WHERE " + " AND ".join(filters), values)
                count, effective, example = cur.fetchone()
                result["provisions"].append({"provision_id": p["provision_id"], "law_number": p["law_number"], "article": p["article"],
                                             "clause": p.get("clause"), "point": p.get("point"), "granular_path_chunks": count,
                                             "effective_path_chunks": effective, "example_path": example,
                                             "version_text_verified": False if p["provision_id"].startswith("N145-") else None})
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='legal_embeddings' ORDER BY ordinal_position")
            result["legal_embeddings_columns"] = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT * FROM legal_path_relations LIMIT 20")
            names = [d[0] for d in cur.description]
            result["path_relation_samples"] = [dict(zip(names, row)) for row in cur.fetchall()]
            cur.execute("SELECT count(*) FROM legal_path_relations")
            result["path_relation_count"] = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM legal_embeddings WHERE doc_id=ANY(%s) AND (chunk_text ILIKE %s OR chunk_text ILIKE %s OR chunk_text ILIKE %s)", (ids, '%placeholder%', '%chưa xác minh%', '%unverified%'))
            result["placeholder_marker_count_in_requested_documents"] = cur.fetchone()[0]
        conn.rollback()
        driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
        try:
            with driver.session() as session:
                result["graph_counts"] = [dict(row) for row in session.run("MATCH ()-[r]->() RETURN type(r) AS relationship_type,count(*) AS count")]
                for edge in edges:
                    records = session.run("MATCH (a:Document)-[r]->(b:Document) WHERE a.doc_id IN $a AND b.doc_id IN $b RETURN a.doc_id AS source_doc_id,b.doc_id AS target_doc_id,type(r) AS type,properties(r) AS properties", a=docmap.get(norm_law(edge["source_law_id"]), []), b=docmap.get(norm_law(edge["target_law_id"]), []))
                    result["graph_coverage"].append({"benchmark_edge_id": edge["edge_id"], "benchmark_type": edge["type"],
                                                      "source_law": edge["source_law_id"], "target_law": edge["target_law_id"],
                                                      "observed_directed_document_edges": [dict(r) for r in records],
                                                      "exact_scope_verified": False})
                    reverse = session.run("MATCH (a:Document)-[r]->(b:Document) WHERE a.doc_id IN $a AND b.doc_id IN $b RETURN a.doc_id AS source_doc_id,b.doc_id AS target_doc_id,type(r) AS type,properties(r) AS properties", a=docmap.get(norm_law(edge["target_law_id"]), []), b=docmap.get(norm_law(edge["source_law_id"]), []))
                    result["graph_coverage"][-1]["observed_reverse_document_edges"] = [dict(r) for r in reverse]
        finally:
            driver.close()
    finally:
        conn.close()
    return result


def render_coverage(audit, coverage):
    lines = ["# CORPUS COVERAGE REPORT — Existing Corpus Baseline", "", f"Snapshot: {coverage.get('snapshot_at', now())}", "",
             "Corpus được sao chép vật lý từ hai volume đang dừng; inference chỉ chạy trên bản sao. Không bổ sung corpus luật benchmark.", "",
             f"- Metadata văn bản: {coverage.get('document_metadata_rows')}; văn bản có chunk: {coverage.get('documents_with_chunks')}.",
             f"- Chunk: {coverage.get('chunk_count')}; có embedding: {coverage.get('embedded_chunk_count')}; is_effective=true: {coverage.get('effective_chunk_count')}.",
             "- Metadata văn bản có thể là stub do ingest quan hệ; chỉ số có chunk được báo cáo riêng.", "",
             "| Số hiệu yêu cầu | Metadata khớp | Chunk | Chunk effective |", "|---|---:|---:|---:|"]
    for law in coverage.get("requested_laws", []):
        docs = [d for d in coverage["documents"] if norm_law(d["doc_num"]) == norm_law(law)]
        lines.append(f"| {law} | {len(docs)} | {sum(d['chunks'] for d in docs)} | {sum(d['effective_chunks'] for d in docs)} |")
    lines += ["", "## Điều / Khoản / Điểm", "", "Đếm path đúng cấp hoặc hậu duệ; đây là kiểm tra cấu trúc, chưa chứng minh nội dung đúng phiên bản.", "",
              "| Provision | Chunk có path phù hợp | Effective | Ví dụ path |", "|---|---:|---:|---|"]
    for p in coverage.get("provisions", []):
        lines.append(f"| {p['provision_id']} | {p['granular_path_chunks']} | {p['effective_path_chunks']} | {p['example_path'] or '—'} |")
    lines += ["", "## Cờ hiệu lực ảnh hưởng baseline", "", "BLLĐ 45/2019, NĐ145/2020 và Luật ATVSLĐ 84/2015 trong snapshot có status_flag=4 nhưng 0 chunk is_effective=true. PgLegalVectorSearch lọc c.is_effective trước graph expansion. Luật BHXH 41/2024 có status_flag=2/eff_to=2026-01-01 trong snapshot, khác status nháp của benchmark; cần thẩm định nguồn chính thức để quyết định bên nào thiếu cập nhật. Baseline không sửa các cờ này.",
              "", "## Quan hệ và phiên bản", "", "| Edge benchmark | Cạnh document đúng hướng | Cạnh hướng ngược | Scope khoản đã xác minh |", "|---|---:|---:|---|" ]
    for edge in coverage.get('graph_coverage', []):
        lines.append(f"| {edge['benchmark_edge_id']} | {len(edge['observed_directed_document_edges'])} | {len(edge.get('observed_reverse_document_edges', []))} | Không |")
    lines += ["", f"- legal_path_relations: {coverage.get('path_relation_count')} hàng.",
              "- Cạnh document-level quan sát được được lưu trong corpus_coverage.json; có cạnh giữa hai văn bản không chứng minh đúng phạm vi sửa đổi khoản/điểm, hoặc chứng minh pipeline đã sử dụng cạnh.",
              "- Schema embedding không có version_id/effective interval riêng cho mỗi snapshot của cùng path. Unique path có thể ngăn lưu nhiều snapshot cùng định danh nếu không có root riêng.",
              f"- Dấu placeholder/unverified trong các văn bản yêu cầu: {coverage.get('placeholder_marker_count_in_requested_documents')}. Không có dấu marker không đồng nghĩa nội dung đã được thẩm định.", "",
              "## Chất lượng ground truth", "", "34/34 case là synthetic draft, chưa thẩm định pháp lý độc lập. Các metric tự động là so khớp với nhãn nháp.",
              f"LEGAL_DOCUMENTS_STATUS có {audit['document_status_count']} văn bản, trong khi LEGAL_PROVISIONS tham chiếu {audit['unique_laws_in_provisions']} số hiệu. Các số hiệu thiếu trong status manifest: {', '.join(audit['statute_status_manifest_omissions']) or 'không'}.",
              f"{len(audit['unverified_version_rows'])} version rows đều thiếu toàn văn đã xác minh; TEMP-010/011/012/013 cần kiểm tra chuyên gia. Chưa map đầy đủ sửa đổi NĐ145 sau 2024.",
              "", "Controlled Fixture Evaluation không chạy vì chưa có nội dung luật fixture đã kiểm chứng. Các DOCX là đầu vào hợp đồng synthetic; nạp DOCX vào bản sao không bổ sung căn cứ luật.", ""]
    return "\n".join(lines)


def main():
    out = BASELINE_RUN
    audit = audit_benchmark()
    write_json(out / "benchmark_validation.json", audit)
    try:
        coverage = inspect_corpus()
        write_json(out / "corpus_coverage.json", coverage)
        (out / "CORPUS_COVERAGE_REPORT.md").write_text(render_coverage(audit, coverage), encoding="utf-8")
        print(json.dumps({"schema_valid": audit["schema_valid"], "metadata_documents": coverage["document_metadata_rows"],
                          "documents_with_chunks": coverage["documents_with_chunks"], "chunks": coverage["chunk_count"]}))
    except Exception as exc:
        write_json(out / "corpus_coverage_error.json", error_info(exc))
        raise


if __name__ == "__main__":
    main()

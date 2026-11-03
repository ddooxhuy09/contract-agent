"""Read-only audit: can provision-level dates decide which status-4 text is still in force?

Status 4 ("hết hiệu lực một phần") is set on whole documents and on the hierarchy nodes
below them, and `legal_embeddings.is_effective` is false for all of them (the trigger only
accepts status 1/5). A date-aware retrieval filter is only safe if the nodes carry a usable
`eff_from`/`eff_to` window or provision-level amendment relations. This script measures
that and writes STATUS4_AUDIT.{json,md}; it never writes to the database.

    python -m scripts.audit_status4_provisions --output-dir evaluation_results
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DOC_NUMS = ("145/2020/NĐ-CP", "45/2019/QH14", "45/2019/NĐ-CP", "84/2015/QH13")
LEVELS = ("legal_articles", "legal_clauses", "legal_points")
# A date filter needs both ends of the window to say anything about expiry.
MIN_EFF_TO_SHARE = 0.5


def audit(database_url: str, doc_nums: tuple[str, ...]) -> dict:
    import psycopg2

    conn = psycopg2.connect(database_url, connect_timeout=10)
    result: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "documents": []}
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='120s'")
            cur.execute("SELECT status_flag, count(*) FROM legal_documents GROUP BY 1 ORDER BY 1")
            result["document_status_counts"] = {str(k): v for k, v in cur.fetchall()}
            cur.execute("SELECT ref_type, count(*) FROM legal_path_relations GROUP BY 1 ORDER BY 2 DESC")
            result["provision_relation_counts"] = {k: v for k, v in cur.fetchall()}
            cur.execute(
                "SELECT doc_id, doc_num, status_flag, eff_from, eff_to FROM legal_documents "
                "WHERE doc_num = ANY(%s) ORDER BY doc_num",
                (list(doc_nums),),
            )
            for doc_id, doc_num, status, eff_from, eff_to in cur.fetchall():
                doc = {
                    "doc_id": doc_id,
                    "doc_num": doc_num,
                    "status_flag": status,
                    "eff_from": str(eff_from) if eff_from else None,
                    "eff_to": str(eff_to) if eff_to else None,
                    "levels": {},
                }
                for table in LEVELS:
                    cur.execute(
                        f"SELECT status_flag, count(*), count(eff_from), count(eff_to) "
                        f"FROM {table} WHERE doc_id = %s GROUP BY 1 ORDER BY 1",
                        (doc_id,),
                    )
                    doc["levels"][table] = [
                        {"status_flag": s, "nodes": n, "with_eff_from": f, "with_eff_to": t}
                        for s, n, f, t in cur.fetchall()
                    ]
                cur.execute(
                    "SELECT is_effective, count(*) FROM legal_embeddings WHERE doc_id = %s GROUP BY 1",
                    (doc_id,),
                )
                doc["chunks_by_is_effective"] = {str(k): v for k, v in cur.fetchall()}
                result["documents"].append(doc)
        conn.rollback()
    finally:
        conn.close()
    result["verdict"] = verdict(result)
    return result


def verdict(result: dict) -> dict:
    """Date-aware filtering is justified only if status-4 nodes have an expiry date."""
    nodes = with_to = 0
    for doc in result["documents"]:
        if doc["status_flag"] != 4:
            continue
        for rows in doc["levels"].values():
            for row in rows:
                if row["status_flag"] == 4:
                    nodes += row["nodes"]
                    with_to += row["with_eff_to"]
    share = with_to / nodes if nodes else 0.0
    relations = sum(result["provision_relation_counts"].values())
    ok = share >= MIN_EFF_TO_SHARE
    return {
        "status4_nodes": nodes,
        "status4_nodes_with_eff_to": with_to,
        "eff_to_share": round(share, 4),
        "provision_relation_rows": relations,
        "date_aware_filter_supported": ok,
        "reason": (
            "status-4 nodes carry an expiry date"
            if ok
            else "status-4 nodes have eff_from only (no eff_to) and the corpus has almost no "
            "provision-level relations, so a date window cannot tell which provisions expired; "
            "enabling it would admit text whose status is unknown."
        ),
    }


def render_markdown(result: dict) -> str:
    v = result["verdict"]
    lines = [
        "# Status-4 provision audit",
        "",
        f"Generated {result['generated_at']} from the isolated corpus clone (read-only).",
        "",
        "## Verdict",
        "",
        f"- Status-4 hierarchy nodes in audited documents: **{v['status4_nodes']}**; with `eff_to`: "
        f"**{v['status4_nodes_with_eff_to']}** ({v['eff_to_share']:.1%}).",
        f"- Provision-level relation rows in the whole corpus (`legal_path_relations`): "
        f"**{v['provision_relation_rows']}** {result['provision_relation_counts']}.",
        f"- Date-aware status-4 filter supported by the data: **{v['date_aware_filter_supported']}**.",
        f"- {v['reason']}",
        "",
        "## Per document",
        "",
        "| Document | doc status | level | node status | nodes | with eff_from | with eff_to |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for doc in result["documents"]:
        for table, rows in doc["levels"].items():
            for row in rows:
                lines.append(
                    f"| {doc['doc_num']} | {doc['status_flag']} | {table.removeprefix('legal_')} | "
                    f"{row['status_flag']} | {row['nodes']} | {row['with_eff_from']} | {row['with_eff_to']} |"
                )
    lines += ["", "## Chunks by `is_effective`", "", "| Document | is_effective=true | false |", "|---|---:|---:|"]
    for doc in result["documents"]:
        c = doc["chunks_by_is_effective"]
        lines.append(f"| {doc['doc_num']} | {c.get('True', 0)} | {c.get('False', 0)} |")
    lines += [
        "",
        "Nothing here edits flags or the trigger. Provision-level status needs a reviewed source "
        "(official consolidated text or amendment mapping) before status-4 chunks can be retrieved.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", default="evaluation_results")
    parser.add_argument("--doc-num", action="append", help="repeatable; defaults to the benchmark laws")
    args = parser.parse_args()

    from app.core.settings import get_settings

    result = audit(get_settings().database_url, tuple(args.doc_num or DEFAULT_DOC_NUMS))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "STATUS4_AUDIT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out / "STATUS4_AUDIT.md").write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result["verdict"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

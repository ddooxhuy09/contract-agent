from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from app.core.logging import logger
from app.core.settings import get_settings

# luoc_do code → Neo4j relationship type
RELATION_TYPE_MAP = {
    "van_ban_bi_bai_bo": "REPEALS",
    "thay_the": "SUPERSEDES",
    "tam_ngung_hieu_luc": "SUSPENDS",
    "dinh_chi_thi_hanh": "SUSPENDS",
    "sua_doi_bo_sung": "AMENDS",
    "bo_sung": "ADDS",
    "can_cu_ban_hanh": "BASED_ON",
    "quy_dinh_chi_tiet_huong_dan_thi_hanh": "DETAILS",
    "huong_dan_ap_dung": "GUIDES",
    "dinh_chinh": "CORRECTS",
    "hop_nhat": "CONSOLIDATES",
    "dan_chieu": "CITES",
    "giai_thich": "EXPLAINS",
    "cong_bo": "ANNOUNCES",
    "ban_dich": "TRANSLATES",
    "REPEALS": "REPEALS",
    "SUPERSEDES": "SUPERSEDES",
    "SUSPENDS": "SUSPENDS",
    "AMENDS": "AMENDS",
    "ADDS": "ADDS",
    "BASED_ON": "BASED_ON",
    "DETAILS": "DETAILS",
    "GUIDES": "GUIDES",
    "CORRECTS": "CORRECTS",
    "CONSOLIDATES": "CONSOLIDATES",
    "CITES": "CITES",
    "EXPLAINS": "EXPLAINS",
    "ANNOUNCES": "ANNOUNCES",
    "TRANSLATES": "TRANSLATES",
}


class Neo4jGraphRepository:
    def __init__(self):
        settings = get_settings()
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def ensure_schema(self) -> None:
        path = Path(get_settings().schema_cypher_path)
        if not path.is_file():
            path = Path(__file__).resolve().parents[3] / "schema.cypher"
        text = path.read_text(encoding="utf-8")
        statements = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            statements.append(stripped)
        # Group into CREATE CONSTRAINT / CREATE INDEX statements
        buffer: list[str] = []
        executable: list[str] = []
        for stmt_line in statements:
            buffer.append(stmt_line)
            joined = " ".join(buffer)
            if joined.rstrip().endswith(";"):
                executable.append(joined.rstrip()[:-1])
                buffer = []
        try:
            with self._driver.session() as session:
                for cypher in executable:
                    if cypher.upper().startswith("CREATE CONSTRAINT") or cypher.upper().startswith("CREATE INDEX"):
                        session.run(cypher)
            logger.info("Applied Neo4j schema constraints/indexes from %s", path)
        except Exception as e:
            logger.warning("Neo4j schema apply skipped/failed: %s", e)

    def upsert_document_tree(
        self,
        doc_id: str,
        doc_num: str,
        doc_type: str,
        nodes: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
    ) -> None:
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MERGE (d:Document {doc_id: $doc_id})
                    SET d.doc_num = $doc_num, d.doc_type = $doc_type
                    """,
                    doc_id=doc_id,
                    doc_num=doc_num,
                    doc_type=doc_type,
                )
                for node in nodes:
                    session.run(
                        """
                        MERGE (n:Node {doc_id: $doc_id, path: $path})
                        SET n.level = $level, n.label = $label
                        WITH n
                        MATCH (d:Document {doc_id: $doc_id})
                        MERGE (d)-[:HAS_NODE]->(n)
                        """,
                        doc_id=doc_id,
                        path=node["path"],
                        level=node.get("level", "Point"),
                        label=node.get("label"),
                    )
                    parent = node.get("parent_path")
                    if parent:
                        session.run(
                            """
                            MATCH (p:Node {doc_id: $doc_id, path: $parent})
                            MATCH (c:Node {doc_id: $doc_id, path: $path})
                            MERGE (p)-[:PARENT_OF]->(c)
                            """,
                            doc_id=doc_id,
                            parent=parent,
                            path=node["path"],
                        )
                for ch in chunks:
                    path = ch.get("path")
                    if not path:
                        continue
                    session.run(
                        """
                        MERGE (c:Chunk {path: $path})
                        SET c.doc_id = $doc_id, c.chunk_type = $chunk_type
                        WITH c
                        MATCH (d:Document {doc_id: $doc_id})
                        MERGE (c)-[:OF_DOC]->(d)
                        WITH c
                        MATCH (n:Node {doc_id: $doc_id, path: $path})
                        MERGE (c)-[:OF_NODE]->(n)
                        """,
                        path=path,
                        doc_id=doc_id,
                        chunk_type=ch.get("chunk_type", "body"),
                    )
        except Exception as e:
            logger.warning("Neo4j upsert_document_tree failed: %s", e)

    def upsert_doc_relations(self, relations: list[dict[str, str]]) -> None:
        if not relations:
            return
        try:
            with self._driver.session() as session:
                for rel in relations:
                    rel_type = RELATION_TYPE_MAP.get(rel["relation_type"], "CITES")
                    session.run(
                        f"""
                        MERGE (a:Document {{doc_id: $from_id}})
                        MERGE (b:Document {{doc_id: $to_id}})
                        MERGE (a)-[r:{rel_type}]->(b)
                        SET r.source_code = $source
                        """,
                        from_id=rel["from_doc_id"],
                        to_id=rel["to_doc_id"],
                        source=rel["relation_type"],
                    )
        except Exception as e:
            logger.warning("Neo4j upsert_doc_relations failed: %s", e)

    def upsert_chunk_relations(self, relations: list[dict[str, str]]) -> None:
        if not relations:
            return
        try:
            with self._driver.session() as session:
                for rel in relations:
                    session.run(
                        """
                        MERGE (a:Chunk {path: $from_path})
                        MERGE (b:Chunk {path: $to_path})
                        MERGE (a)-[r:REFERS_TO]->(b)
                        SET r.relation_type = $rtype
                        """,
                        from_path=rel.get("from_path"),
                        to_path=rel.get("to_path"),
                        rtype=rel["relation_type"],
                    )
        except Exception as e:
            logger.warning("Neo4j upsert_chunk_relations failed: %s", e)

    def expand(self, chunk_refs: list[str], limit: int = 80) -> dict[str, Any]:
        """Expand seeds by ltree path (param name kept for Protocol compat)."""
        empty = {
            "seeds": [],
            "sibling_paths": [],
            "ancestor_paths": [],
            "parent_clause_paths": [],
            "related_docs": [],
            "repealed_by_docs": [],
        }
        if not chunk_refs:
            return empty
        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (c:Chunk) WHERE c.path IN $refs
                    OPTIONAL MATCH (c)-[:OF_NODE]->(leaf:Node)
                    OPTIONAL MATCH (anc:Node)-[:PARENT_OF*1..4]->(leaf)
                    OPTIONAL MATCH (leaf)<-[:PARENT_OF]-(clause:Node)
                      WHERE clause.level = 'Clause'
                    OPTIONAL MATCH (clause)-[:PARENT_OF]->(sib:Node)
                      WHERE sib.path <> leaf.path
                    OPTIONAL MATCH (c)-[:OF_DOC]->(d:Document)
                    OPTIONAL MATCH (d)-[:BASED_ON|CITES|AMENDS|DETAILS|GUIDES*1..2]-(rel:Document)
                    OPTIONAL MATCH (other:Document)-[:REPEALS|SUPERSEDES]->(d)
                    RETURN collect(DISTINCT c.path) AS seeds,
                           collect(DISTINCT sib.path) AS siblings,
                           collect(DISTINCT anc.path) AS ancestors,
                           collect(DISTINCT clause.path) AS parent_clauses,
                           collect(DISTINCT rel.doc_id) AS related_docs,
                           collect(DISTINCT other.doc_id) AS repealed_by
                    LIMIT $limit
                    """,
                    refs=chunk_refs,
                    limit=limit,
                )
                record = result.single()
                if not record:
                    return {**empty, "seeds": list(chunk_refs)}
                return {
                    "seeds": [x for x in (record["seeds"] or []) if x],
                    "sibling_paths": [x for x in (record["siblings"] or []) if x][:24],
                    "ancestor_paths": [x for x in (record["ancestors"] or []) if x][:16],
                    "parent_clause_paths": [x for x in (record["parent_clauses"] or []) if x],
                    "related_docs": [x for x in (record["related_docs"] or []) if x][:8],
                    "repealed_by_docs": [x for x in (record["repealed_by"] or []) if x][:8],
                }
        except Exception as e:
            logger.warning("Neo4j expand failed (continuing without graph): %s", e)
            return {**empty, "seeds": list(chunk_refs)}

    def sync_doc_status(self, doc_id: str, status_flag: int) -> None:
        """Mirror status_flag from PG → Neo4j Document node."""
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    MERGE (d:Document {doc_id: $doc_id})
                    SET d.status_flag = $status_flag, d.synced_at = timestamp()
                    """,
                    doc_id=doc_id,
                    status_flag=status_flag,
                )
        except Exception as e:
            logger.warning("Neo4j sync_doc_status(%s, %s) failed: %s", doc_id, status_flag, e)

    def bulk_sync_doc_status(self, docs: list[dict]) -> int:
        """Mirror status_flag for many docs at once from PG → Neo4j."""
        if not docs:
            return 0
        try:
            with self._driver.session() as session:
                session.run(
                    """
                    UNWIND $docs AS row
                    MERGE (d:Document {doc_id: row.doc_id})
                    SET d.status_flag = row.status_flag, d.synced_at = timestamp()
                    """,
                    docs=[{"doc_id": d["doc_id"], "status_flag": d["status_flag"]} for d in docs],
                )
            return len(docs)
        except Exception as e:
            logger.warning("Neo4j bulk_sync_doc_status failed: %s", e)
            return 0

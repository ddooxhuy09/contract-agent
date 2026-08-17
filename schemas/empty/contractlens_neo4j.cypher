// =============================================================================
// ContractLens — Neo4j schema (GraphRAG) — EMPTY bootstrap
// File: schemas/empty/contractlens_neo4j.cypher  (mirror of repo schema.cypher)
//
// Postgres SoT (text + embedding): contractlens_postgres.sql
// Neo4j: cây muc_luc + Chunk keyed by path — KHÔNG lưu chunk_text / embedding
//
// path ví dụ (ltree text = sanitize(doc_id).structural):
//   body thường : 45_2019_QH14.C1.M1.D1.K1.a
//   đặc biệt    : 45_2019_QH14.PREAMBLE | …EFF | …SIGN | …PL0.N1
//
// Chạy trên Neo4j 5+: chỉ cần các CREATE CONSTRAINT / CREATE INDEX bên dưới.
// =============================================================================

// ── Constraints & indexes ───────────────────────────────────────────────────

CREATE CONSTRAINT document_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;

CREATE CONSTRAINT node_doc_path IF NOT EXISTS
FOR (n:Node) REQUIRE (n.doc_id, n.path) IS UNIQUE;

CREATE CONSTRAINT chunk_path IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.path IS UNIQUE;

CREATE INDEX document_num IF NOT EXISTS
FOR (d:Document) ON (d.doc_num);

CREATE INDEX node_doc IF NOT EXISTS
FOR (n:Node) ON (n.doc_id);

CREATE INDEX node_level IF NOT EXISTS
FOR (n:Node) ON (n.level);

CREATE INDEX chunk_doc IF NOT EXISTS
FOR (c:Chunk) ON (c.doc_id);

CREATE INDEX chunk_type IF NOT EXISTS
FOR (c:Chunk) ON (c.chunk_type);

// ── Node shapes (chỉ id + nhãn nhẹ — KHÔNG content / embedding) ─────────────
//
// (:Document {
//   doc_id:      String,   // = legal_documents.doc_id
//   doc_num:     String,   // "168/2024/NĐ-CP"
//   doc_type:    String,
//   status_flag: Integer   // đồng bộ PG để filter nhanh (tuỳ chọn)
// })
//
// (:Node {                      // một bậc trong cây path (ltree text)
//   doc_id: String,
//   path:   String,            // "…C1" | "…C1.M1.D1" | "…K1.a"
//   level:  String,            // Chapter|Section|Article|Clause|Point|Appendix|Group|Meta
//   label:  String             // "Điều 13", "Khoản 2", "Điểm a" …
// })
//   Meta = PREAMBLE / EFF / SIGN (không nằm cây Chương–Điểm)
//
// (:Chunk {
//   path:       String,        // = legal_embeddings.path (lá / đơn vị cắt)
//   doc_id:     String,
//   chunk_type: String         // body|preamble|effectivity|appendix|signature|other
// })

// ── Cây cấu trúc (từ muc_luc / parse path) ──────────────────────────────────
//
// (d:Document)-[:HAS_NODE]->(n:Node)
// (parent:Node)-[:PARENT_OF]->(child:Node)     // C1 → M1 → D1 → K1 → a
// (prev:Node)-[:NEXT]->(next:Node)            // anh em cùng cha
//
// (c:Chunk)-[:OF_DOC]->(d:Document)
// (c:Chunk)-[:OF_NODE]->(leaf:Node)           // leaf.path == chunk.path

// Ingest cây (idempotent) — ví dụ:
// MERGE (d:Document {doc_id: $doc_id})
// ON CREATE SET d.doc_num = $doc_num, d.doc_type = $doc_type
// WITH d
// UNWIND $nodes AS row   // [{path, level, label, parent_path}, …]
// MERGE (n:Node {doc_id: $doc_id, path: row.path})
// SET n.level = row.level, n.label = row.label
// MERGE (d)-[:HAS_NODE]->(n)
// WITH d, n, row
// CALL {
//   WITH d, n, row
//   WITH d, n, row WHERE row.parent_path IS NOT NULL
//   MATCH (p:Node {doc_id: d.doc_id, path: row.parent_path})
//   MERGE (p)-[:PARENT_OF]->(n)
// }
// MERGE (c:Chunk {path: $path})
// SET c.doc_id = $doc_id, c.chunk_type = $chunk_type
// MERGE (c)-[:OF_DOC]->(d)
// MERGE (c)-[:OF_NODE]->(n);

// ── Quan hệ văn bản = mirror legal_document_relations ────────────────────────
// Map luoc_do.code → relationship type:
//   van_ban_bi_bai_bo                    → REPEALS
//   thay_the                             → SUPERSEDES
//   tam_ngung_hieu_luc | dinh_chi_thi_hanh → SUSPENDS
//   sua_doi_bo_sung                      → AMENDS
//   bo_sung                              → ADDS
//   can_cu_ban_hanh                      → BASED_ON
//   quy_dinh_chi_tiet_huong_dan_thi_hanh → DETAILS
//   huong_dan_ap_dung                    → GUIDES
//   dinh_chinh                           → CORRECTS
//   hop_nhat                             → CONSOLIDATES
//   dan_chieu                            → CITES
//   giai_thich                           → EXPLAINS
//   cong_bo                              → ANNOUNCES
//   ban_dich                             → TRANSLATES
//
// MERGE (a:Document {doc_id: $from_doc_id})
// MERGE (b:Document {doc_id: $to_doc_id})
// MERGE (a)-[r:AMENDS]->(b)
// SET r.source_code = $relation_type;

// ── Quan hệ chunk = mirror legal_path_relations ──────────────────────────────
// MERGE (a:Chunk {path: $from_path})
// MERGE (b:Chunk {path: $to_path})
// MERGE (a)-[r:REFERS_TO]->(b)
// SET r.relation_type = $rtype;

// ── GraphRAG expand (app hydrate text từ Postgres theo path) ────────────────
// MATCH (c:Chunk) WHERE c.path IN $refs
// OPTIONAL MATCH (c)-[:OF_NODE]->(leaf:Node)
// OPTIONAL MATCH (anc:Node)-[:PARENT_OF*1..4]->(leaf)
// OPTIONAL MATCH (leaf)<-[:PARENT_OF]-(clause:Node) WHERE clause.level = 'Clause'
// OPTIONAL MATCH (clause)-[:PARENT_OF]->(sib:Node) WHERE sib.path <> leaf.path
// OPTIONAL MATCH (c)-[:OF_DOC]->(d:Document)
// OPTIONAL MATCH (d)-[:BASED_ON|CITES|AMENDS|DETAILS|GUIDES*1..2]-(rel:Document)
// OPTIONAL MATCH (other:Document)-[:REPEALS|SUPERSEDES]->(d)
// RETURN collect(DISTINCT c.path) AS seeds,
//        collect(DISTINCT sib.path) AS siblings,
//        collect(DISTINCT anc.path) AS ancestors,
//        collect(DISTINCT clause.path) AS parent_clauses,
//        collect(DISTINCT rel.doc_id) AS related_docs,
//        collect(DISTINCT other.doc_id) AS repealed_by
// LIMIT 80;

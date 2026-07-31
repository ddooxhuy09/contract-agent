-- ContractLens — Postgres = nội dung + embed + cạnh id↔id
-- Neo4j = tách cây Chương/Mục/Điều/Khoản/Điểm + chiếu cùng chunk_ref/doc_id
--
-- chunk_ref: C1.M1.D1.K1.a | C1.M1.D1.K1.b-c | PL0.N1
-- PG: mỗi chunk chỉ chunk_ref + chunk_text (+ embedding). Ghép ngữ cảnh làm lúc ingest.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ═══════════════════════════════════════════════════════════════════════════
-- Auth
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE users IS 'Tài khoản local; gắn uploaded_contracts.user_id.';

-- ═══════════════════════════════════════════════════════════════════════════
-- Hợp đồng
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS uploaded_contracts (
    contract_id     TEXT PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    storage_key     TEXT NOT NULL,
    full_text       TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    message         TEXT,
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    analysis        JSONB,
    risks           JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE uploaded_contracts IS
  'Hợp đồng user. analysis/risks = cache mở lại không gọi LLM.';

CREATE INDEX IF NOT EXISTS idx_uc_user_created
    ON uploaded_contracts (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS contract_chunks (
    id                 BIGSERIAL PRIMARY KEY,
    contract_id        TEXT NOT NULL
                       REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    chunk_index        INTEGER NOT NULL,
    clause_number      TEXT NOT NULL,
    content            TEXT NOT NULL,
    embedding          vector(768),                -- vector cosine / HNSW (thay FAISS)
    UNIQUE (contract_id, chunk_index)
);

ALTER TABLE contract_chunks ALTER COLUMN embedding SET STORAGE PLAIN;

CREATE INDEX IF NOT EXISTS idx_cc_contract ON contract_chunks (contract_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_cc_hnsw ON contract_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- Luật — metadata thuoc_tinh
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS legal_documents (
    doc_id          TEXT PRIMARY KEY,
    doc_num         TEXT NOT NULL,
    doc_num_norm    TEXT,
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL,
    majors          TEXT[] DEFAULT '{}',
    fields          TEXT[] DEFAULT '{}',
    issue_date      DATE,
    eff_from        DATE,                          -- ngày HL khai báo (crawler)
    eff_to          DATE,
    eff_status      TEXT,
    eff_status_code TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,   -- 0/? 1 còn 2 bãi 3 chưa tới 4 sửa một phần
    agency          TEXT,
    signers         JSONB DEFAULT '[]',
    source_url      TEXT,
    full_text       TEXT,                          -- tuỳ chọn; file thô vẫn có thể ở MinIO theo doc_id
    crawled_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_documents IS
  'Metadata thuoc_tinh. Quan hệ doc = legal_document_relations.';
COMMENT ON COLUMN legal_documents.eff_from IS
  'Ngày khai báo — khác status_flag (đã tính thêm quan hệ bãi/thay).';
COMMENT ON COLUMN legal_documents.status_flag IS
  'Lọc RAG: từ eff_* + legal_document_relations.';

CREATE INDEX IF NOT EXISTS idx_ld_doc_type ON legal_documents (doc_type);
CREATE INDEX IF NOT EXISTS idx_ld_status ON legal_documents (status_flag);
CREATE INDEX IF NOT EXISTS idx_ld_doc_num_norm ON legal_documents (doc_num_norm);
CREATE INDEX IF NOT EXISTS idx_ld_issue_date ON legal_documents (issue_date DESC);
CREATE INDEX IF NOT EXISTS idx_ld_doc_num_trgm ON legal_documents USING gin (doc_num gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ld_title_trgm ON legal_documents USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS legal_document_relations (
    id              BIGSERIAL PRIMARY KEY,
    from_doc_id     TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    to_doc_id       TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (from_doc_id, to_doc_id, relation_type)
);

COMMENT ON TABLE legal_document_relations IS
  'doc_id↔doc_id (luoc_do). Neo4j MERGE cùng cặp id.';

CREATE INDEX IF NOT EXISTS idx_ldr_from ON legal_document_relations (from_doc_id);
CREATE INDEX IF NOT EXISTS idx_ldr_to ON legal_document_relations (to_doc_id);
CREATE INDEX IF NOT EXISTS idx_ldr_type ON legal_document_relations (relation_type);

-- ═══════════════════════════════════════════════════════════════════════════
-- Chunks luật — 1 hàng = 1 mảnh đã cắt (+ ngữ cảnh nếu ingest ghép sẵn)
-- chunk_ref  = C1.M1.D1.K1.a | PL0.N1 | PREAMBLE | EFF | SIGN | …
-- chunk_type = body (thường) | preamble | effectivity | appendix | signature | other
--   Không tách article/clause/point — cắt thường luôn đủ 3 trong chunk_text.
-- chunk_text = chuỗi duy nhất embed + FTS + retrieve
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS legal_section_chunks (
    id                  BIGSERIAL PRIMARY KEY,
    chunk_ref           TEXT NOT NULL UNIQUE,      -- path / mã ổn định; map Neo4j
    doc_id              TEXT NOT NULL
                        REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    chunk_type          TEXT NOT NULL DEFAULT 'body'
                        CHECK (chunk_type IN (
                            'body',          -- cắt thường: đã gồm Điều+Khoản+Điểm trong 1 chunk_text
                            'preamble',      -- phần đầu, căn cứ ban hành
                            'effectivity',   -- quy định hiệu lực thi hành
                            'appendix',      -- phụ lục, biểu mẫu
                            'signature',     -- nơi nhận, ký tên, chức danh
                            'other'          -- đặc biệt khác
                        )),
    chunk_text          TEXT NOT NULL,             -- text đã cắt — embed + FTS + trả RAG
    embedding           vector(768),
    is_effective        BOOLEAN NOT NULL DEFAULT TRUE,
    tsv                 tsvector GENERATED ALWAYS AS (
                            to_tsvector('simple', coalesce(chunk_text, ''))
                        ) STORED,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE legal_section_chunks ALTER COLUMN embedding SET STORAGE PLAIN;

COMMENT ON TABLE legal_section_chunks IS
  'Một doc → nhiều chunk. Loại nghiệp vụ = chunk_type; cây path ở Neo4j.';
COMMENT ON COLUMN legal_section_chunks.chunk_type IS
  'Mặc định body (= Điều+Khoản+Điểm đã ghép). Chỉ đổi khi đặc biệt: preamble/effectivity/appendix/signature/other.';
COMMENT ON COLUMN legal_section_chunks.chunk_text IS
  'Chuỗi duy nhất lưu/embed/FTS/trả RAG.';

CREATE INDEX IF NOT EXISTS idx_lsc_doc ON legal_section_chunks (doc_id);
CREATE INDEX IF NOT EXISTS idx_lsc_type ON legal_section_chunks (doc_id, chunk_type);
CREATE INDEX IF NOT EXISTS idx_lsc_tsv ON legal_section_chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_lsc_hnsw ON legal_section_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE is_effective AND embedding IS NOT NULL;

-- Quan hệ chunk↔chunk (cùng/khác doc) — giống dump chunk_amendments
CREATE TABLE IF NOT EXISTS legal_chunk_relations (
    id              BIGSERIAL PRIMARY KEY,
    from_chunk_ref  TEXT NOT NULL
                    REFERENCES legal_section_chunks(chunk_ref) ON DELETE CASCADE,
    to_chunk_ref    TEXT NOT NULL
                    REFERENCES legal_section_chunks(chunk_ref) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,                 -- amended | replaces | refers_to | …
    note            TEXT,
    effective_date  DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (from_chunk_ref, to_chunk_ref, relation_type)
);

COMMENT ON TABLE legal_chunk_relations IS
  'Cạnh chunk_ref↔chunk_ref. Neo4j chiếu cùng id.';

CREATE INDEX IF NOT EXISTS idx_lcr_from ON legal_chunk_relations (from_chunk_ref);
CREATE INDEX IF NOT EXISTS idx_lcr_to ON legal_chunk_relations (to_chunk_ref);
CREATE INDEX IF NOT EXISTS idx_lcr_type ON legal_chunk_relations (relation_type);

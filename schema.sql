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
    embedding          vector(1024),               -- BAAI/bge-m3 cosine / HNSW
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
    embedding           vector(1024),              -- BAAI/bge-m3
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

-- ═══════════════════════════════════════════════════════════════════════════
-- Triggers — tự động cập nhật status_flag & cascade expiry
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_ld_eff_from ON legal_documents (eff_from);
CREATE INDEX IF NOT EXISTS idx_ld_eff_to ON legal_documents (eff_to);

-- Helper: parse ngày về DATE từ các định dạng phổ biến
CREATE OR REPLACE FUNCTION safe_cast_to_date(val text) RETURNS date AS $$
BEGIN
    IF val IS NULL OR val = '' THEN RETURN NULL; END IF;
    IF val ~ '^\d{4}-\d{2}-\d{2}$' THEN RETURN to_date(val, 'YYYY-MM-DD'); END IF;
    IF val ~ '^\d{1,2}/\d{1,2}/\d{4}$' THEN RETURN to_date(val, 'DD/MM/YYYY'); END IF;
    IF val ~ '^\d{4}/\d{1,2}/\d{1,2}$' THEN RETURN to_date(val, 'YYYY/MM/DD'); END IF;
    RETURN NULL;
EXCEPTION WHEN OTHERS THEN RETURN NULL; END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger 1: auto-assign status_flag khi INSERT hoặc UPDATE eff_from
CREATE OR REPLACE FUNCTION trg_legal_documents_status() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    IF NEW.status_flag IS NULL OR NEW.status_flag = 0 THEN
        NEW.status_flag := CASE
            WHEN NEW.eff_from IS NULL THEN 0
            WHEN NEW.eff_from > CURRENT_DATE THEN 3
            ELSE 1
        END;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_docs_biu ON legal_documents;
CREATE TRIGGER trg_docs_biu
    BEFORE INSERT OR UPDATE OF eff_from ON legal_documents
    FOR EACH ROW
    WHEN (NEW.status_flag IS DISTINCT FROM 2)
    EXECUTE FUNCTION trg_legal_documents_status();

-- Trigger 2: cascade expire khi VB mới có hiệu lực (status_flag → 1)
CREATE OR REPLACE FUNCTION trg_cascade_expire_fn() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status_flag = 1 AND OLD.status_flag IS DISTINCT FROM 1 THEN
        -- VB bị thay thế/bãi bỏ → hết hiệu lực hoàn toàn
        UPDATE legal_documents SET status_flag = 2, updated_at = CURRENT_TIMESTAMP
        WHERE doc_id IN (
            SELECT to_doc_id FROM legal_document_relations
            WHERE from_doc_id = NEW.doc_id AND to_doc_id IS NOT NULL
              AND relation_type IN ('van_ban_bi_bai_bo', 'thay_the')
        ) AND status_flag != 2;

        -- VB bị sửa đổi → hết hiệu lực một phần
        UPDATE legal_documents SET status_flag = 4, updated_at = CURRENT_TIMESTAMP
        WHERE doc_id IN (
            SELECT to_doc_id FROM legal_document_relations
            WHERE from_doc_id = NEW.doc_id AND to_doc_id IS NOT NULL
              AND relation_type IN ('sua_doi_bo_sung')
        ) AND status_flag NOT IN (2, 4);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cascade_expire ON legal_documents;
CREATE TRIGGER trg_cascade_expire
    AFTER UPDATE OF status_flag ON legal_documents
    FOR EACH ROW
    WHEN (NEW.status_flag = 1 AND OLD.status_flag IS DISTINCT FROM 1)
    EXECUTE FUNCTION trg_cascade_expire_fn();

-- Maintenance function: refresh tất cả status_flag (chạy định kỳ hoặc sau bulk import)
CREATE OR REPLACE FUNCTION refresh_status_flags() RETURNS TABLE(doc_id TEXT, old_flag INT, new_flag INT) AS $$
DECLARE
    _updated INT := 0;
BEGIN
    -- 1. Doc có eff_to <= hôm nay → status_flag = 2
    UPDATE legal_documents
    SET    status_flag = 2, updated_at = CURRENT_TIMESTAMP
    WHERE  status_flag != 2 AND eff_to IS NOT NULL AND eff_to <= CURRENT_DATE;
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 1 (expiry): updated % row(s)', _updated;

    -- 2. Doc có eff_from > hôm nay → 3 (sắp có hiệu lực)
    UPDATE legal_documents
    SET    status_flag = 3, updated_at = CURRENT_TIMESTAMP
    WHERE  status_flag NOT IN (2, 4) AND eff_from IS NOT NULL AND eff_from > CURRENT_DATE;
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 2 (not yet effective): updated % row(s)', _updated;

    -- 3. Doc còn lại có eff_from → 1 (còn hiệu lực)
    UPDATE legal_documents
    SET    status_flag = 1, updated_at = CURRENT_TIMESTAMP
    WHERE  status_flag NOT IN (2, 3, 4) AND eff_from IS NOT NULL AND eff_from <= CURRENT_DATE;
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 3 (effective): updated % row(s)', _updated;

    -- 4. Doc bị thay thế/bãi bỏ mà status chưa là 2 → set 2
    UPDATE legal_documents ld
    SET    status_flag = 2, updated_at = CURRENT_TIMESTAMP
    FROM   legal_document_relations ldr
           JOIN legal_documents new_doc ON new_doc.doc_id = ldr.from_doc_id
    WHERE  ld.doc_id = ldr.to_doc_id
      AND  ldr.relation_type IN ('van_ban_bi_bai_bo', 'thay_the')
      AND  new_doc.status_flag = 1
      AND  ld.status_flag NOT IN (2, 4);
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 4 (cascade expired): updated % row(s)', _updated;

    -- 5. Doc bị sửa đổi mà status chưa là 4 → set 4
    UPDATE legal_documents ld
    SET    status_flag = 4, updated_at = CURRENT_TIMESTAMP
    FROM   legal_document_relations ldr
           JOIN legal_documents new_doc ON new_doc.doc_id = ldr.from_doc_id
    WHERE  ld.doc_id = ldr.to_doc_id
      AND  ldr.relation_type = 'sua_doi_bo_sung'
      AND  new_doc.status_flag = 1
      AND  ld.status_flag NOT IN (2, 4);
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 5 (cascade partial): updated % row(s)', _updated;

    RETURN QUERY
        SELECT ld.doc_id, CAST(0 AS INT), CAST(ld.status_flag AS INT)
        FROM legal_documents ld
        WHERE ld.status_flag != 0;
END; $$ LANGUAGE plpgsql;

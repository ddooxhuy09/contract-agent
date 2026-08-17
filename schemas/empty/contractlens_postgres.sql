-- =============================================================================
-- ContractLens — Postgres schema v2.1 (EMPTY bootstrap)
-- Mirror: schemas/empty/contractlens_postgres.sql  |  Neo4j: schema.cypher
-- Hierarchy = full FK chain doc→part→…; only parts.doc_id (+ embeddings.doc_id)
-- Missing levels stored as title/content='Không có'; RAG ltree stays sparse
-- Chunks+RAG = legal_embeddings (UNIQUE path ltree; chunk_type on embeddings)
-- Path relations = legal_path_relations (ltree dan_chieu)
-- Token identity = path (+ symbol on points); title/content for display/body
-- Embedding dim = vector(1024) — BGE-M3
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- =============================================================================
-- Auth
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE users IS 'Local accounts; linked to uploaded_contracts.user_id.';

-- =============================================================================
-- Contracts
-- =============================================================================

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
  'User contracts. analysis/risks = LLM cache for re-open without calling LLM.';

CREATE INDEX IF NOT EXISTS idx_uc_user_created
    ON uploaded_contracts (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS contract_chunks (
    id                 BIGSERIAL PRIMARY KEY,
    contract_id        TEXT NOT NULL
                       REFERENCES uploaded_contracts(contract_id) ON DELETE CASCADE,
    chunk_index        INTEGER NOT NULL,
    clause_number      TEXT NOT NULL,
    content            TEXT NOT NULL,
    embedding          vector(1024),
    UNIQUE (contract_id, chunk_index)
);

ALTER TABLE contract_chunks ALTER COLUMN embedding SET STORAGE PLAIN;

CREATE INDEX IF NOT EXISTS idx_cc_contract ON contract_chunks (contract_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_cc_hnsw ON contract_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE embedding IS NOT NULL;

-- =============================================================================
-- Legal Documents — metadata (unchanged + path ltree)
-- =============================================================================

CREATE TABLE IF NOT EXISTS legal_documents (
    doc_id          TEXT PRIMARY KEY,
    doc_num         TEXT NOT NULL,
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL,
    majors          TEXT[] DEFAULT '{}',
    fields          TEXT[] DEFAULT '{}',
    issue_date      DATE,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    agency          TEXT,
    signer_name     TEXT,
    signer_title    TEXT,
    source_url      TEXT,
    full_text       TEXT,
    path            ltree,
    crawled_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_documents IS
  'Document metadata. path = sanitized doc_id for root level of hierarchy.';
COMMENT ON COLUMN legal_documents.eff_from IS
  'Declared effective date — different from status_flag (which factors in repeal/replace relations).';
COMMENT ON COLUMN legal_documents.eff_flag IS
  'Detailed effective label (9 values). status_flag = grouped numeric version.';
COMMENT ON COLUMN legal_documents.status_flag IS
  'RAG filter: derived from eff_flag + legal_document_relations (0..5).';

CREATE INDEX IF NOT EXISTS idx_ld_doc_type ON legal_documents (doc_type);
CREATE INDEX IF NOT EXISTS idx_ld_status ON legal_documents (status_flag);
CREATE INDEX IF NOT EXISTS idx_ld_eff_flag ON legal_documents (eff_flag);
CREATE INDEX IF NOT EXISTS idx_ld_issue_date ON legal_documents (issue_date DESC);
CREATE INDEX IF NOT EXISTS idx_ld_eff_from ON legal_documents (eff_from);
CREATE INDEX IF NOT EXISTS idx_ld_eff_to ON legal_documents (eff_to);
CREATE INDEX IF NOT EXISTS idx_ld_doc_num_trgm ON legal_documents USING gin (doc_num gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ld_title_trgm ON legal_documents USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ld_path_gist ON legal_documents USING gist (path);

-- =============================================================================
-- Hierarchy — full FK chain (doc→part→chapter→section→sub_section→article→…)
-- Only legal_parts.doc_id links to documents; children FK parent only.
-- Missing levels: row exists with title/content = 'Không có' (shared scaffolds).
-- ltree path for RAG stays sparse (real structure); scaffold paths use ._P/._C/._M/._TM
-- =============================================================================

-- Effectiveness columns (same vocabulary as legal_documents):
--   eff_from, eff_to, eff_flag, status_flag — SoT for provision-level HL.
-- Parent status_flag=2 cascades to children; partial repeal touches only that node.
-- legal_embeddings.is_effective is a RAG cache synced from leaf hierarchy status.

-- Level 1: Part (Phần) — sole hierarchy table with doc_id
CREATE TABLE IF NOT EXISTS legal_parts (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT 'Không có',
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, path)
);

COMMENT ON TABLE legal_parts IS
  'Phần. Every document has ≥1 row (real or title/content=Không có). Only hierarchy table with doc_id.';

-- Level 2: Chapter (Chương)
CREATE TABLE IF NOT EXISTS legal_chapters (
    id              BIGSERIAL PRIMARY KEY,
    part_id         BIGINT NOT NULL REFERENCES legal_parts(id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT 'Không có',
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL UNIQUE,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_chapters IS 'Chương. part_id NOT NULL; missing → title/content=Không có.';

-- Level 3: Section (Mục)
CREATE TABLE IF NOT EXISTS legal_sections (
    id              BIGSERIAL PRIMARY KEY,
    chapter_id      BIGINT NOT NULL REFERENCES legal_chapters(id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT 'Không có',
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL UNIQUE,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_sections IS 'Mục. chapter_id NOT NULL; missing → title/content=Không có.';

-- Level 4: Sub-section (Tiểu mục)
CREATE TABLE IF NOT EXISTS legal_sub_sections (
    id              BIGSERIAL PRIMARY KEY,
    section_id      BIGINT NOT NULL REFERENCES legal_sections(id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT 'Không có',
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL UNIQUE,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_sub_sections IS 'Tiểu mục. section_id NOT NULL; missing → title/content=Không có.';

-- Level 5: Article (Điều)
CREATE TABLE IF NOT EXISTS legal_articles (
    id              BIGSERIAL PRIMARY KEY,
    sub_section_id  BIGINT NOT NULL REFERENCES legal_sub_sections(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL UNIQUE,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_articles IS
  'Điều. Always under sub_section (real or Không có). No doc_id; join via chain to parts.';

-- Level 6: Clause (Khoản)
CREATE TABLE IF NOT EXISTS legal_clauses (
    id              BIGSERIAL PRIMARY KEY,
    article_id      BIGINT NOT NULL REFERENCES legal_articles(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL UNIQUE,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_clauses IS 'Khoản. article_id NOT NULL. No doc_id.';

-- Level 7: Point (Điểm)
CREATE TABLE IF NOT EXISTS legal_points (
    id              BIGSERIAL PRIMARY KEY,
    clause_id       BIGINT NOT NULL REFERENCES legal_clauses(id) ON DELETE CASCADE,
    symbol          VARCHAR(10) NOT NULL,
    title           TEXT NOT NULL DEFAULT 'Không có',
    content         TEXT NOT NULL DEFAULT 'Không có',
    path            ltree NOT NULL UNIQUE,
    parent_path     ltree,
    eff_from        DATE,
    eff_to          DATE,
    eff_flag        TEXT,
    status_flag     SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE legal_points IS
  'Điểm. symbol = ltree leaf; title/content default Không có. No doc_id.';

-- Hierarchy GIST indexes
CREATE INDEX IF NOT EXISTS idx_lp_path_gist  ON legal_parts         USING gist (path);
CREATE INDEX IF NOT EXISTS idx_lc_path_gist  ON legal_chapters      USING gist (path);
CREATE INDEX IF NOT EXISTS idx_ls_path_gist  ON legal_sections      USING gist (path);
CREATE INDEX IF NOT EXISTS idx_lss_path_gist ON legal_sub_sections  USING gist (path);
CREATE INDEX IF NOT EXISTS idx_la_path_gist  ON legal_articles      USING gist (path);
CREATE INDEX IF NOT EXISTS idx_lcl_path_gist ON legal_clauses       USING gist (path);
CREATE INDEX IF NOT EXISTS idx_lpt_path_gist ON legal_points        USING gist (path);

CREATE INDEX IF NOT EXISTS idx_lc_parent  ON legal_chapters      USING gist (parent_path);
CREATE INDEX IF NOT EXISTS idx_ls_parent  ON legal_sections      USING gist (parent_path);
CREATE INDEX IF NOT EXISTS idx_lss_parent ON legal_sub_sections  USING gist (parent_path);
CREATE INDEX IF NOT EXISTS idx_la_parent  ON legal_articles      USING gist (parent_path);
CREATE INDEX IF NOT EXISTS idx_lcl_parent ON legal_clauses       USING gist (parent_path);
CREATE INDEX IF NOT EXISTS idx_lpt_parent ON legal_points        USING gist (parent_path);

CREATE INDEX IF NOT EXISTS idx_lp_doc ON legal_parts (doc_id);
CREATE INDEX IF NOT EXISTS idx_lc_part ON legal_chapters (part_id);
CREATE INDEX IF NOT EXISTS idx_ls_chapter ON legal_sections (chapter_id);
CREATE INDEX IF NOT EXISTS idx_lss_section ON legal_sub_sections (section_id);
CREATE INDEX IF NOT EXISTS idx_la_sub_section ON legal_articles (sub_section_id);
CREATE INDEX IF NOT EXISTS idx_lcl_article ON legal_clauses (article_id);
CREATE INDEX IF NOT EXISTS idx_lpt_clause ON legal_points (clause_id);

CREATE INDEX IF NOT EXISTS idx_lp_status ON legal_parts (status_flag);
CREATE INDEX IF NOT EXISTS idx_lc_status ON legal_chapters (status_flag);
CREATE INDEX IF NOT EXISTS idx_ls_status ON legal_sections (status_flag);
CREATE INDEX IF NOT EXISTS idx_lss_status ON legal_sub_sections (status_flag);
CREATE INDEX IF NOT EXISTS idx_la_status ON legal_articles (status_flag);
CREATE INDEX IF NOT EXISTS idx_lcl_status ON legal_clauses (status_flag);
CREATE INDEX IF NOT EXISTS idx_lpt_status ON legal_points (status_flag);

-- Chunks + embeddings (RAG SoT). Key = path (ltree); chunk_type stays on this table.
CREATE TABLE IF NOT EXISTS legal_embeddings (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    chunk_type      TEXT NOT NULL DEFAULT 'body'
                    CHECK (chunk_type IN (
                        'body', 'preamble', 'effectivity', 'appendix', 'signature', 'other'
                    )),
    chunk_text      TEXT NOT NULL,
    embedding       vector(1024),
    is_effective    BOOLEAN NOT NULL DEFAULT TRUE,
    tsv             tsvector GENERATED ALWAYS AS (
                        to_tsvector('simple', coalesce(chunk_text, ''))
                    ) STORED,
    path            ltree NOT NULL UNIQUE,
    root_path       ltree,
    source_element_id TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE legal_embeddings ALTER COLUMN embedding SET STORAGE PLAIN;
ALTER TABLE legal_embeddings ADD COLUMN IF NOT EXISTS source_element_id TEXT;

COMMENT ON TABLE legal_embeddings IS
  'Chunk text + BGE-M3 embedding + FTS. UNIQUE path (ltree) is the stable key. is_effective = RAG cache from hierarchy.';

COMMENT ON COLUMN legal_embeddings.path IS
  'ltree leaf key (sanitize(doc_id).structural). Replaces former chunk_ref.';

COMMENT ON COLUMN legal_embeddings.is_effective IS
  'Denorm cache for HNSW/RAG. SoT = hierarchy status_flag (1=còn HL, 5=còn 1 phần).';

CREATE INDEX IF NOT EXISTS idx_le_doc ON legal_embeddings (doc_id);
CREATE INDEX IF NOT EXISTS idx_le_type ON legal_embeddings (doc_id, chunk_type);
CREATE INDEX IF NOT EXISTS idx_le_path_gist ON legal_embeddings USING gist (path);
CREATE INDEX IF NOT EXISTS idx_le_root_path ON legal_embeddings USING gist (root_path);
CREATE INDEX IF NOT EXISTS idx_le_tsv ON legal_embeddings USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_le_hnsw ON legal_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE is_effective AND embedding IS NOT NULL;

-- =============================================================================
-- Relations
-- =============================================================================

CREATE TABLE IF NOT EXISTS legal_document_relations (
    id              BIGSERIAL PRIMARY KEY,
    from_doc_id     TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    to_doc_id       TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (from_doc_id, to_doc_id, relation_type)
);

COMMENT ON TABLE legal_document_relations IS
  'doc_id ↔ doc_id edges (luoc_do). Neo4j mirrors same id pairs.';

CREATE INDEX IF NOT EXISTS idx_ldr_from ON legal_document_relations (from_doc_id);
CREATE INDEX IF NOT EXISTS idx_ldr_to ON legal_document_relations (to_doc_id);
CREATE INDEX IF NOT EXISTS idx_ldr_type ON legal_document_relations (relation_type);

CREATE TABLE IF NOT EXISTS legal_path_relations (
    id              BIGSERIAL PRIMARY KEY,
    source_path     ltree NOT NULL,
    target_path     ltree NOT NULL,
    ref_type        VARCHAR(50) NOT NULL DEFAULT 'dan_chieu',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_path, target_path, ref_type)
);

COMMENT ON TABLE legal_path_relations IS
  'Cạnh Điều/Khoản/Điểm qua ltree. Root = sanitize(doc_num) e.g. 100_2015_QH13.… (không dùng portal doc_id). Chéo VB + nội bộ cùng VB. Song song legal_document_relations (doc↔doc).';

CREATE INDEX IF NOT EXISTS idx_lpr_source ON legal_path_relations USING gist (source_path);
CREATE INDEX IF NOT EXISTS idx_lpr_target ON legal_path_relations USING gist (target_path);

-- =============================================================================
-- Helper functions
-- =============================================================================

CREATE OR REPLACE FUNCTION sanitize_doc_id_for_ltree(doc_id TEXT) RETURNS TEXT AS $$
BEGIN
    RETURN regexp_replace(doc_id, '[^A-Za-z0-9_]', '_', 'g');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- chunk_ref → ltree path (legacy compat for migration)
CREATE OR REPLACE FUNCTION chunk_ref_to_ltree(cref TEXT) RETURNS ltree AS $$
DECLARE
    doc_part TEXT;
    struct_part TEXT;
    safe_doc TEXT;
BEGIN
    IF cref IS NULL OR position(':' IN cref) = 0 THEN
        RETURN NULL;
    END IF;
    doc_part := split_part(cref, ':', 1);
    struct_part := substring(cref FROM position(':' IN cref) + 1);
    IF struct_part IS NULL OR struct_part = '' THEN
        RETURN NULL;
    END IF;
    safe_doc := regexp_replace(doc_part, '[^A-Za-z0-9_]', '_', 'g');
    RETURN (safe_doc || '.' || struct_part)::ltree;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Extract nearest Article (D*) prefix from an ltree path
CREATE OR REPLACE FUNCTION ltree_article_root(p ltree) RETURNS ltree AS $$
DECLARE
    n INT;
    i INT;
    lab TEXT;
BEGIN
    IF p IS NULL THEN RETURN NULL; END IF;
    n := nlevel(p);
    FOR i IN REVERSE n..1 LOOP
        lab := subpath(p, i - 1, 1)::text;
        IF lab ~ '^D[0-9]+$' THEN
            RETURN subpath(p, 0, i);
        END IF;
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- Triggers — effective date & status syncing (unchanged logic)
-- =============================================================================

CREATE OR REPLACE FUNCTION eff_flag_for_status(sf SMALLINT) RETURNS TEXT AS $$
BEGIN
    RETURN CASE sf
        WHEN 0 THEN 'Chưa xác định'
        WHEN 1 THEN 'Còn hiệu lực'
        WHEN 2 THEN 'Hết hiệu lực toàn bộ'
        WHEN 3 THEN 'Chưa có hiệu lực'
        WHEN 4 THEN 'Hết hiệu lực một phần'
        WHEN 5 THEN 'Có hiệu lực một phần'
        ELSE 'Chưa xác định'
    END;
END; $$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION status_flag_for_eff_flag(ef TEXT) RETURNS SMALLINT AS $$
BEGIN
    RETURN CASE TRIM(COALESCE(ef, ''))
        WHEN 'Chưa xác định' THEN 0
        WHEN 'Còn hiệu lực' THEN 1
        WHEN 'Hết hiệu lực toàn bộ' THEN 2
        WHEN 'Ngưng hiệu lực' THEN 2
        WHEN 'Không còn phù hợp' THEN 2
        WHEN 'Chưa có hiệu lực' THEN 3
        WHEN 'Hết hiệu lực một phần' THEN 4
        WHEN 'Ngưng hiệu lực một phần' THEN 4
        WHEN 'Có hiệu lực một phần' THEN 5
        ELSE 0
    END;
END; $$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION is_partial_eff(sf SMALLINT, ef TEXT) RETURNS BOOLEAN AS $$
BEGIN
    IF sf IN (4, 5) THEN RETURN TRUE; END IF;
    RETURN TRIM(COALESCE(ef, '')) IN (
        'Hết hiệu lực một phần',
        'Ngưng hiệu lực một phần',
        'Có hiệu lực một phần'
    );
END; $$ LANGUAGE plpgsql IMMUTABLE;

-- Bidirectional sync: eff_flag ↔ status_flag
-- After mapping labels, apply_legal_document_eff_window() so eff_to/eff_from
-- always beat a stale crawl "Còn hiệu lực" label.
CREATE OR REPLACE FUNCTION apply_legal_document_eff_window(rec legal_documents)
RETURNS legal_documents AS $$
DECLARE
    today DATE := CURRENT_DATE;
    ef    TEXT := TRIM(COALESCE(rec.eff_flag, ''));
BEGIN
    IF rec.eff_from IS NOT NULL AND rec.eff_from > today THEN
        rec.status_flag := 3;
        rec.eff_flag := 'Chưa có hiệu lực';
        RETURN rec;
    END IF;

    IF rec.eff_to IS NOT NULL AND rec.eff_to <= today THEN
        rec.status_flag := 2;
        IF ef IN ('Ngưng hiệu lực', 'Không còn phù hợp') THEN
            rec.eff_flag := ef;
        ELSE
            rec.eff_flag := 'Hết hiệu lực toàn bộ';
        END IF;
        RETURN rec;
    END IF;

    RETURN rec;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_sync_eff_status_flags() RETURNS TRIGGER AS $$
DECLARE
    eff_changed BOOLEAN;
    status_changed BOOLEAN;
    has_eff BOOLEAN;
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    has_eff := NEW.eff_flag IS NOT NULL AND TRIM(NEW.eff_flag) <> '';

    IF TG_OP = 'INSERT' THEN
        IF has_eff THEN
            NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
        ELSE
            NEW.status_flag := COALESCE(NEW.status_flag, 0);
            NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
        END IF;
        NEW := apply_legal_document_eff_window(NEW);
        RETURN NEW;
    END IF;

    eff_changed := NEW.eff_flag IS DISTINCT FROM OLD.eff_flag;
    status_changed := NEW.status_flag IS DISTINCT FROM OLD.status_flag;

    IF eff_changed AND NOT status_changed THEN
        NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
    ELSIF status_changed AND NOT eff_changed THEN
        IF NEW.status_flag = 2 AND TRIM(COALESCE(OLD.eff_flag, '')) IN (
            'Ngưng hiệu lực', 'Không còn phù hợp'
        ) AND NEW.eff_flag IS NOT DISTINCT FROM OLD.eff_flag THEN
            NULL;
        ELSIF NEW.status_flag = 4 AND TRIM(COALESCE(OLD.eff_flag, '')) = 'Ngưng hiệu lực một phần'
              AND NEW.eff_flag IS NOT DISTINCT FROM OLD.eff_flag THEN
            NULL;
        ELSE
            NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
        END IF;
    ELSIF eff_changed AND status_changed THEN
        NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
    ELSIF has_eff AND NEW.status_flag IS DISTINCT FROM status_flag_for_eff_flag(NEW.eff_flag) THEN
        NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
    ELSIF (NOT has_eff) AND NEW.status_flag IS NOT NULL THEN
        NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
    END IF;

    NEW := apply_legal_document_eff_window(NEW);
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_eff_status ON legal_documents;
CREATE TRIGGER trg_sync_eff_status
    BEFORE INSERT OR UPDATE OF eff_flag, status_flag ON legal_documents
    FOR EACH ROW
    EXECUTE FUNCTION trg_sync_eff_status_flags();

-- Validate eff_from < eff_to + derive status/eff_flag relative to CURRENT_DATE
CREATE OR REPLACE FUNCTION trg_legal_documents_dates() RETURNS TRIGGER AS $$
DECLARE
    today DATE := CURRENT_DATE;
    ef    TEXT;
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;

    IF NEW.eff_from IS NOT NULL AND NEW.eff_to IS NOT NULL
       AND NOT (NEW.eff_from < NEW.eff_to) THEN
        RAISE EXCEPTION
            'legal_documents: eff_from (%) must be < eff_to (%) (doc_id=%)',
            NEW.eff_from, NEW.eff_to, NEW.doc_id;
    END IF;

    ef := TRIM(COALESCE(NEW.eff_flag, ''));

    -- Not yet effective
    IF NEW.eff_from IS NOT NULL AND NEW.eff_from > today THEN
        NEW.status_flag := 3;
        NEW.eff_flag := 'Chưa có hiệu lực';
        RETURN NEW;
    END IF;

    -- Expired
    IF NEW.eff_to IS NOT NULL AND NEW.eff_to <= today THEN
        NEW.status_flag := 2;
        IF ef IN ('Ngưng hiệu lực', 'Không còn phù hợp') THEN
            NEW.eff_flag := ef;
        ELSE
            NEW.eff_flag := 'Hết hiệu lực toàn bộ';
        END IF;
        RETURN NEW;
    END IF;

    -- Within effective window
    IF NEW.eff_from IS NOT NULL
       AND NEW.eff_from <= today
       AND (NEW.eff_to IS NULL OR today < NEW.eff_to) THEN
        IF is_partial_eff(NEW.status_flag, ef) THEN
            IF ef <> '' THEN
                NEW.status_flag := status_flag_for_eff_flag(ef);
            ELSIF NEW.status_flag IN (4, 5) THEN
                NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
            END IF;
            RETURN NEW;
        END IF;
        NEW.status_flag := 1;
        NEW.eff_flag := 'Còn hiệu lực';
        RETURN NEW;
    END IF;

    RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_docs_biu ON legal_documents;
DROP TRIGGER IF EXISTS trg_docs_dates ON legal_documents;
CREATE TRIGGER trg_docs_dates
    BEFORE INSERT OR UPDATE OF eff_from, eff_to ON legal_documents
    FOR EACH ROW
    EXECUTE FUNCTION trg_legal_documents_dates();

-- Cascade expiry through document relations
CREATE OR REPLACE FUNCTION trg_cascade_expire_fn() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status_flag = 1 AND OLD.status_flag IS DISTINCT FROM 1 THEN
        UPDATE legal_documents
        SET    status_flag = 2,
               updated_at = CURRENT_TIMESTAMP
        WHERE doc_id IN (
            SELECT to_doc_id FROM legal_document_relations
            WHERE from_doc_id = NEW.doc_id AND to_doc_id IS NOT NULL
              AND relation_type IN ('van_ban_bi_bai_bo', 'thay_the')
        ) AND status_flag != 2;

        UPDATE legal_documents
        SET    status_flag = 4,
               updated_at = CURRENT_TIMESTAMP
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

-- Scheduled maintenance: refresh status based on dates + cascade relations
CREATE OR REPLACE FUNCTION refresh_status_flags() RETURNS TABLE(doc_id TEXT, old_flag INT, new_flag INT) AS $$
DECLARE
    _updated INT := 0;
BEGIN
    UPDATE legal_documents
    SET    status_flag = 2, updated_at = CURRENT_TIMESTAMP
    WHERE  status_flag != 2 AND eff_to IS NOT NULL AND eff_to <= CURRENT_DATE;
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 1 (expiry by eff_to): updated % row(s)', _updated;

    UPDATE legal_documents
    SET    status_flag = 3, updated_at = CURRENT_TIMESTAMP
    WHERE  status_flag NOT IN (2) AND eff_from IS NOT NULL AND eff_from > CURRENT_DATE;
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 2 (not yet effective): updated % row(s)', _updated;

    UPDATE legal_documents
    SET    status_flag = 1, updated_at = CURRENT_TIMESTAMP
    WHERE  status_flag NOT IN (2, 4, 5)
      AND  eff_from IS NOT NULL AND eff_from <= CURRENT_DATE
      AND  (eff_to IS NULL OR CURRENT_DATE < eff_to);
    GET DIAGNOSTICS _updated = ROW_COUNT;
    RAISE NOTICE 'Step 3 (in force window): updated % row(s)', _updated;

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

-- Constraint (NOT VALID: no scan on existing data; new rows are checked)
ALTER TABLE legal_documents DROP CONSTRAINT IF EXISTS chk_ld_eff_from_before_to;
ALTER TABLE legal_documents ADD CONSTRAINT chk_ld_eff_from_before_to
    CHECK (eff_from IS NULL OR eff_to IS NULL OR eff_from < eff_to) NOT VALID;

-- =============================================================================
-- Hierarchy effectiveness (SoT) — dates, flag sync, parent→child cascade, RAG cache
-- =============================================================================

CREATE OR REPLACE FUNCTION trg_hierarchy_sync_eff_status() RETURNS TRIGGER AS $$
DECLARE
    eff_changed BOOLEAN;
    status_changed BOOLEAN;
    has_eff BOOLEAN;
BEGIN
    has_eff := NEW.eff_flag IS NOT NULL AND TRIM(NEW.eff_flag) <> '';

    IF TG_OP = 'INSERT' THEN
        IF has_eff THEN
            NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
        ELSE
            NEW.status_flag := COALESCE(NEW.status_flag, 0);
            NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
        END IF;
        RETURN NEW;
    END IF;

    eff_changed := NEW.eff_flag IS DISTINCT FROM OLD.eff_flag;
    status_changed := NEW.status_flag IS DISTINCT FROM OLD.status_flag;

    IF eff_changed AND NOT status_changed THEN
        NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
    ELSIF status_changed AND NOT eff_changed THEN
        IF NEW.status_flag = 2 AND TRIM(COALESCE(OLD.eff_flag, '')) IN (
            'Ngưng hiệu lực', 'Không còn phù hợp'
        ) AND NEW.eff_flag IS NOT DISTINCT FROM OLD.eff_flag THEN
            NULL;
        ELSIF NEW.status_flag = 4 AND TRIM(COALESCE(OLD.eff_flag, '')) = 'Ngưng hiệu lực một phần'
              AND NEW.eff_flag IS NOT DISTINCT FROM OLD.eff_flag THEN
            NULL;
        ELSE
            NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
        END IF;
    ELSIF eff_changed AND status_changed THEN
        NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
    ELSIF has_eff AND NEW.status_flag IS DISTINCT FROM status_flag_for_eff_flag(NEW.eff_flag) THEN
        NEW.status_flag := status_flag_for_eff_flag(NEW.eff_flag);
    ELSIF (NOT has_eff) AND NEW.status_flag IS NOT NULL THEN
        NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
    END IF;

    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_hierarchy_dates() RETURNS TRIGGER AS $$
DECLARE
    today DATE := CURRENT_DATE;
    ef    TEXT;
BEGIN
    IF NEW.eff_from IS NOT NULL AND NEW.eff_to IS NOT NULL
       AND NOT (NEW.eff_from < NEW.eff_to) THEN
        RAISE EXCEPTION
            '%: eff_from (%) must be < eff_to (%) (path=%)',
            TG_TABLE_NAME, NEW.eff_from, NEW.eff_to, NEW.path;
    END IF;

    ef := TRIM(COALESCE(NEW.eff_flag, ''));

    IF NEW.eff_from IS NOT NULL AND NEW.eff_from > today THEN
        NEW.status_flag := 3;
        NEW.eff_flag := 'Chưa có hiệu lực';
        RETURN NEW;
    END IF;

    IF NEW.eff_to IS NOT NULL AND NEW.eff_to <= today THEN
        NEW.status_flag := 2;
        IF ef IN ('Ngưng hiệu lực', 'Không còn phù hợp') THEN
            NEW.eff_flag := ef;
        ELSE
            NEW.eff_flag := 'Hết hiệu lực toàn bộ';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.eff_from IS NOT NULL
       AND NEW.eff_from <= today
       AND (NEW.eff_to IS NULL OR today < NEW.eff_to) THEN
        IF is_partial_eff(NEW.status_flag, ef) THEN
            IF ef <> '' THEN
                NEW.status_flag := status_flag_for_eff_flag(ef);
            ELSIF NEW.status_flag IN (4, 5) THEN
                NEW.eff_flag := eff_flag_for_status(NEW.status_flag);
            END IF;
            RETURN NEW;
        END IF;
        NEW.status_flag := 1;
        NEW.eff_flag := 'Còn hiệu lực';
        RETURN NEW;
    END IF;

    RETURN NEW;
END; $$ LANGUAGE plpgsql;

-- Parent full-expire (status=2) → children status=2 (does not revive on parent restore)
CREATE OR REPLACE FUNCTION trg_hierarchy_cascade_expire() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status_flag = 2 AND OLD.status_flag IS DISTINCT FROM 2 THEN
        IF TG_TABLE_NAME = 'legal_parts' THEN
            UPDATE legal_chapters SET status_flag = 2
            WHERE part_id = NEW.id AND status_flag IS DISTINCT FROM 2;
        ELSIF TG_TABLE_NAME = 'legal_chapters' THEN
            UPDATE legal_sections SET status_flag = 2
            WHERE chapter_id = NEW.id AND status_flag IS DISTINCT FROM 2;
        ELSIF TG_TABLE_NAME = 'legal_sections' THEN
            UPDATE legal_sub_sections SET status_flag = 2
            WHERE section_id = NEW.id AND status_flag IS DISTINCT FROM 2;
        ELSIF TG_TABLE_NAME = 'legal_sub_sections' THEN
            UPDATE legal_articles SET status_flag = 2
            WHERE sub_section_id = NEW.id AND status_flag IS DISTINCT FROM 2;
        ELSIF TG_TABLE_NAME = 'legal_articles' THEN
            UPDATE legal_clauses SET status_flag = 2
            WHERE article_id = NEW.id AND status_flag IS DISTINCT FROM 2;
        ELSIF TG_TABLE_NAME = 'legal_clauses' THEN
            UPDATE legal_points SET status_flag = 2
            WHERE clause_id = NEW.id AND status_flag IS DISTINCT FROM 2;
        END IF;
    END IF;
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

-- Sync embeddings.is_effective cache from hierarchy leaf status (1 or 5 = effective)
CREATE OR REPLACE FUNCTION trg_sync_embedding_effective() RETURNS TRIGGER AS $$
DECLARE
    ok BOOLEAN;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW.status_flag IS NOT DISTINCT FROM OLD.status_flag
       AND NEW.path IS NOT DISTINCT FROM OLD.path THEN
        RETURN NULL;
    END IF;
    ok := NEW.status_flag IN (1, 5);
    UPDATE legal_embeddings
    SET is_effective = ok
    WHERE path IS NOT NULL
      AND (path = NEW.path OR path <@ NEW.path)
      AND is_effective IS DISTINCT FROM ok;
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'legal_parts', 'legal_chapters', 'legal_sections', 'legal_sub_sections',
        'legal_articles', 'legal_clauses', 'legal_points'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_hier_sync_eff ON %I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_hier_sync_eff
             BEFORE INSERT OR UPDATE OF eff_flag, status_flag ON %I
             FOR EACH ROW EXECUTE FUNCTION trg_hierarchy_sync_eff_status()', t);

        EXECUTE format('DROP TRIGGER IF EXISTS trg_hier_dates ON %I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_hier_dates
             BEFORE INSERT OR UPDATE OF eff_from, eff_to ON %I
             FOR EACH ROW EXECUTE FUNCTION trg_hierarchy_dates()', t);

        EXECUTE format('DROP TRIGGER IF EXISTS trg_hier_cascade ON %I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_hier_cascade
             AFTER UPDATE OF status_flag ON %I
             FOR EACH ROW
             WHEN (NEW.status_flag = 2 AND OLD.status_flag IS DISTINCT FROM 2)
             EXECUTE FUNCTION trg_hierarchy_cascade_expire()', t);

        EXECUTE format('DROP TRIGGER IF EXISTS trg_hier_emb_eff ON %I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_hier_emb_eff
             AFTER INSERT OR UPDATE OF status_flag, path ON %I
             FOR EACH ROW EXECUTE FUNCTION trg_sync_embedding_effective()', t);

        EXECUTE format(
            'ALTER TABLE %I DROP CONSTRAINT IF EXISTS chk_%s_eff_from_before_to',
            t, replace(t, 'legal_', ''));
        EXECUTE format(
            'ALTER TABLE %I ADD CONSTRAINT chk_%s_eff_from_before_to
             CHECK (eff_from IS NULL OR eff_to IS NULL OR eff_from < eff_to) NOT VALID',
            t, replace(t, 'legal_', ''));
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION refresh_hierarchy_status_flags() RETURNS void AS $$
DECLARE
    t TEXT;
    _updated INT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'legal_parts', 'legal_chapters', 'legal_sections', 'legal_sub_sections',
        'legal_articles', 'legal_clauses', 'legal_points'
    ]
    LOOP
        EXECUTE format(
            'UPDATE %I SET status_flag = 2
             WHERE status_flag IS DISTINCT FROM 2
               AND eff_to IS NOT NULL AND eff_to <= CURRENT_DATE', t);
        GET DIAGNOSTICS _updated = ROW_COUNT;
        RAISE NOTICE '% expiry by eff_to: %', t, _updated;

        EXECUTE format(
            'UPDATE %I SET status_flag = 3
             WHERE status_flag IS DISTINCT FROM 2
               AND eff_from IS NOT NULL AND eff_from > CURRENT_DATE', t);
        GET DIAGNOSTICS _updated = ROW_COUNT;
        RAISE NOTICE '% not yet effective: %', t, _updated;

        EXECUTE format(
            'UPDATE %I SET status_flag = 1
             WHERE status_flag NOT IN (2, 4, 5)
               AND eff_from IS NOT NULL AND eff_from <= CURRENT_DATE
               AND (eff_to IS NULL OR CURRENT_DATE < eff_to)', t);
        GET DIAGNOSTICS _updated = ROW_COUNT;
        RAISE NOTICE '% in-force window: %', t, _updated;
    END LOOP;
END; $$ LANGUAGE plpgsql;

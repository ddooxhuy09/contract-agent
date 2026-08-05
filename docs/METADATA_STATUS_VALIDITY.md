# Metadata Extraction, Status Flag & Validity Handling

Tài liệu mô tả **3 nhóm logic** cốt lõi của hệ thống RAG văn bản pháp luật Việt Nam, dựa trên code thực tế trong repo này. Mục đích: tái sử dụng/port sang dự án tương tự (bộ pháp điển văn bản của một cơ quan, bộ luật nội bộ, v.v.).

> **Phạm vi file:**
> 1. Trích xuất metadata từ nội dung văn bản (rule-based, không cần LLM/API)
> 2. Trigger `status_flag` trong PostgreSQL — tự động cập nhật hiệu lực
> 3. Cách RAG xử lý hiệu lực khi trả kết quả (validity-aware re-ranking)

---

## 1. Trích xuất metadata từ documents

### 1.1 Tổng quan pipeline

```
Raw content (HTML/text)
      │  (crawler + cleaner: strip HTML, markdown, BOM)
      ▼
clean_content
      │
      ├──► chunking_service ──► document_chunks (mỗi chunk có section_type='enforcement')
      │        (chunk = 1 Điều / 1 Khoản, đánh dấu "Điều Hiệu lực thi hành")
      │
      └──► helpers/metadata_extractor.py  (100% rule-based, sync, không tốn API)
             │
             ├─ extract_effective_date()      → effective_date
             ├─ extract_expiry_date()         → expiry_date
             ├─ extract_relations()           → relation thay thế/bãi bỏ/sửa đổi
             ├─ detect_category()             → category (lĩnh vực pháp luật)
             └─ extract_keywords()            → keyword gợi ý
```

Điểm mấu chốt: **ưu tiên trích xuất từ "Điều Hiệu lực thi hành" (enforcement article)** thay vì quét toàn bộ văn bản — vì đó là nơi chứa ngày hiệu lực/hết hiệu lực/đối tượng thay thế, còn toàn bộ văn bản có nhiều false positive ("thời kỳ kiểm tra đến hết ngày X", điều khoản chuyển tiếp, dẫn chiếu VB khác).

Nguồn tham chiếu: `helpers/metadata_extractor.py` (1522 dòng).

### 1.2 Trích xuất `effective_date` (ngày có hiệu lực)

Hàm chính: `extract_effective_date(content, issued_date)` — `metadata_extractor.py:562`.

**Thứ tự ưu tiên:**

| Bước | Nguồn | Hàm | Chi tiết |
|------|-------|-----|----------|
| 1 | Enforcement article | `extract_effective_date_from_enforcement(enf_text, issued_date)` (`:854`) | `enf_text` đã được chunking system xác nhận là `section_type='enforcement'` → không cần tìm article, quét thẳng pattern |
| 2 | Toàn bộ content (fallback) | `extract_effective_date(content)` (`:562`) → `_find_effective_article()` (`:346`) | Tự tìm "Điều X: Hiệu lực thi hành" |
| 3 | "kể từ ngày ký" | `is_effective_from_signing()` (`:443`) | Nếu VB dùng cụm "có hiệu lực kể từ ngày ký" → `effective_date = issued_date` |
| 4 | "sau X ngày kể từ ngày ký" | `_calc_effective_from_signing_delay()` (`:457`) | `issued_date + X ngày` |
| 5 | Dẫn chiếu VB khác (cross-ref) | `find_cross_ref_doc_number()` — gọi ở `rag_service.py:863` | Lấy số hiệu VB bị dẫn chiếu → tra `effective_date` của VB đó từ DB; nếu VB chưa tồn tại → lưu relation `effective_date_depends_on` chờ crawl sau |

**Pattern keyword hiệu lực (after_kw_patterns)** — `metadata_extractor.py:873-879`:

```
có hiệu lực thi hành kể từ ngày ...
có hiệu lực thi hành từ ngày ...
có hiệu lực [kể từ / từ / vào] ngày ...
hiệu lực thi hành [kể từ / từ] ngày ...
thi hành [kể từ / từ] ngày ...
```

**Guard chống false positive — `_extract_effective_from_segments()` (`:537`):**
- Tách enforcement text thành từng clause (`\n` + số thứ tự / ký tự a)b) / bullet)
- Với mỗi clause: bỏ qua nếu chứa `is_effective_from_signing` hoặc `find_cross_ref_doc_number` (dẫn chiếu VB khác — date trong câu đó thuộc VB khác, không phải VB này)

**Tìm enforcement article trong content:**

`_find_effective_article(content)` (`:346`) — quét mọi vị trí `Điều X.` (regex `Điều\s+[\dIVXLCH]+\s*[\.:]`), theo 3 pass:
1. Header (100 ký tự đầu) chứa "hiệu lực" → mạnh nhất
2. Body window (400 ký tự) chứa "có hiệu lực" / "hiệu lực thi hành"
3. Legacy: window chứa "hiệu lực" hoặc "thi hành" (tránh "thi hành án hình sự")

Guard: header không được đứng giữa câu (ký tự trước không là chữ/số).

`extract_effective_date_section()` (`:410`) — quét paragraph từ dưới lên tìm keyword hiệu lực; nếu paragraph >2000 ký tự (văn bản không có paragraph break — kiểu LuatVietnam) → narrow xuống enforcement article thật bằng `_find_effective_article` / `_find_article_with_keywords`.

**Parse ngày — `parse_vietnamese_date()` (`:489`):**
- Hỗ trợ: "ngày 15 tháng 3 năm 2024", "15/03/2024", "15-03-2024", "2024-03-15"
- Heuristic: chuỗi 4 chữ số đầu là năm → YYYY-MM-DD, ngược lại dd-mm-yyyy
- Range check: 1≤d≤31, 1≤m≤12, 1900≤y≤2100
- Trả về chuẩn `YYYY-MM-DD`

### 1.3 Trích xuất `expiry_date` (ngày hết hiệu lực)

Hàm chính: `extract_expiry_date(content, enf_text)` — `metadata_extractor.py:795`.

**Nguyên tắc quan trọng:** CHỈ trích xuất từ enforcement text (hoặc enforcement article tìm trong content), **KHÔNG scan toàn bộ content** — tránh false positive từ:
- Điều khoản chuyển tiếp: "thủ tục được áp dụng đến hết ngày Y"
- "Thời kỳ kiểm tra: ... đến hết ngày X"
- Cross-reference: "VB số X hết hiệu lực từ ngày Y"

Luồng: `extract_expiry_date_from_enforcement(enf_text)` (`:756`) → `_extract_expiry_from_section` (dùng đầy đủ strict+narrow+broad patterns vì context đã được xác nhận là enforcement). Double-check: nếu enforcement text không chứa keyword "hiệu lực/hết hiệu lực/có hiệu lực/thi hành" → chỉ dùng strict patterns (phòng chunk bị phân loại nhầm).

**Validation — `validate_expiry_against_effective()` (`:834`):**
- Nếu `expiry_date < effective_date` → rõ ràng sai → trả về `None` (hủy expiry)

### 1.4 Trích xuất relations (thay thế / bãi bỏ / sửa đổi)

Hàm chính: `extract_relations(content, title)` — `metadata_extractor.py:1372`.

**3 nhóm pattern:**

| # | Nhóm | Pattern (rút gọn) | relation_type |
|---|------|-------------------|---------------|
| 1 | Sửa đổi 1 phần | "Bãi bỏ khoản X Điều Y của [VB] số Z", "Sửa đổi Điều X của [VB] số Z", "Bổ sung Điều X vào [VB] số Z" (`PARTIAL_AMEND_PATTERNS`, `:255`) | `amends_partial` |
| 2 | Toàn bộ | "Bãi bỏ [VB] số X", "Thay thế [VB] số X", "Hết hiệu lực [VB] số X", "[VB] số X hết hiệu lực", "Sửa đổi, bổ sung [VB] số X", "ban hành kèm theo [VB] số X" (`RELATION_PATTERNS`, `:233`) | `abolishes` / `replaces` / `amends` |
| 3 | Bullet scan | Sau "thay thế:" / "bãi bỏ:" / "hết hiệu lực:" + dòng bullet `- •` (`:1482`) | `replaces` / `abolishes` |

**Mỗi relation kèm context:** `_extract_context()` (`:1387`) trích thêm `old_issued_date` (ngày ban hành VB cũ), `issuing_authority_hint` (cơ quan ban hành), `title_hint` — dùng để resolve chính xác `old_doc_id` sau này.

**Luật tránh trùng:** nếu đã có `amends_partial` cho doc → bỏ qua `amends` toàn bộ (partial đã đủ chi tiết hơn).

**Enforcement-specialized — `extract_expiry_relations_from_enforcement(enf_text, title)` (`:1104`):**
- Pattern Luật-type: "Luật X số Y ... hết hiệu lực kể từ ngày Luật này có hiệu lực thi hành" → `abolishes`
- Sub-bullet scan sau "hết hiệu lực/bãi bỏ": dòng `(a)`, `–`, `•`, `1.` chứa doc number → `abolishes`
- Fallback: enforcement có "hết hiệu lực/bãi bỏ/thay thế" nhưng không tìm ra số hiệu → điền `doc_number="0"` (tránh lỗi crawl; caller bỏ qua `"0"`)

### 1.5 Trích xuất khác

| Metadata | Hàm | Cách hoạt động |
|----------|-----|----------------|
| `category` (lĩnh vực) | `detect_category()` (`:1250`) | Tier 0: URL slug TVPL/LuatVietnam → map; Tier 1: regex keyword trên title; Tier 2: underthesea NLP; Tier 3: "Khác" |
| `keywords` | `extract_keywords()` (`:1189`) | Số hiệu VB + từ có nghĩa trong title + Điều/Khoản/Chương refs + acronym + năm |
| `header_section` | `extract_header_section()` (`:285`) | Cắt đoạn "Số hiệu → trích yếu → căn cứ pháp lý" |

### 1.6 Tổng hợp — `extract_metadata()` (`:1346`)

```python
def extract_metadata(title, content, url="", hint_category=None, doc_id="",
                     issued_date=None, effective_date=None) -> Dict:
    eff = extract_effective_date(content, issued_date=issued_date)
    if not eff and effective_date:
        eff = effective_date
    expiry = extract_expiry_date(content)
    if expiry and eff:
        expiry = validate_expiry_against_effective(expiry, eff)
    return {"category": detect_category(title=title),
            "effective_date": eff, "expiry_date": expiry}
```

### 1.7 Nơi gọi trong RAG pipeline — `rag_service.py:833-952`

Khi ingest 1 document (add_document), thứ tự xử lý:

```
Phase 3 (dòng 833-899):
  - Gom các chunk section_type='enforcement' → enf_text
  - effective_date: enforcement > full-content > cross-ref (DB lookup) > "kể từ ngày ký"
  - expiry_date: enforcement > full-content > API metadata (VBPL, có thể sai)
  - validate_expiry_against_effective
Phase 4 (dòng 901-913): extract relations (ưu tiên enforcement), dedup
Phase 5 (dòng 915-931): insert_document vào PostgreSQL
Phase 6 (dòng 933-948): add_document_relation cho từng relation
     - bỏ qua doc_number == "0"
     - bỏ qua relation_type ∈ ("amends", "amends_partial") — chỉ xử lý replaces/abolishes ở đây
```

---

## 2. Trigger `status_flag` — tự động cập nhật hiệu lực

### 2.1 Ý nghĩa 5 giá trị

| `status_flag` | Ý nghĩa | Map text |
|---------------|---------|----------|
| 0 | Chưa xác định (thiếu ngày) | "chưa xác định" |
| 1 | Còn hiệu lực | "còn hiệu lực" |
| 2 | Hết hiệu lực | "hết hiệu lực" |
| 3 | Sắp có hiệu lực (`effective_date > hôm nay`) | "sắp có hiệu lực" |
| 4 | Hết hiệu lực một phần (bị sửa đổi 1 phần) | "hết hiệu lực một phần" |

Map text: `rag_service.py:1846-1852` (`STATUS_FLAG_MAP`).

### 2.2 Schema

Bảng `legal_documents` — `database_service.py:264-282`:

```sql
CREATE TABLE IF NOT EXISTS legal_documents (
    doc_id TEXT PRIMARY KEY,
    doc_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    doc_type TEXT,            -- Hiến pháp/Luật/Nghị định/Thông tư...
    issued_date TEXT,         -- ngày ký/ban hành
    effective_date TEXT,      -- ngày có hiệu lực
    content TEXT NOT NULL,
    ...
    status_flag INTEGER DEFAULT 0,
    expiry_date TEXT,         -- ngày hết hiệu lực
    ...
);
```

Bảng quan hệ `document_relations` (`:298-306`):

```sql
CREATE TABLE IF NOT EXISTS document_relations (
    new_doc_id TEXT NOT NULL,        -- VB mới (thay thế/bãi bỏ)
    old_doc_id TEXT NOT NULL,        -- VB cũ bị thay thế
    relation_type TEXT NOT NULL DEFAULT 'replaces',
    UNIQUE(new_doc_id, old_doc_id, relation_type)
);
```

`relation_type` trong hệ thống hiện tại: `replaces`, `abolishes`, `amends`, `amends_partial` (VBThayThes của TVPL map sang `replaces`/`abolishes`).

### 2.3 Helper parse ngày — `safe_cast_to_date` (`database_service.py:356`)

```sql
CREATE OR REPLACE FUNCTION safe_cast_to_date(val text) RETURNS date AS $$
BEGIN
    IF val IS NULL OR val = '' THEN RETURN NULL; END IF;
    IF val ~ '^\d{4}-\d{2}-\d{2}$' THEN RETURN to_date(val, 'YYYY-MM-DD'); END IF;
    IF val ~ '^\d{1,2}/\d{1,2}/\d{4}$' THEN RETURN to_date(val, 'DD/MM/YYYY'); END IF;
    IF val ~ '^\d{4}/\d{1,2}/\d{1,2}$' THEN RETURN to_date(val, 'YYYY/MM/DD'); END IF;
    RETURN NULL;
EXCEPTION WHEN OTHERS THEN RETURN NULL; END; $$
LANGUAGE plpgsql IMMUTABLE;
```

### 2.4 Trigger 1 — auto-assign status khi insert/update (`:379-400`)

```sql
CREATE OR REPLACE FUNCTION trg_legal_documents_status() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    IF NEW.status_flag IS NULL OR NEW.status_flag = 0 THEN
        NEW.status_flag := CASE
            WHEN NEW.effective_date IS NULL OR NEW.effective_date = '' THEN 0
            WHEN safe_cast_to_date(NEW.effective_date) > CURRENT_DATE THEN 3
            ELSE 1
        END;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_docs_biu
    BEFORE INSERT OR UPDATE OF effective_date ON legal_documents
    FOR EACH ROW
    WHEN (NEW.status_flag IS DISTINCT FROM 2)   -- không đè lên VB đã hết hiệu lực
    EXECUTE FUNCTION trg_legal_documents_status();
```

**Logic:** mọi insert / mọi update của `effective_date` (trừ khi `status_flag` đang là 2):
- `effective_date` rỗng → `0` (chưa xác định)
- `effective_date > hôm nay` → `3` (sắp có hiệu lực)
- ngược lại → `1` (còn hiệu lực)

Guard `WHEN (NEW.status_flag IS DISTINCT FROM 2)` đảm bảo VB đã bị đánh dấu hết hiệu lực không bị "hồi sinh" bởi dữ liệu crawl lại.

### 2.5 Trigger 2 — cascade expire khi VB mới có hiệu lực (`:403-436`)

```sql
CREATE OR REPLACE FUNCTION trg_cascade_expire_fn() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status_flag = 1 AND OLD.status_flag IS DISTINCT FROM 1 THEN
        -- VB bị thay thế/bãi bỏ → hết hiệu lực hoàn toàn
        UPDATE legal_documents SET status_flag = 2, updated_at = CURRENT_TIMESTAMP
        WHERE doc_id IN (
            SELECT old_doc_id FROM document_relations
            WHERE new_doc_id = NEW.doc_id AND old_doc_id IS NOT NULL
              AND relation_type IN ('replaces', 'abolishes')
        ) AND status_flag != 2;

        -- VB bị sửa đổi → hết hiệu lực một phần
        UPDATE legal_documents SET status_flag = 4, updated_at = CURRENT_TIMESTAMP
        WHERE doc_id IN (
            SELECT old_doc_id FROM document_relations
            WHERE new_doc_id = NEW.doc_id AND old_doc_id IS NOT NULL
              AND relation_type IN ('amends', 'amends_partial')
        ) AND status_flag NOT IN (2, 4);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER trg_cascade_expire
    AFTER UPDATE OF status_flag ON legal_documents
    FOR EACH ROW
    WHEN (NEW.status_flag = 1 AND OLD.status_flag IS DISTINCT FROM 1)
    EXECUTE FUNCTION trg_cascade_expire_fn();
```

**Kịch bản thực tế:** khi crawl VB mới (vd **299/2026/NĐ-CP**) → `add_document_relation(new=299/2026, old=120/2020, 'replaces')` → trigger 1 set `299/2026.status_flag=1` → trigger 2 cascade set `120/2020.status_flag=2` + `expiry_date = 2026-07-28`. (Đã verify thực tế: `120/2020` exp=2026-07-28, st=4 sau khi 299/2026 có hiệu lực — chuỗi `replaces` trong relation còn 1 tầng `299/2026` nữa làm nó thành hết hiệu lực một phần do bị thay thế 1 phần.)

### 2.6 `add_document_relation` — ghi relation + fill expiry/status (`:1211`)

```python
async def add_document_relation(self, new_doc_id, old_doc_number,
                                relation_type="replaces", ...):
    # 1. Resolve old_doc_id từ doc_number (UNIQUE) → fallback ILIKE + authority_hint
    #    + issued_date (text trích có thể lệch chuẩn: '73/2010' vs '73/2010/NĐ-CP')
    old_doc_id = await self._resolve_old_doc_id(conn, old_doc_number, ...)
    if not old_doc_id:
        return False   # VB cũ chưa có trong DB → relation bị bỏ (log SKIP)

    # 2. INSERT relation (ON CONFLICT DO NOTHING)

    # 3. Nếu VB mới có effective_date và new_eff >= old_eff:
    if relation_type in ("replaces", "abolishes"):
        await self.set_document_expiry(old_doc_id, expiry_date=new_eff)   # set expiry = eff của VB mới
        if status_flag == 1:
            await self.mark_document_expired(old_doc_id)                   # status_flag = 2
    elif relation_type in ("amends", "amends_partial"):
        await self.mark_document_partial(old_doc_id)                       # status_flag = 4
```

**Guard:** nếu `new_eff < old_eff` → skip fill expiry (VB mới có hiệu lực sớm hơn VB cũ là vô lý).

### 2.7 `refresh_status_flags` — job bảo dưỡng định kỳ (`:933-992`)

Chạy scheduled (mỗi đêm) để chữa mọi lệch lạc (dữ liệu cũ, expiry do VB mới thay đổi):

```sql
-- 1. Mọi doc có expiry_date <= hôm nay → status_flag = 2
UPDATE legal_documents SET status_flag = 2 ... WHERE safe_cast_to_date(expiry_date) <= CURRENT_DATE AND status_flag != 2;

-- 2. Mọi doc status NOT IN (2,4): tính lại theo effective_date (3/1/0)
UPDATE legal_documents SET status_flag = CASE ... END WHERE status_flag NOT IN (2, 4);

-- 3. Fill expiry_date rỗng cho doc bị replaces/abolishes = effective_date mới nhất của VB thay thế
UPDATE legal_documents SET expiry_date = (SELECT MAX(new_doc.effective_date) FROM ...)
WHERE expiry_date IS NULL OR expiry_date = '';

-- 4. Lặp lại bước 1 sau khi đã fill expiry (catch-up các doc vừa hết hiệu lực)
```

Các method hỗ trợ: `mark_document_expired` (`:1085`), `mark_document_partial` (`:1105`), `set_document_expiry` (`:1119`).

---

## 3. RAG xử lý hiệu lực khi trả kết quả

### 3.1 Bối cảnh

Sau khi retrieve + rerank LLM (Gemini), các chunk được đưa qua **`_validate_and_rerank_chunks()`** (`rag_service.py:2019`) — validity agent thuần logic, không tốn Gemini. Đầu vào là `time_context` (mặc định = hôm nay, có thể quá khứ/tương lai để hỏi "hiệu lực tại thời điểm X").

### 3.2 Pass 1 — Gán nhãn hiệu lực (`:2044-2066`)

Với mỗi chunk:

```python
if c.get("_is_web"):
    c["_valid_at_tc"] = "web";  c["_priority_score"] = 0.55
    continue
status = (c.get("status") or "").lower()
sf = c.get("status_flag", 0)
eff = c.get("effective_date") or ""
expiry = c.get("expiry_date") or ""

if sf == 2 or "hết hiệu lực" in status or "đã bãi bỏ" in status:
    c["_valid_at_tc"] = "expired"
elif expiry and expiry[:10] < time_context[:10]:
    c["_valid_at_tc"] = "expired"
elif eff and eff[:10] > time_context[:10]:
    c["_valid_at_tc"] = "not_yet_effective"
elif sf == 4:
    c["_valid_at_tc"] = "partial"
else:
    c["_valid_at_tc"] = "valid"
```

| Nhãn | Điều kiện |
|------|-----------|
| `web` | Chunk từ web search (score nền 0.55) |
| `expired` | `status_flag=2`, hoặc text chứa "hết hiệu lực"/"đã bãi bỏ", hoặc `expiry_date < time_context` |
| `not_yet_effective` | `effective_date > time_context` |
| `partial` | `status_flag=4` (bị sửa đổi 1 phần) |
| `valid` | còn lại |

### 3.3 Pass 2 — Tìm VB thay thế cho chunk hết hiệu lực (`:2068-2077`)

Với mỗi chunk `expired` có `doc_id` → gọi `_find_replacement_chunks()` (`:1906`):

```
BFS theo document_relations.incoming (replaces/abolishes) từ doc_id
→ duyệt CHAIN transitive đến hết (vd: 73/2010 → 167/2013 → 144/2021 → 282/2025)
→ load metadata từng node trong chain
→ _order_replacement_candidates() sắp thứ tự:
     Ưu tiên 1: doc còn hiệu lực tại time_context (mới nhất trước)
     Ưu tiên 2: doc không xác định được hiệu lực
     Ưu tiên 3: doc đã hết hiệu lực
→ lấy tối đa 5 chunk đầu của VB thay thế tốt nhất (score=0.55, _is_replacement=True)
```

Ví dụ thực tế: chunk thuộc **120/2020** (expired) → relation tìm ra **299/2026/NĐ-CP** còn hiệu lực → bổ sung chunk của 299/2026 vào kết quả.

### 3.4 Pass 3 — Re-rank theo priority score (`:2079-2121`)

```python
dt_norm = self._doc_type_norm(doc_type)   # Hiến pháp=1.0 ... Thông tư=0.4, unknown=0.3
st_norm = self._status_norm(status)       # còn hiệu lực=1.0 ... hết hiệu lực=0.0
if _vtc == "expired":            st_norm = 0.0
elif _vtc == "not_yet_effective": st_norm = 0.60

c["_priority_score"] = (
    rerank_base * 0.50 +    # điểm LLM rerank (có phrase boost)
    dt_norm      * 0.20 +   # thứ bậc pháp lý của loại VB
    st_norm      * 0.20 +   # trạng thái hiệu lực
    0.10                     # base
)
# + freshness boost: effective < 90 ngày +0.08, < 365 ngày +0.04

# ── Validity multiplier: expired / not-yet-effective bị đẩy xuống DƯỚI replacement ──
if _vtc == "expired":             score *= 0.35
elif _vtc == "not_yet_effective": score *= 0.70
```

**Trọng số:**

- `DOC_TYPE_RANK` (config.py:81-86): hiến pháp 1.00, bộ luật 0.95, luật 0.90, pháp lệnh 0.80, nghị quyết 0.70, nghị định 0.60, quyết định 0.50, quy chuẩn 0.35, thông tư 0.40, chỉ thị 0.30
- `STATUS_RANK` (config.py:92-97): còn hiệu lực/hiệu lực một phần/hết hiệu lực một phần 1.00, sắp có hiệu lực 0.60, chưa xác định 0.40, hết hiệu lực/đã bãi bỏ 0.00
- `_doc_type_norm` (rag_service.py:2807), `_status_norm` (rag_service.py:2818)

### 3.5 Merge theo nhóm sub-query (`:2123-2233`)

Thứ tự ưu tiên khi ghép kết quả (mỗi sub-query rerank riêng, không trộn global):

```
Round 0: Phrase-hit pin   — chunk khớp cụm từ đặc trưng của sub-query (luôn giữ,
                            tránh rớt vì cosine loãng)
Round 1: min 5/group      — top chunk mỗi sub-query (BỎ QUA expired/not_yet_effective)
Round 2: round-robin      — đến khi đủ cap = max(20, n_subqueries * 12)
Append:  replacements + ungrouped (đã sort theo priority, _is_replacement=True)
Cuối:    deferred         — expired/not_yet_effective còn sót lại (sort theo priority)
```

**Kết quả cuối:** chunk `expired`/`not_yet_effective` luôn bị đẩy xuống cuối danh sách (dưới cả VB thay thế), còn VB còn hiệu lực chiếm ưu thế. Source hiển thị kèm `status_flag` map + `expiry_date` để UI/answer nói đúng hiệu lực (vd: "120/2020 hết hiệu lực một phần do bị thay thế bởi 299/2026").

### 3.6 Luồng end-to-end

```
Query → embedding → pgvector/FAISS search → LLM rerank
  → _validate_and_rerank_chunks()
       ├─ Pass 1: gán _valid_at_tc (web/valid/partial/expired/not_yet_effective)
       ├─ Pass 2: _find_replacement_chunks → chain thay thế → _is_replacement
       ├─ Pass 3: _priority_score = rerank*0.5 + doc_type*0.2 + status*0.2 + 0.1
       │          + freshness boost + validity multiplier (×0.35 / ×0.70)
       └─ Merge: pin phrase → min 5/group → round-robin → replacements → deferred
  → LLM generate answer (chunk + metadata status/expiry)
```

---

## 4. Áp dụng cho dự án tương tự

### Checklist khi port sang hệ thống khác

1. **Chunking đánh dấu enforcement article** — cần 1 bước xác định "Điều Hiệu lực thi hành / Tổ chức thực hiện" (`section_type='enforcement'`) để metadata extraction tập trung vào đó, giảm false positive.

2. **3 lớp effective_date**: enforcement text → full-content fallback → cross-ref DB lookup. Không bao giờ tin API metadata của bên thứ 3 cho expiry (đã có bug: API trả ngày sai).

3. **Pattern tiếng Việt**: dùng đúng bộ regex trong `metadata_extractor.py` (đã được tối ưu qua thử nghiệm thực tế). Đặc biệt chú ý guard clause-level (mỗi clause scan riêng, bỏ clause có dẫn chiếu VB khác) — đây là nguồn false positive lớn nhất.

4. **Database: 2 trigger + 1 job**:
   - `trg_docs_biu` (BEFORE): auto-assign status từ effective_date
   - `trg_cascade_expire` (AFTER): cascade expire khi VB mới có hiệu lực
   - `refresh_status_flags` (scheduled): self-heal dữ liệu cũ / lệch lạc

5. **document_relations + expiry fill**: khi thêm relation replaces/abolishes, tự động set `expiry_date = effective_date của VB mới` (có guard `new_eff >= old_eff`). Đây là cơ chế lan truyền hiệu lực chính.

6. **Validity-aware RAG**: 3 pass (mark validity → tìm replacement → re-rank + merge), với validity multiplier (expired ×0.35, not_yet ×0.70) để chunk hết hiệu lực không bao giờ đè lên VB hiện hành. Chuỗi thay thế transitive (BFS qua relations) quan trọng vì chain có thể dài nhiều tầng.

### Con số tham chiếu (hệ thống hiện tại)

- DB: PostgreSQL `legal_db`, container `legal-rag-pg`
- 663.941 chunks, 0 missing embeddings
- Relations: `replaces=522`, `abolishes=789`, `amends=2435`, `amends_partial=189`
- Ví dụ đã verify: 299/2026/NĐ-CP (LawID 717075) → replaces 120/2020 (LawID 379357), eff=2026-07-28; 298/2026/NĐ-CP (LawID 716629) → lv_411082 (243/2025), eff=2026-07-28

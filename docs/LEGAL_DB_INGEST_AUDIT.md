# CSDL pháp luật: schema, luồng nạp, trạng thái hiệu lực, và audit trước khi nạp lô mới

Ngày rà soát: 2026-11-22 · Branch `eval/contract-eval-v1` @ `7d0c599`

> **Cập nhật 2026-11-22: đã sửa B1–B4 và H1–H3.** Mục 7 ghi lại những gì đã thay đổi, cách kiểm chứng
> và quy trình nạp lô mới. Các mục 2–4 bên dưới mô tả trạng thái **trước khi sửa**.
> M1–M5 chưa sửa.

Phạm vi: `schema.sql` (bản sao `schemas/empty/contractlens_postgres.sql` đã diff, khớp 100%),
`scripts/ingest_legal_corpus.py`, `app/application/use_cases/legal_ingest.py`,
`app/infrastructure/legal_corpus/*`, `app/infrastructure/db/{legal_repository,hierarchy_chain}.py`,
`app/infrastructure/vector/pg_search.py`, `scripts/crawl_vbpl/*`.

Cách kiểm chứng: đọc code, rồi chạy `load_document_folder` (chỉ parse, không ghi DB) trên
`tests/fixtures/legal_sample` và trên mẫu thật `data/legal_corpus_samples/Bộ luật Hình sự số 100-2015-QH13--96122`.
**Chưa đối chiếu DB đang chạy**: container `contractlens-postgres-1` không start được vì port 5433 đang bị chiếm.
Các truy vấn ở mục 6 dùng để đo trên DB thật.

---

## 1. Schema hiện tại

### 1.1 Bảng

| Bảng | Khóa / ràng buộc | Vai trò |
|---|---|---|
| `legal_documents` | PK `doc_id` (id portal VBPL, ví dụ `96122`) | Metadata văn bản + `eff_from/eff_to/eff_flag/status_flag`. `path` = `sanitize(doc_num)` |
| `legal_parts` | `UNIQUE(doc_id, path)`, FK `doc_id` | Phần. Bảng cây **duy nhất** có `doc_id` |
| `legal_chapters` → `legal_sections` → `legal_sub_sections` → `legal_articles` → `legal_clauses` → `legal_points` | `path UNIQUE` **toàn cục**, FK tới cha, `ON DELETE CASCADE` | Chương/Mục/Tiểu mục/Điều/Khoản/Điểm. Cấp nào thiếu thì tạo dòng giàn giáo `title/content='Không có'`, path `._P/._C/._M/._TM` |
| `legal_embeddings` | `path UNIQUE` toàn cục, FK `doc_id` | **Chunk dùng cho RAG**: `chunk_text`, `embedding vector(1024)` (BGE-M3), `tsv` (FTS tự sinh), `is_effective`, `chunk_type` ∈ {body, preamble, effectivity, appendix, signature, other} |
| `legal_document_relations` | `UNIQUE(from, to, relation_type)`, FK 2 đầu | Cạnh VB↔VB từ `luoc_do.json` |
| `legal_path_relations` | `UNIQUE(source_path, target_path, ref_type)`, **không FK** | Cạnh Điều/Khoản/Điểm (dẫn chiếu nội bộ + sửa đổi/bãi bỏ cấp khoản) |
| `users`, `uploaded_contracts`, `contract_chunks` | | Phía hợp đồng người dùng, không liên quan corpus luật |

Index: GiST trên mọi `path`/`parent_path`, B-tree trên FK và `status_flag`, GIN trigram cho `doc_num`/`title`,
GIN cho `tsv`, HNSW (`m=16, ef_construction=64`) **chỉ trên dòng `is_effective AND embedding IS NOT NULL`**.

### 1.2 Mã `status_flag` và `eff_flag`

| status_flag | eff_flag (nhãn chuẩn) | Nhãn crawl được gộp vào |
|---|---|---|
| 0 | Chưa xác định | mọi nhãn không nhận ra |
| 1 | Còn hiệu lực | |
| 2 | Hết hiệu lực toàn bộ | Ngưng hiệu lực, Không còn phù hợp, Bãi bỏ |
| 3 | Chưa có hiệu lực | Sắp có hiệu lực |
| 4 | Hết hiệu lực một phần | Ngưng hiệu lực một phần, mã `SD`/`HHL1P` |
| 5 | Có hiệu lực một phần | |

Chuẩn hóa ở `thuoc_tinh_mapper.normalize_eff_flag` (nhãn trực tiếp → alias → mã → so khớp mờ).

---

## 2. Luồng nạp: từ thư mục gốc đến DB

Lệnh: `python -m scripts.ingest_legal_corpus PATH [--dry-run] [--limit N] [--force] [--reset-checkpoint]`

### 2.1 Đầu vào
`discover.py` chỉ nhận thư mục có **đủ 3 file**: `thuoc_tinh.json`, `muc_luc.json`, `van_ban.md`.
`luoc_do.json` là tùy chọn. Thiếu file nào thì thư mục bị **bỏ qua, không báo lỗi**.

### 2.2 Parse (`assemble.load_document_folder`)
1. `thuoc_tinh.json` → `map_thuoc_tinh`: chuẩn hóa `eff_flag`, suy ra `status_flag`.
2. `muc_luc.json` → `build_muc_luc_index`: mỗi node có một nhãn đường dẫn:
   Phần `P{n}`, Chương `C{n}`, Mục `M{n}`, Tiểu mục `TM{n}`, Điều `D{n}`, Khoản `K{n}`, Điểm `a..z` (`đ` → `dd`), Phụ lục `PL{n}`, Nhóm `N{n}`.
   Số được lấy từ tiêu đề (số La Mã, số thường, hoặc thứ tự bằng chữ). Nếu không đọc được số hoặc trùng với anh em
   thì dùng nhãn theo id, ví dụ `D_09556b702d`, để không lấy nhầm số của Điều khác.
3. **Điểm cắt chunk** (`cut_leaves`): Điểm; Khoản không có Điểm; Điều không có con.
4. `van_ban.md` → `van_ban_chunker.build_body_chunks`: lấy khoảng văn bản giữa các mốc `<!-- article_id -->` / `<!-- clause_id -->`.
   - Chunk Điểm = tiêu đề Điều + câu dẫn của Khoản + nội dung Điểm.
   - Chunk Khoản = tiêu đề Điều + nội dung Khoản.
   - Chunk Điều = tiêu đề + nội dung.
   - `chunk_type='effectivity'` nếu Điều có tên "Hiệu lực thi hành" hoặc "Tổ chức thực hiện".
   - Thêm `PREAMBLE` (phần trước Điều đầu tiên, cắt ở 12.000 ký tự) và `SIGN` (phần đuôi có "Nơi nhận"/"TM. Chính phủ"…, cắt ở 8.000 ký tự).
5. `appendix.build_appendix_chunks`: mỗi dòng bảng trong phụ lục là một chunk, kèm tiêu đề phụ lục và dòng header của bảng.
6. `internal_refs.extract_path_relations`: dò "Điều/Khoản/Điểm/Chương …" trong chunk để tạo cạnh `dan_chieu` trong cùng văn bản.
7. `luoc_do_flatten.flatten_luoc_do`: `relations.X` cho cạnh `doc → khác`; `relations_incoming.X` cho cạnh `khác → doc`.
   Văn bản ở đầu kia chưa có trong DB thì tạo stub (`status_flag=0`, `title` lấy từ lược đồ).

### 2.3 Ghi DB (`IngestLegalDocument.execute`). Thứ tự chạy, mỗi bước là một transaction riêng:
1. `legal_documents` upsert (ghi đè toàn bộ metadata).
2. Cây phân cấp `upsert_nodes`: sắp theo độ sâu, upsert từng cấp. `hierarchy_chain.ensure_*` tự tạo giàn giáo `Không có` khi thiếu cấp.
   Node không có hiệu lực riêng thì **kế thừa** `eff_from/eff_to/eff_flag/status_flag` của văn bản.
   Cột `content` của mọi node luôn là `'Không có'`; nội dung thật chỉ nằm trong `legal_embeddings`.
3. Embed toàn bộ chunk (BGE-M3), rồi upsert `legal_embeddings` theo `path`.
   `is_effective` mặc định = `status_flag của văn bản ∈ {1, 5}`.
4. `legal_document_relations` (tạo stub trước nếu cần).
5. `legal_path_relations`.
6. Ghi checkpoint `.legal_ingest_checkpoint.json` trong thư mục gốc.

Chạy tiếp (resume): bỏ qua doc đã có trong checkpoint **hoặc** đã có ≥1 chunk trong DB.
`--force` upsert đè lên, **không xóa** dòng cũ.

Cạnh cấp khoản từ `clause_amendments.json` được nạp riêng bằng `scripts/ingest_clause_amendments.py`.

### 2.4 Khóa đường dẫn (ltree): nguyên tắc dự kiến và thực tế

| Dữ liệu | Root label đang dùng | Ví dụ (Bộ luật Hình sự) |
|---|---|---|
| `legal_embeddings.path` | `sanitize(doc_id)` | `96122.P1.C1.D2.K1` |
| Cây 7 bảng `path` | `sanitize(doc_num)` | `100_2015_QH13.P1.C1.D2.K1` |
| `legal_documents.path` | `sanitize(doc_num)` | `100_2015_QH13` |
| `legal_path_relations` (dẫn chiếu nội bộ) | `doc_id` | `96122.…` |
| `legal_path_relations` (clause_amendments) | `doc_num` | `100_2015_QH13.…` |

Phần đuôi cấu trúc khớp nhau: trên mẫu, 3.719/3.719 chunk body đều có node cây cùng đuôi. **Chỉ có root label là lệch**.
Hệ quả xem B3 và B4.

---

## 3. Trạng thái hiệu lực được cập nhật thế nào

### 3.1 Trigger trên `legal_documents`
Các trigger cùng thời điểm chạy theo thứ tự tên (alphabet), nên `trg_docs_dates` chạy trước `trg_sync_eff_status`.

| Trigger | Khi nào | Làm gì |
|---|---|---|
| `trg_docs_dates` (BEFORE INSERT / UPDATE OF eff_from, eff_to) | | Bắt buộc `eff_from < eff_to`. `eff_from > hôm nay` → 3. `eff_to ≤ hôm nay` → 2. Đang trong khung ngày: giữ 4/5 nếu nhãn là "một phần", **còn lại ép về 1 'Còn hiệu lực'** |
| `trg_sync_eff_status` (BEFORE INSERT / UPDATE OF eff_flag, status_flag) | | Đồng bộ 2 chiều `eff_flag` ↔ `status_flag`, rồi áp lại khung ngày |
| `trg_cascade_expire` (AFTER UPDATE status_flag → 1) | Chỉ khi **UPDATE** (không chạy khi INSERT) | Văn bản bị nó `van_ban_bi_bai_bo`/`thay_the` → 2; bị nó `sua_doi_bo_sung` → 4 |

Chiều cạnh đã kiểm trên mẫu thật: `relations.thay_the` của BLHS 2015 trỏ tới 15/1999/QH10 (from = mới, to = cũ),
`relations_incoming.sua_doi_bo_sung` cho cạnh `175425 → 96122` (from = VB sửa, to = VB bị sửa). Chiều cascade khớp.

### 3.2 Trigger trên 7 bảng cây
`trg_hier_dates` và `trg_hier_sync_eff` giống bản cho văn bản. `trg_hier_cascade`: cha chuyển sang 2 thì con thành 2
(không tự hồi lại). `trg_hier_emb_eff`: khi status/path của node đổi, cập nhật `legal_embeddings.is_effective = status ∈ {1,5}`
cho chunk có `path <@ node.path`.

### 3.3 Hàm định kỳ (schema **không** có cron, phải gọi từ job bên ngoài)
- `refresh_status_flags()`: hết hạn theo `eff_to` → 2; chưa tới `eff_from` → 3; trong khung ngày và không phải 2/4/5 → 1;
  cascade theo quan hệ (cần văn bản mới có status = 1).
- `refresh_hierarchy_status_flags()`: 3 bước ngày tháng đầu, cho 7 bảng cây.

### 3.4 Lúc truy vấn
`pg_search._base_where` lọc `c.is_effective AND embedding IS NOT NULL AND d.status_flag <> 2`, loại `chunk_type` bị loại trừ.
Như vậy status 2 của **văn bản** luôn có tác dụng ngay. Mọi trạng thái khác chỉ có tác dụng qua `is_effective`.

### 3.5 Hợp đồng người dùng (để đủ bức tranh)
`uploaded_contracts.status`: `pending` → `parsed` → `awaiting_review` / `review_rejected` / `approved` → `analyzed`.
Cột này là TEXT tự do, không có CHECK.

---

## 4. Audit: các lỗi tìm được

Mức độ: **B** = chặn, phải sửa hoặc kiểm tra trước khi nạp; **H** = cao; **M** = trung bình; **L** = ghi chú.

### B1. Dữ liệu từ crawler hiện tại (`scripts/crawl_vbpl`) không nạp được
- `crawl_all.py` chỉ ghi `van_ban.md`, `thuoc_tinh.json`, `luoc_do.json`, **không có `muc_luc.json`**.
  `discover.py` yêu cầu file này, nên mọi thư mục crawl mới bị **bỏ qua im lặng**.
- `convert.build_luoc_do` ghi `relations: {loai: [ {...}, ... ]}` (dạng list), còn `flatten_luoc_do` đọc
  `bucket.get("documents")` (dạng dict). Đã chạy thử: `AttributeError: 'list' object has no attribute 'get'`,
  nghĩa là **mọi văn bản có quan hệ đều fail**.
- `REFERENCE_TYPE_NAMES` chỉ map mã 1 → `van_ban_bi_bai_bo` và mã 3 → `can_cu_ban_hanh`. Mã khác thành `reference_type_N`,
  nên `thay_the`, `sua_doi_bo_sung`, `dan_chieu` không bao giờ xuất hiện. Hệ quả: cascade và GraphRAG (`_related_docs`, `_repealed_by_docs`) không có dữ liệu.
- Bộ mẫu `data/legal_corpus_samples` (có `muc_luc.json`, `luoc_do` dạng `{count, documents}`) thì nạp được.
  **Cần xác định lô sắp nạp lấy từ nguồn nào.**

### B2. Văn bản status 4 / 3 bị ẩn hoàn toàn khỏi RAG, và không có cơ chế mở lại
`legal_ingest._build_chunks`: `is_effective = doc_status ∈ {1, 5}`.
- Mẫu Bộ luật Hình sự (status 4 "Hết hiệu lực một phần"): **3.721/3.721 chunk** sẽ có `is_effective = FALSE`, tức không tìm thấy qua vector hoặc FTS.
  Luật lớn thường ở trạng thái 4, nên lô mới sẽ lặp lại lỗi này hàng loạt. Hiện chỉ có `scripts/fix_labor_effectivity.py` vá tay cho 3 văn bản.
- Status 3 (chưa có hiệu lực): tới ngày có hiệu lực, `refresh_status_flags()` đổi văn bản sang 1, nhưng **không có gì đặt lại `is_effective`**.
  Văn bản bị ẩn vĩnh viễn.

### B3. Lệch root giữa chunk (`doc_id`) và cây (`doc_num`), nên trạng thái cấp điều khoản không bao giờ tới RAG
`assemble.py` truyền `path_root = doc_num` cho cây, nhưng chunker dùng `doc_id`.
Trigger `trg_hier_emb_eff` so `legal_embeddings.path <@ node.path`, và vì 2 root khác nhau nên **không bao giờ khớp**.
Comment trong schema ghi "SoT = hierarchy, is_effective là cache" là **sai với dữ liệu thật**.
Chính `fix_labor_effectivity.py` đã phải tự đổi root khi so. Ngoài ra `legal_path_relations` trộn 2 kiểu root
(dẫn chiếu nội bộ dùng `doc_id`, clause_amendments dùng `doc_num`), nên không join thẳng được với `legal_embeddings`.

### B4. Trùng `doc_num` thì cây của văn bản này bị gắn sang văn bản khác (im lặng)
`path` của 6 bảng cây (trừ Phần) là `UNIQUE` toàn cục và có root là `sanitize(doc_num)`. Ví dụ:
- Nhiều văn bản có số hiệu `"Không số"` (đã gặp trong stub: Hiến pháp 2013) cùng root `Kh_ng_s_`.
- `sanitize` biến mọi ký tự ngoài `[A-Za-z0-9_]` thành `_`, nên các số hiệu chỉ khác nhau ở `Đ`/`-`/`/` trùng nhau.

Khi văn bản thứ hai upsert `legal_chapters … ON CONFLICT (path) DO UPDATE SET part_id = EXCLUDED.part_id`,
chương của văn bản thứ nhất (kèm cả cây con qua FK) **chuyển sang văn bản thứ hai**. Không có lỗi hay log nào.
`legal_embeddings` không bị ảnh hưởng vì root là `doc_id` (duy nhất).

### H1. Nạp không nguyên tử; resume có thể đánh dấu "xong" một văn bản thiếu dữ liệu
4 bước ghi chạy trên 4 connection/transaction riêng. Bước embed (chậm nhất) chạy **sau khi** doc và cây đã commit.
Nếu lỗi sau khi chunk đã commit (ví dụ ở bước relations), lần chạy sau thấy `count_for_doc > 0`, tự ghi checkpoint "completed"
và **bỏ qua vĩnh viễn**: văn bản không có `legal_document_relations` / `legal_path_relations`.

### H2. `--force` / nạp lại không xóa dữ liệu cũ
Upsert theo `path` chỉ ghi đè những path vẫn còn. Khi nội dung nguồn hoặc logic cắt thay đổi (ví dụ đổi số Điều, hoặc nhãn `D_xxx` thành `D5`),
chunk cũ vẫn ở lại với `is_effective` cũ, gây **trùng nội dung trong RAG**. Node cây và path relation cũ cũng ở lại.

### H3. Trigger ngày tháng "hồi sinh" văn bản đã hết hiệu lực
`trg_docs_dates` / `trg_hier_dates`: nếu `eff_from ≤ hôm nay` và `eff_to IS NULL` thì mọi nhãn không phải "một phần" bị ép thành **1 'Còn hiệu lực'**,
kể cả `Hết hiệu lực toàn bộ`, `Ngưng hiệu lực`, `Không còn phù hợp`, `Chưa xác định`.
Văn bản crawl ghi "hết hiệu lực" nhưng thiếu `effTo` sẽ thành "còn hiệu lực" và **lọt vào RAG**.
Cascade đặt status 2 xong, lần upsert sau (UPDATE OF eff_from) lại đẩy về 1: trạng thái lật qua lật lại.

### M1. 70% `legal_path_relations` là cạnh rác tự trỏ về Điều cha
Mỗi chunk bắt đầu bằng tiêu đề "Điều N. …", và `parse_internal_refs` đọc luôn dòng này như một dẫn chiếu.
Mẫu BLHS: **3.676/5.204** cạnh là `K/Điểm → chính Điều chứa nó`. Hiện chưa có code trong `app/` đọc bảng này, nên RAG chưa bị ảnh hưởng, nhưng dữ liệu bị bẩn.

### M2. `status_flag or 1`: trạng thái 0 bị coi như 1
`legal_ingest.py` dùng `int(thuoc_tinh.get("status_flag") or 1)` (3 chỗ). Văn bản "Chưa xác định" (0) thì node kế thừa 1
và chunk `is_effective = TRUE`, trong khi dòng `legal_documents` lại bị trigger đặt về 0. Ba nơi không nhất quán.

### M3. Điều có tiêu đề mục lục chỉ là "Điều" thì nhận path `D_<id>`
Mẫu BLHS: 6/432 Điều (ví dụ `96122.P1.C1.D_09556b702d`). Không truy được theo "Điều N"
(ví dụ `find_article_chunks` dùng regex `D{n}`), dù số Điều vẫn đọc được từ heading trong `van_ban.md` (chunk vẫn có heading đó).

### M4. Khoản/Điểm bị bỏ im lặng khi không tìm thấy cha
`_upsert_clause` / `_upsert_point` gặp cha thiếu thì `return`, không log. Mẫu hiện có 0 trường hợp, nhưng không có cách phát hiện khi lô mới gặp.

### M5. Trạng thái tính theo ngày lúc ghi; không có job định kỳ
Mọi phép so với `CURRENT_DATE` chỉ đúng tại thời điểm INSERT/UPDATE. Phải có job ngoài gọi `refresh_status_flags()` và `refresh_hierarchy_status_flags()`.
Ngay cả khi có job, các hàm này **không cập nhật `is_effective`** (xem B2, B3).
`trg_cascade_expire` không chạy khi INSERT, nên cascade sau khi nạp cũng phụ thuộc vào `refresh_status_flags()`.

### L. Ghi chú thiết kế (không cần sửa ngay)
- Trong `app/`, **không có chỗ nào đọc 7 bảng cây hay `legal_path_relations`**; chỉ script audit/fix đọc. RAG chỉ đọc `legal_embeddings`
  (cây "anh em/tổ tiên" khi expand cũng tính bằng ltree trên `legal_embeddings`).
  7 bảng cùng 28 trigger hiện gần như chỉ để ghi. Đừng thêm logic vào đó trước khi sửa B3.
- Node `Meta`/`Appendix`/`Group` được dựng trong `assemble.py` nhưng `upsert_nodes` bỏ qua (code chết).
- Cắt im lặng: preamble 12.000, signature 8.000, appendix 8.000 ký tự.
- `relation_type`, `ref_type`, `uploaded_contracts.status` là TEXT tự do, không có CHECK.
- Stub văn bản từ `relations_incoming` thường không có `doc_num` (portal không trả), nên `doc_num = doc_id`.
- Phần đã đúng: `chunk_type` có CHECK; `eff_from < eff_to` có CHECK + trigger; path chunk không trùng trong một văn bản (0 trùng trên 3.721);
  không có chunk path NULL; độ dài chunk 40–2.108 ký tự (trung bình 335), nằm trong giới hạn BGE-M3; schema và bản sao đồng bộ.

---

## 5. Hướng sửa tối thiểu (đề xuất, chưa áp dụng)

| # | Sửa | Đụng tới | Giải quyết |
|---|---|---|---|
| 1 | `flatten_luoc_do` nhận cả bucket dạng list | `luoc_do_flatten.py` (~2 dòng) | B1 (phần luoc_do) |
| 2 | Quyết định nguồn `muc_luc.json` cho crawl mới (crawler mới chưa sinh file này) và bổ sung mã reference type đã xác minh | `scripts/crawl_vbpl` | B1 |
| 3 | Dùng **một** root là `sanitize(doc_id)` cho mọi path (cây, `legal_documents.path`, clause_amendments); DB cũ thì đổi label đầu của path cây (1 câu UPDATE mỗi bảng) hoặc nạp lại | `assemble.py`, `legal_repository.upsert`, `clause_amendments.py` | B3, B4 |
| 4 | `is_effective` mặc định = `status ∉ {2, 3}`; `refresh_status_flags()` thêm 1 câu UPDATE đồng bộ `is_effective` cho văn bản vừa đổi trạng thái | `legal_ingest.py`, `schema.sql` | B2 |
| 5 | Embed trước mọi lệnh ghi; resume chỉ tin checkpoint (bỏ heal theo `count_for_doc`) | `legal_ingest.py`, `ingest_legal_corpus.py` | H1 |
| 6 | Nạp lại: `DELETE FROM legal_embeddings / legal_parts WHERE doc_id=…` (cascade) trước khi ghi | `legal_ingest.py` | H2 |
| 7 | Trigger ngày: trong khung ngày chỉ nâng 0/3 lên 1, không hạ 2 | `schema.sql` (2 hàm) | H3 |
| 8 | Bỏ dòng tiêu đề Điều khi dò dẫn chiếu; `status_flag or 1` đổi thành `or 0`; log khi bỏ Khoản/Điểm | `internal_refs.py`, `legal_ingest.py`, `legal_repository.py` | M1, M2, M4 |

Thứ tự khuyến nghị: 1 → 3 → 4 → 5 → 6 → 7 → 8. Mục 2 tùy nguồn dữ liệu.

---

## 6. Kiểm tra trước và sau khi nạp (chỉ đọc)

```sql
-- Trước khi nạp: số hiệu trùng sau sanitize (B4)
SELECT sanitize_doc_id_for_ltree(doc_num) AS root, count(*), array_agg(doc_id)
FROM legal_documents GROUP BY 1 HAVING count(*) > 1 ORDER BY 2 DESC;

-- Văn bản mang nhãn hết hiệu lực nhưng đang ở status 1 (H3)
SELECT doc_id, doc_num, eff_flag, status_flag, eff_from, eff_to
FROM legal_documents WHERE status_flag = 1 AND eff_to IS NULL AND doc_num <> '';

-- Văn bản có chunk nhưng toàn bộ chunk bị ẩn (B2)
SELECT d.doc_id, d.doc_num, d.status_flag, count(*) AS chunks
FROM legal_documents d JOIN legal_embeddings e USING (doc_id)
GROUP BY 1, 2, 3 HAVING bool_and(NOT e.is_effective) ORDER BY chunks DESC;

-- Cây bị gắn nhầm văn bản (B4): Điều có root path khác root của văn bản sở hữu
SELECT a.path, p.doc_id, d.path AS doc_root
FROM legal_articles a
JOIN legal_sub_sections ss ON ss.id = a.sub_section_id
JOIN legal_sections s ON s.id = ss.section_id
JOIN legal_chapters c ON c.id = s.chapter_id
JOIN legal_parts p ON p.id = c.part_id
JOIN legal_documents d ON d.doc_id = p.doc_id
WHERE subpath(a.path, 0, 1) <> d.path LIMIT 50;

-- Văn bản thiếu quan hệ dù có luoc_do (H1): so với số liệu --dry-run
SELECT d.doc_id, count(r.*) FROM legal_documents d
LEFT JOIN legal_document_relations r ON r.from_doc_id = d.doc_id OR r.to_doc_id = d.doc_id
WHERE EXISTS (SELECT 1 FROM legal_embeddings e WHERE e.doc_id = d.doc_id)
GROUP BY 1 HAVING count(r.*) = 0;
```

Trước mỗi lô: chạy `python -m scripts.ingest_legal_corpus PATH --dry-run`. Nếu số thư mục tìm thấy ít hơn số thư mục có sẵn
thì đang thiếu `muc_luc.json` (B1).

---

## 7. Đã sửa (2026-11-22)

| Lỗi | Thay đổi | File |
|---|---|---|
| B1 | `flatten_luoc_do` đọc được cả bucket dạng list (`scripts/crawl_vbpl`) lẫn dạng `{count, documents}`. `muc_luc.json` thành **tùy chọn**: nếu thiếu thì dựng cây Phần/Chương/Mục/Điều/Khoản từ `van_ban.md` (dựa vào `## Điều …` + `<!-- article_id -->` và `<!-- clause_id -->`, bỏ qua tiêu đề Công báo lặp lại kiểu "Phần thứ hai"). Không có Điểm nên Khoản là đơn vị chunk nhỏ nhất | `luoc_do_flatten.py`, `muc_luc_derive.py` (mới), `discover.py`, `assemble.py`, `clause_amendments.py` |
| B3, B4 | **Một root duy nhất `sanitize(doc_id)`** cho cây 7 bảng, `legal_documents.path`, `legal_embeddings.path` và `legal_path_relations` (kể cả clause_amendments: nguồn không có `documentId` thì bỏ qua và ghi cảnh báo) | `assemble.py`, `legal_repository.py`, `clause_amendments.py` |
| B3, B4 (DB đang có) | `scripts/migrate_path_root_doc_id.py`: đổi root theo chuỗi FK (không dựa vào `doc_num`), chạy trong một transaction, mặc định dry-run. In danh sách văn bản đã mất cây vì trùng số hiệu, cần nạp lại | mới |
| B2 | Quy tắc tìm được: `is_effective = status NOT IN (2, 3)`, áp dụng cả lúc nạp lẫn trong trigger `trg_hier_emb_eff`. Status 4 không còn làm ẩn cả văn bản. `refresh_status_flags()` thêm bước 6 đồng bộ các chunk nằm ngoài Điều (preamble/appendix/sign) theo status văn bản. Chunk nằm dưới Điều thì đồng bộ qua `refresh_hierarchy_status_flags()` + trigger | `legal_ingest.py`, `schema.sql` |
| B2 (lỗi phát hiện khi test) | `trg_hier_emb_eff` trước khai báo `AFTER UPDATE OF status_flag`, nên không chạy khi status bị trigger ngày tháng đổi. Nay là `AFTER INSERT OR UPDATE` (hàm tự bỏ qua khi status/path không đổi) | `schema.sql` |
| H1 | `transaction()` mới trong `connection.py`: mọi `get_db()` bên trong dùng chung một connection và commit một lần. `ingest_legal_corpus` bọc mỗi văn bản trong một transaction; embed chạy trước mọi lệnh ghi. Nhờ vậy "đã có chunk trong DB" nghĩa là văn bản đã nạp đủ | `connection.py`, `legal_ingest.py`, `ingest_legal_corpus.py` |
| H2 | Trước khi ghi lại, `delete_doc_content(doc_id)` xóa chunk, cây (FK cascade) và các cạnh `dan_chieu` của chính văn bản. Giữ lại `legal_documents`, quan hệ VB↔VB và cạnh clause_amendments | `legal_repository.py`, port `LegalChunkRepository` |
| H3 | `is_full_expired_eff()`: trong khung ngày, nhãn Hết hiệu lực toàn bộ / Ngưng hiệu lực / Không còn phù hợp (hoặc status 2 không có nhãn) giữ nguyên 2, không bị ép về 1. Áp dụng cho cả `legal_documents` và 7 bảng cây | `schema.sql` |

Bản sao `schemas/empty/contractlens_postgres.sql` đã chép lại, giống hệt `schema.sql`.

### Kiểm chứng
- `pytest tests/unit`: 342 passed, 1 skipped. Test mới: luoc_do dạng list, thư mục không có `muc_luc.json`, tiêu đề Công báo lặp, root `doc_id`.
- Script chạy trên một Postgres **rỗng, tạm thời** (pgvector pg16), đạt cả 19/19 kiểm tra:
  1. Dựng schema cũ + dữ liệu kiểu cũ.
  2. Chạy migration `--apply`.
  3. Hết hạn một Điều thì chunk của Điều đó bị ẩn, Điều khác không bị ảnh hưởng.
  4. H3 với 6 tổ hợp nhãn/ngày.
  5. Nạp lại thì chunk/Điều cũ biến mất, cạnh `sua_doi` vẫn còn.
  6. Lỗi giữa chừng thì không còn dòng nào.
  7. Văn bản status 3 tới ngày có hiệu lực thì sau refresh tìm được cả chunk thân lẫn preamble/appendix.
  8. Hai văn bản cùng số hiệu "Không số" mỗi bên giữ 2 Điều riêng.
- **Chưa chạy trên DB thật** (`contractlens-postgres-1` không start được vì port 5433 bị chiếm).

### Quy trình nạp lô mới
1. Backup DB (`scripts/restore_db.*` hoặc `pg_dump`).
2. `python -m scripts.migrate_path_root_doc_id`: đọc kết quả dry-run, đặc biệt dòng "need re-ingest".
3. `python -m scripts.migrate_path_root_doc_id --apply`: áp `schema.sql` mới rồi đổi root. Việc đổi root kích hoạt trigger, nên `is_effective` của chunk dưới Điều được tính lại theo quy tắc mới (status 4 thành tìm được). `scripts/fix_labor_effectivity.py` vì thế không còn cần thiết.
4. Nạp lại các văn bản "need re-ingest": chạy `ingest_legal_corpus PATH --force` trên đúng các thư mục đó.
5. `python -m scripts.ingest_legal_corpus PATH --dry-run`: số thư mục tìm thấy phải bằng số thư mục crawl.
6. `python -m scripts.ingest_legal_corpus PATH`.
7. `SELECT * FROM refresh_status_flags(); SELECT refresh_hierarchy_status_flags();`, rồi chạy các truy vấn ở mục 6.
8. `python -m scripts.ingest_clause_amendments PATH` nếu lô có `clause_amendments.json`.

### Còn lại / giới hạn
- `scripts/crawl_vbpl/convert.py` vẫn chỉ biết mã reference 1 (`van_ban_bi_bai_bo`) và 3 (`can_cu_ban_hanh`). Mã khác thành `reference_type_N`, nên với dữ liệu crawl mới, cascade theo `thay_the`/`sua_doi_bo_sung` và GraphRAG related/repealed vẫn **không có dữ liệu**, cho tới khi mã được xác minh trên một văn bản thật.
- Cây dựng từ `van_ban.md` phụ thuộc chất lượng nguồn. Ví dụ trong mẫu BLHS, một tiêu đề "Chương VIII" bị mất chữ "Chương", nên các Điều của chương đó rơi vào Chương VII. So với `muc_luc.json` thật, 96% đường dẫn Điều/Khoản trùng khớp.
- Trigger đồng bộ từ node cha ghi đè lên cả chunk dưới node con. Hiện mọi node kế thừa cùng ngày tháng với văn bản nên chưa xảy ra xung đột. Khi có ngày hiệu lực riêng cho từng điều khoản thì cần xem lại.
- Nạp lại xóa rồi chèn chunk nên `legal_embeddings.id` đổi; bảng backup của `fix_labor_effectivity` (theo id) không revert được cho văn bản đã nạp lại.
- Văn bản từng nạp **dở** trước lần sửa này (có chunk nhưng thiếu quan hệ) vẫn bị bỏ qua khi resume. Dùng truy vấn cuối ở mục 6 để tìm, rồi chạy `--force` cho chúng.

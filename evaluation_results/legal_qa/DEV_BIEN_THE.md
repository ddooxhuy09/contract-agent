# Kết quả dev: 3 biến thể truy xuất đã khai báo trước

Tập: dev, `--only-covered`, n=216 (đóng băng `split.json`). Commit chạy: `551e9e2` (phạm vi dirty = `app/` và `evaluation/legal_qa_retrieval.py`, sạch). Không gọi LLM. Số liệu lấy từ `runs/*/metrics.json`; `predictions.jsonl` bị `.gitignore` nên chỉ có trên máy.

| Cấu hình | n | R@1 | R@5 [CI95] | R@10 | MRR@10 [CI95] | DocR@10 | Độ trễ median / p95 (ms) |
|---|---:|---:|---|---:|---|---:|---|
| fts (cũ) | 216 | 0,0185 | 0,0324 [0,0093; 0,0556] | 0,0324 | 0,0247 [0,0069; 0,0448] | 0,037 | 70,9 / 140,5 |
| fts + V1 | 216 | 0,0 | 0,0 [0,0; 0,0] | 0,0 | 0,0 [0,0; 0,0] | 0,0046 | 2.972,7 / 5.358,3 |
| vector | 216 | 0,625 | 0,7917 [0,7361; 0,8472] | 0,8241 | 0,7024 [0,6449; 0,7535] | 0,9259 | 171,5 / 210,1 |
| hybrid (cũ) | 216 | 0,6296 | 0,7731 [0,7176; 0,8287] | 0,7917 | 0,678 [0,6192; 0,7336] | 0,912 | 246,3 / 363,0 |
| hybrid + V1 | 216 | 0,6157 | 0,7546 [0,6944; 0,8056] | 0,7824 | 0,6621 [0,6029; 0,7196] | 0,8981 | 3.385,7 / 5.907,0 |
| hybrid + V2 | 216 | 0,6389 | 0,7546 [0,6944; 0,8056] | 0,787 | 0,6779 [0,6166; 0,7361] | 0,875 | 3.713,8 / 6.061,8 |
| hybrid + V3 | 216 | 0,6389 | 0,8009 [0,7454; 0,8519] | 0,8241 | 0,7112 [0,6545; 0,762] | 0,8981 | 3.898,1 / 6.293,3 |

## So sánh ghép cặp MRR@10 (bootstrap 95% trên cùng 216 câu; quy tắc khai báo trước)
| So sánh | Chênh MRR@10 | CI95 |
|---|---:|---|
| hybrid cũ − vector | −0,0244 | [−0,0347; −0,0152] |
| hybrid+V1 − vector | −0,0404 | [−0,0531; −0,0292] |
| hybrid+V2 − vector | −0,0245 | [−0,0392; −0,0097] |
| **hybrid+V3 − vector** | **+0,0088** | **[−0,0015; +0,0200]** |
| hybrid+V3 − hybrid cũ | +0,0332 | [+0,0180; +0,0504] |

## Kết luận (theo quy tắc đã khai báo)
- Biến thể có MRR@10 cao nhất: **V3** (0,7112). Đây là biến thể được chọn cho bước test.
- **Không có biến thể nào hơn vector rõ ràng**: CI của V3 − vector chứa 0. V3 chỉ hơn hybrid cũ có ý nghĩa (+0,033). Nên mô tả là "V3 bằng vector về chất lượng, hơn hybrid cũ", không tuyên bố hybrid vượt vector.
- V1 và V2 không cải thiện: V1 kém hybrid cũ; V2 xấp xỉ hybrid cũ và DocR@10 thấp hơn (0,875 so với 0,912).
- `fts + V1` gần như bằng 0 vì `ts_rank_cd` với truy vấn OR ưu tiên chunk rất dài chứa nhiều từ thông dụng (không lọc stopword, theo đúng khai báo). Đây là hành vi của biến thể chứ không phải lỗi cài đặt; không thử cách lọc stopword vì sẽ là biến thể thứ tư ngoài khai báo.
- **Độ trễ**: mọi cấu hình dùng OR chậm gấp khoảng 14–16 lần (median ~3,0–3,9 s so với 0,17–0,25 s) vì truy vấn OR khớp gần như toàn bộ ~1 triệu chunk. V3 như hiện tại không dùng được cho ứng dụng thật nếu không xử lý hiệu năng (việc đó nằm ngoài khai báo, chưa làm).
- Mô tả mức độ chắc chắn: n=216 nhỏ, chỉ gồm văn bản còn hiệu lực trong DB (24% dataset); V3 được chọn trên chính tập dev nên số dev của V3 hơi lạc quan.

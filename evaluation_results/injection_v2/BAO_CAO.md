# injection_v2: kết quả rule-only, code cũ vs code mới

Bảng đầy đủ: `REPORT.md` (sinh bởi `python -m evaluation.injection_v2.run report`). Bộ 32 ca đóng băng ở tag `injection-v2-frozen` (`fab1cef`); code cũ chạy ở `fab1cef`, code mới ở `04f1e6c`. Không LLM. Mỗi cấu hình chạy một lần (xác định, không ngẫu nhiên).

| Tổng (micro) | Cũ | Mới |
|---|---|---|
| TP / FP / FN | 16 / 16 / 0 | 8 / 8 / 8 |
| Precision [CI95] | 0,50 [0,31; 0,69] | 0,50 [0,23; 0,75] |
| Recall [CI95] | 1,00 [1,00; 1,00] | 0,50 [0,25; 0,76] |
| F1 [CI95] | 0,67 [0,48; 0,81] | 0,50 [0,25; 0,69] |
| Ca hợp lệ bị luật bất kỳ kích hoạt | 16/16 | 8/16 |

| Nhóm | n | Kích hoạt cũ | Kích hoạt mới |
|---|---:|---:|---:|
| Vi phạm V1 (mẫu quen) | 8 | 8 | 8 |
| Vi phạm V2 (có «không» khác gần cụm khóa) | 8 | 8 | 0 |
| Hợp lệ C1 (phủ định ngay trước cụm khóa) | 8 | 8 | 0 |
| Hợp lệ C2 (phủ định sau / bên trong cụm khóa) | 8 | 8 | 8 |

## Đọc kết quả
- Bước quét mới **bỏ được cả 8 báo nhầm kiểu C1**, nhưng **không xử lý C2** (phủ định đứng sau hoặc nằm giữa đoạn khớp): 8/8 vẫn bị báo.
- Cùng cơ chế cửa sổ 30 ký tự **làm mất cả 8 vi phạm V2**: câu như «không đền bù ngày phép và không trả lương tháng cuối» có chữ «không» thứ nhất trong cửa sổ, nên bị coi là phủ định. Recall trên bộ này vì thế giảm từ 1,00 xuống 0,50 và F1 giảm từ 0,67 xuống 0,50; precision giữ 0,50.
- Trên bộ này kết quả ròng là **không tốt hơn**: bớt 8 FP, thêm 8 FN. Bộ cân bằng cố ý giữa V2 và C1 (mỗi loại 8 ca), nên con số phản ánh sự đánh đổi của heuristic, **không phải tần suất ngoài thực tế**: V2 là những câu tác giả viết để thử điểm yếu này; chưa biết hợp đồng thật có bao nhiêu câu như vậy so với câu phủ định kiểu C1.
- Đã thêm test đơn vị (`tests/unit/test_red_flags_negation.py`, 11 test) và làm cửa sổ phủ định dừng ở dấu chấm/xuống dòng để một «không» ở câu trước không che vi phạm ở câu sau.
- **Chưa sửa tiếp**: khi cụm khóa tự bắt đầu bằng «không» (ví dụ «không đóng BHXH»), chữ «không» đứng trước không phải phủ định của nó; hạn chế cửa sổ theo hướng này sẽ giữ lại V2. Việc đó làm sau khi nhìn kết quả trên chính bộ này nên không được tính vào số liệu ở trên; nếu làm cần bộ ca mới.
- Giới hạn: n=32 do tác giả viết, chưa có chuyên gia xác nhận; bộ 80 ca cũ không chạy lại để báo số.

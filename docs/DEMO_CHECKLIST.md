# Checklist buổi demo

Cấu hình được đánh giá và trình diễn: judge **Groq `openai/gpt-oss-120b`** (nhiệt độ 0), truy xuất vector-only, `RED_FLAG_NEGATION_CHECK` tắt.

## 1. Trước buổi demo (làm sớm, không làm sát giờ)

1. Khởi động stack (từ thư mục dự án; không cần `--build` nếu image đã dựng):
   ```bash
   docker compose up -d
   ```
2. Đợi khoảng 1 đến 2 phút (API nạp mô hình bge-m3), rồi kiểm tra:
   ```bash
   curl http://localhost:8010/health
   ```
   Kết quả đúng: `{"status":"ok","service":"ContractLens",...}`. Giao diện ở `http://localhost:5173`.
3. Xác nhận API đang dùng Groq (in nhãn nhà cung cấp, không in key):
   ```bash
   docker exec contractlens-api-1 python -c "from app.agents.llm_client import get_providers;print(get_providers())"
   ```
   Phải thấy `'label': 'Groq openai/gpt-oss-120b'`.
4. Kiểm tra key Groq còn hạn mức (một lời gọi 5 token, chỉ in mã trạng thái và hạn mức còn lại, không in key):
   ```bash
   docker exec contractlens-api-1 python -c "import os,httpx;r=httpx.post('https://api.groq.com/openai/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ['GROG_KEY']},json={'model':'openai/gpt-oss-120b','messages':[{'role':'user','content':'ok'}],'max_tokens':5},timeout=30);print(r.status_code,{k:v for k,v in r.headers.items() if k.startswith('x-ratelimit-remaining')})"
   ```
   Mã `200` và `remaining` còn lớn là ổn. Mã `429` là hết hạn mức, chuyển sang mục 3.
5. Chạy thử đầy đủ một vòng (đăng nhập, mở hợp đồng, xem cờ, hỏi một câu). Hoặc chạy kịch bản tự động, từ thư mục dự án:
   ```bash
   python scripts/api_e2e.py http://127.0.0.1:8010 1
   ```
   Mong đợi: `chua_kiem: 0`, 5/5 Điều đã kiểm, khoảng 6 cờ, `qa_co_trich_dan: true`. Lệnh này tạo một tài khoản thử `e2e-*@example.com`; xóa sau buổi demo nếu không cần.

## 2. Trong buổi demo

- Tài khoản demo: `demo.defense@example.com`; mật khẩu do người làm đề tài giữ (không ghi trong repo). Tài khoản có sẵn một hợp đồng `hop_dong_demo.docx` đã phân tích, mở lại không gọi LLM.
- Hợp đồng demo ra 5 vấn đề nghiêm trọng, 1 cần chú ý. Tải hợp đồng mới lên mất khoảng 15 đến 25 giây để phân tích.
- **Hỏi câu pháp lý** như "Người lao động có được nghỉ phép năm không?" (trả lời có trích Điều 113 BLLĐ 2019 và Điều 23 NĐ 27/2014). Câu hỏi riêng của hợp đồng này như "ngày trả lương" sẽ bị hệ thống hỏi lại vì hợp đồng không ghi, đó là hành vi thiết kế, đừng ngạc nhiên.
- Khi trình bày kết quả đánh giá, nói đúng giới hạn: judge báo nhầm nhiều (62% ca hợp lệ trong 48 ca; 6/8 cờ trên hợp đồng nền), đầu ra là danh sách điểm cần người kiểm tra, không phải kết luận pháp lý. Chi tiết ở `docs/bo_test_hoi_dong/BO_TEST_HOI_DONG.md`.

## 3. Nếu Groq lỗi (429, hết hạn mức, mất mạng tới Groq)

1. Trong `.env` đặt `LLM_PROVIDER=gemini` và điền `GEMINI_API_KEY` (hoặc `GEMINI_API_KEY_1..3` để xoay vòng).
2. Áp dụng cấu hình, không cần build lại:
   ```bash
   docker compose up -d api
   ```
3. Kiểm tra lại bằng lệnh `get_providers()` ở mục 1.3; nhãn phải là `Gemini 2.5 Flash`.
4. Lưu ý: Gemini từng hết hạn mức ngày trong lúc đánh giá; kết quả đã trình bày trong chương 5 là của Groq, nên khi chuyển phải nói rõ là đang chạy bằng Gemini. Muốn quay lại: đặt `LLM_PROVIDER=groq` rồi `docker compose up -d api`.

## 4. Nếu cả hai LLM đều lỗi: bản ghi dự phòng

- Ảnh chụp màn hình trong `docs/demo_backup/`:
  1. `01_danh_sach_hop_dong.jpg`: danh sách hợp đồng
  2. `02_ket_qua_phan_tich_tom_tat.jpg`: kết quả phân tích, kết luận nhanh và các vấn đề ưu tiên
  3. `03_dieu_khoan_co_co_va_can_cu_luat.jpg`: một Điều bị gắn cờ cùng căn cứ pháp luật
  4. `04_hoi_dap_co_trich_dan.jpg`: một câu hỏi đáp có trích dẫn
- Báo cáo đã phân tích mở lại không gọi LLM: hợp đồng đã phân tích của tài khoản demo vẫn xem được khi LLM lỗi (kết quả lưu trong DB).
- Số liệu đánh giá: `docs/CHUONG_DANH_GIA_THUC_NGHIEM.md`, `evaluation_results/`.

## 5. Nhắc quan trọng

- **Không chạy script từ thư mục Temp của Windows** (`C:\Users\Lenovo\AppData\Local\Temp`). Ở đó có `h2.py` ngoài dự án; khi script nằm trong thư mục đó, `import h2` (gói HTTP/2 mà thư viện HTTP nạp) chạy nhầm file này và làm hỏng một lời gọi LLM. Nên đổi tên hoặc xóa `h2.py`. Chạy script luôn từ thư mục dự án.
- Không in hoặc commit giá trị key hay mật khẩu.
- Sau buổi demo: xóa các tài khoản thử `e2e-*` nếu có tạo thêm.

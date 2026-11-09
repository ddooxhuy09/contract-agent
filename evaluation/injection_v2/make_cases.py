"""Sinh cases.jsonl của bộ injection_v2 (32 ca = 8 luật x 4). Chạy một lần trước khi đóng băng."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
V1 = {json.loads(l)["rule_id"]: json.loads(l) for l in
      (HERE.parent / "injection" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

# rule_id: (prefix, slot, tiêu đề Điều, mã dòng, [4 ca])
# Mỗi ca: (hậu tố, nhãn, kiểu_câu, dạng_phủ_định, dòng thân, dự đoán regex CŨ, ghi chú)
SPEC = {
    "ot_unpaid": ("OT", 2, "Điều 2. Thời giờ làm việc và làm thêm giờ", "2.2", [
        ("V1", "violation", "formulaic", "none", "Thời gian làm thêm giờ không được tính thêm tiền lương làm thêm.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "Công ty không đền bù ngày nghỉ và không trả lương làm thêm cho thời gian làm việc ngoài giờ.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa (kiểm tra kiểm phủ định không nuốt vi phạm thật)."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty nghiêm cấm mọi hành vi không trả lương làm thêm giờ cho NLĐ.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc làm thêm giờ mà không trả lương làm thêm là hành vi bị pháp luật cấm và Công ty cam kết không thực hiện.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "no_bhxh": ("BH", 4, "Điều 4. Bảo hiểm", "4.1", [
        ("V1", "violation", "formulaic", "none", "Hai bên thỏa thuận Công ty không đóng BHXH, BHYT cho NLĐ; NLĐ tự chịu trách nhiệm về bảo hiểm của mình.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "Công ty không hỗ trợ viện phí và không tham gia đóng Bảo hiểm Xã hội cho NLĐ.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty không được thỏa thuận không đóng BHXH, BHYT với NLĐ dưới bất kỳ hình thức nào; Công ty đóng đầy đủ theo luật.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc thỏa thuận không đóng BHXH, BHYT là trái pháp luật và bị cấm; Công ty đóng đầy đủ cho NLĐ.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "retain_id_papers": ("GT", 5, "Điều 5. Giấy tờ của người lao động", "5.2", [
        ("V1", "violation", "formulaic", "none", "NLĐ bàn giao bản gốc Căn cước công dân và bằng cấp cho Công ty giữ trong suốt thời gian làm việc.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "Công ty không thu tiền cọc; Công ty giữ bản gốc CCCD của NLĐ đến hết thời gian thử việc.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty không giữ bản gốc CCCD, bằng cấp hay bất kỳ giấy tờ tùy thân nào của NLĐ; chỉ lưu bản sao.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc giữ bản gốc CCCD hoặc bằng cấp của NLĐ là hành vi bị pháp luật cấm, Công ty không thực hiện.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "training_cost_flat": ("DT", 6, "Điều 6. Đào tạo", "6.2", [
        ("V1", "violation", "formulaic", "none", "Nếu NLĐ nghỉ việc trong 24 tháng đầu, NLĐ phải bồi thường chi phí đào tạo tương đương 06 tháng lương.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "NLĐ không nghỉ việc khi chưa hết khóa học, nếu không NLĐ phải bồi thường chi phí đào tạo tương đương 12 tháng lương.", "hit", "Vi phạm thật; «nếu không» (điều kiện, không phải phủ định) nằm trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "NLĐ không phải bồi thường chi phí đào tạo đối với các khóa đào tạo nội bộ do Công ty tổ chức.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc NLĐ bồi thường chi phí đào tạo tương đương 06 tháng lương cố định là không được phép; hai bên chỉ hoàn trả theo hợp đồng đào tạo nghề và chi phí thực tế có chứng từ.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "fine_deduct_wage": ("KL", 7, "Điều 7. Kỷ luật lao động và trách nhiệm vật chất", "7.2", [
        ("V1", "violation", "formulaic", "none", "Hình thức kỷ luật phạt tiền: NLĐ đi muộn bị phạt 200.000 đồng/lần, khấu trừ trực tiếp vào tiền lương.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "Công ty không sa thải mà áp dụng kỷ luật phạt tiền bằng 10% lương tháng đối với lỗi vi phạm nội quy.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty không áp dụng hình thức kỷ luật phạt tiền đối với NLĐ.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc phạt tiền NLĐ và khấu trừ vào tiền lương thay cho xử lý kỷ luật là hành vi bị pháp luật nghiêm cấm.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "forfeit_wage_quit": ("LU", 8, "Điều 8. Chấm dứt hợp đồng do người lao động đơn phương", "8.2", [
        ("V1", "violation", "formulaic", "none", "NLĐ đơn phương chấm dứt hợp đồng trước thời hạn thì không được nhận lương của tháng cuối cùng.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "Công ty không đền bù ngày phép và không trả lương tháng cuối cho NLĐ nghỉ việc trước hạn.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty tuyệt đối không tước lương của NLĐ khi NLĐ chấm dứt hợp đồng; lương được thanh toán đầy đủ.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc tước lương tháng cuối của NLĐ khi nghỉ việc là trái luật nên Công ty không áp dụng.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "terminate_pregnancy": ("TS", 9, "Điều 9. Bảo vệ lao động nữ và chấm dứt hợp đồng", "9.2", [
        ("V1", "violation", "formulaic", "none", "Công ty có quyền chấm dứt hợp đồng lao động đối với lao động nữ khi lao động nữ kết hôn hoặc mang thai.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "Công ty không bố trí lại, có quyền chấm dứt hợp đồng khi NLĐ mang thai.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty không được đơn phương chấm dứt hợp đồng lao động vì lý do NLĐ kết hôn, mang thai, nghỉ thai sản hoặc nuôi con dưới 12 tháng tuổi.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "after", "Việc chấm dứt hợp đồng với lao động nữ vì lý do kết hôn hoặc mang thai là điều Công ty không bao giờ thực hiện và pháp luật cấm.", "trap", "Phủ định đứng sau cụm khóa."),
    ]),
    "ban_lawsuit": ("TC", 10, "Điều 10. Giải quyết tranh chấp", "10.1", [
        ("V1", "violation", "formulaic", "none", "Mọi tranh chấp do Giám đốc Công ty quyết định cuối cùng; NLĐ không được khởi kiện ra Tòa án.", "hit", "Mẫu quen thuộc."),
        ("V2", "violation", "unrelated_negation_nearby", "none", "NLĐ không cần ký lại và không được khởi kiện Công ty ra Tòa án về tranh chấp phát sinh.", "hit", "Vi phạm thật; có chữ «không» khác trong 30 ký tự trước cụm khóa."),
        ("C1", "compliant", "negation_trap", "direct_before", "Công ty cam kết không để Giám đốc quyết định cuối cùng các tranh chấp lao động; NLĐ có quyền khởi kiện ra Tòa án.", "trap", "Phủ định đứng ngay trước cụm khóa."),
        ("C2", "compliant", "negation_trap", "inside", "Giám đốc Công ty không có quyền quyết định cuối cùng về tranh chấp; NLĐ có quyền khởi kiện ra Tòa án.", "trap", "Phủ định nằm bên trong đoạn khớp của cụm khóa."),
    ]),
}

rows = []
for rule, (pre, slot, head, ref, items) in SPEC.items():
    for suffix, label, phrasing, neg, body, exp, note in items:
        rows.append({
            "case_id": f"{pre}2-{suffix}", "rule_id": rule, "label": label, "slot": slot,
            "clause_text": f"{head}\n{ref}. {body}",
            "legal_basis": V1[rule]["legal_basis"], "phrasing": phrasing, "negation_form": neg,
            "regex_expected": exp, "note": note,
        })
(HERE / "cases.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8", newline="\n")
print(len(rows), "cases")

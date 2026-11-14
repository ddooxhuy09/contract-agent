"""Sinh cases.jsonl cho injection_v3 (chạy một lần trước khi đóng băng; sau tag không chạy lại).

Mỗi luật 6 ca: 3 vi phạm (V-a mẫu quen, V-b diễn đạt lại, V-c dạng khác) + 3 hợp lệ
(C-a câu phủ định chứa từ khoá, C-b biến thể hợp pháp, C-c chỉ dẫn chiếu luật).
Ca được xoay vòng qua 3 hợp đồng nền A/B/C; {n} là số Điều của slot trong hợp đồng nền.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

RULES = ["ot_unpaid", "no_bhxh", "retain_id_papers", "training_cost_flat",
         "fine_deduct_wage", "forfeit_wage_quit", "terminate_pregnancy", "ban_lawsuit"]

BASIS = {
    "ot_unpaid": "BLLĐ 2019 Điều 98 khoản 1 (lương làm thêm giờ ít nhất 150%/200%/300%); Điều 107 khoản 1, 2 (làm thêm giờ phải được NLĐ đồng ý; không quá 50% giờ bình thường/ngày, 40 giờ/tháng, 200 giờ/năm trừ trường hợp luật cho phép)",
    "no_bhxh": "BLLĐ 2019 Điều 168 khoản 1 (NSDLĐ và NLĐ phải tham gia BHXH bắt buộc, BHYT, BHTN); Luật BHXH 2024 (41/2024/QH15) về tiền lương làm căn cứ đóng và hành vi bị nghiêm cấm (trốn đóng, đóng không đúng mức)",
    "retain_id_papers": "BLLĐ 2019 Điều 17 khoản 1 (không được giữ bản chính giấy tờ tùy thân, văn bằng, chứng chỉ của NLĐ), khoản 2 (không được yêu cầu NLĐ thực hiện biện pháp bảo đảm bằng tiền hoặc tài sản)",
    "training_cost_flat": "BLLĐ 2019 Điều 62 (hợp đồng đào tạo nghề; chi phí đào tạo là khoản chi có chứng từ hợp lệ); Điều 40 khoản 3 (hoàn trả chi phí đào tạo theo Điều 62)",
    "fine_deduct_wage": "BLLĐ 2019 Điều 127 khoản 2 (cấm phạt tiền, cắt lương thay cho xử lý kỷ luật); Điều 124 (hình thức kỷ luật); Điều 102 (khấu trừ lương chỉ để bồi thường thiệt hại tài sản theo Điều 129, không quá 30% tiền lương thực trả)",
    "forfeit_wage_quit": "BLLĐ 2019 Điều 94 khoản 1 (trả lương đầy đủ, đúng hạn); Điều 40 (nghĩa vụ của NLĐ chấm dứt trái luật: nửa tháng lương và tiền lương những ngày không báo trước); Điều 48 khoản 1 (thanh toán trong 14 ngày làm việc, kéo dài không quá 30 ngày trong trường hợp đặc biệt)",
    "terminate_pregnancy": "BLLĐ 2019 Điều 137 khoản 3 (không được sa thải hoặc đơn phương chấm dứt HĐLĐ vì kết hôn, mang thai, nghỉ thai sản, nuôi con dưới 12 tháng tuổi); Điều 138 khoản 1 (quyền đơn phương chấm dứt/tạm hoãn của lao động nữ mang thai); Điều 139 (nghỉ thai sản 06 tháng)",
    "ban_lawsuit": "BLLĐ 2019 Điều 179 (tranh chấp lao động); Điều 187, 188 (cơ quan có thẩm quyền và trình tự giải quyết tranh chấp lao động cá nhân: hòa giải viên lao động, Hội đồng trọng tài lao động, Tòa án nhân dân)",
}

REST = "{n}.2. NLĐ được nghỉ giữa giờ, nghỉ hằng tuần, nghỉ lễ, tết và nghỉ hằng năm có hưởng lương theo Bộ luật Lao động."
NOTICE = "{n}.1. NLĐ có quyền đơn phương chấm dứt hợp đồng lao động với thời hạn báo trước theo Điều 35 Bộ luật Lao động."

# (rule, kind, label, phrasing, body, note)
CASES = [
    # ---- ot_unpaid ----
    ("ot_unpaid", "V-a", "violation", "formulaic",
     "{n}.1. Thời giờ làm việc bình thường 08 giờ/ngày.\n" + REST + "\n{n}.3. Khi Công ty có nhu cầu, NLĐ làm thêm giờ và thời gian làm thêm giờ không được tính lương.",
     "làm thêm giờ không trả lương"),
    ("ot_unpaid", "V-b", "violation", "paraphrase",
     "{n}.1. Thời giờ làm việc bình thường 08 giờ/ngày.\n" + REST + "\n{n}.3. Mức lương thỏa thuận trong hợp đồng đã bao gồm toàn bộ thời gian NLĐ ở lại sau giờ làm việc để hoàn thành công việc được giao; Công ty không chi thêm bất kỳ khoản nào cho thời gian này.",
     "giờ ở lại sau ca không được trả, không có từ «làm thêm»"),
    ("ot_unpaid", "V-c", "violation", "number_words",
     "{n}.1. Thời giờ làm việc bình thường 08 giờ/ngày.\n" + REST + "\n{n}.3. NLĐ có nghĩa vụ làm thêm giờ theo phân công của quản lý, tối đa bốn giờ mỗi ngày và sáu mươi giờ mỗi tháng, và không được từ chối.",
     "bắt buộc làm thêm, vượt 40 giờ/tháng (Điều 107)"),
    ("ot_unpaid", "C-a", "compliant", "negation_trap",
     "{n}.1. Thời giờ làm việc bình thường 08 giờ/ngày.\n" + REST + "\n{n}.3. Công ty chỉ bố trí làm thêm giờ khi NLĐ đồng ý và nghiêm cấm việc không trả lương làm thêm giờ; tiền lương làm thêm ít nhất bằng 150% vào ngày thường, 200% vào ngày nghỉ hằng tuần, 300% vào ngày lễ, tết.",
     "phủ định chứa cụm khoá «không trả lương làm thêm»"),
    ("ot_unpaid", "C-b", "compliant", "lawful_variant",
     "{n}.1. Thời giờ làm việc bình thường 08 giờ/ngày.\n" + REST + "\n{n}.3. Khi NLĐ đồng ý làm thêm giờ, tiền lương làm thêm được tính theo đơn giá tiền lương của công việc đang làm, ít nhất bằng 150% vào ngày thường, 200% vào ngày nghỉ hằng tuần, 300% vào ngày lễ, tết, ngày nghỉ có hưởng lương; số giờ làm thêm không quá 40 giờ trong 01 tháng và 200 giờ trong 01 năm.",
     "nêu cụ thể mức lương và giới hạn, đúng luật"),
    ("ot_unpaid", "C-c", "compliant", "law_reference",
     "{n}.1. Thời giờ làm việc bình thường 08 giờ/ngày.\n{n}.2. Thời giờ nghỉ ngơi và làm thêm giờ (nếu có) thực hiện theo quy định của Bộ luật Lao động.",
     "chỉ dẫn chiếu luật, không chép lại giới hạn"),
    # ---- no_bhxh ----
    ("no_bhxh", "V-a", "violation", "formulaic",
     "{n}.1. Hai bên thỏa thuận Công ty không đóng BHXH cho NLĐ trong 06 tháng đầu của hợp đồng.\n{n}.2. Từ tháng thứ 07, Công ty và NLĐ đóng BHXH, BHYT, BHTN theo quy định.",
     "hoãn đóng BHXH 6 tháng đầu"),
    ("no_bhxh", "V-b", "violation", "paraphrase",
     "{n}.1. Theo đề nghị của NLĐ, Công ty chi trả phần bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp vào lương hằng tháng để NLĐ tự quyết định việc tham gia; Công ty không kê khai NLĐ với cơ quan bảo hiểm xã hội.",
     "trả tiền thay đóng bảo hiểm, không có từ khoá «không đóng»"),
    ("no_bhxh", "V-c", "violation", "other",
     "{n}.1. Công ty và NLĐ đóng bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp trên mức tiền lương 5.000.000 đồng/tháng, thấp hơn mức lương ghi trong hợp đồng, nhằm giảm chi phí cho cả hai bên.",
     "đóng thấp hơn tiền lương hợp đồng"),
    ("no_bhxh", "C-a", "compliant", "negation_trap",
     "{n}.1. Công ty và NLĐ tham gia bảo hiểm xã hội bắt buộc, bảo hiểm y tế, bảo hiểm thất nghiệp trên tiền lương ghi trong hợp đồng.\n{n}.2. Công ty bảo đảm không để xảy ra tình trạng không đóng BHXH hoặc đóng chậm cho NLĐ; nếu chậm đóng, Công ty chịu toàn bộ tiền lãi chậm đóng.",
     "phủ định chứa cụm khoá «không đóng BHXH»"),
    ("no_bhxh", "C-b", "compliant", "lawful_variant",
     "{n}.1. Công ty và NLĐ đóng bảo hiểm xã hội bắt buộc, bảo hiểm y tế, bảo hiểm thất nghiệp hằng tháng trên tiền lương ghi trong hợp đồng.\n{n}.2. Tháng nào NLĐ không làm việc và không hưởng tiền lương từ 14 ngày làm việc trở lên thì không đóng BHXH tháng đó; thời gian này không được tính để hưởng bảo hiểm xã hội, trừ trường hợp nghỉ việc hưởng chế độ thai sản.",
     "ngoại lệ 14 ngày theo Luật BHXH; chứa «không đóng BHXH»"),
    ("no_bhxh", "C-c", "compliant", "law_reference",
     "{n}.1. Chế độ bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp: hai bên tham gia theo quy định của pháp luật hiện hành.",
     "chỉ dẫn chiếu luật"),
    # ---- retain_id_papers ----
    ("retain_id_papers", "V-a", "violation", "formulaic",
     "{n}.1. Khi nhận việc, NLĐ bàn giao bản gốc CCCD và bằng tốt nghiệp cho phòng Nhân sự; Công ty hoàn trả khi NLĐ nghỉ việc.",
     "giữ bản gốc giấy tờ"),
    ("retain_id_papers", "V-b", "violation", "paraphrase",
     "{n}.1. Để bảo đảm NLĐ gắn bó lâu dài, NLĐ nộp văn bằng chuyên môn bản chính; phòng Nhân sự quản lý văn bằng này trong suốt thời hạn hợp đồng.",
     "giữ văn bằng bản chính, không dùng «giữ/bản gốc»"),
    ("retain_id_papers", "V-c", "violation", "other",
     "{n}.1. NLĐ đặt cọc 3.000.000 (ba triệu) đồng khi ký hợp đồng để bảo đảm thực hiện hợp đồng; khoản cọc được hoàn lại khi NLĐ làm đủ thời hạn hợp đồng.",
     "biện pháp bảo đảm bằng tiền (Điều 17 khoản 2), cùng Điều luật với luật giữ giấy tờ"),
    ("retain_id_papers", "C-a", "compliant", "negation_trap",
     "{n}.1. Công ty không giữ bản gốc giấy tờ tùy thân, văn bằng, chứng chỉ của NLĐ; NLĐ chỉ nộp bản sao có chứng thực cho hồ sơ nhân sự.",
     "phủ định chứa cụm khoá «giữ bản gốc»"),
    ("retain_id_papers", "C-b", "compliant", "lawful_variant",
     "{n}.1. NLĐ xuất trình bản chính Căn cước công dân và văn bằng để phòng Nhân sự đối chiếu khi ký hợp đồng, nhận lại ngay sau khi đối chiếu; Công ty lưu bản sao.",
     "xuất trình để đối chiếu rồi trả lại"),
    ("retain_id_papers", "C-c", "compliant", "law_reference",
     "{n}.1. NLĐ cung cấp hồ sơ nhân sự theo yêu cầu của Công ty phù hợp với quy định của pháp luật lao động.",
     "chỉ dẫn chiếu luật"),
    # ---- training_cost_flat ----
    ("training_cost_flat", "V-a", "violation", "formulaic",
     "{n}.1. Công ty cử NLĐ đi đào tạo chuyên môn. Nếu nghỉ việc trước 24 tháng kể từ khi kết thúc khóa học, NLĐ phải bồi thường chi phí đào tạo bằng 06 tháng lương, không phụ thuộc chi phí thực tế.",
     "bồi thường cố định theo tháng lương"),
    ("training_cost_flat", "V-b", "violation", "paraphrase",
     "{n}.1. Công ty tổ chức bồi dưỡng nghiệp vụ cho NLĐ theo kế hoạch hằng năm.\n{n}.2. NLĐ được cử đi học mà chấm dứt hợp đồng trong vòng hai năm sau khóa học thì nộp lại cho Công ty một khoản cố định 50.000.000 đồng, không cần đối chiếu hóa đơn, chứng từ.",
     "khoản cố định không theo chứng từ, không có cụm «chi phí đào tạo»"),
    ("training_cost_flat", "V-c", "violation", "other",
     "{n}.1. Công ty tổ chức đào tạo hội nhập cho NLĐ mới.\n{n}.2. Mọi NLĐ nghỉ việc trong năm đầu tiên đều phải hoàn trả phí đào tạo hội nhập 5.000.000 đồng.",
     "thu phí đào tạo hội nhập cố định, không có hợp đồng đào tạo nghề"),
    ("training_cost_flat", "C-a", "compliant", "negation_trap",
     "{n}.1. Công ty tổ chức đào tạo hội nhập và đào tạo nghiệp vụ nội bộ cho NLĐ.\n{n}.2. NLĐ không phải bồi thường chi phí đào tạo đối với các khóa đào tạo hội nhập và đào tạo nghiệp vụ nội bộ do Công ty tổ chức.",
     "phủ định chứa cụm khoá «bồi thường chi phí đào tạo»"),
    ("training_cost_flat", "C-b", "compliant", "lawful_variant",
     "{n}.1. Công ty tổ chức bồi dưỡng nâng cao trình độ kỹ năng nghề cho NLĐ theo kế hoạch hằng năm.\n{n}.2. Khi NLĐ được cử đi đào tạo bằng kinh phí của Công ty, hai bên ký hợp đồng đào tạo nghề ghi rõ chi phí đào tạo có chứng từ hợp lệ và thời hạn cam kết làm việc; NLĐ vi phạm cam kết thì hoàn trả chi phí đào tạo tương ứng với thời gian cam kết còn lại theo hợp đồng đào tạo.",
     "hoàn trả theo chứng từ, tỷ lệ thời gian còn lại"),
    ("training_cost_flat", "C-c", "compliant", "law_reference",
     "{n}.1. Công ty tổ chức đào tạo, bồi dưỡng nâng cao trình độ, kỹ năng nghề cho NLĐ theo kế hoạch hằng năm; quyền và nghĩa vụ của hai bên khi đào tạo thực hiện theo Bộ luật Lao động.",
     "chỉ dẫn chiếu luật"),
    # ---- fine_deduct_wage ----
    ("fine_deduct_wage", "V-a", "violation", "formulaic",
     "{n}.1. NLĐ chấp hành nội quy lao động của Công ty.\n{n}.2. NLĐ đi làm muộn quá 03 lần trong tháng bị kỷ luật phạt tiền 200.000 đồng mỗi lần, khấu trừ trực tiếp vào tiền lương.",
     "phạt tiền, khấu trừ lương"),
    ("fine_deduct_wage", "V-b", "violation", "paraphrase",
     "{n}.1. NLĐ chấp hành nội quy lao động của Công ty.\n{n}.2. NLĐ không đạt chỉ tiêu công việc của tháng sẽ bị giảm 10% lương của tháng đó như một hình thức xử lý vi phạm.",
     "cắt lương thay xử lý kỷ luật"),
    ("fine_deduct_wage", "V-c", "violation", "number_words",
     "{n}.1. NLĐ chấp hành nội quy lao động của Công ty.\n{n}.2. NLĐ làm sai quy trình lần thứ hai trong quý bị trừ năm trăm nghìn đồng vào thu nhập tháng.",
     "trừ tiền bằng chữ, không có «phạt tiền/khấu trừ»"),
    ("fine_deduct_wage", "C-a", "compliant", "negation_trap",
     "{n}.1. NLĐ chấp hành nội quy lao động của Công ty.\n{n}.2. Công ty không áp dụng hình thức kỷ luật phạt tiền và không khấu trừ trực tiếp vào tiền lương để thay cho việc xử lý kỷ luật lao động.",
     "phủ định chứa hai cụm khoá"),
    ("fine_deduct_wage", "C-b", "compliant", "lawful_variant",
     "{n}.1. NLĐ chấp hành nội quy lao động; việc xử lý kỷ luật theo Điều 124 Bộ luật Lao động.\n{n}.2. NLĐ làm hư hỏng dụng cụ, thiết bị do lỗi của mình thì bồi thường theo Điều 129 Bộ luật Lao động; Công ty có thể khấu trừ tiền lương hằng tháng để bồi thường nhưng không quá 30% tiền lương thực trả sau khi trích nộp bảo hiểm bắt buộc và thuế thu nhập cá nhân.",
     "khấu trừ bồi thường thiệt hại theo Điều 102"),
    ("fine_deduct_wage", "C-c", "compliant", "law_reference",
     "{n}.1. NLĐ chấp hành nội quy lao động. Hình thức, trình tự xử lý kỷ luật lao động thực hiện theo Bộ luật Lao động và nội quy lao động của Công ty.",
     "chỉ dẫn chiếu luật"),
    # ---- forfeit_wage_quit ----
    ("forfeit_wage_quit", "V-a", "violation", "formulaic",
     NOTICE + "\n{n}.2. NLĐ nghỉ việc mà không báo trước đủ thời hạn thì không được nhận lương của tháng cuối cùng làm việc.",
     "mất lương tháng cuối"),
    ("forfeit_wage_quit", "V-b", "violation", "paraphrase",
     NOTICE + "\n{n}.2. Trường hợp NLĐ tự ý nghỉ việc, toàn bộ tiền lương và thưởng chưa thanh toán được Công ty giữ lại để bù đắp thiệt hại.",
     "giữ lại toàn bộ lương chưa trả"),
    ("forfeit_wage_quit", "V-c", "violation", "number_words",
     NOTICE + "\n{n}.2. Khi chấm dứt hợp đồng, Công ty thanh toán các khoản liên quan đến quyền lợi của NLĐ trong vòng sáu mươi ngày.",
     "thanh toán quá thời hạn Điều 48"),
    ("forfeit_wage_quit", "C-a", "compliant", "negation_trap",
     NOTICE + "\n{n}.2. NLĐ chấm dứt hợp đồng vẫn được nhận đủ tiền lương những ngày đã làm việc; Công ty không trả lương tháng cuối chậm quá 14 ngày làm việc kể từ ngày chấm dứt hợp đồng.",
     "phủ định chứa cụm khoá «không trả lương tháng cuối»"),
    ("forfeit_wage_quit", "C-b", "compliant", "lawful_variant",
     NOTICE + "\n{n}.2. NLĐ đơn phương chấm dứt hợp đồng trái pháp luật thì phải bồi thường cho Công ty nửa tháng tiền lương theo hợp đồng và tiền lương tương ứng với những ngày không báo trước; Công ty vẫn thanh toán đầy đủ tiền lương những ngày NLĐ đã làm việc trong thời hạn 14 ngày làm việc.",
     "nghĩa vụ bồi thường theo Điều 40"),
    ("forfeit_wage_quit", "C-c", "compliant", "law_reference",
     "{n}.1. Quyền đơn phương chấm dứt hợp đồng của mỗi bên, thời hạn báo trước và trách nhiệm thanh toán khi chấm dứt thực hiện theo Bộ luật Lao động.",
     "chỉ dẫn chiếu luật"),
    # ---- terminate_pregnancy ----
    ("terminate_pregnancy", "V-a", "violation", "formulaic",
     "{n}.1. Công ty thực hiện chế độ thai sản theo Luật Bảo hiểm xã hội.\n{n}.2. Công ty có quyền đơn phương chấm dứt hợp đồng lao động đối với lao động nữ mang thai nếu vị trí công việc không bố trí được người thay thế.",
     "chấm dứt vì mang thai"),
    ("terminate_pregnancy", "V-b", "violation", "paraphrase",
     "{n}.1. Công ty thực hiện chế độ thai sản theo Luật Bảo hiểm xã hội.\n{n}.2. Lao động nữ nghỉ sinh con quá 04 tháng được coi là không còn nhu cầu làm việc và Công ty sẽ thanh lý hợp đồng.",
     "thanh lý hợp đồng khi nghỉ thai sản, không có «chấm dứt/mang thai»"),
    ("terminate_pregnancy", "V-c", "violation", "other",
     "{n}.1. Công ty thực hiện chế độ thai sản theo Luật Bảo hiểm xã hội.\n{n}.2. NLĐ nữ cam kết không sinh con trong 24 tháng đầu làm việc; vi phạm cam kết này là căn cứ để Công ty kết thúc hợp đồng.",
     "cam kết không sinh con, kết thúc hợp đồng"),
    ("terminate_pregnancy", "C-a", "compliant", "negation_trap",
     "{n}.1. Công ty thực hiện chế độ thai sản theo Luật Bảo hiểm xã hội.\n{n}.2. Công ty không được sa thải hoặc đơn phương chấm dứt hợp đồng lao động với lao động nữ vì lý do kết hôn, mang thai, nghỉ thai sản, nuôi con dưới 12 tháng tuổi.",
     "nhắc lại điều cấm, chứa cụm khoá"),
    ("terminate_pregnancy", "C-b", "compliant", "lawful_variant",
     "{n}.1. Công ty thực hiện chế độ thai sản theo Luật Bảo hiểm xã hội.\n{n}.2. Lao động nữ mang thai có quyền đơn phương chấm dứt hoặc tạm hoãn hợp đồng lao động nếu có xác nhận của cơ sở khám bệnh, chữa bệnh có thẩm quyền về việc tiếp tục làm việc sẽ ảnh hưởng xấu tới thai nhi.",
     "quyền của NLĐ theo Điều 138, chứa «mang thai … chấm dứt»"),
    ("terminate_pregnancy", "C-c", "compliant", "law_reference",
     "{n}.1. Công ty thực hiện các chế độ đối với lao động nữ và bảo đảm bình đẳng giới theo Chương X Bộ luật Lao động.",
     "chỉ dẫn chiếu luật"),
    # ---- ban_lawsuit ----
    ("ban_lawsuit", "V-a", "violation", "formulaic",
     "{n}.1. Mọi tranh chấp được giải quyết nội bộ; NLĐ không được khởi kiện Công ty ra Tòa án trong mọi trường hợp.",
     "cấm khởi kiện"),
    ("ban_lawsuit", "V-b", "violation", "paraphrase",
     "{n}.1. Tranh chấp phát sinh do Tổng Giám đốc Công ty xem xét; kết luận của Tổng Giám đốc là kết quả giải quyết sau cùng mà hai bên phải thi hành.",
     "người đứng đầu NSDLĐ quyết định chung thẩm, không khớp mẫu «quyết định cuối cùng»"),
    ("ban_lawsuit", "V-c", "violation", "other",
     "{n}.1. NLĐ cam kết từ bỏ quyền yêu cầu hòa giải viên lao động, Hội đồng trọng tài lao động và Tòa án giải quyết tranh chấp phát sinh từ hợp đồng này.",
     "từ bỏ quyền yêu cầu giải quyết"),
    ("ban_lawsuit", "C-a", "compliant", "negation_trap",
     "{n}.1. Công ty không có quyền buộc NLĐ cam kết không được khởi kiện; NLĐ có quyền yêu cầu hòa giải viên lao động, Hội đồng trọng tài lao động hoặc Tòa án nhân dân giải quyết tranh chấp theo Điều 187, 188 Bộ luật Lao động.",
     "phủ định chứa cụm khoá «không được khởi kiện»"),
    ("ban_lawsuit", "C-b", "compliant", "lawful_variant",
     "{n}.1. Tranh chấp lao động cá nhân trước hết được giải quyết thông qua hòa giải viên lao động, trừ các trường hợp không bắt buộc qua hòa giải theo Điều 188 Bộ luật Lao động; hòa giải không thành thì mỗi bên có quyền yêu cầu Hội đồng trọng tài lao động hoặc Tòa án nhân dân giải quyết.",
     "trình tự hòa giải bắt buộc đúng luật"),
    ("ban_lawsuit", "C-c", "compliant", "law_reference",
     "{n}.1. Tranh chấp phát sinh được giải quyết theo quy định của pháp luật về lao động.",
     "chỉ dẫn chiếu luật"),
]

PREFIX = {"ot_unpaid": "OT", "no_bhxh": "BH", "retain_id_papers": "GT", "training_cost_flat": "DT",
          "fine_deduct_wage": "KL", "forfeit_wage_quit": "LU", "terminate_pregnancy": "TS", "ban_lawsuit": "TC"}
BASES = ["A", "B", "C"]
KINDS_V, KINDS_C = ["V-a", "V-b", "V-c"], ["C-a", "C-b", "C-c"]


def base_for(rule: str, kind: str) -> str:
    """Xoay vòng: mỗi luật có đúng 1 vi phạm và 1 hợp lệ trên mỗi hợp đồng nền."""
    i = RULES.index(rule)
    if kind in KINDS_V:
        return BASES[(i + KINDS_V.index(kind)) % 3]
    return BASES[(i + 1 + KINDS_C.index(kind)) % 3]


def main() -> None:
    assert len(CASES) == 48 and len({(r, k) for r, k, *_ in CASES}) == 48
    rows = []
    for rule, kind, label, phrasing, body, note in CASES:
        rows.append({
            "case_id": f"{PREFIX[rule]}-{kind.replace('-', '')}",
            "base": base_for(rule, kind), "rule_id": rule, "label": label, "kind": kind,
            "phrasing": phrasing, "body": body, "legal_basis": BASIS[rule], "note": note,
        })
    with (HERE / "cases.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} cases")


if __name__ == "__main__":
    main()

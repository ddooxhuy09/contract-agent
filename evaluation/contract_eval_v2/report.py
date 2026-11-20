"""Render the paired dev report from metrics and per-case evidence."""
from pathlib import Path

from evaluation.contract_eval_v2.experiment import DEFAULT, ROOT, read_json, rows


def percent(value):
    return "chưa có" if value is None else f"{100 * value:.1f}%"


def interval(value):
    return "chưa có" if value is None else f"[{100 * value[0]:+.1f}; {100 * value[1]:+.1f}] điểm %"


def plot(metrics):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    before, after = metrics["qa"]["baseline"], metrics["qa"]["grounded"]
    baseline = [metrics["retrieval"]["baseline"]["legal_recall@5"], before["correctness"], before["fully_correct"], before["source_clause_hit"]]
    grounded = [metrics["retrieval"]["grounded"]["legal_recall@5"], after["correctness"], after["fully_correct"], after["source_clause_hit"]]
    if any(v is None for v in baseline + grounded):
        return None
    fig, ax = plt.subplots(figsize=(12.8, 6.7))
    for offset, values, color, label in [(-.19, baseline, "#64748b", "Trước sửa"), (.19, grounded, "#0f766e", "Sau sửa")]:
        bars = ax.bar([i + offset for i in range(4)], [v * 100 for v in values], width=.35, color=color, label=label)
        ax.bar_label(bars, labels=[f"{v * 100:.1f}%" for v in values], padding=5, fontsize=12)
    ax.set_xticks(range(4), ["Tìm luật R@5\n72 câu", "QA correctness\n32 câu / cấu hình", "QA đúng đủ\n32 câu / cấu hình", "Nguồn Điều đúng\n32 câu / cấu hình"], fontsize=11)
    ax.set_ylim(0, 102)
    ax.set_ylabel("Điểm / tỷ lệ (%)", fontsize=12)
    ax.set_title("Cải tiến QA: so sánh trên cùng tập dev", loc="left", fontsize=18, pad=20)
    ax.legend(frameon=False, loc="upper left", ncols=2)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=.2)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(.08, .035, "16 ca gốc tổng hợp; các biến thể cùng ca có liên quan. QA chấm bằng LLM judge.\nĐây là kết quả dev, chưa phải test độc lập hoặc xác nhận của chuyên gia.", fontsize=10, color="#475569")
    fig.subplots_adjust(left=.08, right=.98, top=.86, bottom=.23)
    target = ROOT / "docs/bo_test_hoi_dong/QA_DEV_TRUOC_SAU.png"
    fig.savefig(target, dpi=150, facecolor="white")
    plt.close(fig)
    return target


def report(output=DEFAULT):
    m = read_json(output / "metrics.json")
    audit = read_json(Path(__file__).parent / "QUALITY_AUDIT.json")
    b, r, g = (m["retrieval"][s] for s in ("baseline", "reference_only", "grounded"))
    qb, qg = (m["qa"][s] for s in ("baseline", "grounded"))
    if qb["judged"] < qb["expected"] or qg["judged"] < qg["expected"]:
        qa_interpretation = "QA chưa chấm đủ, chưa kết luận cải thiện câu trả lời."
    elif m["paired_qa_delta_ci95_cluster"][0] > 0:
        qa_interpretation = "QA tăng điểm theo judge và CI95 chênh lệch trên 0 trong tập dev này; còn cần người kiểm và test độc lập."
    elif m["paired_qa_delta"] > 0:
        qa_interpretation = "QA tăng điểm trung bình nhưng CI95 chưa loại được chênh lệch 0; chưa có bằng chứng chắc chắn về mức tăng."
    elif m["paired_qa_delta"] < 0:
        qa_interpretation = "QA giảm điểm trung bình dù retrieval tốt hơn; không được tuyên bố đã cải thiện toàn bộ hệ thống."
    else:
        qa_interpretation = "QA chưa tăng điểm trung bình; cải thiện retrieval chưa chuyển thành cải thiện câu trả lời."
    text = [
        "# ContractLens: bộ test đã được làm rõ và kết quả cải tiến có đối chứng",
        "", "Ngày: 18/11/2026. Đây là thí nghiệm **dev sau v1**, không phải điểm test giữ kín mới.", "",
        "**Kết luận và số liệu chính**", "",
        f"Đã sửa QA để lấy đúng Điều hợp đồng được hỏi rồi dùng nội dung Điều đó để tìm luật. "
        f"Trên cùng tập dev, R@5 luật tăng từ **{percent(b['legal_recall@5'])} lên {percent(g['legal_recall@5'])}** "
        f"({g['legal_scored']} câu có căn cứ gold; {m['n_base_cases']} ca gốc). "
        f"CI95 của chênh lệch, lấy mẫu theo ca gốc: {interval(m['paired_recall_delta_ci95_cluster'])}.",
        "", qa_interpretation,
        "", "| Chỉ số | Trước sửa | Sau sửa | Mẫu số/ý nghĩa |", "|---|---:|---:|---|",
        f"| Retrieval luật R@5 | {percent(b['legal_recall@5'])} | {percent(g['legal_recall@5'])} | 72 câu có gold luật; 16 ca gốc |",
        f"| R@5 riêng câu T1 | {percent(b['by_variant']['T1']['recall@5'])} | {percent(g['by_variant']['T1']['recall@5'])} | 16 câu chỉ nêu số Điều |",
        f"| R@5 sau đổi số Điều | {percent(b['by_variant']['renumbered']['recall@5'])} | {percent(g['by_variant']['renumbered']['recall@5'])} | 16 câu, cùng nội dung nghĩa vụ |",
        f"| QA correctness trung bình | {percent(qb['correctness'])} | {percent(qg['correctness'])} | {qb['judged']}/{qb['expected']} và {qg['judged']}/{qg['expected']} câu được judge chấm |",
        f"| QA đúng đủ 2/2 | {percent(qb['fully_correct'])} | {percent(qg['fully_correct'])} | Tỷ lệ đạt trọn điểm, khác correctness trung bình |",
        f"| QA kết luận khớp nhãn | {percent(qb['conclusion_match'])} | {percent(qg['conclusion_match'])} | Nhãn kế thừa, chưa có người xác nhận |",
        f"| QA faithfulness | {percent(qb.get('faithfulness'))} | {percent(qg.get('faithfulness'))} | {qb.get('faithfulness_scored', 0)}/32 và {qg.get('faithfulness_scored', 0)}/32 câu có mệnh đề để chấm |",
        f"| QA trả đúng nguồn Điều hợp đồng | {percent(qb['source_clause_hit'])} | {percent(qg['source_clause_hit'])} | `source_clauses` chứa Điều gold |",
        "", f"QA theo cặp: **{m['qa_changes']['improved']} câu tốt lên, {m['qa_changes']['regressed']} câu xấu đi, "
        f"{m['qa_changes']['unchanged']} câu không đổi**. CI95 của chênh correctness: {interval(m['paired_qa_delta_ci95_cluster'])}.",
        "", "Số QA là đánh giá tự động bằng LLM judge chưa được người hiệu chuẩn trên đầu ra này. "
        "Không dùng các số dev này thay điểm test v1, không suy ra tỷ lệ đúng trên hợp đồng thực tế, "
        "không so trực tiếp điểm QA dev này với 0,51 trên toàn test v1.", "",
        "**1. Đã làm gì khác so với chỉ viết lại báo cáo?**", "",
        "- Sửa mã chạy thật trong QA; giữ API, prompt sinh, auth, streaming, retry và checkpointer.",
        "- Tạo bộ dev có 80 câu hỏi, đáp án tách riêng, đường dẫn/id trung tính, hash dữ liệu và hợp đồng.",
        "- Thêm đổi cách hỏi và đổi số Điều để kiểm tra hệ thống có phụ thuộc mẫu/vị trí không.",
        "- Chạy ba cấu hình retrieval để phân biệt tác động lấy đúng Điều với tác động đưa nội dung vào truy vấn luật.",
        "- Chạy QA trước/sau trên cùng đầu vào; lưu câu trả lời, nguồn, context thực, token và thời gian.",
        "- Xuất audit chất lượng, kết quả từng ca và bảng kiểm nhãn/đầu ra cho người duyệt.",
        "- Có 17 test tự động mới; toàn bộ test không integration: 372 passed, 1 skipped trong container.", "",
        "**2. Bộ test đến từ đâu, số nào là hợp đồng, số nào là câu?**", "",
        "```text", "Bộ hợp nhất v1: 154 ca gốc → 378 câu",
        "├─ injection:    80 ca × 3 câu = 240", "├─ injection_v2: 32 ca × 3 câu =  96",
        "├─ fixture QA:    8 câu", "└─ v04:          34 tình huống giả lập",
        "   Loại 3 ca gốc / 9 câu → 151 ca gốc / 369 câu",
        "   ├─ dev:  23 ca gốc /  55 câu", "   └─ test: 128 ca gốc / 314 câu",
        "", "Thí nghiệm hiện tại: chỉ lấy 16 ca injection trong dev v1",
        "└─ mỗi ca: T1 + T2 + T3 + hỏi lại + đổi số Điều = 5 câu",
        "   → 80 câu / 16 ca gốc / 32 văn bản hợp đồng (16 gốc + 16 đổi số)", "```", "",
        "Các hợp đồng này là tổng hợp, dùng chung nền 11 Điều. Mỗi nhóm có ca vi phạm và ca hợp lệ gần giống. "
        "Đáp án được kế thừa từ cách xây ca và kiểm chéo v1; không sinh lại nhãn để khớp kết quả. "
        "Các ca có quan hệ với nhau, nên không coi 80 câu hoặc 32 văn bản là những mẫu độc lập hoàn toàn.", "",
        "Bộ Zalo bên ngoài chỉ dùng để đánh giá truy xuất pháp luật riêng, không được gộp vào 80 câu dev này "
        "và không chứng minh QA hợp đồng tốt. Chi tiết nguồn v1 ở báo cáo phân tích đi kèm.", "",
        "**3. Vì sao phép chấm rõ hơn?**", "",
        "| Phép đo | Số kỳ vọng | Số hoàn tất | Số được chấm |",
        "|---|---:|---:|---:|",
        *[f"| Retrieval {name} | {s['expected']} | {s['completed']} | {s['legal_scored']} có gold luật |"
          for name, s in (("baseline", b), ("reference_only", r), ("grounded", g))],
        f"| QA baseline | {qb['expected']} | {qb['completed']} | {qb['judged']} |",
        f"| QA grounded | {qg['expected']} | {qg['completed']} | {qg['judged']} |", "",
        "Tám câu T3 trên ca hợp lệ không có gold luật/Điều cần tìm nên không chấm recall luật. "
        "Chúng vẫn nằm trong bộ và trong số hoàn tất, không bị loại vì hệ thống trả lời khó. "
        "QA chọn trước 32 câu T1 gốc/đổi số; không lấy các câu trả lời đẹp để chọn mẫu sau khi chạy.", "",
        "R@5 đo mức bao phủ căn cứ gold trong năm kết quả, không phải độ chính xác câu trả lời. "
        "Correctness là điểm trung bình 0–2 chuẩn hóa; tỷ lệ đúng đủ là số câu đạt 2/2. "
        "Faithfulness là mức context hỗ trợ các mệnh đề, không tự xác minh luật đúng. Câu chỉ hỏi ngược không có mệnh đề "
        "được bỏ khỏi trung bình faithfulness, nên bảng ghi riêng 31/32 và 30/32; correctness vẫn chấm đủ 32 câu mỗi bên. "
        "Khoảng tin cậy lấy mẫu theo 16 ca gốc; vẫn chưa xử lý hết phụ thuộc do dùng chung hợp đồng nền.", "",
        "**4. Đối chứng cho thấy chính xác điều gì?**", "",
        "| Cấu hình | Cách lấy Điều | Truy vấn luật | R@5 |", "|---|---|---|---:|",
        f"| baseline | Vector như cũ | Câu hỏi | {percent(b['legal_recall@5'])} |",
        f"| reference_only | Ưu tiên đúng số Điều được hỏi | Vẫn chỉ câu hỏi | {percent(r['legal_recall@5'])} |",
        f"| grounded | Ưu tiên đúng số Điều được hỏi | Câu hỏi + nội dung Điều | {percent(g['legal_recall@5'])} |", "",
        "Lấy đúng Điều nhưng không đưa nội dung đó vào tìm luật chưa cải thiện recall luật. "
        "Sự tăng điểm nằm ở cấu hình có nội dung Điều. Đây là bằng chứng cho việc thiếu thông tin truy vấn, "
        "không phải bằng chứng chỉ cần đổi vector sang hybrid hoặc tăng số kết quả là đủ.", "",
        "| Kiểu câu hỏi | n chấm luật | Trước | Sau |", "|---|---:|---:|---:|",
        *[f"| {v} | {b['by_variant'][v]['n']} | {percent(b['by_variant'][v]['recall@5'])} | {percent(g['by_variant'][v]['recall@5'])} |"
          for v in ("T1", "T2", "T3", "paraphrase", "renumbered")], "",
        "T2 và T3 giữ nguyên truy vấn theo thiết kế nên chưa được cải thiện bởi thay đổi này. "
        "Điểm giữa T1 và đổi số Điều chưa hoàn toàn bằng nhau: truy vấn vẫn chứa các số/diễn đạt có thể "
        "ảnh hưởng embedding. Chưa thể tuyên bố hệ thống bất biến với việc đánh số.", "",
        "**5. Báo nhầm và giới hạn của đầu ra**", "",
    ]
    figure = plot(m)
    if figure:
        text[4:4] = [f"![So sánh trước/sau trên dev]({figure.as_posix()})", ""]
    for name, summary in (("Trước", qb), ("Sau", qg)):
        alarm = summary.get("false_alarm", {"numerator": 0, "denominator": 0})
        text.append(f"- {name}: báo vi phạm trên ca gold hợp lệ {alarm['numerator']}/{alarm['denominator']} câu. "
                    "Các câu gốc/đổi số dùng cùng ca, không phải những hợp đồng hợp lệ độc lập.")
    text += ["", "| Nhãn gold QA | Kết luận của máy (qua judge) | Trước | Sau |", "|---|---|---:|---:|"]
    for label, label_vi in (("violation", "Vi phạm"), ("compliant", "Hợp lệ")):
        for prediction, prediction_vi in (("violation", "Vi phạm"), ("compliant", "Hợp lệ"), ("unclear", "Chưa kết luận / hỏi lại")):
            text.append(f"| {label_vi} | {prediction_vi} | {qb['confusion'][label][prediction]} | {qg['confusion'][label][prediction]} |")
    text += ["", "Trên 16 câu gold vi phạm, bản sau vẫn có 3 câu kết luận hợp lệ và 3 câu chưa kết luận. "
             "Số câu vi phạm bị kết luận hợp lệ tăng từ 2 lên 3, dù tổng điểm tăng. Đây là lỗi phải xử lý, không che bằng điểm trung bình. "
             "Không dùng 0/16 báo nhầm QA để thay tỷ lệ báo nhầm 20/49 của bước phát hiện rủi ro v1: hai phép đo khác nhau."]
    text += ["", "Truy xuất tốt hơn chưa bảo đảm kết luận tốt hơn. Cần đọc các ca xấu đi, kiểm nhãn còn tranh cãi "
             "và xem LLM có thực sự áp dụng đúng điều kiện/ngoại lệ. Không sửa nhãn theo câu trả lời của model.", "",
             "**6. Ví dụ trước/sau để tự kiểm tra**", ""]
    answers = {(x["id"], x["system"]): x for x in rows(output / "qa.jsonl")}
    gold = {x["id"]: x for x in rows(output / "gold.jsonl")}
    changes = read_json(output / "paired_qa_changes.json")
    examples = sorted([x for x in changes if x["delta"] > 0], key=lambda x: (-x["delta"], x["id"]))[:2]
    examples += sorted([x for x in changes if x["delta"] < 0], key=lambda x: (x["delta"], x["id"]))[:2]
    for example in examples:
        uid = example["id"]
        text += [f"**{uid} — nguồn {example['source_id']}; điểm {example['baseline']}/2 → {example['grounded']}/2**", "",
                 f"Câu hỏi: {gold[uid]['question']} Nhãn kế thừa: `{gold[uid]['gold_label']}`.", ""]
        for name, system in (("Trước", "baseline"), ("Sau", "grounded")):
            excerpt = answers[uid, system]["answer"].replace("\n", " ")[:650]
            text.append(f"- {name}: {excerpt}…")
        text += ["", "Đây là trích đoạn minh họa theo điểm judge; mở trace và `human_review.csv` để kiểm đầy đủ.", ""]
    text += ["**7. Những điều còn thiếu để báo cáo thuyết phục ở mức đồ án**", "",
        "| Điều kiện | Bằng chứng hiện tại | Việc còn cần |", "|---|---|---|",
        f"| Dữ liệu v1 còn nguyên | {sum(audit['frozen_files_match'].values())}/6 hash khớp | Giữ nguyên v1 và test.lock |",
        f"| Nhãn do người kiểm | {audit['human_review']['user_approved']}/112 ô duyệt được điền | Người có chuyên môn xem nhãn và căn cứ |",
        "| Gold set 30 Điều | Hai người gán và chuyên gia đều chưa điền nhãn | Gán độc lập; không dùng nhãn AI thay người |",
        "| Test mới giữ kín | Chưa có trong thí nghiệm này | Thu thập đa nền/nguồn, gán nhãn trước, khóa trước khi chọn cấu hình |",
        "| Workflow phân tích toàn hợp đồng | F1 v1 dùng Điều gold chỉ sẵn | Đo cả tìm Điều, luật cố định, LLM, hợp nhất và cảnh báo trên nền sạch |",
        "| QA nhiều lượt và streaming | Chưa đo trong thí nghiệm dev này | Có tập riêng nếu đưa thành tuyên bố của đồ án |",
        "| Temporal | V1 đang gộp 27 test + 7 dev trong nhóm 34 câu | Báo riêng test; xác minh phiên bản và adapter xuất cạnh |", "",
        "Một tập dev tốt hơn không tự biến thành benchmark pháp lý đáng tin cậy. "
        "Phần không thể tự hoàn tất thay người là xác nhận nhãn độc lập và bổ sung hợp đồng thực tế được phép sử dụng. "
        "Đã tạo `LABEL_REVIEW.csv` cho 16 ca nguồn và `human_review.csv` cho đầu ra để công việc này có đầu vào cụ thể.", "",
        "Về khả năng tái lập: hai cấu hình dùng cùng DB bản sao; snapshot có 137.151 văn bản, 1.004.988 embedding "
        "và 660.960 quan hệ văn bản. Đây là snapshot số lượng, không phải hash toàn nội dung corpus. "
        "64/64 truy vấn và danh sách path trong trace QA khớp bước retrieval tương ứng. "
        "64 lượt sinh dùng 227.409 token; 64 lượt judge dùng 137.519 token theo usage API. "
        "Độ trễ QA trung vị quan sát khoảng 2,54 → 3,06 giây; có cache và warm-up, chưa phải benchmark hiệu năng độc lập.", "",
        "**8. Thứ tự cải thiện tiếp theo dựa trên bằng chứng**", "",
        "1. Kiểm thủ công các ca regression và ca compliant bị báo nhầm trong bảng đầu ra. Chốt lại nhãn có tranh cãi trước khi tối ưu kết luận.",
        "2. Cải thiện áp dụng phủ định/ngoại lệ và phân biệt thiếu dữ kiện với vi phạm; luôn theo dõi recall để tránh đổi báo nhầm lấy bỏ sót.",
        "3. Kiểm soát định danh nguồn: phân biệt Điều hợp đồng với Điều luật; xác minh căn cứ có hỗ trợ kết luận, không chỉ tồn tại trong kho.",
        "4. Thiết kế riêng truy vấn cho câu tổng quát T3; thay đổi hiện tại chưa xử lý loại này.",
        "5. Chốt phương pháp, chuẩn bị holdout mới đa dạng và đánh giá toàn luồng. Dùng v1/dev làm hồi quy, không công bố điểm dev như test độc lập.", "",
        "**9. File nào nên đọc và dùng để bảo vệ?**", "",
        "- Báo cáo này: kết luận trước/sau, nguồn, mẫu số, đối chứng và giới hạn.",
        "- `evaluation/contract_eval_v2/QUALITY_AUDIT.json`: bằng chứng kiểm chất lượng v1.",
        "- `evaluation/contract_eval_v2/README.md`: phương pháp, quy tắc, lệnh tái lập.",
        "- `evaluation/contract_eval_v2/artifacts/dev_clause_grounding/metrics.json`: số tổng hợp.",
        "- `per_case_metrics.json`, `paired_qa_changes.json`: điểm từng ca và regression.",
        "- `retrieval.jsonl`, `qa.jsonl`, `judge.jsonl`: nguồn, câu trả lời và lý do chấm thực tế.",
        "- `LABEL_REVIEW.csv`, `human_review.csv`: phần cần người xác minh.", "",
        "Chưa commit/push. Các hợp đồng dev mới ở DB bản sao dưới user `contract-eval-v2-dev@example.invalid`; "
        "không tự xóa. Ruff toàn repo còn F401 đã có ở `evaluation/check_chapter_numbers.py`; các file thay đổi qua kiểm tra F.", ""]
    target = ROOT / "docs/bo_test_hoi_dong/CAI_THIEN_V2_KET_QUA_VA_BANG_CHUNG.md"
    target.write_text("\n".join(text), encoding="utf-8")
    return target


if __name__ == "__main__":
    print(report())

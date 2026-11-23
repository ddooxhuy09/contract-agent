"""Render complete results for the frozen research round, without selecting runs."""
from evaluation.contract_eval_v2 import experiment as exp
from evaluation.contract_eval_v2.research_round import OUTPUT, SPLITS, check_protocol


def pct(value):
    return "chưa có" if value is None else f"{value * 100:.1f}%"


def ci(value):
    return "chưa có" if not value else f"[{value[0] * 100:+.1f}; {value[1] * 100:+.1f}] điểm %"


def report():
    check_protocol()
    metrics = {split: exp.read_json(OUTPUT / split / "metrics.json") for split in SPLITS}
    labels = {"dev": "Dev đã phân tích", "regression_test": "Regression từ test v1", "fresh_source_checked": "Ca mới đối chiếu nguồn"}
    text = ["# Kết quả vòng v3: cải tiến có nghiên cứu, truy xuất thật và chấm thật", "",
        "Ngày 18/11/2026. Điểm là số đo tự động trên các nhóm dữ liệu tổng hợp dưới đây; không thay nhãn hoặc rubric để tăng điểm.", "",
        "**Kết quả trước/sau**", "",
        "Baseline là **v2 đã có nội dung Điều hợp đồng**; candidate là code mới với truy xuất chính xác theo chủ đề, tinh lọc căn cứ và prompt QA mới. "
        "Không dùng baseline yếu chỉ tìm từ câu hỏi để làm mức tăng trông lớn hơn.", "",
        "| Nhóm | QA / cấu hình | Correctness trước → sau | Đúng đủ trước → sau | Kết luận đúng trước → sau | Nguồn Điều đúng trước → sau |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for split, m in metrics.items():
        b, g = m["qa"]["baseline"], m["qa"]["grounded"]
        text.append(f"| {labels[split]} | {b['judged']}/{b['expected']}; {g['judged']}/{g['expected']} | {pct(b['correctness'])} → **{pct(g['correctness'])}** | {pct(b['fully_correct'])} → **{pct(g['fully_correct'])}** | {pct(b['conclusion_match'])} → **{pct(g['conclusion_match'])}** | {pct(b['source_clause_hit'])} → **{pct(g['source_clause_hit'])}** |")
    text += ["", "Correctness là điểm trung bình 0–2 chuẩn hóa 0–1; đúng đủ là tỷ lệ câu đạt 2/2. Không coi hai đại lượng này là cùng một tỷ lệ chính xác.", "",
        "**Đã chạy những gì?**", "",
        "- 80 câu dev từ 16 ca gốc: T1/T2/T3, hỏi lại và đổi số Điều. Retrieval chấm 72 câu có gold luật; QA chấm trước 32 câu T1/đổi số mỗi cấu hình.",
        "- 32 ca regression chọn cân bằng, có seed, từ test v1: tám nhóm × hai nguồn × một vi phạm/một hợp lệ. Không trùng ca gốc dev. Đã dùng trong v1 nên không gọi là test hoàn toàn mới giữ kín.",
        "- Tám ca mới về giới hạn thử việc, lương thử việc và nghỉ hằng năm: bốn vi phạm/bốn hợp lệ, viết trước khi chạy từ nguồn Chính phủ. Do tác giả code soạn và chưa có chuyên gia duyệt nên không phải benchmark độc lập.",
        "- Cùng GPT-OSS-120b sinh, cùng Qwen judge, cùng embedding BGE-M3, cùng kho luật và cùng rubric. Baseline và candidate chạy xen kẽ trên cùng đầu vào. Cả nhãn lẫn cách chấm được giữ nguyên trong vòng này.",
        "- Đáp án gold đọc ở bước chấm; lúc inference chỉ có câu hỏi, hợp đồng và ngữ cảnh lấy qua repository. Không có nhãn/gold Điều luật trong prompt hệ thống.", "",
        "**Truy xuất, mức hỗ trợ bởi nguồn và chi phí**", "",
        "| Nhóm | R@5 luật trước → sau | n có gold luật | Faithfulness trước → sau | n faithfulness trước/sau |",
        "|---|---:|---:|---:|---:|",
    ]
    totals = {"generation_calls": 0, "generation_tokens": 0, "judge_calls": 0, "judge_tokens": 0}
    for split, m in metrics.items():
        b, g = m["qa"]["baseline"], m["qa"]["grounded"]
        rb, rg = m["retrieval"]["baseline"], m["retrieval"]["grounded"]
        text.append(f"| {labels[split]} | {pct(rb['legal_recall@5'])} → **{pct(rg['legal_recall@5'])}** | {rb['legal_scored']}; {rg['legal_scored']} | {pct(b.get('faithfulness'))} → {pct(g.get('faithfulness'))} | {b.get('faithfulness_scored', 0)}; {g.get('faithfulness_scored', 0)} |")
        for row in exp.rows(OUTPUT / split / "qa.jsonl"):
            totals["generation_calls"] += row["usage"]["llm_calls"]
            totals["generation_tokens"] += row["usage"]["tokens"]
        if (OUTPUT / split / "judge_metadata.json").exists():
            jm = exp.read_json(OUTPUT / split / "judge_metadata.json")
            totals["judge_calls"] += jm["calls_this_process"]
            totals["judge_tokens"] += jm["tokens_this_process"]
    text += ["", "Faithfulness chỉ chấm câu có mệnh đề; câu hỏi ngược hoặc không có mệnh đề được báo bằng mẫu số riêng, không âm thầm coi là đúng. Correctness vẫn tính đủ các câu được judge chấm.", "",
        f"Usage API: {totals['generation_calls']} lượt gọi sinh, {totals['generation_tokens']:,} token; "
        f"{totals['judge_calls']} lượt judge, {totals['judge_tokens']:,} token. Không quy đổi thành tiền khi chưa có hóa đơn/bảng giá tài khoản.", "",
        "**So sánh theo cặp và các ca còn sai**", "",
    ]
    for split, m in metrics.items():
        change = m["qa_changes"]
        text += [f"**{labels[split]}**", "",
            f"- {change['improved']} câu tăng điểm, {change['regressed']} câu giảm, {change['unchanged']} câu không đổi.",
            f"- CI95 chênh correctness: {ci(m['paired_qa_delta_ci95_cluster'])}; CI95 chênh R@5: {ci(m['paired_recall_delta_ci95_cluster'])}.",
            "- Bootstrap 1.000 lần theo ca gốc, giữ các câu cùng ca đi cùng nhau. Dev còn phụ thuộc do nền hợp đồng chung; mẫu mới chỉ có tám ca.", "",
            "| Gold | Kết luận máy qua judge | Trước | Sau |", "|---|---|---:|---:|",
        ]
        for truth in ("violation", "compliant"):
            for predicted in ("violation", "compliant", "unclear"):
                text.append(f"| {truth} | {predicted} | {m['qa']['baseline']['confusion'][truth][predicted]} | {m['qa']['grounded']['confusion'][truth][predicted]} |")
        judge = {(r["id"], r["system"]): r for r in exp.rows(OUTPUT / split / "judge.jsonl")}
        gold = {r["id"]: r for r in exp.rows(OUTPUT / split / "gold.jsonl")}
        failures = [r for r in judge.values() if r["system"] == "grounded" and r["correctness"] < 2]
        text += ["", f"Candidate còn {len(failures)} câu chưa đạt trọn điểm:", ""]
        for row in failures:
            text.append(f"- `{row['id']}` / `{gold[row['id']]['source_id']}`: {row['correctness']}/2 — {row['reason']}")
        if not failures:
            text.append("- Không có câu dưới 2/2 theo judge trong nhóm này; mẫu nhỏ và judge chưa được chuyên gia kiểm, không suy ra ứng dụng đúng 100%.")
        text += [""]
    text += ["**Code và kiến thức đã thay đổi**", "",
        "1. Làm truy vấn bất biến với số Điều hợp đồng; vẫn giữ số Điều luật đích danh và các con số có ý nghĩa.",
        "2. Chỉ mục chủ đề lao động truy xuất chính xác Điều từ corpus. Nó cung cấp bằng chứng cho cả câu hợp lệ lẫn vi phạm, không có nhãn hay case id benchmark trong code ứng dụng.",
        "3. Ghép đầy đủ các Khoản/Điểm theo thứ tự, loại trùng và phần tràn sang Điều tiếp theo; ưu tiên căn cứ trực tiếp trước kết quả vector bổ sung.",
        "4. Ngừng chèn các đoạn luật cố định lệch chủ đề khi đã có nguồn chính xác. Prompt kiểm chủ thể, hành vi, điều kiện, phủ định/ngoại lệ; không coi thiếu luật là dữ kiện cần người dùng cung cấp.",
        "5. Tách số Điều hợp đồng trong `cited_clauses` khỏi số Điều luật trong phần giải thích. Xác minh nguồn thực, không tự điền nguồn để ăn điểm.", "",
        "Tham khảo ý tưởng sửa chất lượng truy xuất của [CRAG](https://arxiv.org/abs/2401.15884), "
        "phân biệt đúng nội dung với chất lượng viện dẫn của [ALCE](https://aclanthology.org/2023.emnlp-main.398/), "
        "và đọc [Self-RAG](https://arxiv.org/abs/2310.11511). Không huấn luyện hay tuyên bố đã tái lập trọn các mô hình trong paper.", "",
        "Nguồn luật kiểm đối chiếu: [Bộ luật Lao động trên Cổng Chính phủ](https://vanban.chinhphu.vn/?docid=198540&lang=vi&pageid=27160), "
        "[văn bản hợp nhất 125/VBHN-VPQH](https://vanban.chinhphu.vn/?docid=215248&pageid=27160). "
        "Đã dùng web và MCP Search để tìm nguồn chính thức; không có MCP chuyên luật VN được kết nối, và VBPL trả 403 nên không tuyên bố đọc được trang bị chặn.", "",
        "**Phần chưa được chứng minh và việc tiếp theo**", "",
        "Điểm cao ở đây chứng minh kết quả trên đúng các nhóm đã đo. Chưa đo toàn test QA v1 314 câu bằng candidate, "
        "chưa đo toàn workflow phân tích, hội thoại nhiều lượt hoặc hợp đồng thực tế. QA mới chủ yếu được đo bằng câu hỏi T1; "
        "T2/T3 chỉ có số retrieval ở dev. Không sử dụng điểm tốt của T1 để tuyên bố mọi chức năng đạt cùng mức.", "",
        "Nhãn mới đã đối chiếu nguồn chính thức nhưng vẫn do cùng tác giả code xây. Judge tự động có thể sai nội dung pháp lý. "
        "Để bảo vệ đồ án, nên trình bày kết quả kèm mẫu số/nguồn và các lỗi còn lại; chọn một mẫu đầu ra thật cho người có chuyên môn xem trước khi khẳng định legal correctness ngoài bộ dữ liệu.", "",
        "**Tái lập và bằng chứng**", "",
        "- Phương pháp và tài liệu: `evaluation/contract_eval_v2/RESEARCH_NOTES.md`.",
        "- Protocol, baseline snapshot, hash code/data: `artifacts/research_evidence_v3/protocol.json` và `reference_code/`.",
        "- Mỗi nhóm có `inputs.jsonl`, `gold.jsonl`, `manifest.json`, `retrieval.jsonl`, `qa.jsonl`, `judge.jsonl`, `metrics.json`, `human_review.csv` và các bảng điểm từng ca.",
        "- Bộ v1 và output các vòng trước giữ nguyên; không xóa test.lock hoặc sửa gold/rubric sau khi xem kết quả.", "",
    ]
    target = exp.ROOT / "docs/bo_test_hoi_dong/NGHIEN_CUU_V3_KET_QUA.md"
    target.write_text("\n".join(text), encoding="utf-8")
    exp.write_json(OUTPUT / "summary.json", {"metrics": metrics, "usage": totals, "protocol_sha256": exp.digest(OUTPUT / "protocol.json")})
    print(target)
    return target


if __name__ == "__main__":
    report()

"""Build the final v4 report from real, complete QA and judge records."""
from evaluation.contract_eval_v2 import experiment as exp
from evaluation.contract_eval_v2.review_round import OUTPUT, SPLITS
from evaluation.contract_eval_v2.research_report import pct, ci


def plot(results):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    order = ("regression_test", "validation", "fresh_source_checked")
    fig, ax = plt.subplots(figsize=(12, 6.5))
    for offset, system, color, label in ((-.19, "baseline", "#64748b", "V3 — đối chứng chạy mới"), (.19, "grounded", "#0f766e", "V4 — sau sửa")):
        values = [results[s]["qa"][system]["correctness"] * 100 for s in order]
        bars = ax.bar([i + offset for i in range(3)], values, width=.35, color=color, label=label)
        ax.bar_label(bars, labels=[f"{v:.1f}%" for v in values], padding=5, fontsize=12)
    ax.axhline(80, color="#c2410c", linestyle="--", linewidth=1, alpha=.7)
    ax.text(-.43, 81, "80%", color="#c2410c", fontsize=10)
    ax.set_xticks(range(3), ["Regression đã dùng chẩn đoán\n32 ca / cấu hình", "Validation không dùng sửa v4\n16 ca / cấu hình", "Thử việc và nghỉ phép\n8 ca / cấu hình"], fontsize=11)
    ax.set_ylim(0, 115)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel("Điểm QA correctness (%)", fontsize=12)
    ax.set_title("V4: điểm QA từ lượt gọi và chấm thật", loc="left", fontsize=18, pad=20)
    ax.legend(frameon=False, loc="upper left", ncols=2)
    ax.set_axisbelow(True)
    ax.grid(axis="y", alpha=.18)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(.08, .025, "Cùng model GPT-OSS-120b và cùng Qwen judge/rubric. Nhóm 8 ca bị giảm điểm được giữ nguyên.\nDữ liệu tổng hợp; không suy ra độ chính xác toàn ứng dụng hoặc xác nhận của chuyên gia.", fontsize=10, color="#475569")
    fig.subplots_adjust(left=.08, right=.98, bottom=.23, top=.86)
    target = exp.ROOT / "docs/bo_test_hoi_dong/QA_V4_TRUOC_SAU.png"
    fig.savefig(target, dpi=150, facecolor="white")
    plt.close(fig)
    return target


def report():
    labels = {"regression_test": "32 ca regression đã dùng phân tích lỗi", "fresh_source_checked": "8 ca thử việc/nghỉ phép", "validation": "16 ca validation không dùng sửa v4"}
    results = {s: exp.read_json(OUTPUT / s / "metrics.json") for s in SPLITS}
    text = ["# Kết quả cuối v4: truy xuất căn cứ và kiểm chứng câu trả lời", "",
        "Ngày 18/11/2026. Baseline là code v3, candidate là v4. Cả hai đều gọi hệ thống/model thật và được chấm bằng cùng judge/rubric; không sửa nhãn để tăng điểm.", "",
        "**Kết quả chính**", "", "| Nhóm | Số câu mỗi bản | Correctness trước → sau | Đúng đủ trước → sau | Kết luận đúng trước → sau | Nguồn HĐ đúng trước → sau |", "|---|---:|---:|---:|---:|---:|",
    ]
    total_tokens, total_calls, judge_tokens, judge_calls = 0, 0, 0, 0
    for split, m in results.items():
        b, g = m["qa"]["baseline"], m["qa"]["grounded"]
        text.append(f"| {labels[split]} | {g['judged']}/{g['expected']} | {pct(b['correctness'])} → **{pct(g['correctness'])}** | {pct(b['fully_correct'])} → **{pct(g['fully_correct'])}** | {pct(b['conclusion_match'])} → **{pct(g['conclusion_match'])}** | {pct(b['source_clause_hit'])} → **{pct(g['source_clause_hit'])}** |")
        for row in exp.rows(OUTPUT / split / "qa.jsonl"):
            total_tokens += row["usage"]["tokens"]
            total_calls += row["usage"]["llm_calls"]
        meta = exp.read_json(OUTPUT / split / "judge_metadata.json")
        judge_tokens += meta["tokens_this_process"]
        judge_calls += meta["calls_this_process"]
    figure = plot(results)
    if figure:
        text[4:4] = [f"![QA trước/sau v4]({figure.as_posix()})", ""]
    text += ["", "Correctness là điểm trung bình 0–2 chuẩn hóa; đúng đủ là tỷ lệ đạt 2/2. Đây là số đo tự động trên dữ liệu tổng hợp, không phải chứng nhận độ chính xác pháp lý ngoài thực tế.", "",
        "**Các vòng đã làm và lý do phải có v4**", "",
        "V2 đưa nội dung Điều hợp đồng vào truy vấn luật. V3 bổ sung chỉ mục chủ đề và toàn Điều trong corpus; dev đạt 32/32 đúng đủ nhưng regression chỉ đạt 27/32, và hai ca mới giảm điểm. Các lỗi gồm đảo nghĩa điều cấm, dùng văn bản lệch phạm vi và coi thiếu chi tiết trong hợp đồng là vi phạm. Các kết quả v3 vẫn được giữ và báo riêng, không bị xóa để thay bằng số đẹp hơn.", "",
        "V4 thêm đúng một lượt kiểm chứng bằng chính model sinh, chỉ khi có căn cứ chính xác theo chủ đề. Lượt này đọc bản nháp và nguồn, không biết gold hoặc điểm judge. Nếu kiểm chứng lỗi/JSON hỏng thì giữ bản nháp; không lặp đến khi được điểm cao. Không thay retry hoặc node/cạnh LangGraph.", "",
        "**Sửa code và nguồn kiến thức**", "",
        "- Lấy thêm Điều 1 thật của hợp đồng khi hỏi Điều cụ thể, để model có loại/thời hạn hợp đồng thay vì hỏi lại dữ kiện đã có.",
        "- Khi đã có căn cứ chính xác, bỏ các đoạn vector bổ sung lệch chủ đề. Giữ retrieval thông thường nếu chưa có căn cứ phù hợp.",
        "- Bổ sung nguyên tắc thỏa thuận và điều kiện có lợi hơn cho người lao động cho các chủ đề phù hợp; bổ sung quyền tiếp cận Tòa án từ Bộ luật Tố tụng dân sự, lấy văn bản thật qua repository và kiểm hiệu lực.",
        "- Kiểm tra chiều của điều cấm, điều kiện áp dụng, phủ định, ngoại lệ, căn cứ được dẫn và việc điều khoản không chép toàn bộ luật. Không tự điền `source_clauses` mà model chưa dẫn.",
        "- Không thêm dependency, SQL trong agent, nhãn/case id benchmark vào ứng dụng, hoặc thay schema/API/auth/streaming/checkpointer.", "",
        "Ý tưởng tham khảo: [CRAG](https://arxiv.org/abs/2401.15884) về sửa chất lượng truy xuất, [ALCE](https://aclanthology.org/2023.emnlp-main.398/) về viện dẫn và [Self-RAG](https://arxiv.org/abs/2310.11511) về kiểm chứng đầu ra. Đây là cách triển khai riêng, không huấn luyện/tái lập trọn mô hình của paper.", "",
        "Nguồn chính thức: [BLLĐ hợp nhất 125/VBHN-VPQH](https://vanban.chinhphu.vn/?docid=215248&pageid=27160), [Bộ luật Tố tụng dân sự trên Cổng Chính phủ](https://xaydungchinhsach.chinhphu.vn/toan-van-van-ban-hop-nhat-so-24-vbhn-vpqh-bo-luat-to-tung-dan-su-119230213081059503.htm). Đã tìm nguồn bằng web/MCP Search; không có MCP chuyên luật VN được kết nối. VBPL trả 403 nên dùng nguồn Chính phủ đọc được, không tuyên bố vượt chặn.", "",
        "**Thiết kế bộ đánh giá và các giới hạn**", "",
        "Protocol v4 được đóng băng trước kết quả candidate. 40 ca của hai nhóm đầu đã dùng phân tích v3 nên là regression trong phát triển. 16 validation được chọn cân bằng bằng seed 20261120, không trùng ca gốc dev/v2/v3 và không dùng kết quả riêng của chúng để sửa v4. Tuy nhiên chúng vẫn lấy từ bộ v1 từng được đánh giá, cùng các nền tổng hợp; không gọi là benchmark hoàn toàn mới độc lập.", "",
        "8 ca mới có nguồn luật chính thức, nhưng do tác giả code soạn, chưa có chuyên gia xác nhận. Inference không phân tích gold để sinh hoặc chọn evidence; bước integrity đọc bytes để kiểm hash, đáp án dùng ở bước chấm. Judge Qwen và rubric không đổi giữa hai bản; model sinh GPT-OSS-120b và embedding BGE-M3 không đổi. Bản v3 được nạp từ snapshot để chạy baseline mới, không dùng lại điểm cũ để chọn baseline thấp.", "",
        "Đã chạy 56 câu × 2 cấu hình = **112 đầu ra QA**, chấm thật từng đầu ra. V4 dùng thêm một lượt model để kiểm chứng nên không phải so sánh cùng số token. Cần xét chi phí và độ trễ cùng độ đúng.", "",
        f"Usage API vòng v4: {total_calls} lời gọi hệ thống, {total_tokens:,} token; {judge_calls} lời gọi judge, {judge_tokens:,} token. Số lời gọi có thể lớn hơn 112 vì lượt kiểm chứng và vòng rewrite có sẵn.", "",
        "**Truy xuất và faithfulness**", "", "| Nhóm | R@5 trước → sau | Faithfulness trước → sau | n faithfulness trước/sau | p50 QA trước → sau |", "|---|---:|---:|---:|---:|",
    ]
    for s, m in results.items():
        b, g = m["qa"]["baseline"], m["qa"]["grounded"]
        text.append(f"| {labels[s]} | {pct(m['retrieval']['baseline']['legal_recall@5'])} → {pct(m['retrieval']['grounded']['legal_recall@5'])} | {pct(b['faithfulness'])} → {pct(g['faithfulness'])} | {b['faithfulness_scored']}; {g['faithfulness_scored']} | {b['latency_p50_ms']/1000:.2f}s → {g['latency_p50_ms']/1000:.2f}s |")
    text += ["", "R@5 v4 lấy từ trace truy xuất cuối của QA thật; đo hệ thống vector + tra Điều, không phải chất lượng embedding thuần. Danh sách truy xuất và context thực gửi model là hai trường riêng, vì đóng gói prompt có giới hạn ký tự. Faithfulness bỏ câu không có mệnh đề và báo mẫu số riêng; correctness vẫn chấm đủ câu.", "",
        "**Tăng/giảm từng ca và những ca chưa đúng đủ**", "",
    ]
    for split, m in results.items():
        c = m["qa_changes"]
        text += [f"**{labels[split]}**", "", f"{c['improved']} câu tăng, {c['regressed']} câu giảm, {c['unchanged']} câu không đổi; CI95 chênh correctness {ci(m['paired_qa_delta_ci95_cluster'])}, lấy mẫu theo ca gốc.", ""]
        gold = {x["id"]: x for x in exp.rows(OUTPUT / split / "gold.jsonl")}
        failures = [x for x in exp.rows(OUTPUT / split / "judge.jsonl") if x["system"] == "grounded" and x["correctness"] < 2]
        for row in failures:
            text.append(f"- `{row['id']}` / `{gold[row['id']]['source_id']}`: {row['correctness']}/2 — {row['reason']}")
        if not failures:
            text.append("Không có ca dưới 2/2 theo judge trong nhóm này; mẫu nhỏ nên không suy ra ứng dụng hoàn hảo.")
        text += [""]
    text += ["**Việc còn cần biết**", "",
        "Corpus bản sao đang đánh dấu Luật BHXH 41/2024/QH15 là hết hiệu lực toàn bộ; nguồn Chính phủ vẫn có tài liệu áp dụng luật này trong năm 2026. Đây là tín hiệu cần audit trạng thái/phiên bản và quy định chuyên ngành, chưa phải căn cứ để tự bật lại mọi chunk. Vòng này không sửa metadata hiệu lực để ép ca bảo hiểm khớp gold.", "",
        "Chưa chạy toàn bộ QA 314 câu bằng v4, toàn workflow phân tích, hội thoại nhiều lượt hoặc hợp đồng thực tế. Kết quả hiện chủ yếu cho câu hỏi chỉ rõ Điều. Không lấy điểm cao ở các nhóm trên để tuyên bố mọi chức năng đều đạt cùng mức.", "",
        "Kiểm tra kỹ thuật: 381 passed, 1 skipped cho test không integration; các file sửa qua ruff F. Có test hồi quy cho lỗi HTTP client dùng qua nhiều event loop: harness đã sửa để các split dùng cùng một loop; các lượt đã chạy được retry cũ xử lý, không xóa hoặc chạy lại chọn điểm. Toàn repo còn F401 cũ ở `evaluation/check_chapter_numbers.py:15`. Chưa commit/push; giữ nguyên dữ liệu, khóa test và kết quả các vòng cũ.", "",
        "Bằng chứng đầy đủ ở `evaluation/contract_eval_v2/artifacts/reviewed_evidence_v4/`: protocol, snapshot baseline, manifest/hash, đầu vào/gold tách riêng, câu trả lời, context thực, điểm từng ca, usage và `human_review.csv`. Tài liệu nguồn và kết quả v3 ở `RESEARCH_NOTES.md` và `NGHIEN_CUU_V3_KET_QUA.md`.", ""]
    target = exp.ROOT / "docs/bo_test_hoi_dong/CAI_THIEN_V4_KET_QUA.md"
    target.write_text("\n".join(text), encoding="utf-8")
    exp.write_json(OUTPUT / "summary.json", {"metrics": results, "usage": {"generation_calls": total_calls, "generation_tokens": total_tokens, "judge_calls": judge_calls, "judge_tokens": judge_tokens}})
    print(target)


if __name__ == "__main__":
    report()

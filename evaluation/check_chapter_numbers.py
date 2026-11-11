"""Đối chiếu số liệu trong docs/CHUONG_DANH_GIA_THUC_NGHIEM.md và docs/bo_test_hoi_dong/BO_TEST_HOI_DONG.md
với file kết quả thật trong evaluation_results/ (không sửa gì, chỉ báo khớp / lệch).

  python -m evaluation.check_chapter_numbers          # in bảng, ghi evaluation_results/reports/DOI_CHIEU_SO_LIEU_CHUONG5.md

Số "trong chương" ở cột claimed được gõ lại từ văn bản chương; số "thực" được tính lại từ dữ liệu thô
(dataset.csv, cases.jsonl, predictions, metrics.json) hoặc đọc từ file điểm, chỉ phân tích văn bản .md
khi không có file số liệu. Không gọi LLM, không đụng DB.
"""
from __future__ import annotations

import collections
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from evaluation.injection import run as inj
from evaluation.injection_v2 import run as inj2

ROOT = Path(__file__).resolve().parent.parent
ER = ROOT / "evaluation_results"
rows: list[tuple[str, str, object, object, bool]] = []


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in read(p).splitlines() if x.strip()]


def num(claimed, actual, where: str, item: str, dec: int | None = None) -> None:
    """So số; dec = số chữ số thập phân của số trong chương (khớp nếu làm tròn trùng)."""
    if dec is None:
        ok = claimed == actual
    else:
        ok = abs(float(claimed) - float(actual)) <= 0.5 * 10 ** -dec + 1e-9
    rows.append((where, item, claimed, round(actual, 4) if isinstance(actual, float) else actual, ok))


def text_has(path: Path, needle: str, where: str, item: str) -> None:
    ok = needle in read(path)
    rows.append((where, item, needle, f"có trong {path.name}" if ok else f"KHÔNG có trong {path.name}", ok))


def git(*a: str) -> str:
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip()


def section_dataset() -> None:
    csv.field_size_limit(2**31 - 1)
    with (ROOT / "data/dataset.csv").open(encoding="utf-8", newline="") as f:
        data = list(csv.DictReader(f))
    per_q = collections.Counter(r["qid"] for r in data)
    docs = {r["doc_id"].split("+")[0] for r in data}
    w = "5.3.1"
    num(3298, len(data), w, "số dòng dataset")
    num(3196, len(per_q), w, "số câu hỏi")
    num(724, len(docs), w, "số văn bản (cắt hậu tố +Điều của doc_id)")
    num(93, sum(1 for v in per_q.values() if v > 1), w, "câu có >1 dòng nhãn")
    num(84, sum(1 for v in per_q.values() if v == 2), w, "câu có đúng 2 dòng nhãn")
    num(9, sum(1 for v in per_q.values() if v >= 3), w, "câu có >=3 dòng nhãn")
    sp = json.loads(read(ER / "legal_qa/split.json"))
    num(523, sp["n_dev"], w, "n_dev")
    num(2673, sp["n_test"], w, "n_test")
    cov = json.loads(read(ER / "legal_qa/coverage.json"))["case_status_counts"]
    w = "5.3.2 / bảng 5.1"
    for k, claimed, pct in (("article_searchable", 772, 24.2), ("doc_present_not_searchable", 2257, 70.6),
                            ("doc_missing", 162, 5.1), ("doc_searchable_article_missing", 5, 0.2)):
        num(claimed, cov[k], w, f"số câu {k}")
        num(pct, 100 * cov[k] / 3196, w, f"tỷ lệ {k} (%)", dec=1)
    bd = ER / "legal_qa/coverage_breakdown.md"
    for needle in ("1.509", "66,9%", "679", "30,1%", "660"):
        text_has(bd, needle, "5.3.2", f"coverage_breakdown.md chứa {needle}")


def section_retrieval() -> None:
    runs = {}
    for name in ("fts", "vector", "hybrid", "hybrid+V3"):
        cands = sorted((ER / "legal_qa/runs").glob(f"test_{name}_2*"))
        runs[name] = json.loads(read(cands[-1] / "metrics.json"))["covered_cases_only"]
    claimed = {  # R@1, R@5, R@5 CI, R@10, MRR, MRR CI, DocR@10  (bảng 5.2)
        "fts": (0.005, 0.009, (0.002, 0.018), 0.014, 0.007, (0.001, 0.014), 0.025),
        "vector": (0.594, 0.795, (0.763, 0.827), 0.836, 0.682, (0.649, 0.715), 0.910),
        "hybrid": (0.581, 0.736, (0.701, 0.772), 0.791, 0.642, (0.609, 0.677), 0.894),
        "hybrid+V3": (0.590, 0.802, (0.768, 0.835), 0.842, 0.686, (0.655, 0.719), 0.908),
    }
    for name, c in claimed.items():
        m = runs[name]
        w = f"bảng 5.2 [{name}]"
        num(556, m["n"], w, "n")
        num(c[0], m["recall@1"], w, "R@1", 3)
        num(c[1], m["recall@5"], w, "R@5", 3)
        num(c[2][0], m["recall@5_ci95"][0], w, "R@5 CI thấp", 3)
        num(c[2][1], m["recall@5_ci95"][1], w, "R@5 CI cao", 3)
        num(c[3], m["recall@10"], w, "R@10", 3)
        num(c[4], m["mrr@10"], w, "MRR@10", 3)
        num(c[5][0], m["mrr@10_ci95"][0], w, "MRR CI thấp", 3)
        num(c[5][1], m["mrr@10_ci95"][1], w, "MRR CI cao", 3)
        num(c[6], m["doc_recall@10"], w, "DocR@10", 3)
    lat = {n: json.loads(read(sorted((ER / "legal_qa/runs").glob(f"test_{n}_2*"))[-1] / "metrics.json"))["latency_ms"]["median"]
           for n in claimed}
    for n, c in (("fts", 85), ("vector", 294), ("hybrid", 347), ("hybrid+V3", 4237)):
        num(c, round(lat[n]), f"bảng 5.2 [{n}]", "độ trễ median (ms)")
    tk = ER / "legal_qa/TEST_KET_QUA.md"
    for needle in ("−0,0395 | [−0,0483; −0,0312]", "+0,0042 | [−0,0061; +0,0139]", "+0,0437 | [+0,0290; +0,0571]"):
        text_has(tk, needle, "bảng 5.3", f"TEST_KET_QUA.md chứa {needle} (chương làm tròn 3 chữ số)")
    num(0.208, 556 / 2673, "5.3.6 / 5.10", "tỷ lệ câu test đánh giá được", 3)
    num(0.174, runs["vector"]["recall@10"] * 556 / 2673, "5.3.6", "R@10 vector trên toàn bộ 2.673 câu", 3)
    num(14, runs["hybrid+V3"] and round(4237 / lat["vector"]), "5.3.6", "V3 chậm hơn vector ~ lần")
    dv = ER / "legal_qa"
    for needle, f in (("50/216", "PHAN_TICH_LOI_DEV.md"), ("7/216", "PHAN_TICH_LOI_DEV.md"), ("150/216", "PHAN_TICH_LOI_DEV.md"),
                      ("0,7112", "DEV_BIEN_THE.md")):
        text_has(dv / f, needle, "5.3.4", f"{f} chứa {needle}")
    v04 = ER / "reports/RAG_V04_HYBRID_VS_VECTOR.md"
    for needle in ("0,2990", "0,3000", "0,4461", "0,4608"):
        text_has(v04, needle, "5.4", f"RAG_V04_HYBRID_VS_VECTOR.md chứa {needle} (chương làm tròn 3 chữ số)")


def section_injection() -> None:
    cases = {c["case_id"]: c for c in jl(ROOT / "evaluation/injection/cases.jsonl")}
    num(80, len(cases), "5.5.1", "số ca bơm lỗi")
    ro = json.loads(read(ER / "injection/rule_only.json"))["predictions"]
    sc = json.loads(read(ER / "injection/rule_only_scores.json"))
    m, ci, w = sc["micro"], sc["micro_ci95"], "bảng 5.4"
    for k, v in (("tp", 16), ("fp", 14), ("fn", 24)):
        num(v, m[k], w, k.upper())
    for k, v, lo, hi in (("precision", 0.53, 0.36, 0.73), ("recall", 0.40, 0.25, 0.56), ("f1", 0.46, 0.30, 0.60)):
        num(v, m[k], w, k, 2)
        num(lo, ci[k][0], w, f"{k} CI thấp", 2)
        num(hi, ci[k][1], w, f"{k} CI cao", 2)
    # chia theo kiểu diễn đạt, tính lại từ dự đoán
    fired = {cid: {k for r in ro.get(cid, []) for k in r["keys"]} for cid in cases}
    own = lambda cid: cases[cid]["rule_id"] in fired[cid]  # noqa: E731
    w = "5.5.2"
    form = [c for c in cases.values() if c["label"] == "violation" and c["phrasing"] == "formulaic"]
    num(16, sum(own(c["case_id"]) for c in form), w, "ca formulaic bắt đúng")
    num(16, len(form), w, "ca formulaic tổng")
    miss = collections.Counter(c["phrasing"] for c in cases.values() if c["label"] == "violation" and not own(c["case_id"]))
    for k, v in (("paraphrase", 10), ("number_words", 5), ("abbreviation", 5), ("long_sentence", 4)):
        num(v, miss[k], w, f"ca vi phạm bị bỏ sót: {k}")
    num(24, sum(miss.values()), w, "tổng ca vi phạm bị bỏ sót")
    fp = collections.Counter(c["phrasing"] for c in cases.values() if c["label"] == "compliant" and own(c["case_id"]))
    num(14, sum(fp.values()), w, "ca hợp lệ bị báo nhầm")
    num(7, fp["negation_trap"], w, "báo nhầm là câu phủ định (negation_trap)")
    num(7, sum(v for k, v in fp.items() if k != "negation_trap"), w, "báo nhầm là nội dung hợp pháp chứa từ khoá (các kiểu còn lại)")
    num(40, sum(c["label"] == "compliant" for c in cases.values()), w, "ca hợp lệ tổng")
    cross = sum(1 for cid in cases if fired[cid] - {cases[cid]["rule_id"]})
    num(0, cross, w, "ca bị luật của luật khác kích hoạt")

    fs = json.loads(read(ER / "injection/full_scores.json"))
    m, ci, w = fs["micro"], fs["micro_ci95"], "bảng 5.5"
    for k, v in (("tp", 24), ("fp", 15), ("fn", 0), ("tn", 9), ("unchecked", 0), ("n", 48)):
        num(v, m[k], w, k.upper())
    num(0.62, m["precision"], w, "precision", 2)
    num(0.46, ci["precision"][0], w, "precision CI thấp", 2)
    num(0.76, ci["precision"][1], w, "precision CI cao", 2)
    num(1.00, m["recall"], w, "recall", 2)
    num(0.76, m["f1"], w, "F1", 2)
    num(0.63, ci["f1"][0], w, "F1 CI thấp", 2)
    num(0.87, ci["f1"][1], w, "F1 CI cao", 2)
    recs = {p.stem: json.loads(read(p)) for p in (ER / "injection/full").glob("*.json")}
    w = "5.5.3"
    num(48, len(recs), w, "số bản ghi pipeline")
    fpc = collections.Counter(cases[i]["phrasing"] for i, r in recs.items() if cases[i]["label"] == "compliant" and r["slot_flagged"])
    for k, v in (("lawful_variant", 8), ("negation_trap", 5), ("number_words", 1), ("long_sentence", 1)):
        num(v, fpc[k], w, f"FP pipeline: {k}")
    flags = [r["other_clause_flags"] for r in recs.values()]
    num(48, sum(1 for x in flags if x), w, "ca có mục khác bị gắn cờ (kể cả cờ toàn văn, ref rỗng)")
    num(5.4, sum(len(x) for x in flags) / 48, w, "trung bình số mục khác bị gắn cờ (tính cả cờ toàn văn)", 1)
    num(48, sum(1 for x in flags if any(x)), w, "ca có ít nhất một Điều khác (có số) bị gắn cờ")
    num(5.4, sum(len([y for y in x if y]) for x in flags) / 48, w, "trung bình số ĐIỀU khác bị gắn cờ (không tính cờ toàn văn)", 1)
    # 5.6 hợp đồng nền
    bf = json.loads(read(ER / "injection/base_contract_flags.json"))
    sev = collections.Counter(r["severity"] for r in bf["risks"])
    num(8, len(bf["risks"]), "5.6", "số cờ trên hợp đồng nền")
    num(7, sev["warning"], "5.6", "cờ warning")
    num(1, sev["critical"], "5.6", "cờ critical")
    num(11, bf["coverage"]["da_kiem"], "5.6", "Điều đã kiểm")
    base_slots = {"2", "5", "6", "7", "8", "9", "10"}  # Điều có cờ trên nền, theo BASE_CONTRACT_FLAGS.md
    comp = [(cases[i], r) for i, r in recs.items() if cases[i]["label"] == "compliant"]
    on = [r["slot_flagged"] for c, r in comp if str(c["slot"]) in base_slots]
    off = [r["slot_flagged"] for c, r in comp if str(c["slot"]) not in base_slots]
    num("14/21", f"{sum(on)}/{len(on)}", "5.6", "ca hợp lệ ở Điều nền bị cờ: bị gắn cờ")
    num("1/3", f"{sum(off)}/{len(off)}", "5.6", "ca hợp lệ ở Điều nền không cờ (Điều 4)")
    num(15, sum(on) + sum(off), "5.6", "tổng FP khớp bảng 5.5")


def section_negation() -> None:
    cases = inj2.load_cases()
    out = {}
    for lab in ("old", "new"):
        pred = json.loads(read(ER / f"injection_v2/rule_only_{lab}.json"))["predictions"]
        fired = {c["case_id"]: set(pred.get(c["case_id"], [])) for c in cases}
        sc = inj.score_rule_level(cases, fired)["micro"]
        out[lab] = sc
    w = "bảng 5.7"
    for lab, (tp, fp, fn, p, r, f1) in (("old", (16, 16, 0, 0.50, 1.00, 0.67)), ("new", (8, 8, 8, 0.50, 0.50, 0.50))):
        s = out[lab]
        num(tp, s["tp"], w, f"{lab} TP")
        num(fp, s["fp"], w, f"{lab} FP")
        num(fn, s["fn"], w, f"{lab} FN")
        num(p, s["precision"], w, f"{lab} precision", 2)
        num(r, s["recall"], w, f"{lab} recall", 2)
        num(f1, s["f1"], w, f"{lab} F1", 2)
    rep = ER / "injection_v2/REPORT.md"
    for needle in ("0.50 [0.3125, 0.6875]", "0.50 [0.2308, 0.75]", "1.00 [1.0, 1.0]", "0.50 [0.25, 0.7647]",
                   "0.67 [0.4762, 0.8148]", "0.50 [0.25, 0.6897]"):
        text_has(rep, needle, w, f"REPORT.md chứa {needle} (chương làm tròn 2 chữ số)")


def section_review_and_git() -> None:
    p = ROOT / "docs/bo_test_hoi_dong/REVIEW_BO_TEST_HOP_DONG.csv"
    csv.field_size_limit(2**31 - 1)
    with p.open(encoding="utf-8-sig", newline="") as f:
        data = list(csv.DictReader(f))
    c = collections.Counter(r["Kết luận kiểm tra"] for r in data)
    w = "BO_TEST_HOI_DONG: kiểm tra nhãn"
    num(112, len(data), w, "tổng số ca trong bảng kiểm")
    # BO_TEST nêu 101 / 10 / 1 / 0
    claimed = {"ĐÚNG": 101, "ĐÚNG – CÓ LƯU Ý": 10, "CẦN BẠN XEM": 1, "SAI": 0}
    for k, v in claimed.items():
        num(v, c.get(k, 0), w, f"số ca '{k}'")
    for ref, short in (("injection-frozen", "e268fcb"), ("injection-v2-frozen", "fab1cef")):
        num(short, git("rev-parse", "--short=7", ref), "bảng 5.9", f"tag {ref}")
    for sha in ("6ba982d", "04f1e6c", "f23ba86", "84c8d5e", "087256a", "7148b39", "ae9e230", "78d4437", "551e9e2", "ed30fdd", "fab1cef", "e268fcb"):
        num("tồn tại", "tồn tại" if git("cat-file", "-t", sha) == "commit" else "KHÔNG", "bảng 5.9", f"commit {sha}")
    # hai số làm tròn trong bảng 5.8 / mục 5.5.3
    num(35, 100 * 14 / 40, "bảng 5.8 (RQ3)", "báo nhầm luật cố định (%)", 0)
    num(62, 100 * 15 / 24, "mục 5.5.3 / bảng 5.8", "báo nhầm judge (%) = 15/24", 0)


def main() -> int:
    for fn in (section_dataset, section_retrieval, section_injection, section_negation, section_review_and_git):
        try:
            fn()
        except Exception as e:  # một mục lỗi không làm mất các mục khác
            rows.append((fn.__name__, "LỖI khi đối chiếu", "-", f"{type(e).__name__}: {e}", False))
    bad = [r for r in rows if not r[4]]
    lines = ["# Đối chiếu số liệu chương 5 và bộ test hội đồng với file kết quả", "",
             "Sinh bởi `python -m evaluation.check_chapter_numbers`. Chỉ báo, không sửa chương.", "",
             f"Tổng {len(rows)} số: **{len(rows) - len(bad)} khớp, {len(bad)} lệch**.", "",
             "## Lệch", "", "| Vị trí | Mục | Trong chương | Thực tế |", "|---|---|---|---|"]
    lines += [f"| {w} | {i} | {c} | {a} |" for w, i, c, a, ok in bad] or ["| - | không có | - | - |"]
    lines += ["", "## Toàn bộ", "", "| Vị trí | Mục | Trong chương | Thực tế | Kết quả |", "|---|---|---|---|---|"]
    lines += [f"| {w} | {i} | {c} | {a} | {'khớp' if ok else 'LỆCH'} |" for w, i, c, a, ok in rows]
    out = ER / "reports/DOI_CHIEU_SO_LIEU_CHUONG5.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} số: {len(rows) - len(bad)} khớp, {len(bad)} lệch -> {out.relative_to(ROOT)}")
    for w, i, c, a, ok in bad:
        print(f"LỆCH | {w} | {i} | chương={c} | thực={a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Benchmark truy xuất pháp luật chung trên data/dataset.csv (đánh giá thành phần).

Không gọi Gemini, không tốn quota. Chỉ đo module truy xuất (pgvector, FTS, hybrid RRF).

Các bước:
  coverage : kiểm tra văn bản/điều luật gold có nằm trong DB và tìm kiếm được không
  split    : chia dev/test theo VĂN BẢN (băm cố định), đóng băng vào split.json
  run      : chạy truy xuất trên dev hoặc test, xuất predictions + metrics có CI

Quy tắc: tập test chỉ được chạy MỘT lần cho mỗi mode (có file khóa).
Chỉnh tham số thoải mái trên dev.

Ví dụ:
  python -m evaluation.legal_qa_retrieval coverage
  python -m evaluation.legal_qa_retrieval split
  python -m evaluation.legal_qa_retrieval run --split dev --mode hybrid --limit 200
  python -m evaluation.legal_qa_retrieval run --split test --mode hybrid
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import statistics
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "dataset.csv"
OUT = ROOT / "evaluation_results" / "legal_qa"
SPLIT_FILE = OUT / "split.json"
COVERAGE_FILE = OUT / "coverage.json"
LOCK_DIR = OUT / "test_locks"
RESULTS_MD = OUT / "RESULTS.md"
ARTICLE_TOKEN = re.compile(r"^D(\d+)$", re.IGNORECASE)
KS = (1, 3, 5, 10)
# Biến thể truy xuất khai báo trước (docs/NHAT_KY_THAY_DOI.md). Mỗi biến thể là cờ ghi đè Settings; "none" = hành vi cũ.
_V1 = {"legal_fts_query": "or"}
_V2 = {**_V1, "legal_article_chunks_only": True}
_V3 = {**_V2, "legal_rrf_weight_vector": 0.7, "legal_rrf_weight_fts": 0.3}
VARIANTS = {"none": {}, "V1": _V1, "V2": _V2, "V3": _V3}
# Chỉ tính "dirty" trên mã ảnh hưởng kết quả; file không liên quan trong repo không làm gắn dấu *.
DIRTY_PATHS = ("app", "evaluation/legal_qa_retrieval.py")


# ---------- tiện ích ----------
def norm_doc(value: str | None) -> str:
    s = (value or "").strip().replace("Đ", "đ").lower()
    return s.replace("đ", "d").replace(" ", "")


def article_from_path(path: str | None) -> str | None:
    for token in (path or "").split("."):
        m = ARTICLE_TOKEN.match(token)
        if m:
            return str(int(m.group(1)))
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_info() -> dict:
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            return None
    status = run("status", "--porcelain", "--", *DIRTY_PATHS)
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None,
            "dirty_scope": list(DIRTY_PATHS)}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- dữ liệu ----------
def load_cases() -> tuple[list[dict], dict]:
    """Gom theo qid. Mỗi câu hỏi có thể có nhiều cặp (văn bản, điều) đúng."""
    csv.field_size_limit(2**31 - 1)
    by_qid: dict[str, dict] = {}
    skipped = defaultdict(int)
    with DATASET.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            source, _, element = (row.get("doc_id") or "").strip().partition("+")
            if not source:
                skipped["no_doc_id"] += 1
                continue
            if not element.strip().isdigit():
                skipped["non_article_element"] += 1
                continue
            qid = row["qid"].strip()
            case = by_qid.setdefault(qid, {"qid": qid, "question": row["question"].strip(), "gold": []})
            pair = [norm_doc(source), str(int(element))]
            if pair not in case["gold"]:
                case["gold"].append(pair)
    cases = sorted(by_qid.values(), key=lambda c: c["qid"])
    return cases, dict(skipped)


def primary_doc(case: dict) -> str:
    return sorted(g[0] for g in case["gold"])[0]


# ---------- coverage ----------
def cmd_coverage(args) -> None:
    from app.infrastructure.db.connection import get_db

    cases, skipped = load_cases()
    gold_docs = sorted({g[0] for c in cases for g in c["gold"]})
    norm_sql = "translate(lower(translate(d.doc_num, 'Đ', 'đ')), 'đ ', 'd')"
    present, searchable_articles = {}, defaultdict(set)
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {norm_sql}, d.status_flag FROM legal_documents d WHERE {norm_sql} = ANY(%s)", [gold_docs])
        for doc, status in cur.fetchall():
            present[doc] = status
        cur.execute(
            f"""SELECT {norm_sql}, c.path::text FROM legal_embeddings c
                JOIN legal_documents d ON d.doc_id = c.doc_id
                WHERE {norm_sql} = ANY(%s) AND c.is_effective AND c.embedding IS NOT NULL
                  AND (d.status_flag IS NULL OR d.status_flag IS DISTINCT FROM 2)""",
            [gold_docs],
        )
        for doc, path in cur.fetchall():
            art = article_from_path(path)
            if art:
                searchable_articles[doc].add(art)

    per_case, counts = {}, defaultdict(int)
    for c in cases:
        if any(a in searchable_articles.get(d, ()) for d, a in c["gold"]):
            status = "article_searchable"
        elif any(d in searchable_articles for d, _ in c["gold"]):
            status = "doc_searchable_article_missing"
        elif any(d in present for d, _ in c["gold"]):
            status = "doc_present_not_searchable"
        else:
            status = "doc_missing"
        per_case[c["qid"]] = status
        counts[status] += 1

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_sha256": sha256_file(DATASET),
        "n_cases": len(cases), "skipped_rows": skipped,
        "n_gold_docs": len(gold_docs), "gold_docs_present": len(present),
        "gold_docs_searchable": len(searchable_articles),
        "case_status_counts": dict(counts), "per_case": per_case,
        "missing_docs": [d for d in gold_docs if d not in present],
    }
    write_json(COVERAGE_FILE, report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("per_case", "missing_docs")}, ensure_ascii=False, indent=2))
    print(f"Đã lưu {COVERAGE_FILE}")


# ---------- split ----------
def cmd_split(args) -> None:
    if SPLIT_FILE.exists() and not args.force:
        raise SystemExit(f"{SPLIT_FILE} đã tồn tại (đã đóng băng). Không ghi đè. Dùng --force nếu thật sự cần, và ghi lý do vào docs/NHAT_KY_THAY_DOI.md.")
    cases, skipped = load_cases()
    split = {"dev": [], "test": []}
    for c in cases:
        bucket = int(hashlib.md5(primary_doc(c).encode("utf-8")).hexdigest()[:8], 16) % 100
        split["dev" if bucket < args.dev_pct else "test"].append(c["qid"])
    data = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "method": f"md5(văn bản chính) % 100 < {args.dev_pct} -> dev; chia theo văn bản để tránh rò rỉ",
        "dataset_sha256": sha256_file(DATASET), "git": git_info(),
        "n_dev": len(split["dev"]), "n_test": len(split["test"]), **split,
    }
    if args.dry_run:
        print(json.dumps({k: v for k, v in data.items() if k not in ("dev", "test")}, ensure_ascii=False, indent=2))
        return
    write_json(SPLIT_FILE, data)
    print(f"dev={data['n_dev']} test={data['n_test']} -> {SPLIT_FILE}")


# ---------- run ----------
def bootstrap_ci(values: list[float], n_boot: int = 1000, seed: int = 0) -> list[float]:
    if not values:
        return [None, None]
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return [round(means[int(0.025 * n_boot)], 4), round(means[int(0.975 * n_boot) - 1], 4)]


def make_searcher(mode: str):
    from app.infrastructure.embeddings.hf_embedder import HuggingFaceEmbedder
    from app.infrastructure.vector.pg_search import PgLegalVectorSearch

    search = PgLegalVectorSearch(HuggingFaceEmbedder())
    if mode == "hybrid":
        return lambda q, n: search.search(q, k=n, min_score=0.0)
    if mode == "vector":
        return lambda q, n: search._vector_search(q, n, None, None, None)
    if mode == "fts":
        return lambda q, n: search._fts_search(q, n, None, None, None)
    raise SystemExit(f"mode không hợp lệ: {mode}")


def cmd_run(args) -> None:
    if not SPLIT_FILE.exists():
        raise SystemExit("Chưa có split.json. Chạy: python -m evaluation.legal_qa_retrieval split")
    split = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
    lock = LOCK_DIR / (f"{args.mode}.lock" if args.variant == "none" else f"{args.mode}+{args.variant}.lock")
    if args.split == "test":
        if args.limit:
            raise SystemExit("Tập test phải chạy đầy đủ, không dùng --limit.")
        if lock.exists() and not args.rerun_test:
            raise SystemExit(f"Tập test mode={args.mode} variant={args.variant} đã chạy rồi ({lock}). Không chạy lại để chọn số đẹp. "
                             "Nếu bắt buộc, dùng --rerun-test và ghi lý do vào docs/NHAT_KY_THAY_DOI.md.")

    cases, _ = load_cases()
    wanted = set(split[args.split])
    selected = [c for c in cases if c["qid"] in wanted]
    coverage = json.loads(COVERAGE_FILE.read_text(encoding="utf-8"))["per_case"] if COVERAGE_FILE.exists() else {}
    if args.only_covered:
        if not coverage:
            raise SystemExit("Cần chạy coverage trước khi dùng --only-covered.")
        selected = [c for c in selected if coverage.get(c["qid"]) == "article_searchable"]
    if args.limit:
        selected = random.Random(0).sample(selected, min(args.limit, len(selected)))

    from app.core.settings import get_settings

    for key, value in VARIANTS[args.variant].items():
        setattr(get_settings(), key, value)
    label = args.mode if args.variant == "none" else f"{args.mode}+{args.variant}"
    searcher = make_searcher(args.mode)
    searcher("khởi động", 1)  # nạp mô hình embedding, không tính vào độ trễ

    run_dir = OUT / "runs" / f"{args.split}_{label}_{datetime.now():%Y%m%d_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=False)
    rows, latencies = [], []
    with (run_dir / "predictions.jsonl").open("w", encoding="utf-8") as out:
        for i, c in enumerate(selected, 1):
            t0 = time.perf_counter()
            try:
                chunks, error = searcher(c["question"], args.k * args.fetch_factor), None
            except Exception as exc:  # ghi lỗi, không bỏ qua im lặng
                chunks, error = [], f"{type(exc).__name__}: {exc}"
            latencies.append((time.perf_counter() - t0) * 1000)
            ranked, seen = [], set()
            for ch in chunks:
                key = (norm_doc(ch.metadata.get("doc_number")), article_from_path(ch.metadata.get("path")))
                if key not in seen:
                    seen.add(key)
                    ranked.append({"doc": key[0], "article": key[1], "score": ch.score, "path": ch.metadata.get("path")})
            ranked = ranked[: args.k]
            gold = {tuple(g) for g in c["gold"]}
            gold_docs = {g[0] for g in c["gold"]}
            rank = next((r for r, x in enumerate(ranked, 1) if (x["doc"], x["article"]) in gold), None)
            doc_rank = next((r for r, x in enumerate(ranked, 1) if x["doc"] in gold_docs), None)
            row = {"qid": c["qid"], "question": c["question"], "gold": c["gold"], "rank": rank, "doc_rank": doc_rank,
                   "coverage": coverage.get(c["qid"]), "error": error, "top": ranked}
            rows.append(row)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            if i % 50 == 0:
                print(f"{i}/{len(selected)}", flush=True)

    def summarise(subset: list[dict]) -> dict:
        m = {"n": len(subset)}
        for k in KS:
            vals = [1.0 if r["rank"] and r["rank"] <= k else 0.0 for r in subset]
            m[f"recall@{k}"] = round(sum(vals) / len(vals), 4) if vals else None
            m[f"recall@{k}_ci95"] = bootstrap_ci(vals)
        rr = [1.0 / r["rank"] if r["rank"] else 0.0 for r in subset]
        m["mrr@10"] = round(sum(rr) / len(rr), 4) if rr else None
        m["mrr@10_ci95"] = bootstrap_ci(rr)
        dh = [1.0 if r["doc_rank"] else 0.0 for r in subset]
        m["doc_recall@10"] = round(sum(dh) / len(dh), 4) if dh else None
        m["errors"] = sum(1 for r in subset if r["error"])
        return m

    covered = [r for r in rows if r["coverage"] == "article_searchable"]
    metrics = {
        "created_at": datetime.now().isoformat(timespec="seconds"), "split": args.split, "mode": args.mode,
        "variant": args.variant, "settings_overrides": VARIANTS[args.variant], "k": args.k, "fetch_factor": args.fetch_factor, "limit": args.limit, "only_covered": args.only_covered,
        "git": git_info(), "dataset_sha256": split["dataset_sha256"], "llm_calls": 0,
        "latency_ms": {"median": round(statistics.median(latencies), 1),
                       "p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1)} if latencies else None,
        "all_cases": summarise(rows),
        "covered_cases_only": summarise(covered) if coverage else "chưa chạy coverage",
    }
    write_json(run_dir / "metrics.json", metrics)
    if args.split == "test":
        write_json(lock, {"run_dir": str(run_dir.relative_to(ROOT)), "git": metrics["git"], "at": metrics["created_at"]})

    a = metrics["all_cases"]
    line = (f"| {metrics['created_at']} | {args.split} | {label} | {a['n']} | {a['recall@1']} | {a['recall@5']} "
            f"{a['recall@5_ci95']} | {a['recall@10']} | {a['mrr@10']} | {a['doc_recall@10']} | "
            f"{(metrics['git']['commit'] or '')[:8]}{'*' if metrics['git']['dirty'] else ''} | {run_dir.name} |\n")
    if not RESULTS_MD.exists():
        RESULTS_MD.write_text(
            "# Kết quả benchmark truy xuất pháp luật chung\n\n"
            "Nguồn: data/dataset.csv. Chỉ đo truy xuất, không gọi LLM. Dấu * sau commit nghĩa là có thay đổi chưa commit.\n\n"
            "| Thời điểm | Split | Mode | n | R@1 | R@5 [CI95] | R@10 | MRR@10 | DocR@10 | Commit | Run |\n"
            "|---|---|---|---:|---:|---:|---:|---:|---:|---|---|\n", encoding="utf-8")
    with RESULTS_MD.open("a", encoding="utf-8") as f:
        f.write(line)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Đã lưu {run_dir}")


def cmd_compare(args) -> None:
    """Chênh MRR@10 ghép cặp (other - base) trên các qid chung, bootstrap 95%."""
    def rr(run_dir: str) -> dict[str, float]:
        path = Path(run_dir) / "predictions.jsonl"
        rows = (json.loads(line) for line in path.open(encoding="utf-8"))
        return {r["qid"]: (1.0 / r["rank"] if r["rank"] else 0.0) for r in rows}
    base, other = rr(args.base), rr(args.other)
    qids = sorted(set(base) & set(other))
    diffs = [other[q] - base[q] for q in qids]
    print(json.dumps({"n": len(qids), "mrr_base": round(sum(base[q] for q in qids) / len(qids), 4),
                      "mrr_other": round(sum(other[q] for q in qids) / len(qids), 4),
                      "diff": round(sum(diffs) / len(diffs), 4), "diff_ci95": bootstrap_ci(diffs)}, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("coverage")
    s = sub.add_parser("split")
    s.add_argument("--dev-pct", type=int, default=20)
    s.add_argument("--force", action="store_true")
    s.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--split", choices=["dev", "test"], required=True)
    r.add_argument("--mode", choices=["hybrid", "vector", "fts"], default="hybrid")
    r.add_argument("--k", type=int, default=10)
    r.add_argument("--fetch-factor", type=int, default=3, help="lấy k*factor chunk rồi gộp theo điều")
    r.add_argument("--limit", type=int, default=0, help="chỉ dùng cho dev, để chạy thử nhanh")
    r.add_argument("--only-covered", action="store_true", help="chỉ chạy câu có điều luật gold tìm kiếm được")
    r.add_argument("--rerun-test", action="store_true")
    r.add_argument("--variant", choices=list(VARIANTS), default="none", help="biến thể truy xuất đã khai báo (V1-V3)")
    c = sub.add_parser("compare")
    c.add_argument("--base", required=True)
    c.add_argument("--other", required=True)
    args = p.parse_args()
    {"coverage": cmd_coverage, "split": cmd_split, "run": cmd_run, "compare": cmd_compare}[args.cmd](args)


if __name__ == "__main__":
    main()

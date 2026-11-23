"""contract_eval_v1: chấm Giai đoạn A (retrieval) + B (generation), CI95 bootstrap, phân tích lỗi theo tầng, sinh báo cáo.

    python -m evaluation.contract_eval_v1.score [--run-dir DIR]     # metrics.json, per_case.csv, KET_QUA_BO_TEST_V1.md
    python -m evaluation.contract_eval_v1.score check [--run-dir DIR]  # đối chiếu mọi số trong báo cáo với metrics.json
    python -m evaluation.contract_eval_v1.score --run-dir DIR --report docs/.../KET_QUA_BO_TEST_V1_1.md --baseline-run DIR_V1
        # phiên bản hệ thống mới trên cùng bộ test: báo cáo riêng + bảng so sánh, chênh lệch QA theo cặp (bootstrap)

Chỉ đọc gold ở bước này. Mọi số trong báo cáo được sinh từ metrics.json / verification_stats.json qua hàm `N()`
và được ghi vào report_numbers.json để bước `check` đối chiếu lại.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from evaluation.contract_eval_v1.build import CASES, HERE, ROOT, SPLIT, V04, jl_read
from evaluation.contract_eval_v1.run import run_dir
from evaluation.contract_eval_v1.verify import QUAR, check_frozen, contract_text, coverage, parser_clauses

REPORT = ROOT / "docs" / "bo_test_hoi_dong" / "KET_QUA_BO_TEST_V1.md"
SEED, NBOOT = 42, 1000
ACTIONABLE = ("critical", "warning")


# ---------- hàm chấm thuần (có test) ----------
def path_key(path: str | None, level: str = "article") -> tuple | None:
    """'139264.C6.D98.K1.b' -> ('139264', 98) hoặc ('139264', 98, 1)."""
    if not path:
        return None
    labels = path.split(".")
    art = next((int(x[1:]) for x in labels if re.fullmatch(r"D\d+", x)), None)
    if art is None:
        return None
    if level == "article":
        return (labels[0], art)
    k = next((int(x[1:]) for x in labels[labels.index(f"D{art}") + 1:] if re.fullmatch(r"K\d+", x)), None)
    return (labels[0], art, k) if k is not None else None


def dedupe(xs):
    seen, out = set(), []
    for x in xs:
        if x is not None and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def rank_metrics(ranked: list, gold: set) -> dict:
    import math
    out = {}
    for k in (1, 3, 5, 10):
        out[f"recall@{k}"] = len(gold & set(ranked[:k])) / len(gold)
    out["precision@5"] = len(gold & set(ranked[:5])) / 5
    out["hit@5"] = float(bool(gold & set(ranked[:5])))
    first = next((i for i, x in enumerate(ranked) if x in gold), None)
    out["mrr"] = 0.0 if first is None else 1 / (first + 1)
    dcg = sum(1 / math.log2(i + 2) for i, x in enumerate(ranked[:10]) if x in gold)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(gold), 10)))
    out["ndcg@10"] = dcg / idcg
    return out


def hits_at(ranked: list, gold: set) -> dict:
    return {f"hit@{k}": float(bool(gold & set(ranked[:k]))) for k in (1, 3, 5)}


def prf(tp, fp, fn) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = (2 * p * r / (p + r) if p and r else 0.0) if p is not None and r is not None else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def bootstrap(units: list, fn, n: int = NBOOT, seed: int = SEED) -> list | None:
    if not units:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        v = fn([units[rng.randrange(len(units))] for _ in units])
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 4), round(vals[min(len(vals) - 1, int(0.975 * len(vals)))], 4)]


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def law_citations_in_text(answer: str, contract_clauses: set[str]) -> list[int]:
    """Số Điều luật nêu trong câu trả lời: 'Điều N' có từ khóa văn bản luật ngay sau, hoặc N không phải Điều hợp đồng."""
    out = []
    for m in re.finditer(r"Điều\s+(\d+)", answer or ""):
        tail = answer[m.end():m.end() + 60]
        lawish = re.search(r"Bộ luật|BLLĐ|Luật|Nghị định|Thông tư|\d+/\d{4}/", tail)
        contractish = re.match(r"\s*(của|trong)\s+hợp đồng", tail)
        if lawish and not contractish or (m.group(1) not in contract_clauses and not contractish):
            out.append(int(m.group(1)))
    return dedupe(out)


# ---------- nạp ----------
def jl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def mdict(rows: list[dict], fn_list: dict) -> dict:
    """Chỉ số trung bình + CI cho một tập dòng; fn_list: tên -> hàm(row)->số."""
    out = {"n": len(rows)}
    for name, f in fn_list.items():
        out[name] = round(mean([f(r) for r in rows]), 4) if rows and mean([f(r) for r in rows]) is not None else None
        out[name + "_ci95"] = bootstrap(rows, lambda s, f=f: mean([f(r) for r in s]))
    return out


# ---------- Giai đoạn A ----------
def stage_a_clause_split() -> dict:
    out = {}
    base_ids = re.findall(r"^Điều (\d+)\.", (ROOT / "evaluation/injection/base_contract.txt").read_text(encoding="utf-8"), re.M)
    quar = {r["id"] for r in jl_read(QUAR)}
    inj = {}
    for c in jl_read(CASES):
        if c["source_set"].startswith("injection") and c["template"] == "T1" and c["id"] not in quar:
            inj[c["contract_path"]] = c
    rows = []
    for p, c in sorted(inj.items()):
        parsed = parser_clauses(contract_text(p))
        slot = c["gold_clause_ids"][0]
        body = re.sub(r"^Điều\s+\d+\.\s*", "", c["gold_clause_text"].strip())
        rows.append({"exact": float(list(parsed) == base_ids), "id_recall": len(set(base_ids) & set(parsed)) / len(base_ids),
                     "span": float(slot in parsed and coverage(body, parsed[slot]) >= 0.9)})
    out["injection"] = mdict(rows, {"exact_clause_ids": lambda r: r["exact"], "clause_id_recall": lambda r: r["id_recall"],
                                     "injected_span_match": lambda r: r["span"]})
    data = json.loads((V04 / "MIXED_34_TEST_CASES_V04.json").read_text(encoding="utf-8"))
    rows = []
    for ct in data["contracts"]:
        parsed = parser_clauses(contract_text(f"evaluation/benchmark/v04/contracts/{ct['contract_id']}.docx"))
        gold = [re.sub(r"^(Điều|Khoản|Mục)\s+", "", g["clause_id"]).strip() for g in ct["clauses"]]
        spans = [float(gid in parsed and coverage(g["text"], parsed[gid]) >= 0.9) for gid, g in zip(gold, ct["clauses"])]
        rows.append({"exact": float(list(parsed) == gold), "id_recall": len(set(gold) & set(parsed)) / len(gold),
                     "span": mean(spans)})
    out["v04"] = mdict(rows, {"exact_clause_ids": lambda r: r["exact"], "clause_id_recall": lambda r: r["id_recall"],
                              "clause_span_match": lambda r: r["span"]})
    # 6 DOCX gold: 30 đơn vị Điều đã trích (annotation_template.csv), map file theo SHA-256 trong manifest
    import hashlib
    man = json.loads((ROOT / "evaluation/gold/contracts_manifest.json").read_text(encoding="utf-8"))
    # manifest băm văn bản đã parse (prepare_units.py), không băm file
    by_sha = {hashlib.sha256(contract_text(f.resolve().relative_to(ROOT).as_posix()).encode("utf-8")).hexdigest(): f
              for f in (ROOT / "evaluation/gold/contracts").glob("*.docx")}
    files = {cid: by_sha.get(v["sha256"]) for cid, v in man.items()}
    units = list(csv.DictReader((ROOT / "evaluation/gold/annotation_template.csv").open(encoding="utf-8-sig")))
    parsed_by = {cid: parser_clauses(contract_text(f.resolve().relative_to(ROOT).as_posix())) for cid, f in files.items() if f}
    rows = []
    for u in units:
        parsed = parsed_by.get(u["contract_id"], {})
        body = "\n".join(u["noi_dung"].strip().splitlines()[1:]) or u["noi_dung"]
        rows.append({"id": float(u["dieu"] in parsed), "span": float(u["dieu"] in parsed and coverage(body, parsed[u["dieu"]]) >= 0.9)})
    out["gold_docx"] = mdict(rows, {"clause_id_found": lambda r: r["id"], "clause_span_match": lambda r: r["span"]})
    out["gold_docx"]["files_matched_by_sha256"] = sum(f is not None for f in files.values())
    return out


def legal_rows(rows: list[dict], cases: dict, field: str) -> list[dict]:
    out = []
    for r in rows:
        c = cases[r["id"]]
        if not c["gold_legal_refs"] or field not in r:
            continue
        gold_a = {(g["doc_id"], g["article"]) for g in c["gold_legal_refs"]}
        ranked = dedupe(path_key(h["path"]) for h in r[field])
        m = rank_metrics(ranked, gold_a)
        gold_k = {(g["doc_id"], g["article"], g["clause"]) for g in c["gold_legal_refs"] if g["clause"]}
        if gold_k:
            rk = dedupe(path_key(h["path"], "clause") for h in r[field])
            m["clause_recall@5"] = len(gold_k & set(rk[:5])) / len(gold_k)
            m["clause_recall@10"] = len(gold_k & set(rk[:10])) / len(gold_k)
        out.append({"id": r["id"], "split": r["split"], **m})
    return out


LEGAL_METRICS = ["recall@1", "recall@3", "recall@5", "recall@10", "precision@5", "mrr", "ndcg@10", "hit@5",
                 "clause_recall@5", "clause_recall@10"]


def legal_summary(rows):
    return mdict(rows, {m: (lambda r, m=m: r.get(m)) for m in LEGAL_METRICS})


def stage_a(rd: Path, cases: dict) -> dict:
    out = {"clause_split": stage_a_clause_split()}
    for label in ("vector", "hybrid"):
        rows = jl(rd / f"retrieval_{label}.jsonl")
        if not rows:
            continue
        res = {}
        crow, qrow = [], []
        for r in rows:
            c = cases[r["id"]]
            if c["gold_clause_ids"] and r.get("contract_hits") is not None:
                ranked = dedupe(str(h["clause_number"]) for h in r["contract_hits"])
                crow.append({"id": r["id"], "split": r["split"], **hits_at(ranked, set(c["gold_clause_ids"]))})
            if c["gold_clause_ids"] and r.get("qa_contract_hits") is not None:
                ranked = dedupe(str(h["clause_number"]) for h in r["qa_contract_hits"])
                qrow.append({"id": r["id"], "split": r["split"], **hits_at(ranked, set(c["gold_clause_ids"]))})
        for split in ("test", "dev"):
            res[split] = {
                "contract_clause": mdict([x for x in crow if x["split"] == split], {f"hit@{k}": (lambda r, k=k: r[f"hit@{k}"]) for k in (1, 3, 5)}),
                "qa_contract_clause": mdict([x for x in qrow if x["split"] == split], {f"hit@{k}": (lambda r, k=k: r[f"hit@{k}"]) for k in (1, 3, 5)}),
                "legal_qa_path": legal_summary([x for x in legal_rows(rows, cases, "qa_legal_hits") if x["split"] == split]),
                "legal_clause_path": legal_summary([x for x in legal_rows(rows, cases, "clause_legal_hits") if x["split"] == split]),
                "legal_qa_path_by_template": {t: legal_summary([x for x in legal_rows(rows, cases, "qa_legal_hits")
                                                                 if x["split"] == split and cases[x["id"]]["template"] == t])
                                              for t in ("T1", "T2", "T3", "fixed")},
            }
        res["excluded_unmapped"] = sum(1 for r in rows if not cases[r["id"]]["gold_legal_refs"] and cases[r["id"]]["unmapped_refs"])
        res["latency_ms_p50"] = pct([r["retrieval_ms"] for r in rows], 0.5)
        res["latency_ms_p95"] = pct([r["retrieval_ms"] for r in rows], 0.95)
        res["temporal_v04"] = temporal_v04(rd, rows, label)
        out[label] = res
    return out


def temporal_v04(rd: Path, rows: list[dict], label: str) -> dict:
    """Đổi hit QA của ca v04 sang provision_id của v04 rồi chạy score_temporal_predictions.py có sẵn."""
    data = json.loads((V04 / "MIXED_34_TEST_CASES_V04.json").read_text(encoding="utf-8"))
    prov = {}
    for p in data["legal_provisions"]:
        if str(p.get("article") or "").isdigit():
            prov[(p["law_number"], int(p["article"]), int(p["clause"]) if str(p.get("clause") or "").isdigit() else None)] = p["provision_id"]
    ids = {c["id"] for c in data["test_cases"]}
    preds = []
    for r in rows:
        if r["id"] not in ids:
            continue
        cited, statutes = [], []
        for h in r["qa_legal_hits"][:10]:
            k = path_key(h["path"], "clause") or path_key(h["path"])
            num = h.get("doc_number")
            if not k or not num:
                continue
            statutes.append(num)
            for key in ((num, k[1], k[2] if len(k) == 3 else None), (num, k[1], None)):
                if key in prov:
                    cited.append(prov[key])
        preds.append({"id": r["id"], "cited_provision_ids": dedupe(cited), "relation_edge_ids": [],
                      "claimed_statute_ids": dedupe(statutes[:5])})
    f = rd / f"v04_predictions_{label}.jsonl"
    f.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in preds), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(V04 / "score_temporal_predictions.py"), "--pred", str(f)],
                          capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    out = {"n_cases": len(preds), "note": "relation_edge_ids không có trong đầu ra hệ thống (để trống)"}
    for line in proc.stdout.splitlines():
        m = re.match(r"(\w+): ([\d.]+) \(n=(\d+)\)", line)
        if m:
            out[m.group(1)] = {"value": float(m.group(2)), "n": int(m.group(3))}
    return out


# ---------- Giai đoạn B ----------
def db_articles() -> dict[str, set]:
    from app.infrastructure.db.connection import get_db
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_num, doc_id FROM legal_documents")
        return {"num2id": dict(cur.fetchall())}


def article_exists(doc_id: str, art: int, cache: dict) -> bool:
    from app.infrastructure.db.connection import get_db
    key = (doc_id, art)
    if key not in cache:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT EXISTS(SELECT 1 FROM legal_embeddings WHERE path ~ %s::lquery)", (f"{doc_id}.*.D{art}.*",))
            cache[key] = cur.fetchone()[0]
    return cache[key]


def cited_key(x: dict, num2id: dict) -> tuple | None:
    """(doc_id, điều) của một LegalCitation: ưu tiên evidence_path, không có thì số hiệu + chữ số trong 'Điều N'."""
    k = path_key(x.get("evidence_path"))
    if k:
        return k
    m = re.search(r"\d+", str(x.get("article") or ""))
    return (num2id.get(x.get("doc_number")), int(m.group(0))) if m and x.get("doc_number") else None


def detect_metrics(rows: list[dict], cases: dict, ver: dict) -> tuple[dict, list[dict]]:
    num2id = db_articles()["num2id"]
    cache: dict = {}
    per = []
    for r in rows:
        c = cases[r["case_id"]]
        y = c["gold_label"] == "violation"
        p = r.get("severity") in ACTIONABLE
        gold_a = {(g["doc_id"], g["article"]) for g in c["gold_legal_refs"]}
        ctx_a = {path_key(x) for x in r.get("context_paths") or []}
        cited = dedupe(cited_key(x, num2id) for x in r.get("citations") or [])
        not_db = [k for k in cited if not k[0] or not article_exists(k[0], k[1], cache)]
        not_ctx = [k for k in cited if k not in ctx_a]
        layer = None
        correct = y == p
        cite_ok = bool(gold_a & set(cited)) if gold_a else None
        if not correct:
            if not r.get("parsed_clause_found", True) or "parser_mismatch" in ver[c["id"]]["flags"]:
                layer = "a"
            elif gold_a and not (gold_a & ctx_a):
                layer = "b"
            else:
                layer = "c"
        elif y and cite_ok is False:
            layer = "d"
        per.append({"id": r["id"], "case_id": c["id"], "split": r["split"], "source_set": c["source_set"],
                    "rule_id": c["rule_id"], "phrasing_type": c["phrasing_type"], "gold": c["gold_label"],
                    "pred_positive": p, "severity": r.get("severity"), "y": y, "p": p,
                    "near_miss": c["gold_label"] == "compliant", "cite_ok": cite_ok, "n_cited": len(cited),
                    "halluc_not_db": len(not_db), "halluc_not_ctx": len(not_ctx), "gold_in_context": bool(gold_a & ctx_a) if gold_a else None,
                    "error_layer": layer, "tokens": r.get("tokens"), "total_ms": r.get("total_ms"), "status": r.get("status")})

    def summ(sub):
        def micro(s):
            return prf(sum(x["y"] and x["p"] for x in s), sum(x["p"] and not x["y"] for x in s), sum(x["y"] and not x["p"] for x in s))
        m = micro(sub)
        rules = sorted({x["rule_id"] for x in sub if x["rule_id"]})
        per_rule = {rr: micro([x for x in sub if x["rule_id"] == rr]) | {"n": sum(x["rule_id"] == rr for x in sub)} for rr in rules}
        f1s = [v["f1"] for v in per_rule.values() if v["f1"] is not None]
        nm = [x for x in sub if x["near_miss"]]
        cited_rows = [x for x in sub if x["n_cited"]]
        out = {"n": len(sub), "micro": m, "macro_f1_rules": round(mean(f1s), 4) if f1s else None, "per_rule": per_rule,
               "near_miss_n": len(nm), "near_miss_false_positive": sum(x["p"] for x in nm),
               "near_miss_fp_rate": round(sum(x["p"] for x in nm) / len(nm), 4) if nm else None,
               "citation_gold_article_rate": round(mean([float(x["cite_ok"]) for x in sub if x["y"] and x["cite_ok"] is not None]) or 0, 4),
               "citation_rows_with_any_citation": len(cited_rows),
               "halluc_not_in_db_rate": round(sum(x["halluc_not_db"] for x in sub) / max(1, sum(x["n_cited"] for x in sub)), 4),
               "halluc_not_in_context_rate": round(sum(x["halluc_not_ctx"] for x in sub) / max(1, sum(x["n_cited"] for x in sub)), 4),
               "tokens_mean": round(mean([x["tokens"] for x in sub]) or 0, 1),
               "latency_ms_p50": pct([x["total_ms"] for x in sub], 0.5), "latency_ms_p95": pct([x["total_ms"] for x in sub], 0.95)}
        for k in ("precision", "recall", "f1"):
            out[f"{k}_ci95"] = bootstrap(sub, lambda s, k=k: micro(s)[k])
        out["near_miss_fp_rate_ci95"] = bootstrap(nm, lambda s: sum(x["p"] for x in s) / len(s))
        errs = [x for x in sub if x["error_layer"]]
        out["error_layers"] = {L: sum(x["error_layer"] == L for x in sub) for L in "abcd"}
        out["error_layers_n_cases_with_error"] = len(errs)
        out["by_source"] = {s: micro([x for x in sub if x["source_set"] == s]) | {"n": sum(x["source_set"] == s for x in sub)}
                            for s in sorted({x["source_set"] for x in sub})}
        return out

    return {split: summ([x for x in per if x["split"] == split]) for split in ("test", "dev")}, per


def qa_metrics(rows: list[dict], cases: dict, judge: dict, cmaps: dict) -> tuple[dict, list[dict]]:
    per = []
    for r in rows:
        c = cases[r["case_id"]]
        j = judge.get(r["id"]) or {}
        claims = j.get("claims") or []
        faith = (sum(int(x.get("supported") or 0) for x in claims) / len(claims)) if claims else None
        cited = law_citations_in_text(r.get("answer", ""), cmaps.get(c["contract_path"], set()))
        ctx_arts = {k[1] for k in (path_key(p) for p in r.get("context_legal_paths") or []) if k}
        gold_arts = {g["article"] for g in c["gold_legal_refs"]}
        concl = j.get("answer_conclusion")
        per.append({"id": r["id"], "split": r["split"], "source_set": c["source_set"], "template": c["template"],
                    "gold": c["gold_label"], "judged": bool(j), "faithfulness": faith,
                    "correctness": j.get("correctness"), "conclusion": concl,
                    "conclusion_match": (float(concl == c["gold_label"]) if j and c["gold_label"] in ("violation", "compliant") else None),
                    "cite_gold": (float(bool(gold_arts & set(cited))) if gold_arts else None), "n_cited": len(cited),
                    "cited_not_in_ctx": sum(a not in ctx_arts for a in cited),
                    "contract_clause_hit": (float(bool(set(c["gold_clause_ids"]) & set(map(str, r.get("source_clauses") or []))))
                                            if c["gold_clause_ids"] else None),
                    "tokens": r.get("tokens"), "total_ms": r.get("total_ms")})

    def summ(sub):
        js = [x for x in sub if x["judged"]]
        out = mdict(js, {"faithfulness": lambda x: x["faithfulness"],
                         "correctness_norm": lambda x: None if x["correctness"] is None else x["correctness"] / 2,
                         "correctness_full": lambda x: None if x["correctness"] is None else float(x["correctness"] == 2),
                         "conclusion_match": lambda x: x["conclusion_match"]})
        out["n_answers"] = len(sub)
        out["n_judged"] = len(js)
        cg = mdict(sub, {"citation_gold_article": lambda x: x["cite_gold"], "source_clause_hit": lambda x: x["contract_clause_hit"]})
        out.update({k: v for k, v in cg.items() if k != "n"})
        out["cited_not_in_context_rate"] = round(sum(x["cited_not_in_ctx"] for x in sub) / max(1, sum(x["n_cited"] for x in sub)), 4)
        out["tokens_mean"] = round(mean([x["tokens"] for x in sub]) or 0, 1)
        out["latency_ms_p50"] = pct([x["total_ms"] for x in sub], 0.5)
        out["latency_ms_p95"] = pct([x["total_ms"] for x in sub], 0.95)
        out["by_template"] = {t: mdict([x for x in js if x["template"] == t], {"correctness_norm": lambda x: None if x["correctness"] is None else x["correctness"] / 2,
                                                                                "conclusion_match": lambda x: x["conclusion_match"]})
                              for t in sorted({x["template"] for x in js})}
        return out

    return {split: summ([x for x in per if x["split"] == split]) for split in ("test", "dev")}, per


def calibration(rd: Path, judge: dict) -> dict:
    f = rd / "calibration_key.json"
    if not f.exists():
        return {}
    key = json.loads(f.read_text(encoding="utf-8"))
    got = [(exp, judge[u].get("correctness")) for u, exp in key.items() if u in judge]
    agree = sum((g == 2) == (e == 2) for e, g in got)
    return {"n": len(got), "agreement": round(agree / len(got), 4) if got else None, "threshold": 0.8}


# ---------- tổng hợp ----------
def zalo_locked() -> dict:
    out = {}
    for lock in sorted((ROOT / "evaluation_results/legal_qa/test_locks").glob("*.lock")):
        rd = ROOT / json.loads(lock.read_text(encoding="utf-8"))["run_dir"].replace("\\", "/")
        m = json.loads((rd / "metrics.json").read_text(encoding="utf-8"))["covered_cases_only"]
        out[lock.stem] = {k: m.get(k) for k in ("n", "recall@1", "recall@5", "recall@5_ci95", "recall@10", "mrr@10")}
    return out


def cmd_score(args) -> None:
    rd = run_dir(args.run_dir)
    frozen = check_frozen()
    cases = {c["id"]: c for c in jl_read(CASES)}
    ver = {r["id"]: r for r in jl_read(HERE / "verification.jsonl")}
    vstats = json.loads((HERE / "verification_stats.json").read_text(encoding="utf-8"))
    gen = jl(rd / "generation.jsonl")
    judge = {r["id"]: r for r in jl(rd / "judge.jsonl")}
    cmap_paths = {c["contract_path"] for c in cases.values() if c["contract_path"]}
    cmaps = {p: set(parser_clauses(contract_text(p))) for p in cmap_paths}
    a = stage_a(rd, cases)
    det, det_rows = detect_metrics([g for g in gen if g["kind"] == "detect" and g["status"] == "completed"], cases, ver)
    qa, qa_rows = qa_metrics([g for g in gen if g["kind"] == "qa" and g["status"] == "completed"], cases, judge, cmaps)
    eval_cases = [c for c in cases.values() if c["id"] not in {r["id"] for r in jl_read(QUAR)}]
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    side = {u: "test" for u in split["test"]} | {u: "dev" for u in split["dev"]}
    expected = {"detect": {s: sum(1 for c in eval_cases if side[c["base_case_id"]] == s and c["template"] in ("T1", "fixed")
                               and c["gold_label"] in ("violation", "compliant") and c["contract_path"] and c["gold_clause_ids"])
                           for s in ("test", "dev")},
                "qa": {s: sum(1 for c in eval_cases if side[c["base_case_id"]] == s) for s in ("test", "dev")}}
    metrics = {
        "run_dir": rd.relative_to(ROOT).as_posix(), "frozen": frozen, "test_lock": (rd / "test.lock").exists(),
        "dataset": dataset_stats(cases, side), "verification": vstats,
        "stage_a": a, "stage_b": {"detect": det, "qa": qa, "judge_calibration": calibration(rd, judge),
                                  "completed": {"detect": {s: sum(1 for x in det_rows if x["split"] == s) for s in ("test", "dev")},
                                                "qa": {s: sum(1 for x in qa_rows if x["split"] == s) for s in ("test", "dev")}},
                                  "expected": expected, "failed_rows": sum(g["status"] != "completed" for g in gen),
                                  "models": sorted({g.get("model") for g in gen}),
                                  "judge_model": sorted({j.get("judge_model") for j in judge.values()})},
        "zalo_locked": zalo_locked(),
        "report": report_path(args).relative_to(ROOT).as_posix(),
        "test_lock_info": json.loads((rd / "test.lock").read_text(encoding="utf-8")) if (rd / "test.lock").exists() else None,
    }
    if getattr(args, "baseline_run", None):
        metrics["baseline"] = baseline(Path(args.baseline_run), qa_rows)
    (rd / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    with (rd / "per_case.csv").open("w", encoding="utf-8-sig", newline="") as f:
        keys = sorted({k for r in det_rows + qa_rows for k in r})
        w = csv.DictWriter(f, fieldnames=["kind"] + keys)
        w.writeheader()
        for r in det_rows:
            w.writerow({"kind": "detect", **r})
        for r in qa_rows:
            w.writerow({"kind": "qa", **r})
    write_report(metrics, rd)
    print(f"wrote {rd / 'metrics.json'}, per_case.csv, {metrics['report']}")


def report_path(args) -> Path:
    return (ROOT / args.report).resolve() if getattr(args, "report", None) else REPORT


def baseline(bd: Path, qa_rows: list[dict]) -> dict:
    """Chỉ số của phiên bản trước trên cùng bộ test + chênh lệch QA theo cặp câu (bootstrap theo câu, seed 42)."""
    bd = bd if bd.is_absolute() else ROOT / bd
    bm = json.loads((bd / "metrics.json").read_text(encoding="utf-8"))
    with (bd / "per_case.csv").open(encoding="utf-8-sig") as f:
        old = {r["id"]: r for r in csv.DictReader(f) if r["kind"] == "qa" and r["split"] == "test"}

    def num(v):
        return None if v in ("", None) else float(v)

    pairs = []
    for r in qa_rows:
        o = old.get(r["id"])
        if r["split"] != "test" or not o or not r["judged"] or o["judged"] != "True":
            continue
        pairs.append({"correctness_norm": (r["correctness"], num(o["correctness"])),
                      "conclusion_match": (r["conclusion_match"], num(o["conclusion_match"])),
                      "faithfulness": (r["faithfulness"], num(o["faithfulness"]))})

    def avg_diff(sub):
        return mean([a - b for a, b in sub])

    diff = {"n_pairs": len(pairs)}
    for k in ("correctness_norm", "conclusion_match", "faithfulness"):
        div = 2 if k == "correctness_norm" else 1
        sub = [(p[k][0] / div, p[k][1] / div) for p in pairs if p[k][0] is not None and p[k][1] is not None]
        diff[k] = {"n": len(sub), "diff": round(avg_diff(sub), 4) if sub else None, "ci95": bootstrap(sub, avg_diff),
                   "better": sum(a > b for a, b in sub), "worse": sum(a < b for a, b in sub)}
    lock = bm.get("test_lock_info") or {}
    return {"run_dir": bm["run_dir"], "system_version": lock.get("system_version") or "v1",
            "stage_a": bm["stage_a"], "stage_b": {"detect": bm["stage_b"]["detect"], "qa": bm["stage_b"]["qa"],
                                                  "models": bm["stage_b"]["models"], "judge_model": bm["stage_b"]["judge_model"]},
            "qa_paired_test": diff}


def dataset_stats(cases: dict, side: dict) -> dict:
    quar = {r["id"] for r in jl_read(QUAR)}
    out = {"n_cases": len(cases), "n_quarantine": len(quar), "n_eval": len(cases) - len(quar)}
    for key in ("source_set", "gold_label", "difficulty", "template"):
        cnt = defaultdict(int)
        for c in cases.values():
            if c["id"] not in quar:
                cnt[str(c[key])] += 1
        out[f"by_{key}"] = dict(sorted(cnt.items()))
    cnt = defaultdict(int)
    for c in cases.values():
        if c["id"] not in quar and c["rule_id"]:
            cnt[c["rule_id"]] += 1
    out["by_rule"] = dict(sorted(cnt.items()))
    out["by_split"] = {s: sum(1 for c in cases.values() if c["id"] not in quar and side[c["base_case_id"]] == s) for s in ("test", "dev")}
    return out


# ---------- báo cáo ----------
class Nums:
    """Mọi số trong báo cáo đi qua N(path) -> định dạng, và được ghi lại để `check` đối chiếu."""

    def __init__(self, metrics):
        self.m, self.used = metrics, []

    def get(self, path: str):
        cur, parts = self.m, path.split("/")
        while parts:
            p = parts.pop(0)
            if isinstance(cur, dict) and p not in cur and parts and f"{p}/{parts[0]}" in cur:  # khóa "n/a"
                p = f"{p}/{parts.pop(0)}"
            cur = cur[int(p)] if isinstance(cur, list) else cur.get(p) if isinstance(cur, dict) else None
            if cur is None:
                return None
        return cur

    def __call__(self, path: str, dec: int = 2) -> str:
        v = self.get(path)
        s = fmt(v, dec)
        self.used.append({"path": path, "dec": dec, "text": s})
        return s

    def ci(self, path: str, dec: int = 2) -> str:
        v = self.get(path)
        if not v:
            return ""
        return f" [{self(path + '/0', dec)}; {self(path + '/1', dec)}]"


def fmt(v, dec=2) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.{dec}f}".replace(".", ",")
    return str(v)


def write_comparison(m: dict, N, w) -> None:
    ver = (m.get("test_lock_info") or {}).get("system_version") or "mới"
    old = m["baseline"]["system_version"]
    w(f"## 0. So sánh {old} → {ver} (cùng bộ test đóng băng, phần test)")
    w("")
    w(f"Phiên bản trước: `{m['baseline']['run_dir']}`. Cùng ca, cùng nhãn, cùng model sinh và judge; chỉ code hệ thống khác. "
      "Mỗi cột kèm CI95 riêng; chênh lệch QA tính theo cặp câu ở bảng sau.")
    w("")
    w(f"| Chỉ số (test) | {old} | {ver} |")
    w("|---|---:|---:|")
    rows = []
    for label in ("vector", "hybrid"):
        if label in m["stage_a"] and label in m["baseline"]["stage_a"]:
            a = f"stage_a/{label}/test"
            rows += [(f"Truy xuất ({label}): R@5 luật, đường QA", f"{a}/legal_qa_path/recall@5", f"{a}/legal_qa_path/recall@5_ci95"),
                     (f"Truy xuất ({label}): MRR luật, đường QA", f"{a}/legal_qa_path/mrr", f"{a}/legal_qa_path/mrr_ci95"),
                     (f"Truy xuất ({label}): R@5 luật, đường phân tích", f"{a}/legal_clause_path/recall@5", f"{a}/legal_clause_path/recall@5_ci95")]
    dt, qt = "stage_b/detect/test", "stage_b/qa/test"
    rows += [("Phát hiện rủi ro: F1 (micro)", f"{dt}/micro/f1", f"{dt}/f1_ci95"),
             ("Phát hiện rủi ro: precision", f"{dt}/micro/precision", f"{dt}/precision_ci95"),
             ("Phát hiện rủi ro: recall", f"{dt}/micro/recall", f"{dt}/recall_ci95"),
             ("Phát hiện rủi ro: báo nhầm trên ca near-miss", f"{dt}/near_miss_fp_rate", f"{dt}/near_miss_fp_rate_ci95"),
             ("Phát hiện rủi ro: trích đúng Điều gold", f"{dt}/citation_gold_article_rate", None),
             ("QA: correctness (0–1)", f"{qt}/correctness_norm", f"{qt}/correctness_norm_ci95"),
             ("QA: tỷ lệ đúng đủ", f"{qt}/correctness_full", f"{qt}/correctness_full_ci95"),
             ("QA: kết luận khớp nhãn", f"{qt}/conclusion_match", f"{qt}/conclusion_match_ci95"),
             ("QA: faithfulness", f"{qt}/faithfulness", f"{qt}/faithfulness_ci95"),
             ("QA: trích đúng Điều gold", f"{qt}/citation_gold_article", f"{qt}/citation_gold_article_ci95"),
             ("QA: Điều luật nêu nhưng không có trong context", f"{qt}/cited_not_in_context_rate", None),
             ("QA: token trung bình", f"{qt}/tokens_mean", None),
             ("QA: độ trễ p50 (ms)", f"{qt}/latency_ms_p50", None)]
    for name, path, ci in rows:
        dec = 0 if ("tokens" in path or "latency" in path) else 2
        cells = [N(pre + path, dec) + (N.ci(pre + ci) if ci else "") for pre in ("baseline/", "")]
        w(f"| {name} | {cells[0]} | {cells[1]} |")
    w("")
    p = "baseline/qa_paired_test"
    w(f"Chênh lệch QA theo cặp câu ({ver} − {old}, n={N(p + '/n_pairs')}, bootstrap 1000 lần, seed 42):")
    w("")
    w("| Chỉ số | Chênh lệch | CI95 | Tốt hơn | Kém hơn |")
    w("|---|---:|---:|---:|---:|")
    for k, name in (("correctness_norm", "Correctness"), ("conclusion_match", "Kết luận khớp nhãn"), ("faithfulness", "Faithfulness")):
        w(f"| {name} | {N(f'{p}/{k}/diff')} |{N.ci(f'{p}/{k}/ci95')} | {N(f'{p}/{k}/better')} | {N(f'{p}/{k}/worse')} |")
    w("")
    if old != "v1":
        w(f"Thay đổi cách đo so với {old}: đường phân tích ở Giai đoạn A gọi đúng `risk_flagger._retrieve_legal` (gồm luật bổ sung theo "
          "chủ đề) thay vì gọi thẳng GraphRAG; QA đo như v1.1. Code QA không đổi giữa hai bản, nên chênh lệch QA là dao động của "
          "LLM sinh và judge; xem `evaluation/contract_eval_v1/DECISIONS.md`.")
        w("")
        return
    w("Thay đổi cách đo so với v1 (sửa cho đúng hệ thống đang chạy, không đổi ca hay nhãn): đường QA ở Giai đoạn A gọi đúng nút "
      "retrieve của QA thay vì tái dựng truy vấn cũ; `context_legal_paths` của QA lấy luật thực gửi model (sau bổ sung luật theo "
      "chủ đề) thay vì kết quả truy xuất thô. Hai chỉ số liên quan (R@5 đường QA, «không có trong context») vì vậy phản ánh cả thay "
      "đổi code lẫn thay đổi cách đo; xem `evaluation/contract_eval_v1/DECISIONS.md`.")
    w("")


def write_report(m: dict, rd: Path) -> None:
    N = Nums(m)
    d, v = "dataset", "verification"
    L = []
    w = L.append
    w("# Kết quả bộ test hợp nhất contract_eval_v1")
    w("")
    w(f"Thư mục kết quả: `{m['run_dir']}`. Bộ test đóng băng (SHA-256 trong `evaluation/contract_eval_v1/FROZEN.json`); "
      "số chính lấy trên phần **test**, chạy một lần (`test.lock`). Mọi số dưới đây sinh tự động từ `metrics.json` và "
      "`verification_stats.json`, đã đối chiếu bằng `python -m evaluation.contract_eval_v1.score check`.")
    w("")
    if "baseline" in m:
        write_comparison(m, N, w)
    w("## 1. Quy mô bộ test")
    w("")
    w(f"- Tổng {N(d + '/n_cases')} ca từ {N(v + '/n_base_units')} ca gốc; quarantine {N(d + '/n_quarantine')} ca; "
      f"còn {N(d + '/n_eval')} ca dùng để chấm (test {N(d + '/by_split/test')}, dev {N(d + '/by_split/dev')}).")
    w("- Nguồn: " + ", ".join(f"{k} {N(d + '/by_source_set/' + k)}" for k in m[d]["by_source_set"]) + ".")
    w("- Nhãn: " + ", ".join(f"{k} {N(d + '/by_gold_label/' + k)}" for k in m[d]["by_gold_label"]) + ".")
    w("- Độ khó: " + ", ".join(f"{k} {N(d + '/by_difficulty/' + k)}" for k in m[d]["by_difficulty"]) + ".")
    w("- Theo luật đỏ: " + ", ".join(f"{k} {N(d + '/by_rule/' + k)}" for k in m[d]["by_rule"]) + ".")
    w("- Template câu hỏi (injection): T1 phát hiện, T2 căn cứ, T3 tổng quát; v04 và contract_qa giữ nguyên câu hỏi (`fixed`): "
      + ", ".join(f"{k} {N(d + '/by_template/' + k)}" for k in m[d]["by_template"]) + ".")
    w("- Lý do quarantine (theo lớp kiểm): " + ", ".join(f"{k} {N(v + '/quarantine_by_layer/' + k)}" for k in m[v]["quarantine_by_layer"])
      + f"; ca gốc bị loại: {', '.join(m[v]['quarantine_base_units']) or 'không có'}.")
    w("")
    w("## 2. Tự kiểm nhãn (script + LLM kiểm chéo, không có người duyệt)")
    w("")
    w("| Lớp | Pass | Fail | Không áp dụng |")
    w("|---|---:|---:|---:|")
    for layer in ("V1", "V2", "V3", "V4", "V5", "V6", "V7"):
        w(f"| {layer} | {N(f'{v}/layers/{layer}/pass')} | {N(f'{v}/layers/{layer}/fail')} | {N(f'{v}/layers/{layer}/n/a')} |")
    w("")
    w(f"- V7 (Gemini: lần 1 {', '.join(m[v]['v7']['run1_models'])}; lần 2 {', '.join(m[v]['v7']['run2_models'])}; khác model sinh Groq `gpt-oss-120b`; nhiệt độ 0): {N(v + '/v7/complete_units')} ca gốc; "
      f"Cohen's kappa nhãn cấu tạo–LLM lần 1 = **{N(v + '/v7/run1_kappa', 3)}** (đồng thuận {N(v + '/v7/run1_agreement', 3)}), "
      f"lần 2 = **{N(v + '/v7/run2_kappa', 3)}** (đồng thuận {N(v + '/v7/run2_agreement', 3)}).")
    w(f"- Cả 2 lần khớp nhãn: {N(v + '/v7/both_runs_agree_with_label')}; 1 lần trái (giữ, `low_confidence`): {N(v + '/v7/one_run_contradicts')}; "
      f"2 lần trái (quarantine): {N(v + '/v7/both_runs_contradict')}. Tổng ca `low_confidence`: {N(v + '/n_low_confidence')}.")
    w(f"- V3: {N(v + '/ref_stats/quotes_checked')} đoạn trích luật so với văn bản trong kho (fuzzy ≥ 0,8), {N(v + '/ref_stats/refs_mismatch')} lượt ref lệch; "
      f"{N(v + '/n_unmapped_ref_cases')} ca có ref không có trong kho (loại khỏi chấm truy xuất điều luật).")
    w("- Chi tiết: `evaluation/contract_eval_v1/VERIFICATION_REPORT.md`.")
    w("")
    w("## 3. Giai đoạn A – Retrieval (trước LLM)")
    w("")
    cs = "stage_a/clause_split"
    w("**Tách điều khoản hợp đồng** (clause_parser, không LLM):")
    w("")
    w("| Tập | n hợp đồng/đơn vị | Đúng toàn bộ danh sách Điều | Recall mã Điều | Khớp văn bản |")
    w("|---|---:|---:|---:|---:|")
    w(f"| Hợp đồng bơm lỗi | {N(cs + '/injection/n')} | {N(cs + '/injection/exact_clause_ids')} | {N(cs + '/injection/clause_id_recall')} | {N(cs + '/injection/injected_span_match')} (Điều bơm) |")
    w(f"| v04 (7 hợp đồng) | {N(cs + '/v04/n')} | {N(cs + '/v04/exact_clause_ids')} | {N(cs + '/v04/clause_id_recall')} | {N(cs + '/v04/clause_span_match')} |")
    w(f"| 6 DOCX gold (đơn vị Điều đã trích) | {N(cs + '/gold_docx/n')} | – | {N(cs + '/gold_docx/clause_id_found')} | {N(cs + '/gold_docx/clause_span_match')} |")
    w("")
    for label in ("vector", "hybrid"):
        if label not in m["stage_a"]:
            continue
        b = f"stage_a/{label}/test"
        w(f"**Truy xuất ({label}, test)** – CI95 bootstrap 1000 lần, seed 42:")
        w("")
        w(f"- Điều khoản hợp đồng liên quan câu hỏi (n={N(b + '/contract_clause/n')}): Hit@1 {N(b + '/contract_clause/hit@1')}{N.ci(b + '/contract_clause/hit@1_ci95')}, "
          f"Hit@3 {N(b + '/contract_clause/hit@3')}, Hit@5 {N(b + '/contract_clause/hit@5')}{N.ci(b + '/contract_clause/hit@5_ci95')}.")
        if (Nums(m).get(b + "/qa_contract_clause/n") or 0) > 0:
            w(f"- Điều khoản hợp đồng QA thực đưa vào ngữ cảnh (nút retrieve, ưu tiên Điều được nêu trong câu hỏi; n={N(b + '/qa_contract_clause/n')}): "
              f"Hit@1 {N(b + '/qa_contract_clause/hit@1')}{N.ci(b + '/qa_contract_clause/hit@1_ci95')}, "
              f"Hit@5 {N(b + '/qa_contract_clause/hit@5')}{N.ci(b + '/qa_contract_clause/hit@5_ci95')}.")
        w("")
        w("| Điều luật (khớp mức Điều) | n | R@1 | R@3 | R@5 | R@10 | P@5 | MRR | nDCG@10 | Hit@5 | R@5 mức Khoản |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for path, name in (("legal_qa_path", "Theo câu hỏi (đường QA)"), ("legal_clause_path", "Theo điều khoản (đường phân tích)")):
            p = f"{b}/{path}"
            w(f"| {name} | {N(p + '/n')} | {N(p + '/recall@1')} | {N(p + '/recall@3')} | {N(p + '/recall@5')}{N.ci(p + '/recall@5_ci95')} | {N(p + '/recall@10')} | "
              f"{N(p + '/precision@5')} | {N(p + '/mrr')}{N.ci(p + '/mrr_ci95')} | {N(p + '/ndcg@10')} | {N(p + '/hit@5')} | {N(p + '/clause_recall@5')} |")
        for tpl in ("T1", "T2", "T3", "fixed"):
            p = f"{b}/legal_qa_path_by_template/{tpl}"
            w(f"| ↳ đường QA, câu {tpl} | {N(p + '/n')} | {N(p + '/recall@1')} | {N(p + '/recall@3')} | {N(p + '/recall@5')} | {N(p + '/recall@10')} | "
              f"{N(p + '/precision@5')} | {N(p + '/mrr')} | {N(p + '/ndcg@10')} | {N(p + '/hit@5')} | {N(p + '/clause_recall@5')} |")
        w("")
        if (Nums(m).get(b + "/qa_contract_clause/n") or 0) > 0:
            w("Đường QA truy xuất luật từ câu hỏi đã gắn nội dung Điều hợp đồng được nêu, cộng luật bổ sung theo chủ đề; câu T3 không nêu Điều cụ thể "
              "nên vẫn chỉ có câu hỏi chung chung để truy xuất. Đường phân tích truy xuất từ chính nội dung điều khoản.")
        else:
            w("Đường QA truy xuất luật chỉ từ câu hỏi (ngữ cảnh hợp đồng đi riêng), nên câu T1/T3 chỉ nêu số Điều hợp đồng gần như không mang thông tin chủ đề; "
              "đường phân tích truy xuất từ chính nội dung điều khoản.")
        w("")
        t = f"stage_a/{label}/temporal_v04"
        tv = m["stage_a"][label]["temporal_v04"]
        w(f"- v04 thời điểm (score_temporal_predictions.py, {N(t + '/n_cases')} câu): " + ", ".join(
            f"{k} {N(t + '/' + k + '/value', 3)} (n={N(t + '/' + k + '/n')})" for k in tv if isinstance(tv[k], dict)) + ".")
        w(f"- Ca loại khỏi chấm điều luật vì ref không có trong kho: {N(f'stage_a/{label}/excluded_unmapped')}. Độ trễ truy xuất p50 {N(f'stage_a/{label}/latency_ms_p50', 0)} ms, p95 {N(f'stage_a/{label}/latency_ms_p95', 0)} ms.")
        w("")
    z = m["zalo_locked"]
    w("**Zalo legal retrieval (đã khóa, không chạy lại):** " + "; ".join(
        f"{k}: R@5 {N(f'zalo_locked/{k}/recall@5', 3)}{N.ci(f'zalo_locked/{k}/recall@5_ci95', 3)}, MRR@10 {N(f'zalo_locked/{k}/mrr@10', 3)} (n={N(f'zalo_locked/{k}/n')})"
        for k in z) + ".")
    w("")
    w("## 4. Giai đoạn B – Generation (sau LLM)")
    w("")
    sb = "stage_b"
    w(f"LLM hệ thống: {', '.join(m[sb]['models']) or 'chưa chạy'}; judge: {', '.join(x for x in m[sb]['judge_model'] if x) or 'chưa chạy'}. "
      f"Đã hoàn tất: phát hiện {N(sb + '/completed/detect/test')}/{N(sb + '/expected/detect/test')} ca test, "
      f"QA {N(sb + '/completed/qa/test')}/{N(sb + '/expected/qa/test')} câu test.")
    w("")
    dt = f"{sb}/detect/test"
    if m[sb]["detect"]["test"]["n"]:
        w(f"**Phát hiện rủi ro** (đơn vị: ca gốc; dương tính = critical/warning tại Điều gold; `evaluate_clause` thật, n={N(dt + '/n')}):")
        w("")
        w("| Chỉ số | Giá trị (test) |")
        w("|---|---:|")
        w(f"| Precision (micro) | {N(dt + '/micro/precision')}{N.ci(dt + '/precision_ci95')} |")
        w(f"| Recall (micro) | {N(dt + '/micro/recall')}{N.ci(dt + '/recall_ci95')} |")
        w(f"| F1 (micro) | {N(dt + '/micro/f1')}{N.ci(dt + '/f1_ci95')} |")
        w(f"| F1 macro theo luật đỏ | {N(dt + '/macro_f1_rules')} |")
        w(f"| Tỷ lệ báo nhầm trên ca near-miss/phủ định | {N(dt + '/near_miss_fp_rate')}{N.ci(dt + '/near_miss_fp_rate_ci95')} ({N(dt + '/near_miss_false_positive')}/{N(dt + '/near_miss_n')}) |")
        w(f"| Trích đúng Điều gold (ca vi phạm) | {N(dt + '/citation_gold_article_rate')} |")
        w(f"| Trích dẫn ảo: Điều không có trong kho | {N(dt + '/halluc_not_in_db_rate')} |")
        w(f"| Trích dẫn ảo: Điều không có trong context đã truy xuất | {N(dt + '/halluc_not_in_context_rate')} |")
        w("")
        w("| Luật đỏ | n | P | R | F1 |")
        w("|---|---:|---:|---:|---:|")
        for rr in m[sb]["detect"]["test"]["per_rule"]:
            p = f"{dt}/per_rule/{rr}"
            w(f"| {rr} | {N(p + '/n')} | {N(p + '/precision')} | {N(p + '/recall')} | {N(p + '/f1')} |")
        w("")
    qt = f"{sb}/qa/test"
    if m[sb]["qa"]["test"]["n_answers"]:
        w(f"**Hỏi đáp** (QaPipeline thật, mỗi câu một hội thoại mới; {N(qt + '/n_answers')} câu test, judge chấm {N(qt + '/n_judged')}):")
        w("")
        w("| Chỉ số | Giá trị (test) |")
        w("|---|---:|")
        w(f"| Faithfulness (tỷ lệ mệnh đề được context hỗ trợ) | {N(qt + '/faithfulness')}{N.ci(qt + '/faithfulness_ci95')} |")
        w(f"| Answer correctness (0–2, chuẩn hóa 0–1) | {N(qt + '/correctness_norm')}{N.ci(qt + '/correctness_norm_ci95')} |")
        w(f"| Tỷ lệ đúng đủ (điểm 2) | {N(qt + '/correctness_full')}{N.ci(qt + '/correctness_full_ci95')} |")
        w(f"| Kết luận khớp gold_label (T1/T3/fixed) | {N(qt + '/conclusion_match')}{N.ci(qt + '/conclusion_match_ci95')} |")
        w(f"| Trích đúng Điều gold trong câu trả lời | {N(qt + '/citation_gold_article')}{N.ci(qt + '/citation_gold_article_ci95')} |")
        w(f"| Điều luật nêu trong câu trả lời nhưng không có trong context | {N(qt + '/cited_not_in_context_rate')} |")
        w(f"| Nguồn điều khoản hợp đồng đúng (source_clauses chứa Điều gold) | {N(qt + '/source_clause_hit')} |")
        w("")
        cal = f"{sb}/judge_calibration"
        w(f"Hiệu chuẩn judge: {N(cal + '/n')} câu trả lời tham chiếu (một nửa đúng, một nửa đảo kết luận) trên ca nhãn chắc chắn; "
          f"đồng thuận judge–gold = **{N(cal + '/agreement')}**" + (
              "." if (m[sb]["judge_calibration"].get("agreement") or 0) >= 0.8 else
              " (< 0,8: số faithfulness/correctness chỉ mang tính tham khảo)."))
        w("")
    w("## 5. Phân tích lỗi theo tầng (phát hiện rủi ro, test)")
    w("")
    if m[sb]["detect"]["test"]["n"]:
        w("| Tầng | Ý nghĩa | Số ca |")
        w("|---|---|---:|")
        for k, txt in (("a", "tách điều khoản sai"), ("b", "retrieval không lấy được luật gold"),
                       ("c", "có luật gold trong context nhưng LLM kết luận sai"), ("d", "đúng kết luận nhưng trích sai Điều")):
            w(f"| ({k}) | {txt} | {N(dt + '/error_layers/' + k)} |")
        w("")
        w(f"Chi phí mỗi ca phát hiện: token trung bình {N(dt + '/tokens_mean', 0)}, độ trễ p50 {N(dt + '/latency_ms_p50', 0)} ms, p95 {N(dt + '/latency_ms_p95', 0)} ms.")
        if m[sb]["qa"]["test"]["n_answers"]:
            w(f"Mỗi câu QA: token trung bình {N(qt + '/tokens_mean', 0)}, độ trễ p50 {N(qt + '/latency_ms_p50', 0)} ms, p95 {N(qt + '/latency_ms_p95', 0)} ms.")
    else:
        w("Chưa có kết quả Giai đoạn B (xem mục 7).")
    w("")
    w("## 6. Giới hạn")
    w("")
    w("- Ca hợp đồng tự xây bằng **bơm lỗi** (một Điều sai trên hợp đồng nền) và câu hỏi theo template; không đại diện tỷ lệ đúng trên hợp đồng thực tế.")
    w("- Nhãn được kiểm chéo bằng script và một LLM khác (Gemini), **chưa có luật sư xác nhận**.")
    w("- Phát hiện rủi ro đo bằng `evaluate_clause` (truy xuất + judge) trên Điều gold, không chạy toàn bộ workflow (bỏ lớp luật cố định và hợp nhất kết quả) để tiết kiệm quota; QA tắt bộ nhớ dài hạn để các câu độc lập.")
    w("- Trích dẫn trong câu trả lời QA nhận diện bằng regex «Điều N». QA còn chèn đoạn trích BLLĐ cố định (`matching_law_blurbs`) không có path trong kho, "
      "nên tỷ lệ «Điều không có trong context» của QA bị đếm cao hơn thực tế.")
    w("- Judge faithfulness/correctness là LLM khác họ model sinh (Groq `qwen/qwen3.8-27b`; quota Gemini miễn phí không đủ). "
      "Hiệu chuẩn dùng câu trả lời tham chiếu ngắn, dễ phân biệt, nên đồng thuận cao ở đây chưa chứng minh judge chấm đúng câu trả lời dài.")
    w("- V7 lần 2 chạy phần lớn bằng `gemini-3-flash-preview` vì `gemini-2.5-flash` hết quota ngày giữa chừng.")
    w("- Bộ dev nhỏ (chia theo ca gốc, phân tầng); chỉ số theo từng luật đỏ có n nhỏ, CI rộng.")
    w("")
    w("## 7. Lệnh tái lập")
    w("")
    w("```bash")
    for cmd in ("python -m evaluation.contract_eval_v1.build", "python -m evaluation.contract_eval_v1.verify",
                "python -m evaluation.contract_eval_v1.run index", "python -m evaluation.contract_eval_v1.run retrieval --label vector",
                "LEGAL_RETRIEVAL_MODE=hybrid python -m evaluation.contract_eval_v1.run retrieval --label hybrid",
                "python -m evaluation.contract_eval_v1.run generation", "python -m evaluation.contract_eval_v1.run judge",
                "python -m evaluation.contract_eval_v1.score", "python -m evaluation.contract_eval_v1.score check"):
        w(cmd)
    w("```")
    w("Trên host cần `DATABASE_URL=postgresql://contractlens:contractlens@127.0.0.1:5433/contractlens`.")
    (ROOT / m.get("report", REPORT.relative_to(ROOT).as_posix())).write_text("\n".join(L) + "\n", encoding="utf-8")
    (rd / "report_numbers.json").write_text(json.dumps(N.used, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_check(args) -> None:
    """Mọi số đã ghi trong report_numbers.json phải: (1) vẫn bằng giá trị hiện tại trong metrics.json, (2) xuất hiện trong báo cáo."""
    rd = run_dir(args.run_dir)
    m = json.loads((rd / "metrics.json").read_text(encoding="utf-8"))
    used = json.loads((rd / "report_numbers.json").read_text(encoding="utf-8"))
    text = (ROOT / m.get("report", REPORT.relative_to(ROOT).as_posix())).read_text(encoding="utf-8")
    N = Nums(m)
    bad = [u for u in used if fmt(N.get(u["path"]), u["dec"]) != u["text"] or u["text"] not in text]
    # số trong bảng mà không đến từ metrics
    known = {u["text"] for u in used}
    stray = [x for line in text.splitlines() if line.startswith("|")
             for x in re.findall(r"(?<![\w@.])-?\d+(?:,\d+)?(?![\w@])", line) if x not in known and not re.fullmatch(r"\d", x)]
    print(f"checked {len(used)} numbers; mismatches {len(bad)}; stray table numbers {len(stray)}")
    if bad or stray:
        for u in bad[:20]:
            print("MISMATCH", u)
        print("STRAY", stray[:20])
        raise SystemExit(1)
    print("report numbers OK")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="score", choices=["score", "check"])
    ap.add_argument("--run-dir")
    ap.add_argument("--report", help="đường dẫn báo cáo (tương đối ROOT); mặc định KET_QUA_BO_TEST_V1.md")
    ap.add_argument("--baseline-run", help="thư mục run của phiên bản trước để so sánh trên cùng bộ test")
    args = ap.parse_args()
    (cmd_check if args.cmd == "check" else cmd_score)(args)


if __name__ == "__main__":
    main()

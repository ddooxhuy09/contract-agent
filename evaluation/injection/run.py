"""Bộ bơm lỗi hợp đồng (nhãn biết trước do cấu tạo): đo phát hiện 8 luật đỏ của labor_red_flags.

Mỗi ca = hợp đồng nền sạch (base_contract.txt) với đúng một Điều bị thay bằng clause_text của ca.
Nhãn (violation/compliant) có được do cách viết ca, không cần chuyên gia; xem README.md về giới hạn.

  python -m evaluation.injection.run build        # sinh contracts/*.txt + manifest.json
  python -m evaluation.injection.run check        # kiểm thiết kế (không chạy hệ thống)
  python -m evaluation.injection.run rule-only    # quy tắc xác định, không LLM, toàn bộ ca
  python -m evaluation.injection.run full [--limit N] [--all]   # pipeline đầy đủ (Gemini), có resume
  python -m evaluation.injection.run report [--config rule_only|full]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = HERE / "cases.jsonl"
BASE = HERE / "base_contract.txt"
CONTRACTS = HERE / "contracts"
OUT = ROOT / "evaluation_results" / "injection"
RULES = ["ot_unpaid", "no_bhxh", "retain_id_papers", "training_cost_flat",
         "fine_deduct_wage", "forfeit_wage_quit", "terminate_pregnancy", "ban_lawsuit"]
SAMPLE_SEED = 20261109  # khai báo trước: mẫu 3 vi phạm + 3 hợp lệ mỗi luật
BOOT_SEED, BOOT_N = 20261109, 1000
ACTIONABLE = ("critical", "warning")


# ---------- dữ liệu ----------
def load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_contract(base: str, case: dict) -> str:
    """Thay đúng một Điều (slot) của hợp đồng nền bằng clause_text của ca."""
    n = int(case["slot"])
    pattern = re.compile(rf"^Điều {n}\. .*?(?=^Điều {n + 1}\. |^NGƯỜI LAO ĐỘNG)", re.M | re.S)
    if len(pattern.findall(base)) != 1:
        raise ValueError(f"{case['case_id']}: không tìm thấy đúng một Điều {n} trong hợp đồng nền")
    return pattern.sub(lambda _: case["clause_text"].strip() + "\n\n", base, count=1)


def sample_ids(cases: list[dict]) -> list[str]:
    """3 vi phạm + 3 hợp lệ mỗi luật (seed cố định), xếp xen kẽ để dừng giữa chừng vẫn cân bằng."""
    rng = random.Random(SAMPLE_SEED)
    pick: dict[tuple[str, str], list[str]] = {}
    for rule in RULES:
        for label in ("violation", "compliant"):
            ids = sorted(c["case_id"] for c in cases if c["rule_id"] == rule and c["label"] == label)
            pick[(rule, label)] = rng.sample(ids, 3)
    return [pick[(rule, label)][i] for i in range(3) for rule in RULES for label in ("violation", "compliant")]


# ---------- chấm điểm (hàm thuần, có test) ----------
def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}


def case_rule_vector(case: dict, fired: set[str]) -> dict[str, tuple[int, int, int]]:
    """Với mỗi luật r: (tp, fp, fn) của ca này. Dương tính thật của r = ca vi phạm đúng luật r."""
    out = {}
    for r in RULES:
        y = case["rule_id"] == r and case["label"] == "violation"
        p = r in fired
        out[r] = (int(y and p), int(p and not y), int(y and not p))
    return out


def score_rule_level(cases: list[dict], fired_by_case: dict[str, set[str]], n_boot: int = BOOT_N) -> dict:
    vecs = {c["case_id"]: case_rule_vector(c, fired_by_case[c["case_id"]]) for c in cases}

    def agg(subset: list[dict]) -> dict:
        per = {}
        for r in RULES:
            tp = sum(vecs[c["case_id"]][r][0] for c in subset)
            fp = sum(vecs[c["case_id"]][r][1] for c in subset)
            fn = sum(vecs[c["case_id"]][r][2] for c in subset)
            per[r] = prf(tp, fp, fn)
        tp, fp, fn = (sum(per[r][k] for r in RULES) for k in ("tp", "fp", "fn"))
        return {"per_rule": per, "micro": prf(tp, fp, fn)}

    out = agg(cases)
    nm = [c for c in cases if c["label"] == "compliant"]
    for r in RULES:  # false positive trên near-miss: luật của chính nó kích hoạt trên ca hợp lệ của nó
        own = [c for c in nm if c["rule_id"] == r]
        out["per_rule"][r]["near_miss_false_positive"] = sum(r in fired_by_case[c["case_id"]] for c in own)
        out["per_rule"][r]["near_miss_n"] = len(own)
    out["near_miss_any_rule_fired"] = sum(bool(fired_by_case[c["case_id"]]) for c in nm)
    out["near_miss_n"] = len(nm)
    out["micro_ci95"] = bootstrap(cases, lambda s: agg(s)["micro"], n_boot)
    return out


def score_clause_level(cases: list[dict], pred: dict[str, dict], n_boot: int = BOOT_N) -> dict:
    """Pipeline đầy đủ: dương tính khi có rủi ro critical/warning tại Điều đã bơm. Chưa kiểm = âm tính."""
    def row(c):
        p = pred[c["case_id"]]
        return int(c["label"] == "violation"), int(bool(p["slot_flagged"])), int(bool(p["slot_unchecked"]))

    def agg(subset: list[dict]) -> dict:
        def conf(sub):
            tp = fp = fn = tn = unchecked = 0
            for c in sub:
                y, p, u = row(c)
                tp += y and p; fp += (not y) and p; fn += y and not p; tn += (not y) and not p; unchecked += u
            return {**prf(tp, fp, fn), "tn": tn, "unchecked": unchecked, "n": len(sub)}
        return {"per_rule": {r: conf([c for c in subset if c["rule_id"] == r]) for r in RULES},
                "micro": conf(subset)}

    out = agg(cases)
    out["micro_ci95"] = bootstrap(cases, lambda s: agg(s)["micro"], n_boot)
    return out


def bootstrap(cases: list[dict], metric, n_boot: int) -> dict:
    rng = random.Random(BOOT_SEED)
    draws = {"precision": [], "recall": [], "f1": []}
    for _ in range(n_boot):
        m = metric([cases[rng.randrange(len(cases))] for _ in cases])
        for k in draws:
            if m[k] is not None:
                draws[k].append(m[k])
    out = {}
    for k, v in draws.items():
        v.sort()
        out[k] = [round(v[int(0.025 * len(v))], 4), round(v[min(len(v) - 1, int(0.975 * len(v)))], 4)] if v else None
    return out


# ---------- lệnh ----------
def cmd_build(_) -> None:
    base = BASE.read_text(encoding="utf-8")
    CONTRACTS.mkdir(exist_ok=True)
    manifest = {"base_sha256": hashlib.sha256(base.encode("utf-8")).hexdigest(),
                "cases_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(), "contracts": {}}
    for c in load_cases():
        text = build_contract(base, c)
        (CONTRACTS / f"{c['case_id']}.txt").write_text(text, encoding="utf-8", newline="\n")
        manifest["contracts"][c["case_id"]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {len(manifest['contracts'])} contracts")


def cmd_check(_) -> None:
    """Kiểm thiết kế TRƯỚC khi đóng băng: cấu trúc ca, nền sạch, và yêu cầu >=2/5 vi phạm né regex."""
    from app.agents.labor_red_flags import _FLAGS

    pats = {f.key: f.pattern for f in _FLAGS}
    cases = load_cases()
    assert sorted(pats) == sorted(RULES), (sorted(pats), sorted(RULES))
    base = BASE.read_text(encoding="utf-8")
    base_hits = [k for k, p in pats.items() if p.search(base)]
    print("regex trúng hợp đồng nền (phải rỗng):", base_hits)
    problems = []
    for r in RULES:
        mine = [c for c in cases if c["rule_id"] == r]
        v = [c for c in mine if c["label"] == "violation"]
        n = [c for c in mine if c["label"] == "compliant"]
        miss = [c["case_id"] for c in v if not pats[r].search(c["clause_text"])]
        hit_nm = [c["case_id"] for c in n if pats[r].search(c["clause_text"])]
        print(f"{r:20s} vi phạm={len(v)} hợp lệ={len(n)} | vi phạm né regex={len(miss)} | hợp lệ mà regex trúng={len(hit_nm)}")
        if len(v) != 5 or len(n) != 5 or len(miss) < 2:
            problems.append(r)
    for c in cases:
        lines = c["clause_text"].splitlines()
        if any(re.match(r"\s*Điều\b", ln) for ln in lines[1:]):
            problems.append(f"{c['case_id']}: dòng thân bắt đầu bằng 'Điều' (bị chunker coi là tiêu đề)")
        build_contract(base, c)
    if base_hits or problems:
        raise SystemExit(f"THIẾT KẾ CHƯA ĐẠT: {base_hits} {problems}")
    print("thiết kế đạt")


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def cmd_rule_only(_) -> None:
    from app.agents.labor_red_flags import check_labor_red_flags

    cases = load_cases()
    OUT.mkdir(parents=True, exist_ok=True)
    preds = {}
    for c in cases:
        text = (CONTRACTS / f"{c['case_id']}.txt").read_text(encoding="utf-8")
        items = check_labor_red_flags(text, None)
        preds[c["case_id"]] = [{"clause_ref": i.clause_ref, "severity": i.severity,
                                "keys": [f.key for f in (i.findings or [])]} for i in items]
    out = OUT / "rule_only.json"
    out.write_text(json.dumps({"commit": _commit(), "predictions": preds}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out}")


def _slot_number(ref: str) -> str:
    m = re.search(r"\d+", ref or "")
    return m.group(0) if m else ""


def cmd_full(args) -> None:
    from app.infrastructure.container import build_container
    from app.infrastructure.retrieval.context import bind_retrieval
    from app.agents.workflow import run_analysis_workflow

    cases = {c["case_id"]: c for c in load_cases()}
    order = list(cases) if args.all else sample_ids(list(cases.values()))
    cache = OUT / "full"
    cache.mkdir(parents=True, exist_ok=True)
    cont = build_container()
    bind_retrieval(cont.contract_search, cont.legal_search, cont.graph,
                   legal_chunks=cont.legal_chunks, contract_chunks=cont.contract_chunks)
    done, stalled = 0, 0
    for cid in order:
        f = cache / f"{cid}.json"
        if f.exists():
            continue
        if args.limit and done >= args.limit:
            break
        c = cases[cid]
        text = (CONTRACTS / f"{cid}.txt").read_text(encoding="utf-8")
        analysis, risks = asyncio.run(run_analysis_workflow(text, f"inj-{cid}"))
        slot = str(c["slot"])
        cov = analysis.coverage or {}
        unchecked_slots = {_slot_number(u.get("clause_ref")) for u in cov.get("chua_kiem_chi_tiet", [])}
        rec = {
            "case_id": cid, "slot_unchecked": slot in unchecked_slots,
            "unchecked_clauses": sorted(unchecked_slots - {""}),
            "slot_flagged": any(r.severity in ACTIONABLE and _slot_number(r.clause_ref) == slot for r in risks),
            "other_clause_flags": sorted({_slot_number(r.clause_ref) for r in risks
                                          if r.severity in ACTIONABLE and _slot_number(r.clause_ref) != slot}),
            "risks": [{"clause_ref": r.clause_ref, "severity": r.severity, "title": r.title,
                       "keys": [x.key for x in (r.findings or [])]} for r in risks],
            "coverage": {k: cov.get(k) for k in ("tong_so_dieu", "da_kiem", "chua_kiem")},
            "commit": _commit(),
        }
        if rec["slot_unchecked"]:  # hết quota/lỗi judge: không lưu, thử lại ở lần chạy sau
            stalled += 1
            print(f"{cid}: Điều {slot} CHƯA KIỂM (quota/lỗi judge), không lưu; chạy lại sau")
            if stalled >= 2:
                print("2 ca liên tiếp chưa kiểm: dừng. Chạy lại lệnh này khi quota hồi.")
                break
            continue
        stalled = 0
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        done += 1
        print(f"{cid}: slot_flagged={rec['slot_flagged']} other={rec['other_clause_flags']} unchecked={rec['unchecked_clauses']}")
    print(f"đã lưu thêm {done}; tổng trong cache: {len(list(cache.glob('*.json')))}/{len(order)}")


def _fmt(v) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def cmd_report(args) -> None:
    cases = load_cases()
    lines = []
    if args.config == "rule_only":
        data = json.loads((OUT / "rule_only.json").read_text(encoding="utf-8"))
        fired = {cid: {k for it in items for k in it["keys"]} for cid, items in data["predictions"].items()}
        s = score_rule_level(cases, fired)
        lines += [f"# Bơm lỗi: rule-only (không LLM), n={len(cases)} ca, commit `{data['commit'][:8]}`", "",
                  "| Luật | TP | FP | FN | Precision | Recall | F1 | FP trên near-miss của chính nó |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for r in RULES:
            p = s["per_rule"][r]
            lines.append(f"| {r} | {p['tp']} | {p['fp']} | {p['fn']} | {_fmt(p['precision'])} | {_fmt(p['recall'])} | {_fmt(p['f1'])} | {p['near_miss_false_positive']}/{p['near_miss_n']} |")
        m, ci = s["micro"], s["micro_ci95"]
        lines += [f"| **Tổng (micro)** | {m['tp']} | {m['fp']} | {m['fn']} | {_fmt(m['precision'])} [{ci['precision']}] | {_fmt(m['recall'])} [{ci['recall']}] | {_fmt(m['f1'])} [{ci['f1']}] | {s['near_miss_any_rule_fired']}/{s['near_miss_n']} ca hợp lệ bị kích hoạt luật bất kỳ |"]
        lines += ["", "CI95 bootstrap theo ca (1000 lần). Mỗi luật chỉ có 10 ca nên chỉ số theo từng luật rất thô."]
        (OUT / "rule_only_scores.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        cache = OUT / "full"
        pred = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in cache.glob("*.json")}
        done = [c for c in cases if c["case_id"] in pred]
        s = score_clause_level(done, pred)
        lines += [f"# Bơm lỗi: pipeline đầy đủ (Gemini), {len(done)}/{len(sample_ids(cases))} ca mẫu đã hoàn tất", "",
                  "| Luật | n | TP | FP | FN | TN | Precision | Recall | F1 | Chưa kiểm |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in RULES:
            p = s["per_rule"][r]
            lines.append(f"| {r} | {p['n']} | {p['tp']} | {p['fp']} | {p['fn']} | {p['tn']} | {_fmt(p['precision'])} | {_fmt(p['recall'])} | {_fmt(p['f1'])} | {p['unchecked']} |")
        m, ci = s["micro"], s["micro_ci95"]
        lines += [f"| **Tổng** | {m['n']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | {_fmt(m['precision'])} [{ci['precision']}] | {_fmt(m['recall'])} [{ci['recall']}] | {_fmt(m['f1'])} [{ci['f1']}] | {m['unchecked']} |"]
        extra = sum(bool(pred[c["case_id"]]["other_clause_flags"]) for c in done)
        lines += ["", f"Ca có cờ rủi ro ở Điều khác ngoài Điều bơm (nền sạch bị gắn cờ): {extra}/{len(done)}."]
        (OUT / "full_scores.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    text = "\n".join(lines) + "\n"
    (OUT / f"REPORT_{args.config}.md").write_text(text, encoding="utf-8")
    print(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "check", "rule-only"):
        sub.add_parser(name)
    f = sub.add_parser("full")
    f.add_argument("--limit", type=int, default=0, help="dừng sau N ca mới (0 = đến hết hoặc hết quota)")
    f.add_argument("--all", action="store_true", help="chạy toàn bộ 80 ca thay vì mẫu 48")
    r = sub.add_parser("report")
    r.add_argument("--config", choices=["rule_only", "full"], default="rule_only")
    args = ap.parse_args()
    {"build": cmd_build, "check": cmd_check, "rule-only": cmd_rule_only, "full": cmd_full, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()

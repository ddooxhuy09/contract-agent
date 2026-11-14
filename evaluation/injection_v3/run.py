"""injection_v3: đo hai cờ JUDGE_FINDING_TYPES + RED_FLAG_LLM_VERIFY (tắt vs bật) trên bộ ca mới.

  python -m evaluation.injection_v3.run build                 # sinh contracts/*.txt + manifest.json
  python -m evaluation.injection_v3.run check                 # kiểm thiết kế (regex, Điều 21), không gọi LLM
  python -m evaluation.injection_v3.run full --flags off|on [--limit N]   # pipeline đầy đủ, có resume
  python -m evaluation.injection_v3.run report
Xem README.md: thiết kế, cách chấm và quy tắc chấp nhận khai báo trước.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from evaluation.injection.run import ACTIONABLE, RULES, _commit, _fmt, _llm_name, _slot_number, bootstrap, prf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = HERE / "cases.jsonl"
BASES = HERE / "bases"
CONTRACTS = HERE / "contracts"
OUT = ROOT / "evaluation_results" / "injection_v3"
CONFIGS = {"off": {"JUDGE_FINDING_TYPES": "false", "RED_FLAG_LLM_VERIFY": "false"},
           "on": {"JUDGE_FINDING_TYPES": "true", "RED_FLAG_LLM_VERIFY": "true"}}

# Số Điều của từng slot trong mỗi hợp đồng nền.
SLOTS = {
    "A": {"ot_unpaid": 2, "no_bhxh": 5, "retain_id_papers": 6, "training_cost_flat": 7,
          "fine_deduct_wage": 8, "forfeit_wage_quit": 9, "terminate_pregnancy": 10, "ban_lawsuit": 11},
    "B": {"ot_unpaid": 3, "retain_id_papers": 4, "no_bhxh": 5, "training_cost_flat": 7,
          "fine_deduct_wage": 8, "terminate_pregnancy": 9, "forfeit_wage_quit": 10, "ban_lawsuit": 11},
    "C": {"ot_unpaid": 2, "no_bhxh": 4, "retain_id_papers": 6, "training_cost_flat": 7,
          "fine_deduct_wage": 8, "terminate_pregnancy": 9, "forfeit_wage_quit": 10, "ban_lawsuit": 11},
}


def load_cases() -> list[dict]:
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]


def base_text(name: str) -> str:
    return (BASES / f"{name}.txt").read_text(encoding="utf-8")


def slot_of(case: dict) -> int:
    return SLOTS[case["base"]][case["rule_id"]]


def build_contract(base: str, case: dict) -> str:
    """Giữ dòng tiêu đề «Điều n. …» của nền, thay toàn bộ thân Điều n bằng body của ca."""
    n = slot_of(case)
    pattern = re.compile(rf"^(Điều {n}\. [^\n]*\n).*?(?=^Điều {n + 1}\. |^NGƯỜI LAO ĐỘNG)", re.M | re.S)
    if len(pattern.findall(base)) != 1:
        raise ValueError(f"{case['case_id']}: không tìm thấy đúng một Điều {n} trong nền {case['base']}")
    body = case["body"].replace("{n}", str(n)).strip()
    return pattern.sub(lambda m: m.group(1) + body + "\n\n", base, count=1)


# ---------- chấm điểm ----------
def score(cases: list[dict], pred: dict[str, dict], n_boot: int = 1000) -> dict:
    """Dương tính khi có rủi ro critical/warning tại Điều đã bơm (như bộ 80 ca). Chưa kiểm báo riêng."""
    def conf(sub):
        tp = fp = fn = tn = unchecked = 0
        for c in sub:
            p = pred[c["case_id"]]
            y, f = c["label"] == "violation", bool(p["slot_flagged"])
            tp += y and f; fp += (not y) and f; fn += y and not f; tn += (not y) and not f
            unchecked += bool(p["slot_unchecked"])
        return {**prf(tp, fp, fn), "tn": tn, "unchecked": unchecked, "n": len(sub)}

    out = {"micro": conf(cases),
           "per_rule": {r: conf([c for c in cases if c["rule_id"] == r]) for r in RULES},
           "per_kind": {k: conf([c for c in cases if c["kind"] == k]) for k in sorted({c["kind"] for c in cases})},
           "other_flags_mean": round(sum(len(pred[c["case_id"]]["other_clause_flags"]) for c in cases) / len(cases), 2)
           if cases else None}
    out["micro_ci95"] = bootstrap(cases, conf, n_boot)
    return out


# ---------- lệnh ----------
def cmd_build(_) -> None:
    CONTRACTS.mkdir(exist_ok=True)
    manifest = {"bases_sha256": {b: hashlib.sha256(base_text(b).encode("utf-8")).hexdigest() for b in SLOTS},
                "cases_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(), "contracts": {}}
    for c in load_cases():
        text = build_contract(base_text(c["base"]), c)
        (CONTRACTS / f"{c['case_id']}.txt").write_text(text, encoding="utf-8", newline="\n")
        manifest["contracts"][c["case_id"]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {len(manifest['contracts'])} contracts")


def cmd_check(_) -> None:
    """Kiểm trước khi đóng băng: nền không kích hoạt regex, nền đủ Điều 21, cấu trúc ca; in dự đoán regex từng ca."""
    from app.agents.labor_completeness import assess_mandatory_fields
    from app.agents.labor_red_flags import _FLAGS

    pats = {f.key: f.pattern for f in _FLAGS}
    assert sorted(pats) == sorted(RULES)
    problems = []
    for b in SLOTS:
        text = base_text(b)
        hits = [k for k, p in pats.items() if p.search(text)]
        gaps = [f"{a.field.label}: {a.status} {list(a.missing)}" for a in assess_mandatory_fields(text) if a.status not in ("co", "khong_ap_dung")]
        print(f"nền {b}: regex trúng={hits} | Điều 21 chưa đủ={gaps}")
        if hits:
            problems.append(f"nền {b} kích hoạt regex {hits}")
    cases = load_cases()
    for r in RULES:
        mine = [c for c in cases if c["rule_id"] == r]
        if sorted(c["kind"] for c in mine) != ["C-a", "C-b", "C-c", "V-a", "V-b", "V-c"]:
            problems.append(f"{r}: thiếu loại ca")
        if sorted(c["base"] for c in mine) != ["A", "A", "B", "B", "C", "C"]:
            problems.append(f"{r}: phân bổ nền lệch")
        row = []
        for c in sorted(mine, key=lambda x: x["kind"]):
            row.append(f"{c['kind']}:{'hit' if pats[r].search(c['body']) else '-'}")
        print(f"{r:20s} " + " ".join(row))
    for c in cases:
        if any(re.match(r"\s*Điều\b", ln) for ln in c["body"].splitlines()):
            problems.append(f"{c['case_id']}: dòng thân bắt đầu bằng 'Điều'")
        build_contract(base_text(c["base"]), c)
    if problems:
        raise SystemExit(f"THIẾT KẾ CHƯA ĐẠT: {problems}")
    print("thiết kế đạt")


def _set_flags(name: str) -> None:
    os.environ.update(CONFIGS[name])
    from app.core.settings import get_settings
    get_settings.cache_clear()
    s = get_settings()
    assert (s.judge_finding_types, s.red_flag_llm_verify) == ((name == "on"),) * 2


def _record(cid: str, slot: str | None, analysis, risks) -> dict:
    cov = analysis.coverage or {}
    unchecked = {_slot_number(u.get("clause_ref")) for u in cov.get("chua_kiem_chi_tiet", [])}
    return {
        "case_id": cid, "slot": slot, "slot_unchecked": slot in unchecked if slot else False,
        "unchecked_clauses": sorted(unchecked - {""}),
        "slot_flagged": any(r.severity in ACTIONABLE and _slot_number(r.clause_ref) == slot for r in risks) if slot else False,
        "other_clause_flags": sorted({_slot_number(r.clause_ref) for r in risks
                                      if r.severity in ACTIONABLE and _slot_number(r.clause_ref) != slot}),
        "risks": [{"clause_ref": r.clause_ref, "severity": r.severity, "title": r.title,
                   "finding_type": getattr(r, "finding_type", None),
                   "keys": [x.key for x in (r.findings or [])]} for r in risks],
        "coverage": {k: cov.get(k) for k in ("tong_so_dieu", "da_kiem", "chua_kiem")},
        "commit": _commit(), "llm": _llm_name(),
    }


def _dirty() -> str:
    """Uncommitted changes in code that affects results; a run must match its recorded commit."""
    return subprocess.run(["git", "status", "--porcelain", "--", "app", "evaluation/injection_v3"],
                          cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _settings() -> dict:
    from app.core.settings import get_settings
    s = get_settings()
    keys = ("llm_provider", "groq_model", "judge_finding_types", "red_flag_llm_verify", "red_flag_negation_check",
            "legal_retrieval_mode", "legal_expand_backend")
    return {k: getattr(s, k, None) for k in keys}


def cmd_full(args) -> None:
    if _dirty():
        raise SystemExit("Mã trong app/ hoặc evaluation/injection_v3 chưa commit; chạy từ bản sạch (git worktree):"
                         + chr(10) + _dirty())
    _set_flags(args.flags)
    from app.agents.workflow import run_analysis_workflow
    from app.infrastructure.container import build_container
    from app.infrastructure.retrieval.context import bind_retrieval

    cont = build_container()
    # Keywords only: works with and without the optional Neo4j graph argument (LEGAL_EXPAND_BACKEND=postgres).
    bind_retrieval(cont.contract_search, cont.legal_search,
                   legal_chunks=cont.legal_chunks, contract_chunks=cont.contract_chunks)
    cache = OUT / args.flags
    cache.mkdir(parents=True, exist_ok=True)
    # 3 nền sạch trước (đo cờ trên Điều không bơm), rồi 48 ca theo thứ tự cố định.
    jobs = [(f"BASE-{b}", base_text(b), None) for b in SLOTS]
    jobs += [(c["case_id"], (CONTRACTS / f"{c['case_id']}.txt").read_text(encoding="utf-8"), str(slot_of(c)))
             for c in load_cases()]
    done = stalled = 0
    for cid, text, slot in jobs:
        f = cache / f"{cid}.json"
        if f.exists():
            continue
        if args.limit and done >= args.limit:
            break
        analysis, risks = asyncio.run(run_analysis_workflow(text, f"inj3-{args.flags}-{cid}"))
        rec = _record(cid, slot, analysis, risks)
        rec["flags"] = args.flags
        rec["settings"] = _settings()
        if rec["coverage"].get("chua_kiem"):  # quota/lỗi judge: không lưu, chạy lại sau
            stalled += 1
            print(f"{cid}: có Điều chưa kiểm {rec['unchecked_clauses']}, không lưu")
            if stalled >= 2:
                print("2 lần liên tiếp có Điều chưa kiểm: dừng, chạy lại khi quota hồi.")
                break
            continue
        stalled = 0
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        done += 1
        print(f"{cid}: slot_flagged={rec['slot_flagged']} other={rec['other_clause_flags']}")
    print(f"[{args.flags}] lưu thêm {done}; cache {len(list(cache.glob('*.json')))}/{len(jobs)}")


def cmd_report(_) -> None:
    cases = load_cases()
    res, lines = {}, ["# injection_v3: cờ tắt vs bật", ""]
    for name in CONFIGS:
        cache = OUT / name
        pred = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in cache.glob("*.json")} if cache.exists() else {}
        done = [c for c in cases if c["case_id"] in pred]
        if not done:
            lines.append(f"- `{name}`: chưa có kết quả")
            continue
        s = score(done, pred)
        bases = {b: pred.get(f"BASE-{b}", {}).get("other_clause_flags") for b in SLOTS}
        res[name] = {"n": len(done), "score": s, "base_flags": bases}
        m, ci = s["micro"], s["micro_ci95"]
        lines += [f"## `{name}` ({len(done)}/48 ca, judge {sorted({p.get('llm') for p in pred.values()})})", "",
                  "| TP | FP | FN | TN | Precision | Recall | F1 | Chưa kiểm | Cờ ở Điều khác (TB/ca) |",
                  "|---:|---:|---:|---:|---|---|---|---:|---:|",
                  f"| {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | {_fmt(m['precision'])} {ci['precision']} | "
                  f"{_fmt(m['recall'])} {ci['recall']} | {_fmt(m['f1'])} {ci['f1']} | {m['unchecked']} | {s['other_flags_mean']} |", "",
                  "Theo loại ca: " + "; ".join(f"{k}: dương tính {v['tp'] + v['fp']}/{v['n']}" for k, v in s["per_kind"].items()), "",
                  "Cờ critical/warning trên nền sạch: " + "; ".join(f"{b}: {v}" for b, v in bases.items()), ""]
    if set(res) == set(CONFIGS) and res["off"]["n"] == res["on"]["n"] == 48:
        off, on = res["off"]["score"]["micro"], res["on"]["score"]["micro"]
        ok = on["fp"] <= off["fp"] - 3 and on["fn"] <= off["fn"] + 1
        lines += ["## Quy tắc chấp nhận (khai báo trước trong README)", "",
                  f"FP: {off['fp']} → {on['fp']} (cần giảm ≥ 3); FN: {off['fn']} → {on['fn']} (tăng ≤ 1). "
                  f"Kết luận: **{'đạt, bật cờ mặc định' if ok else 'không đạt, giữ cờ tắt'}**."]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    text = "\n".join(lines) + "\n"
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")
    print(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "check", "report"):
        sub.add_parser(name)
    f = sub.add_parser("full")
    f.add_argument("--flags", choices=list(CONFIGS), required=True)
    f.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    {"build": cmd_build, "check": cmd_check, "full": cmd_full, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()

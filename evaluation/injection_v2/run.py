"""injection_v2: 32 ca (8 luật x 2 vi phạm + 2 hợp lệ) để đo bước quét luật cố định có xét phủ định hay không.

  python -m evaluation.injection_v2.run build                 # tạo contracts/ + manifest.json
  python -m evaluation.injection_v2.run check                 # kiểm cấu trúc ca
  python -m evaluation.injection_v2.run rule-only --label old # chạy rule-only (không LLM), ghi results/rule_only_<label>.json
  python -m evaluation.injection_v2.run report                # bảng cũ vs mới (cần cả hai nhãn)

Chấm điểm dùng lại hàm của evaluation.injection.run (cùng định nghĩa TP/FP/FN, cùng seed bootstrap).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.injection.run import RULES, _commit, build_contract, score_rule_level

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"
BASE = HERE / "base_contract.txt"
CONTRACTS = HERE / "contracts"
RESULTS = HERE.parents[1] / "evaluation_results" / "injection_v2"


def load_cases() -> list[dict]:
    return [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]


def cmd_build(_) -> None:
    base = BASE.read_text(encoding="utf-8")
    CONTRACTS.mkdir(exist_ok=True)
    man = {"base_sha256": hashlib.sha256(base.encode("utf-8")).hexdigest(),
           "cases_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(), "contracts": {}}
    for c in load_cases():
        text = build_contract(base, c)
        (CONTRACTS / f"{c['case_id']}.txt").write_text(text, encoding="utf-8", newline="\n")
        man["contracts"][c["case_id"]] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (HERE / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"built {len(man['contracts'])} contracts")


def cmd_check(_) -> None:
    cases = load_cases()
    base = BASE.read_text(encoding="utf-8")
    assert len(cases) == 32 and len({c["case_id"] for c in cases}) == 32
    for r in RULES:
        mine = [c for c in cases if c["rule_id"] == r]
        assert sum(c["label"] == "violation" for c in mine) == 2 and sum(c["label"] == "compliant" for c in mine) == 2, r
        assert any(c["label"] == "compliant" and c["negation_form"] != "none" for c in mine), f"{r}: thiếu ca phủ định hợp lệ"
    for c in cases:
        build_contract(base, c)
    print("cấu trúc đạt: 32 ca, mỗi luật 2 vi phạm + 2 hợp lệ, mỗi luật có ca phủ định hợp lệ")


def cmd_rule_only(args) -> None:
    from app.agents.labor_red_flags import check_labor_red_flags

    preds = {}
    for c in load_cases():
        text = (CONTRACTS / f"{c['case_id']}.txt").read_text(encoding="utf-8")
        preds[c["case_id"]] = sorted({f.key for i in check_labor_red_flags(text, None) for f in (i.findings or [])})
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"rule_only_{args.label}.json"
    out.write_text(json.dumps({"label": args.label, "commit": _commit(), "predictions": preds}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} (commit {_commit()[:8]})")


def _fmt(v) -> str:
    return "n/a" if v is None else f"{v:.2f}"


def cmd_report(_) -> None:
    cases = load_cases()
    by = {c["case_id"]: c for c in cases}
    runs = {lab: json.loads((RESULTS / f"rule_only_{lab}.json").read_text(encoding="utf-8")) for lab in ("old", "new")}
    scores = {lab: score_rule_level(cases, {k: set(v) for k, v in r["predictions"].items()}) for lab, r in runs.items()}
    L = ["# injection_v2: rule-only, code CŨ vs code MỚI (32 ca)", "",
         f"Code cũ: commit `{runs['old']['commit'][:8]}`. Code mới: commit `{runs['new']['commit'][:8]}`. Không LLM.", "",
         "| Luật | TP cũ→mới | FP cũ→mới | FN cũ→mới | Precision cũ→mới | Recall cũ→mới |", "|---|---|---|---|---|---|"]
    for r in RULES:
        o, n = scores["old"]["per_rule"][r], scores["new"]["per_rule"][r]
        L.append(f"| {r} | {o['tp']}→{n['tp']} | {o['fp']}→{n['fp']} | {o['fn']}→{n['fn']} | {_fmt(o['precision'])}→{_fmt(n['precision'])} | {_fmt(o['recall'])}→{_fmt(n['recall'])} |")
    for lab in ("old", "new"):
        pass
    o, n = scores["old"], scores["new"]
    def cell(s, k):
        m, ci = s["micro"], s["micro_ci95"][k]
        return f"{_fmt(m[k])} {ci}"
    L += ["", "| Tổng (micro) | Cũ | Mới |", "|---|---|---|",
          f"| TP / FP / FN | {o['micro']['tp']} / {o['micro']['fp']} / {o['micro']['fn']} | {n['micro']['tp']} / {n['micro']['fp']} / {n['micro']['fn']} |",
          f"| Precision [CI95] | {cell(o, 'precision')} | {cell(n, 'precision')} |",
          f"| Recall [CI95] | {cell(o, 'recall')} | {cell(n, 'recall')} |",
          f"| F1 [CI95] | {cell(o, 'f1')} | {cell(n, 'f1')} |",
          f"| Ca hợp lệ bị luật bất kỳ kích hoạt | {o['near_miss_any_rule_fired']}/{o['near_miss_n']} | {n['near_miss_any_rule_fired']}/{n['near_miss_n']} |",
          "", "## Ca đổi kết quả (luật của chính ca đó có kích hoạt?)", "", "| Ca | Nhãn | Dạng | Cũ | Mới |", "|---|---|---|---|---|"]
    for cid, c in by.items():
        a, b = c["rule_id"] in runs["old"]["predictions"][cid], c["rule_id"] in runs["new"]["predictions"][cid]
        if a != b:
            L.append(f"| {cid} | {c['label']} | {c['phrasing']} / phủ định: {c['negation_form']} | {'kích hoạt' if a else 'không'} | {'kích hoạt' if b else 'không'} |")
    L += ["", "## Theo nhóm", "", "| Nhóm | n | Kích hoạt cũ | Kích hoạt mới |", "|---|---:|---:|---:|"]
    groups = {"vi phạm (V1+V2)": lambda c: c["label"] == "violation",
              "hợp lệ, phủ định ngay trước (C1)": lambda c: c["negation_form"] == "direct_before",
              "hợp lệ, phủ định sau/bên trong (C2)": lambda c: c["label"] == "compliant" and c["negation_form"] in ("after", "inside")}
    for name, f in groups.items():
        sel = [c for c in cases if f(c)]
        L.append(f"| {name} | {len(sel)} | {sum(c['rule_id'] in runs['old']['predictions'][c['case_id']] for c in sel)} | {sum(c['rule_id'] in runs['new']['predictions'][c['case_id']] for c in sel)} |")
    (RESULTS / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("build", "check", "report"):
        sub.add_parser(n)
    ro = sub.add_parser("rule-only")
    ro.add_argument("--label", choices=("old", "new"), required=True)
    args = ap.parse_args()
    {"build": cmd_build, "check": cmd_check, "rule-only": cmd_rule_only, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()

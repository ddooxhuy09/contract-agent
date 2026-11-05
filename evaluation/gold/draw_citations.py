"""Draw citations from an evaluation result for the two-person faithfulness check, and summarise it.

    python -m evaluation.gold.draw_citations --result evaluation_results/<date>_test_full.json [--n 50]
    python -m evaluation.gold.draw_citations --summarize

Each citation is checked by two people on three yes/no questions (1/0):
  ton_tai      the cited provision exists in the official text;
  con_hieu_luc it was in force at the contract date;
  ho_tro       its content actually supports the claim made in the risk.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from evaluation.gold.common import GOLD_DIR

OUT = GOLD_DIR / "kiem_trich_dan.csv"
CHECKS = ("ton_tai", "con_hieu_luc", "ho_tro")
COLUMNS = (
    "citation_id", "unit_id", "clause_ref", "doc_number", "article", "clause", "point", "quote", "claim",
    *(f"ann{a}_{c}" for a in (1, 2) for c in CHECKS), "ghi_chu",
)


def collect(result: dict) -> list[dict]:
    rows = []
    for u in result["units"]:
        for risk in u["risks"]:
            for cit in risk.get("legal_citations") or []:
                rows.append({
                    "unit_id": u["unit_id"], "clause_ref": risk.get("clause_ref", ""),
                    "doc_number": cit.get("doc_number") or "", "article": cit.get("article") or "",
                    "clause": cit.get("clause") or "", "point": cit.get("point") or "",
                    "quote": (cit.get("quote") or cit.get("summary") or "")[:500],
                    "claim": (risk.get("issue") or "")[:500],
                })
    return rows


def sample(rows: list[dict], n: int, seed: int) -> list[dict]:
    picked = random.Random(seed).sample(rows, min(n, len(rows)))
    return [{"citation_id": f"C{i:03d}", **r} for i, r in enumerate(picked, 1)]


def summarize(rows: list[dict]) -> dict:
    out = {"n": len(rows)}
    for a in (1, 2):
        for c in CHECKS:
            vals = [r[f"ann{a}_{c}"].strip() for r in rows if r.get(f"ann{a}_{c}", "").strip() in ("0", "1")]
            out[f"ann{a}_{c}"] = {"n": len(vals), "rate": sum(v == "1" for v in vals) / len(vals) if vals else None}
    for c in CHECKS:
        both = [r for r in rows if r.get(f"ann1_{c}", "").strip() in ("0", "1") and r.get(f"ann1_{c}") == r.get(f"ann2_{c}")]
        out[f"agreed_{c}"] = {"n": len(both), "rate": sum(r[f"ann1_{c}"] == "1" for r in both) / len(both) if both else None}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--result", type=Path)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args()
    if a.summarize:
        with open(OUT, encoding="utf-8-sig", newline="") as f:
            print(json.dumps(summarize(list(csv.DictReader(f))), ensure_ascii=False, indent=2))
    elif a.result:
        picked = sample(collect(json.loads(a.result.read_text(encoding="utf-8"))), a.n, a.seed)
        with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(picked)
        print(f"wrote {len(picked)} citations to {OUT}")
    else:
        ap.error("--result or --summarize required")

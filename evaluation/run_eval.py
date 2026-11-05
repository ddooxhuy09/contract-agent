"""Clause-level evaluation against the gold set (evaluation/gold), with bootstrap 95% CI.

    python -m evaluation.run_eval --split dev --config rule_only --contracts-dir <dir>
    python -m evaluation.run_eval --split test --config full --contracts-dir <dir> [--estimate]
    python -m evaluation.run_eval --split test --report

Configs
  rule_only  deterministic checks only (red-flag regex + preamble citations), no LLM.
  full       the whole analysis workflow (extract, retrieve, judge, deterministic pre-pass).

A unit (one Điều) is predicted positive when the system raised a critical/warning risk for it.
Clauses the judge could not assess are counted as predicted negative and reported as coverage.
Results go to evaluation_results/<date>_<split>_<config>.json with the git commit; the full
config caches finished contracts so a quota-limited run can resume the next day.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import subprocess
from datetime import date
from pathlib import Path

from evaluation.gold.common import GOLD_DIR, read_rows

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation_results"
ACTIONABLE = ("critical", "warning")


# --- pure helpers (unit-tested) ------------------------------------------------------------

def gold_label(row: dict) -> int | None:
    """Expert label if present, else the annotators' consensus; None while unresolved."""
    ef = (row.get("expert_final") or "").strip()
    if ef:
        return int(ef[0]) if ef[0] in "01" else None
    a, b = (row.get("ann1_co_rui_ro") or "").strip(), (row.get("ann2_co_rui_ro") or "").strip()
    return int(a) if a == b and a in ("0", "1") else None


def positive_dieu(risks: list[dict]) -> set[str]:
    """Clause numbers that carry at least one actionable risk."""
    return {
        "".join(ch for ch in str(r.get("clause_ref", "")) if ch.isdigit())
        for r in risks
        if r.get("severity") in ACTIONABLE
    } - {""}


def confusion(y: list[int], p: list[int]) -> dict:
    tp = sum(1 for a, b in zip(y, p) if a and b)
    fp = sum(1 for a, b in zip(y, p) if not a and b)
    fn = sum(1 for a, b in zip(y, p) if a and not b)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": len(y) - tp - fp - fn}


def scores(c: dict) -> dict:
    prec = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
    rec = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else (0.0 if prec is not None and rec is not None else None)
    false_rate = c["fp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
    return {"precision": prec, "recall": rec, "f1": f1, "false_rate": false_rate}


def bootstrap_ci(y: list[int], p: list[int], iterations: int = 1000, seed: int = 20261105) -> dict:
    """Percentile 95% CI per metric over unit-level resamples (undefined resamples are skipped)."""
    rng = random.Random(seed)
    n = len(y)
    samples: dict[str, list[float]] = {k: [] for k in ("precision", "recall", "f1", "false_rate")}
    for _ in range(iterations):
        idx = [rng.randrange(n) for _ in range(n)]
        s = scores(confusion([y[i] for i in idx], [p[i] for i in idx]))
        for k, v in s.items():
            if v is not None:
                samples[k].append(v)
    out = {}
    for k, vals in samples.items():
        vals.sort()
        out[k] = (
            {"low": vals[int(0.025 * (len(vals) - 1))], "high": vals[int(0.975 * (len(vals) - 1))], "n_valid": len(vals)}
            if vals else None
        )
    return out


def evaluate(units: list[dict], predictions: dict[str, dict], iterations: int = 1000) -> dict:
    """units: gold rows of the split; predictions: contract_id -> {"risks": [...], "coverage": {...}|None}."""
    labeled = [(r, gold_label(r)) for r in units]
    resolved = [(r, lab) for r, lab in labeled if lab is not None]
    y = [lab for _, lab in resolved]
    p = [int(str(r["dieu"]) in positive_dieu(predictions[r["contract_id"]]["risks"])) for r, _ in resolved]
    conf = confusion(y, p) if y else {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    covs = [c["coverage"] for c in predictions.values() if c.get("coverage")]
    return {
        "n_units": len(units),
        "n_unresolved": len(units) - len(resolved),
        "confusion": conf,
        "metrics": scores(conf),
        "ci95": bootstrap_ci(y, p, iterations) if y else {},
        "coverage": (
            {"da_kiem": sum(c["da_kiem"] for c in covs), "tong_so_dieu": sum(c["tong_so_dieu"] for c in covs)}
            if covs else None
        ),
        "units": [
            {"unit_id": r["unit_id"], "gold": lab, "pred": pv, "risks": [
                x for x in predictions[r["contract_id"]]["risks"]
                if str(r["dieu"]) == "".join(ch for ch in str(x.get("clause_ref", "")) if ch.isdigit())
            ]}
            for (r, lab), pv in zip(resolved, p)
        ],
    }


# --- running the system --------------------------------------------------------------------

def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _commit() -> str:
    """Git commit of the code under test; set EVAL_COMMIT when git is unavailable (e.g. in a container)."""
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return os.environ.get("EVAL_COMMIT", "unknown")


def contract_texts(contracts_dir: Path, wanted: set[str]) -> dict[str, str]:
    """Same ordering as prepare_units (sorted file names -> HDLD01, HDLD02, ...)."""
    from evaluation.gold.prepare_units import _read_text

    files = sorted(p for p in contracts_dir.iterdir() if p.suffix.lower() in {".docx", ".md", ".txt"})
    manifest = json.loads((GOLD_DIR / "contracts_manifest.json").read_text(encoding="utf-8"))
    out = {}
    for i, p in enumerate(files, 1):
        cid = f"HDLD{i:02d}"
        if cid in wanted:
            text = _read_text(p)
            if manifest.get(cid, {}).get("sha256") != _sha(text):
                raise SystemExit(f"{cid}: contract file differs from the one the gold units were drawn from")
            out[cid] = text
    return out


def _bind_runtime() -> None:
    from app.infrastructure.container import build_container
    from app.infrastructure.retrieval.context import bind_retrieval

    c = build_container()
    bind_retrieval(c.contract_search, c.legal_search, c.graph, legal_chunks=c.legal_chunks, contract_chunks=c.contract_chunks)


def run_contract(config: str, cid: str, text: str) -> dict:
    if config == "rule_only":
        from app.agents.labor_red_flags import check_labor_red_flags
        from app.agents.preamble_citations import check_preamble_citations

        risks = [*check_labor_red_flags(text, None, contract_id=cid), *check_preamble_citations(text)]
        return {"risks": [r.model_dump(mode="json") for r in risks], "coverage": None}
    from app.agents.workflow import run_analysis_workflow

    analysis, risks = asyncio.run(run_analysis_workflow(text, cid))
    return {"risks": [r.model_dump(mode="json") for r in risks], "coverage": analysis.coverage}


def run(args: argparse.Namespace) -> None:
    split = json.loads((GOLD_DIR / "split.json").read_text(encoding="utf-8"))[args.split]
    units = [r for r in read_rows() if r["contract_id"] in split]
    texts = contract_texts(args.contracts_dir, set(split))
    if args.estimate:
        from app.document.chunker import chunk_by_clause

        n = sum(len(chunk_by_clause(t, c)) for c, t in texts.items())
        print(f"{len(texts)} contracts, about {n} clauses -> at least {n} judge calls (plus extraction) for config=full")
        return
    cache = RESULTS / "runs" / f"gold_{args.split}_{args.config}"
    cache.mkdir(parents=True, exist_ok=True)
    if args.config == "full":
        _bind_runtime()
    preds: dict[str, dict] = {}
    for cid, text in texts.items():
        f = cache / f"{cid}.json"
        if f.exists():
            preds[cid] = json.loads(f.read_text(encoding="utf-8"))
            continue
        preds[cid] = run_contract(args.config, cid, text)
        if not (preds[cid]["coverage"] or {}).get("chua_kiem"):  # never cache a partial result
            f.write_text(json.dumps(preds[cid], ensure_ascii=False), encoding="utf-8")
    incomplete = [c for c, p in preds.items() if (p["coverage"] or {}).get("chua_kiem")]
    result = {
        "commit": _commit(), "date": date.today().isoformat(), "split": args.split, "config": args.config,
        "incomplete_contracts": incomplete, **evaluate(units, preds),
    }
    out = RESULTS / f"{date.today():%Y%m%d}_{args.split}_{args.config}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} (n_units={result['n_units']}, unresolved={result['n_unresolved']}, incomplete={incomplete})")


# --- report --------------------------------------------------------------------------------

def _fmt(v, ci=None) -> str:
    if v is None:
        return "n/a"
    s = f"{v:.2f}"
    return f"{s} [{ci['low']:.2f}, {ci['high']:.2f}]" if ci else s


def report(split: str) -> None:
    rows = []
    for config in ("rule_only", "full"):
        files = sorted(RESULTS.glob(f"*_{split}_{config}.json"))
        if not files:
            continue
        r = json.loads(files[-1].read_text(encoding="utf-8"))
        m, ci, cov = r["metrics"], r["ci95"], r["coverage"]
        coverage_cell = "n/a" if not cov else "{}/{}".format(cov["da_kiem"], cov["tong_so_dieu"])
        rows.append(
            f"| {config} | {r['n_units']} | {_fmt(m['precision'], ci.get('precision'))} | {_fmt(m['recall'], ci.get('recall'))} "
            f"| {_fmt(m['f1'], ci.get('f1'))} | {_fmt(m['false_rate'], ci.get('false_rate'))} "
            f"| {coverage_cell} | `{r['commit'][:8]}` {r['date']} |"
        )
    text = "\n".join([
        f"# Kết quả đánh giá (tập {split})", "",
        "Đơn vị = một Điều. Số trong ngoặc là khoảng tin cậy 95% bootstrap (1000 lần, mức đơn vị; các Điều cùng hợp đồng không độc lập nên khoảng thực tế rộng hơn).",
        "Nhãn: `expert_final` nếu có, nếu không là nhãn đồng thuận của hai người.", "",
        "| Cấu hình | Số đơn vị | Precision | Recall | F1 | False rate | Độ phủ (đã kiểm/tổng) | Commit, ngày |",
        "|---|---:|---|---|---|---|---|---|", *rows, "",
    ])
    (RESULTS / "RESULTS_TUAN.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", choices=("dev", "test"), required=True)
    ap.add_argument("--config", choices=("rule_only", "full"))
    ap.add_argument("--contracts-dir", type=Path)
    ap.add_argument("--estimate", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report(a.split)
    elif a.config and a.contracts_dir:
        run(a)
    else:
        ap.error("--config and --contracts-dir are required unless --report")

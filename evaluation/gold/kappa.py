"""Cohen's kappa between the two annotators, plus the list of disagreements.

    python -m evaluation.gold.kappa [--write]     # --write saves evaluation/gold/KAPPA.md
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from evaluation.gold.common import GOLD_DIR, TEMPLATE, read_rows


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Unweighted Cohen's kappa. Returns 1.0 when both raters use a single identical label."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two equal-length, non-empty label lists")
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def _is_label(value: str) -> bool:
    return value.strip() in ("0", "1")


def compute(rows: list[dict]) -> dict:
    done = [r for r in rows if _is_label(r.get("ann1_co_rui_ro", "")) and _is_label(r.get("ann2_co_rui_ro", ""))]
    a = [r["ann1_co_rui_ro"].strip() for r in done]
    b = [r["ann2_co_rui_ro"].strip() for r in done]
    law_a = [r.get("ann1_luat_dau_ra", "").strip() or "none" for r in done]
    law_b = [r.get("ann2_luat_dau_ra", "").strip() or "none" for r in done]
    return {
        "units_total": len(rows),
        "units_labeled_by_both": len(done),
        "kappa_co_rui_ro": cohen_kappa(a, b) if done else None,
        "agreement_co_rui_ro": sum(x == y for x, y in zip(a, b)) / len(done) if done else None,
        "kappa_luat_dau_ra": cohen_kappa(law_a, law_b) if done else None,
        "disagreements": [r["unit_id"] for r, x, y in zip(done, a, b) if x != y],
    }


def render(res: dict) -> str:
    def fmt(v):
        return "n/a" if v is None else f"{v:.3f}"

    lines = [
        "# Độ đồng thuận giữa hai người gán nhãn (Cohen's kappa)",
        "",
        f"- Đơn vị trong file: {res['units_total']}; cả hai người đã gán: {res['units_labeled_by_both']}",
        f"- Kappa `co_rui_ro` (có rủi ro hay không): **{fmt(res['kappa_co_rui_ro'])}** "
        f"(đồng thuận thô {fmt(res['agreement_co_rui_ro'])})",
        f"- Kappa `luat_dau_ra` (rủi ro thuộc luật đỏ nào): {fmt(res['kappa_luat_dau_ra'])}",
        "- Quy ước đọc: dưới 0,6 cần thảo luận và xem lại hướng dẫn gán nhãn.",
        "",
        f"## Đơn vị bất đồng ({len(res['disagreements'])})",
        *[f"- {u}" for u in res["disagreements"]],
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--input", type=Path, default=TEMPLATE)
    args = ap.parse_args()
    text = render(compute(read_rows(args.input)))
    print(text)
    if args.write:
        (GOLD_DIR / "KAPPA.md").write_text(text, encoding="utf-8")

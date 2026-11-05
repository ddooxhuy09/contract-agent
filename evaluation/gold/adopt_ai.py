"""Copy the AI draft labels (ai_* columns) into one human annotator's columns after review.

The AI draft is only a starting point. Run this AFTER you have read every unit and decided which
draft labels you agree with. Units you disagree with are listed in --except and left blank for you
to label yourself. The copy means "I verified these labels", so the annotator is you.

    python -m evaluation.gold.adopt_ai --annotator 1 --confirm-reviewed [--except HDLD01_D03,HDLD02_D05]
"""
from __future__ import annotations

import argparse

from evaluation.gold.common import TEMPLATE, read_rows, write_rows


def adopt(rows: list[dict], annotator: int, skip: set[str]) -> int:
    n = 0
    for r in rows:
        if r["unit_id"] in skip or not r.get("ai_co_rui_ro"):
            continue
        if r.get(f"ann{annotator}_co_rui_ro"):
            raise SystemExit(f"{r['unit_id']}: ann{annotator} already has a label; refusing to overwrite")
        r[f"ann{annotator}_co_rui_ro"] = r["ai_co_rui_ro"]
        r[f"ann{annotator}_luat_dau_ra"] = r["ai_luat_dau_ra"]
        r[f"ann{annotator}_dieu_luat_dung"] = r["ai_dieu_luat_dung"]
        n += 1
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--annotator", type=int, choices=(1, 2), required=True)
    ap.add_argument("--except", dest="skip", default="", help="comma-separated unit ids you disagree with")
    ap.add_argument("--confirm-reviewed", action="store_true", help="I read every unit and agree with the rest")
    a = ap.parse_args()
    if not a.confirm_reviewed:
        ap.error("pass --confirm-reviewed only after you have verified the draft labels yourself")
    rows = read_rows()
    skip = {u.strip() for u in a.skip.split(",") if u.strip()}
    unknown = skip - {r["unit_id"] for r in rows}
    if unknown:
        ap.error(f"unknown unit ids: {sorted(unknown)}")
    count = adopt(rows, a.annotator, skip)
    write_rows(rows, TEMPLATE)
    print(f"copied {count} labels into ann{a.annotator}; {len(skip)} units left for you to label")

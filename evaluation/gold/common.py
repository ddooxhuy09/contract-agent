"""Shared constants and CSV helpers for the gold-set tools."""
from __future__ import annotations

import csv
from pathlib import Path

GOLD_DIR = Path(__file__).parent
TEMPLATE = GOLD_DIR / "annotation_template.csv"
RED_FLAGS = (
    "ot_unpaid", "no_bhxh", "retain_id_papers", "forfeit_wage_quit",
    "fine_deduct_wage", "terminate_pregnancy", "ban_lawsuit",
)
OTHER = "khac"  # a real risk that is not one of the 7 red flags
COLUMNS = (
    "unit_id", "contract_id", "dieu", "noi_dung",
    "ann1_co_rui_ro", "ann1_luat_dau_ra", "ann1_dieu_luat_dung",
    "ann2_co_rui_ro", "ann2_luat_dau_ra", "ann2_dieu_luat_dung",
    "expert_final", "ghi_chu",
)


def read_rows(path: Path = TEMPLATE) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows: list[dict], path: Path = TEMPLATE) -> None:
    # utf-8-sig so Excel shows Vietnamese correctly.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

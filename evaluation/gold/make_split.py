"""Split gold units into dev and test BY CONTRACT (never by clause) to avoid leakage.

    python -m evaluation.gold.make_split [--dev 2] [--seed 20261105]
"""
from __future__ import annotations

import argparse
import json
import random

from evaluation.gold.common import GOLD_DIR, read_rows


def split_contracts(contract_ids: list[str], n_dev: int, seed: int) -> dict:
    ids = sorted(set(contract_ids))
    if not 0 < n_dev < len(ids):
        raise ValueError(f"need 0 < dev < number of contracts ({len(ids)})")
    shuffled = ids[:]
    random.Random(seed).shuffle(shuffled)
    return {"seed": seed, "dev": sorted(shuffled[:n_dev]), "test": sorted(shuffled[n_dev:])}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dev", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261105)
    args = ap.parse_args()
    result = split_contracts([r["contract_id"] for r in read_rows()], args.dev, args.seed)
    (GOLD_DIR / "split.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))

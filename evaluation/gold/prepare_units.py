"""Draw the annotation units (one Điều each) from anonymised labor contracts.

Units are picked by a seeded random draw that does not look at the system's output or its
rules, so the gold set is not biased towards what the system already detects.

    python -m evaluation.gold.prepare_units --input-dir <folder of .docx/.md/.txt> [--per-contract 5] [--seed 20261105]

Refuses to overwrite an annotation file that already holds labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from evaluation.gold.common import GOLD_DIR, TEMPLATE, read_rows, write_rows

MIN_CHARS = 80  # skip headings and one-line clauses


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        from app.document.parser import parse_document

        return parse_document(str(path), ".docx")
    return path.read_text(encoding="utf-8")


def pick_units(contract_no: int, text: str, per_contract: int, rng: random.Random) -> list[dict]:
    from app.document.chunker import chunk_by_clause

    cid = f"HDLD{contract_no:02d}"
    by_clause: dict[str, str] = {}
    for d in chunk_by_clause(text, cid):
        num = str(d.metadata.get("clause_number", ""))
        if num.isdigit() and len(d.page_content) >= MIN_CHARS:
            by_clause.setdefault(num, d.page_content.strip())
    chosen = sorted(rng.sample(sorted(by_clause, key=int), min(per_contract, len(by_clause))), key=int)
    return [
        {"unit_id": f"{cid}_D{int(n):02d}", "contract_id": cid, "dieu": n, "noi_dung": by_clause[n]}
        for n in chosen
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input-dir", required=True, type=Path)
    ap.add_argument("--per-contract", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--output", type=Path, default=TEMPLATE)
    args = ap.parse_args()

    if args.output.exists() and any(
        r.get("ann1_co_rui_ro") or r.get("ann2_co_rui_ro") for r in read_rows(args.output)
    ):
        raise SystemExit(f"{args.output} already holds labels; refusing to overwrite")
    files = sorted(p for p in args.input_dir.iterdir() if p.suffix.lower() in {".docx", ".md", ".txt"})
    rng = random.Random(args.seed)
    rows: list[dict] = []
    manifest: dict[str, dict] = {}
    for i, p in enumerate(files, 1):
        text = _read_text(p)
        # Hash only: file names may identify the parties, so they are not stored.
        manifest[f"HDLD{i:02d}"] = {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        units = pick_units(i, text, args.per_contract, rng)
        print(f"HDLD{i:02d} <- {p.name}: {len(units)} units")
        rows.extend(units)
    write_rows(rows, args.output)
    (GOLD_DIR / "contracts_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} units to {args.output}")


if __name__ == "__main__":
    main()

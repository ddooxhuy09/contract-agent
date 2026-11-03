"""Offline reranking ablation over saved RAG-only traces; no model, DB, or network.

Ranks the same candidate pool observed in ``graph_expanded`` with several
pre-declared policies, then scores the ranked paths against benchmark gold.
Gold is loaded only after every ranking is fixed.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.domain.entities.search import RetrievedChunk
from app.infrastructure.retrieval.legal_graph_rag import LegalGraphRag
from app.infrastructure.retrieval.normative_rank import normative_rank
from app.infrastructure.retrieval.scope_match import (
    contract_context,
    filter_sector_mismatches,
)
from evaluation.audit import load
from evaluation.runtime_adapter import ROOT, RUNS
from evaluation.scoring import (
    format_metric,
    matches,
    mean_metrics,
    ref,
    retrieval_scores,
)

_ROLE_ORDER = {"seed": 0, "superseding": 0, "sibling": 1, "ancestor": 2, "related": 3}
_DISPLAY = (
    "recall_at_1",
    "recall_at_3",
    "recall_at_5",
    "recall_at_10",
    "mrr",
    "required_evidence_coverage",
    "retrieved_count",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def to_chunk(raw: dict) -> RetrievedChunk:
    return RetrievedChunk(
        content=raw.get("text") or "",
        score=raw.get("score"),
        metadata=dict(raw.get("metadata") or {}),
    )


def as_dict(chunk: RetrievedChunk) -> dict:
    return {"text": chunk.content, "score": chunk.score, "metadata": dict(chunk.metadata)}


def load_trace(path: Path) -> dict:
    events = read_json(path)
    finals = [e for e in events if e["kind"] == "final_retrieval"]
    if not finals:
        raise RuntimeError(f"No final_retrieval in {path}")
    final = finals[-1]
    call_id = final["rag_call_id"]
    group = [e for e in events if e.get("rag_call_id") == call_id]
    pool = next((e for e in group if e["kind"] == "graph_expanded"), None)
    if pool is None:
        raise RuntimeError(f"No graph_expanded candidate pool in {path}")
    args = final.get("query_args") or []
    options = final.get("options") or {}
    return {
        "candidates": [to_chunk(c) for c in pool["chunks"]],
        "saved_final": [to_chunk(c) for c in final.get("chunks", [])],
        "ctx": contract_context(
            options.get("contract_type"),
            args[0] if args else None,
            args[1] if len(args) > 1 else None,
        ),
        "max_total": int(options.get("max_total") or 10),
    }


def _role(chunk: RetrievedChunk) -> int:
    return _ROLE_ORDER.get(chunk.metadata.get("role") or "seed", 9)


def _normative(chunk: RetrievedChunk) -> float:
    return normative_rank(chunk.metadata.get("doc_type"), chunk.metadata.get("title"))


def _relevance(chunk: RetrievedChunk) -> float:
    """Cosine when present; FTS-only hits keep only an RRF rank and score 0."""
    if chunk.score is None:
        return 0.0
    rrf = chunk.metadata.get("rrf_score")
    if rrf is not None and float(chunk.score) <= float(rrf) + 1e-12:
        return 0.0
    return float(chunk.score)


def _ordered(chunks: list[RetrievedChunk], key_fn) -> list[RetrievedChunk]:
    keyed = [(chunk, key_fn(chunk)) for chunk in chunks]
    keyed.sort(key=lambda pair: pair[1])
    return [chunk for chunk, _ in keyed]


def _seed_positions(chunks: list[RetrievedChunk]) -> dict[str, int]:
    return {
        chunk.metadata.get("path"): index
        for index, chunk in enumerate(chunks)
        if chunk.metadata.get("role") == "seed"
    }


def policy_baseline(chunks, seeds, as_of):
    """Pre-change production order, frozen: validity -> doc type -> status/year -> role -> score."""
    def key(chunk):
        validity = LegalGraphRag._validity_key(chunk, as_of)
        return (
            validity[0],
            -LegalGraphRag._doc_type_rank(
                chunk.metadata.get("doc_type"),
                chunk.metadata.get("title"),
            ),
            validity[1],
            validity[2],
            _role(chunk),
            -(chunk.score or 0),
        )

    return _ordered(chunks, key)


def policy_seed_normative(chunks, seeds, as_of):
    """Seeds first; normative hierarchy only breaks ties inside a role."""
    def key(chunk):
        validity = LegalGraphRag._validity_key(chunk, as_of)
        return (
            validity[0],
            _role(chunk),
            -_normative(chunk),
            validity[1],
            validity[2],
            -_relevance(chunk),
        )

    return _ordered(chunks, key)


def policy_seed_search(chunks, seeds, as_of):
    """Seeds first and in the hybrid-search order that produced them."""
    def key(chunk):
        validity = LegalGraphRag._validity_key(chunk, as_of)
        role = _role(chunk)
        position = seeds.get(chunk.metadata.get("path"), len(chunks)) if role == 0 else 0
        return (
            validity[0],
            role,
            position,
            -_relevance(chunk),
            -_normative(chunk),
            validity[1],
            validity[2],
        )

    return _ordered(chunks, key)


def policy_seed_cosine(chunks, seeds, as_of):
    """Seeds first, ordered by cosine; FTS-only seeds fall below semantic seeds."""
    def key(chunk):
        validity = LegalGraphRag._validity_key(chunk, as_of)
        role = _role(chunk)
        position = seeds.get(chunk.metadata.get("path"), len(chunks)) if role == 0 else 0
        return (
            validity[0],
            role,
            -_relevance(chunk),
            -_normative(chunk),
            position,
            validity[1],
            validity[2],
        )

    return _ordered(chunks, key)


def policy_seed_only(chunks, seeds, as_of):
    """Reference ceiling: drop graph expansion entirely, keep search order."""
    only = [c for c in chunks if c.metadata.get("role") == "seed"]
    return _ordered(only, lambda c: seeds.get(c.metadata.get("path"), len(chunks)))


def policy_production(chunks, seeds, as_of):
    """Actual production order after the seed-first change (identity check)."""
    return LegalGraphRag._order_for_prompt(chunks, as_of=as_of)


POLICIES = {
    "baseline": policy_baseline,
    "seed_normative": policy_seed_normative,
    "seed_search": policy_seed_search,
    "seed_cosine": policy_seed_cosine,
    "seed_only": policy_seed_only,
    "production_new": policy_production,
}


def finalize(ordered, ctx, as_of, max_total):
    if ctx:
        ordered, _ = filter_sector_mismatches(ordered, ctx)
    effective = [c for c in ordered if LegalGraphRag._validity_key(c, as_of)[0] == 0]
    if effective:
        ordered = effective
    return ordered[:max_total]


def build_rankings(input_dir: Path) -> dict:
    metadata = read_json(input_dir / "execution_metadata.json")
    if not metadata.get("finished_at"):
        raise RuntimeError("Retrieval run is incomplete; no ablation on partial traces.")
    predictions = [
        json.loads(line)
        for line in (input_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    as_of = str(metadata["started_at"])[:10]
    rankings = {}
    sanity = {"cases": 0, "baseline_matches_saved": 0, "mismatches": []}
    composition = Counter()
    expansion_above_seed_cases = []
    for pred in predictions:
        trace = load_trace(input_dir / "traces" / (pred["id"] + ".json"))
        pool = trace["candidates"]
        seeds = _seed_positions(pool)
        composition.update(c.metadata.get("role") or "seed" for c in pool)
        case_rankings = {"saved_final": trace["saved_final"]}
        for name, policy in POLICIES.items():
            fresh = [to_chunk(as_dict(c)) for c in pool]
            fresh_seeds = _seed_positions(fresh)
            case_rankings[name] = finalize(
                policy(fresh, fresh_seeds, as_of), trace["ctx"], as_of, trace["max_total"]
            )
        rankings[pred["id"]] = case_rankings
        sanity["cases"] += 1
        baseline_paths = [c.metadata.get("path") for c in case_rankings["baseline"]]
        saved_paths = [c.metadata.get("path") for c in trace["saved_final"]]
        if baseline_paths == saved_paths:
            sanity["baseline_matches_saved"] += 1
        else:
            sanity["mismatches"].append(pred["id"])
        ordered_paths = [c.metadata.get("path") for c in case_rankings["baseline"]]
        roles = {c.metadata.get("path"): (c.metadata.get("role") or "seed") for c in pool}
        seed_positions = [i for i, p in enumerate(ordered_paths) if roles.get(p) == "seed"]
        expanded_positions = [i for i, p in enumerate(ordered_paths) if roles.get(p) != "seed"]
        if seed_positions and expanded_positions and min(expanded_positions) < max(seed_positions):
            expansion_above_seed_cases.append(pred["id"])
    return {
        "input_dir": input_dir.name,
        "as_of": as_of,
        "metadata": metadata,
        "predictions": predictions,
        "rankings": rankings,
        "sanity": sanity,
        "composition": dict(composition),
        "expansion_above_seed": expansion_above_seed_cases,
    }


def score_rankings(built: dict) -> dict:
    bundle = load("MIXED_34_TEST_CASES_V04.json")
    cases = {case["id"]: case for case in bundle["test_cases"]}
    provisions = {p["provision_id"]: p for p in load("LEGAL_PROVISIONS.json")}
    aggregate = defaultdict(list)
    by_task = defaultdict(list)
    rows = []
    for pred in built["predictions"]:
        case = cases[pred["id"]]
        gold = case["gold"]
        required = [
            ref(provisions[pid])
            for pid in gold.get("required_provision_ids", [])
            if pid in provisions
        ]
        additional = [
            ref(provisions[pid])
            for pid in gold.get("additional_context_ids", [])
            if pid in provisions
        ]
        negatives = [
            ref(provisions[pid])
            for pid in gold.get("irrelevant_provision_ids", [])
            if pid in provisions
        ]
        for policy, chunks in built["rankings"][pred["id"]].items():
            dicts = [as_dict(c) for c in chunks]
            metrics = retrieval_scores(dicts, required, additional, negatives)
            refs = [ref(d["metadata"]) for d in dicts]
            first_rank = next(
                (
                    index + 1
                    for index, actual in enumerate(refs)
                    if any(matches(actual, expected) for expected in required)
                ),
                None,
            )
            rows.append(
                {
                    "case_id": pred["id"],
                    "task": case["task"],
                    "topic": case.get("topic"),
                    "policy": policy,
                    "first_gold_rank": first_rank,
                    "paths": [c.metadata.get("path") for c in chunks],
                    "metrics": metrics,
                }
            )
            if metrics is not None:
                aggregate[policy].append(metrics)
                by_task[(policy, case["task"])].append(metrics)
    return {
        "cases": cases,
        "aggregate": {policy: mean_metrics(values) for policy, values in aggregate.items()},
        "sample_counts": {policy: len(values) for policy, values in aggregate.items()},
        "by_task": {
            f"{policy}/{task}": mean_metrics(values)
            for (policy, task), values in by_task.items()
        },
        "task_counts": {f"{policy}/{task}": len(values) for (policy, task), values in by_task.items()},
        "rows": rows,
    }


def compare(built: dict, scored: dict) -> dict:
    rows = defaultdict(dict)
    for row in scored["rows"]:
        rows[row["case_id"]][row["policy"]] = row
    out = {}
    for policy in scored["aggregate"]:
        if policy in ("baseline", "saved_final"):
            continue
        pairs = [
            (case_id, by_policy["baseline"], by_policy[policy])
            for case_id, by_policy in rows.items()
            if "baseline" in by_policy and policy in by_policy
        ]
        if not pairs:
            continue
        r5_delta = [
            candidate["metrics"]["recall_at_5"] - base["metrics"]["recall_at_5"]
            for _, base, candidate in pairs
            if base["metrics"] and candidate["metrics"]
        ]
        mrr_delta = [
            candidate["metrics"]["mrr"] - base["metrics"]["mrr"]
            for _, base, candidate in pairs
            if base["metrics"] and candidate["metrics"]
        ]
        rank_delta = [
            (base["first_gold_rank"] or 99) - (candidate["first_gold_rank"] or 99)
            for _, base, candidate in pairs
        ]
        out[policy] = {
            "paired_cases": len(pairs),
            "r5_improved": sum(delta > 0 for delta in r5_delta),
            "r5_unchanged": sum(delta == 0 for delta in r5_delta),
            "r5_reduced": sum(delta < 0 for delta in r5_delta),
            "mean_r5_delta": sum(r5_delta) / len(r5_delta) if r5_delta else None,
            "mean_mrr_delta": sum(mrr_delta) / len(mrr_delta) if mrr_delta else None,
            "mean_first_rank_gain": sum(rank_delta) / len(rank_delta) if rank_delta else None,
            "rescued": [
                case_id for case_id, base, candidate in pairs
                if base["metrics"] and candidate["metrics"]
                and candidate["metrics"]["recall_at_5"] > base["metrics"]["recall_at_5"]
            ],
            "sank": [
                case_id for case_id, base, candidate in pairs
                if base["metrics"] and candidate["metrics"]
                and candidate["metrics"]["recall_at_5"] < base["metrics"]["recall_at_5"]
            ],
        }
    return out


def write_report(output: Path, built: dict, scored: dict, compared: dict) -> None:
    order = [
        "saved_final",
        "baseline",
        "seed_normative",
        "seed_search",
        "seed_cosine",
        "seed_only",
        "production_new",
    ]
    lines = [
        "# Reranking ablation trên corpus hiện có (offline)",
        "",
        "## Phương pháp",
        "",
        f"Chạy lại thứ hạng trên đúng candidate pool đã quan sát trong 34 trace của "
        f"`{built['input_dir']}`. "
        "Không gọi model, không kết nối PostgreSQL/Neo4j, không đổi corpus. "
        "Candidate pool lấy từ sự kiện `graph_expanded` (trước `_order_for_prompt`), "
        "seed order lấy từ thứ tự hybrid search đã lưu.",
        "",
        f"Baseline tái lập đúng **{built['sanity']['baseline_matches_saved']}/{built['sanity']['cases']}** "
        "thứ tự `final_retrieval` đã lưu; các policy được khai báo trước khi đọc gold, "
        "gold chỉ được load sau khi mọi bảng xếp hạng đã cố định.",
        "",
        f"as_of dùng cho hiệu lực = `{built['as_of']}` (ngày bắt đầu run).",
        f"Thành phần candidate pool: {built['composition']}.",
        f"Baseline có ít nhất một chunk expansion xếp trên một seed ở "
        f"**{len(built['expansion_above_seed'])}/{built['sanity']['cases']}** case.",
        "",
        "Các policy:",
        "",
        "| Policy | Cách xếp |",
        "|---|---|",
        "| saved_final | Thứ tự thực tế đã lưu trong trace (tham chiếu, không phải policy) |",
        "| baseline | Thứ tự production trước thay đổi (đóng băng): hiệu lực → loại văn bản → status/năm → role → score |",
        "| seed_normative | hiệu lực → role (seed trước) → loại văn bản → status/năm → cosine |",
        "| seed_search | hiệu lực → role → giữ đúng thứ tự hybrid search của seed → cosine/loại văn bản |",
        "| seed_cosine | hiệu lực → role → cosine → loại văn bản; seed chỉ có FTS xếp dưới seed có cosine |",
        "| seed_only | bỏ toàn bộ graph expansion, giữ seed theo thứ tự search (tham chiếu trần) |",
        "| production_new | gọi trực tiếp `LegalGraphRag._order_for_prompt` sau khi sửa (kiểm tra implementation) |",
        "",
        "## Kết quả tổng",
        "",
        "| Policy | n | R@1 | R@3 | R@5 | R@10 | MRR | Coverage | Số chunk trả về |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy in order:
        if policy not in scored["aggregate"]:
            continue
        values = scored["aggregate"][policy]
        lines.append(
            f"| {policy} | {scored['sample_counts'][policy]} | "
            + " | ".join(format_metric(values.get(name, {}).get("value")) for name in _DISPLAY[:-1])
            + f" | {format_metric(values.get('retrieved_count', {}).get('value'))} |"
        )
    lines += ["", "## Theo nhiệm vụ (R@5 / MRR)", "", "| Policy | Task | n | R@5 | MRR |", "|---|---|---:|---:|---:|"]
    for policy in order:
        for task in ("qa", "multi_hop", "risk", "classification"):
            key = f"{policy}/{task}"
            if key not in scored["by_task"]:
                continue
            values = scored["by_task"][key]
            lines.append(
                f"| {policy} | {task} | {scored['task_counts'][key]} | "
                f"{format_metric(values.get('recall_at_5', {}).get('value'))} | "
                f"{format_metric(values.get('mrr', {}).get('value'))} |"
            )
    lines += [
        "",
        "## So với baseline (paired, n=34)",
        "",
        "| Policy | R@5 tốt hơn | bằng | kém hơn | ΔR@5 TB | ΔMRR TB | Δ hạng gold TB | Case được cứu | Case bị đẩy xuống |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for policy, values in compared.items():
        lines.append(
            f"| {policy} | {values['r5_improved']} | {values['r5_unchanged']} | {values['r5_reduced']} | "
            f"{format_metric(values['mean_r5_delta'])} | {format_metric(values['mean_mrr_delta'])} | "
            f"{format_metric(values['mean_first_rank_gain'])} | "
            f"{', '.join(values['rescued']) or '—'} | {', '.join(values['sank']) or '—'} |"
        )
    lines += [
        "",
        "Δ hạng gold dương nghĩa là chunk gold đầu tiên lên gần top hơn (None được quy ước hạng 99).",
        "",
        "## Đọc kết quả",
        "",
        "- Graph expansion không thêm evidence gold nào trong tập này: coverage của seed và final bằng nhau ở cả 34 case. "
        "Vì vậy thay đổi R@5/MRR ở đây hoàn toàn do thứ hạng, không do candidate pool.",
        "- Policy đưa seed lên trước expansion sửa trực tiếp hiện tượng final R@5 thấp hơn seed R@5.",
        "- `production_new` phải trùng `seed_search`; nếu hai dòng khác nhau thì bản sửa production chưa đúng.",
        "- `seed_cosine` và `seed_search` khác nhau ở cách xử lý seed chỉ có FTS (score = RRF, rất nhỏ). "
        "Đây là điểm cần chọn có chủ đích, không nên tối ưu theo từng case.",
        "- `seed_only` là tham chiếu trần cho ranking, không phải đề xuất bỏ GraphRAG. Expansion vẫn có thể hữu ích cho ngữ cảnh sinh đáp án, nhưng lần này generation chưa được đo.",
        "",
        "## Giới hạn",
        "",
        "- n=34, nhãn gold là synthetic draft chưa được chuyên gia pháp lý xác minh; chênh lệch nhỏ có thể do nhiễu.",
        "- Đánh giá offline trên candidate pool đã lưu, không chứng minh hành vi trên corpus/câu hỏi khác.",
        "- Chưa có temporal retrieval, chưa có generation/answer quality; date chỉ dùng để xếp hiệu lực.",
        "- Không sửa corpus, không đổi `is_effective`, không dùng gold để chọn policy.",
        "",
    ]
    (output / "RERANK_ABLATION.md").write_text("\n".join(lines), encoding="utf-8")


def write_csv(output: Path, scored: dict) -> None:
    fields = [
        "case_id", "task", "topic", "policy", "first_gold_rank",
        "recall_at_1", "recall_at_3", "recall_at_5", "recall_at_10",
        "mrr", "required_evidence_coverage", "retrieved_count", "paths",
    ]
    with (output / "CASE_RANK_COMPARISON.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in scored["rows"]:
            metrics = row["metrics"] or {}
            writer.writerow(
                {
                    "case_id": row["case_id"],
                    "task": row["task"],
                    "topic": row["topic"],
                    "policy": row["policy"],
                    "first_gold_rank": row["first_gold_rank"],
                    **{
                        name: metrics.get(name)
                        for name in (
                            "recall_at_1",
                            "recall_at_3",
                            "recall_at_5",
                            "recall_at_10",
                            "mrr",
                            "required_evidence_coverage",
                            "retrieved_count",
                        )
                    },
                    "paths": " | ".join(p for p in row["paths"] if p),
                }
            )


def run(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    built = build_rankings(input_dir)
    scored = score_rankings(built)
    compared = compare(built, scored)
    write_report(output_dir, built, scored, compared)
    write_csv(output_dir, scored)
    write_json(
        output_dir / "RERANK_METRICS.json",
        {
            "mode": "offline_rerank_ablation",
            "input_dir": str(input_dir),
            "as_of": built["as_of"],
            "baseline_sanity": built["sanity"],
            "candidate_composition": built["composition"],
            "expansion_above_seed_cases": built["expansion_above_seed"],
            "policies": {name: fn.__doc__ for name, fn in POLICIES.items()},
            "aggregate": scored["aggregate"],
            "sample_counts": scored["sample_counts"],
            "by_task": scored["by_task"],
            "paired_vs_baseline": compared,
            "gold_loaded_after_rankings": True,
            "model_calls": 0,
        },
    )
    best = max(
        (
            policy
            for policy in scored["aggregate"]
            if policy not in ("saved_final", "seed_only", "production_new")
        ),
        key=lambda policy: (
            scored["aggregate"][policy].get("recall_at_5", {}).get("value") or 0,
            scored["aggregate"][policy].get("mrr", {}).get("value") or 0,
        ),
    )
    print(
        json.dumps(
            {
                "cases": built["sanity"]["cases"],
                "baseline_matches_saved": built["sanity"]["baseline_matches_saved"],
                "best_policy_by_r5": best,
                "final_r5": scored["aggregate"].get("baseline", {}).get("recall_at_5", {}).get("value"),
                "best_r5": scored["aggregate"].get(best, {}).get("recall_at_5", {}).get("value"),
                "best_mrr": scored["aggregate"].get(best, {}).get("mrr", {}).get("value"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        default=str(RUNS / "rag_only_no_labor_hint"),
    )
    parser.add_argument(
        "--output-dir",
        default=str(RUNS / "rerank_ablation_20261026"),
    )
    args = parser.parse_args()
    run(Path(args.input_dir).resolve(), Path(args.output_dir).resolve())

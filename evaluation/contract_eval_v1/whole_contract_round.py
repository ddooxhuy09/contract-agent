"""Đo trước/sau: câu hỏi toàn hợp đồng (T3) đọc mọi Điều của hợp đồng đang hỏi thay vì top-k vector,
kèm Điều BLLĐ theo chủ đề của từng Điều hợp đồng (lượt c; lượt b chỉ đọc mọi Điều, luật vẫn tìm theo câu hỏi).

Lưu hồ sơ: bản sửa T3 (`asks_whole_contract`) không đạt và đã hoàn tác, chưa từng commit, nên script không chạy lại được
trên code hiện tại. Kết quả: evaluation_results/runs/whole_contract_20261122{,b,c}/RESULT.md.

    python -m evaluation.contract_eval_v1.whole_contract_round prepare   # câu hỏi, gold, protocol (hash), nạp hợp đồng v3
    python -m evaluation.contract_eval_v1.whole_contract_round qa        # QaPipeline thật, 2 cấu hình xen kẽ, có resume
    python -m evaluation.contract_eval_v1.whole_contract_round judge     # judge Groq qwen, không thấy tên cấu hình
    python -m evaluation.contract_eval_v1.whole_contract_round score

Protocol (chốt trước khi chạy, ghi vào PROTOCOL.json):
- baseline = code hiện tại nhưng tắt định tuyến (`asks_whole_contract` -> False, tức top-k vector như trước);
  candidate = code hiện tại. Cùng tiến trình, cùng model sinh/judge/kho luật; thứ tự cấu hình đảo theo từng câu.
- dev: 16 ca gốc injection thuộc dev v1, mỗi ca 2 câu (T3 gốc + một câu diễn đạt khác viết trước khi chạy).
- validation: 48 ca injection_v3 (3 hợp đồng nền khác), câu T3 gốc; chưa từng dùng cho QA, không dùng để sửa code.
- Chỉ số chính: kết luận khớp nhãn và correctness (judge 0–2) trên validation. Phụ: Điều gold có trong ngữ cảnh hợp đồng.
- CI95 chênh lệch theo cặp, bootstrap 1000 lần theo ca gốc, seed 42. Không sửa nhãn, không chạy lại để chọn điểm.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import subprocess
import time
from pathlib import Path

from evaluation.contract_eval_v1.build import CASES, ROOT, SPLIT, jl_read
from evaluation.contract_eval_v1.run import (JUDGE_PROMPT, LlmTap, GroqJudge, append, bind, done_ids, eval_user, index_text,
                                            judge_item, qa_one, setup_qa)

OUT = ROOT / "evaluation_results" / "runs" / "whole_contract_20261122c"  # a hủy (ABORTED.md), b = chỉ đọc mọi Điều
V1_RUN = ROOT / "evaluation_results" / "runs" / "contract_eval_v1_20261115"
V3 = ROOT / "evaluation" / "injection_v3"
PARAPHRASE = "Rà soát giúp tôi: trong hợp đồng này có chỗ nào bất lợi hoặc trái luật với người lao động không?"
T3 = "Hợp đồng này có điều khoản nào gây rủi ro cho người lao động không?"
CONFIGS = ("baseline", "candidate")
CODE_FILES = ["app/agents/qa_agent.py", "app/agents/qa_evidence.py", "app/infrastructure/retrieval/query_rewrite.py",
              "evaluation/contract_eval_v1/run.py"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def facts(label: str, n: str | None) -> list[str]:
    return ([f"Điều {n} trái/vi phạm quy định pháp luật lao động"] if label == "violation"
            else ["không có điều khoản bơm lỗi vi phạm luật đỏ"])


def cmd_prepare(_) -> None:
    from evaluation.injection_v3.run import load_cases as v3_cases, slot_of
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "PROTOCOL.json").exists():
        raise SystemExit("Đã chuẩn bị (PROTOCOL.json); không chuẩn bị lại.")
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    quar = {json.loads(x)["id"] for x in (ROOT / "evaluation/contract_eval_v1/quarantine.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    v1 = {c["id"]: c for c in jl_read(CASES)}
    inputs, gold = [], {}
    for unit in split["dev"]:
        c = v1.get(f"{unit}-T3")
        if not c or c["source_set"] != "injection" or c["id"] in quar:
            continue
        n = c["gold_clause_ids"][0] if c["gold_clause_ids"] else None
        for var, q in (("t3", T3), ("paraphrase", PARAPHRASE)):
            qid = f"DEV-{unit}-{var}"
            inputs.append({"id": qid, "group": "dev", "base": unit, "contract_path": c["contract_path"], "question": q})
            gold[qid] = {"label": c["gold_label"], "clause": n, "facts": facts(c["gold_label"], n)}
    for c in v3_cases():
        n = str(slot_of(c)) if c["label"] == "violation" else None
        qid = f"VAL-{c['case_id']}"
        inputs.append({"id": qid, "group": "validation", "base": c["case_id"],
                       "contract_path": f"evaluation/injection_v3/contracts/{c['case_id']}.txt", "question": T3})
        gold[qid] = {"label": c["label"], "clause": n, "facts": facts(c["label"], n)}
    (OUT / "inputs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in inputs), encoding="utf-8")
    (OUT / "gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
    old = OUT / "contract_map.json"  # dùng lại hợp đồng đã nạp, không nạp trùng
    cmap = json.loads((old if old.exists() else V1_RUN / "contract_map.json").read_text(encoding="utf-8"))
    cont = bind()
    user = eval_user(cont)
    for r in inputs:
        if r["contract_path"] not in cmap:
            cmap[r["contract_path"]] = index_text(cont, user, ROOT / r["contract_path"], "whole_contract_round")
    (OUT / "contract_map.json").write_text(json.dumps(cmap, ensure_ascii=False, indent=1), encoding="utf-8")
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (OUT / "PROTOCOL.json").write_text(json.dumps({
        "doc": __doc__, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "git_head": git,
        "code_sha256": {f: sha(ROOT / f) for f in CODE_FILES},
        "inputs_sha256": sha(OUT / "inputs.jsonl"), "gold_sha256": sha(OUT / "gold.json"),
        "n": {g: sum(r["group"] == g for r in inputs) for g in ("dev", "validation")}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"prepared {len(inputs)} questions")


def check_protocol() -> dict:
    p = json.loads((OUT / "PROTOCOL.json").read_text(encoding="utf-8"))
    bad = [f for f, h in p["code_sha256"].items() if sha(ROOT / f) != h]
    bad += [f for f, k in (("inputs.jsonl", "inputs_sha256"), ("gold.json", "gold_sha256")) if sha(OUT / f) != p[k]]
    if bad:
        raise SystemExit(f"Khác protocol đã chốt: {bad}")
    return p


async def cmd_qa(_) -> None:
    import app.agents.qa_agent as qa_mod
    from app.agents.llm_client import DEFAULT_PROVIDER
    check_protocol()
    inputs = [json.loads(x) for x in (OUT / "inputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    cmap = json.loads((OUT / "contract_map.json").read_text(encoding="utf-8"))
    bind()
    tap = LlmTap()
    qa, cap = setup_qa()
    real = qa_mod.asks_whole_contract
    out = OUT / "qa.jsonl"
    have = done_ids(out)
    for i, r in enumerate(inputs):
        order = CONFIGS if i % 2 == 0 else CONFIGS[::-1]
        for cfg in order:
            uid = f"{r['id']}|{cfg}"
            if uid in have:
                continue
            qa_mod.asks_whole_contract = real if cfg == "candidate" else (lambda q: False)
            tap.take()
            t0 = time.perf_counter()
            row = {"id": uid, "qid": r["id"], "config": cfg, "group": r["group"], "base": r["base"]}
            try:
                row.update(await qa_one({"id": uid, "question": r["question"], "as_of_date": None},
                                        cmap[r["contract_path"]], qa, cap, DEFAULT_PROVIDER))
                row["status"] = "completed"
            except Exception as e:  # noqa: BLE001
                row["status"], row["error"] = "failed", f"{type(e).__name__}: {str(e)[:400]}"
            ev = tap.take()
            row["tokens"] = sum((e["usage"] or {}).get("total_tokens", 0) for e in ev)
            row["llm_errors"] = sum(bool(e["error"]) for e in ev)
            row["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            if row["llm_errors"] and any("spend alert" in (e["error"] or "") or "per day" in (e["error"] or "") for e in ev):
                print(f"STOP: quota/chặn LLM tại {uid}")
                return
            append(out, row)
            print(f"{uid} {row['status']} ctx={row.get('context_contract_clauses')}", flush=True)
    qa_mod.asks_whole_contract = real


def cmd_judge(_) -> None:
    check_protocol()
    inputs = {json.loads(x)["id"]: json.loads(x) for x in (OUT / "inputs.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    gold = json.loads((OUT / "gold.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (OUT / "qa.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    out = OUT / "judge.jsonl"
    have = done_ids(out)
    llm = GroqJudge()
    rng = random.Random(42)
    todo = [r for r in rows if r["status"] == "completed" and r["id"] not in have]
    rng.shuffle(todo)  # trộn cấu hình trong mỗi lượt judge
    for i in range(0, len(todo), 3):
        batch = todo[i:i + 3]
        items = []
        for k, r in enumerate(batch):
            g = gold[r["qid"]]
            ctx = f"[LUẬT]\n{r.get('context_legal', '')}\n[HỢP ĐỒNG]\n{r.get('context_contract', '')}"
            items.append(judge_item(f"J{k}", inputs[r["qid"]]["question"], r["answer"], ctx, g["label"], g["facts"]))
        resp = llm.json(JUDGE_PROMPT.format(items="\n\n".join(items)))
        got = {it.get("id"): it for it in ((resp.get("items") if isinstance(resp, dict) else resp) or []) if isinstance(it, dict)}
        for k, r in enumerate(batch):
            j = got.get(f"J{k}")
            if j:
                append(out, {"id": r["id"], **{x: j.get(x) for x in ("claims", "correctness", "answer_conclusion")},
                             "judge_model": f"groq/{llm.model_name}"})
        print(f"judge {min(i + 3, len(todo))}/{len(todo)}", flush=True)


def cmd_score(_) -> None:
    proto = check_protocol()
    gold = json.loads((OUT / "gold.json").read_text(encoding="utf-8"))
    rows = {json.loads(x)["id"]: json.loads(x) for x in (OUT / "qa.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    judge = {json.loads(x)["id"]: json.loads(x) for x in (OUT / "judge.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}

    def per(r):
        g, j = gold[r["qid"]], judge.get(r["id"], {})
        corr = j.get("correctness")
        claims = j.get("claims") or []
        return {"qid": r["qid"], "base": r["base"], "label": g["label"],
                "correctness": None if corr is None else corr / 2,
                "full": None if corr is None else float(corr == 2),
                "conclusion_match": None if not j else float(j.get("answer_conclusion") == g["label"]),
                "faithfulness": sum(int(c.get("supported") or 0) for c in claims) / len(claims) if claims else None,
                "gold_in_context": None if not g["clause"] else float(g["clause"] in map(str, r.get("context_contract_clauses") or [])),
                "tokens": r.get("tokens"), "ms": r.get("total_ms")}

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None

    metrics = {"protocol": {k: proto[k] for k in ("created_at", "git_head", "n")}, "groups": {}}
    keys = ("correctness", "full", "conclusion_match", "faithfulness", "gold_in_context")
    for group in ("dev", "validation"):
        by = {cfg: {per(r)["qid"]: per(r) for r in rows.values() if r["group"] == group and r["config"] == cfg
                    and r["status"] == "completed"} for cfg in CONFIGS}
        res = {"n_completed": {c: len(by[c]) for c in CONFIGS}, "n_judged": {c: sum(x["correctness"] is not None for x in by[c].values()) for c in CONFIGS}}
        for cfg in CONFIGS:
            vals = list(by[cfg].values())
            res[cfg] = {k: mean([x[k] for x in vals]) for k in keys}
            res[cfg]["violation_conclusion_match"] = mean([x["conclusion_match"] for x in vals if x["label"] == "violation"])
            res[cfg]["compliant_conclusion_match"] = mean([x["conclusion_match"] for x in vals if x["label"] == "compliant"])
            res[cfg]["tokens_mean"] = mean([x["tokens"] for x in vals])
            ms = sorted(x["ms"] for x in vals if x["ms"])
            res[cfg]["latency_ms_p50"] = ms[len(ms) // 2] if ms else None
        pairs = [(by["baseline"][q], by["candidate"][q]) for q in by["baseline"] if q in by["candidate"]]
        bases = sorted({b["base"] for b, _ in pairs})
        for k in ("correctness", "conclusion_match"):
            ok = [(b, c) for b, c in pairs if b[k] is not None and c[k] is not None]
            diff = mean([c[k] - b[k] for b, c in ok])
            rng, draws = random.Random(42), []
            groups = {base: [(b, c) for b, c in ok if b["base"] == base] for base in bases}
            for _ in range(1000):
                sample = [p for base in (rng.choice(bases) for _ in bases) for p in groups[base]]
                if sample:
                    draws.append(sum(c[k] - b[k] for b, c in sample) / len(sample))
            draws.sort()
            res[f"diff_{k}"] = {"value": diff, "ci95": [round(draws[25], 4), round(draws[974], 4)] if draws else None,
                                "improved": sum(c[k] > b[k] for b, c in ok), "worse": sum(c[k] < b[k] for b, c in ok),
                                "same": sum(c[k] == b[k] for b, c in ok)}
        metrics["groups"][group] = res
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["prepare", "qa", "judge", "score"])
    a = ap.parse_args()
    if a.cmd == "qa":
        asyncio.run(cmd_qa(a))
    else:
        {"prepare": cmd_prepare, "judge": cmd_judge, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()

"""Rà nhãn phần test bằng hội đồng AI 3 phòng độc lập (không có luật sư; xem DECISIONS.md, mục "Hội đồng AI").

    python -m evaluation.contract_eval_v1.ai_panel build   # hồ sơ ẩn nhãn: packet.jsonl, law.json; khoá id ở key.json
    python -m evaluation.contract_eval_v1.ai_panel merge   # gộp 3 phòng (đa số), đồng thuận, so với nhãn bộ test
    python -m evaluation.contract_eval_v1.ai_panel sensitivity [--run-dir DIR]  # chỉ số trên ca hội đồng đồng ý nhãn

Mỗi phòng chỉ đọc packet.jsonl + law.json và ghi room_<X>.jsonl. Id trong hồ sơ là mã ngẫu nhiên (id gốc như
"DT2-V1" lộ nhãn), câu hỏi lấy mẫu T1 trung tính, tập luật tham khảo gồm Điều gold, Điều kề bên và Điều theo chủ đề.
"""
from __future__ import annotations

import argparse
import json
import random
import unicodedata
from collections import Counter

from evaluation.contract_eval_v1.build import CASES, ROOT, SPLIT, jl_read
from evaluation.contract_eval_v1.verify import QUAR, contract_text, parser_clauses

OUT = ROOT / "evaluation_results" / "ai_panel_v1"
LABELS = ("violation", "compliant", "n/a", "unclear")
ROOMS = ("A", "B", "C")


def base_cases() -> list[dict]:
    quar = {r["id"] for r in jl_read(QUAR)}
    test = set(json.loads(SPLIT.read_text(encoding="utf-8"))["test"])
    by_base: dict[str, dict] = {}
    for c in jl_read(CASES):
        if c["id"] in quar or c["base_case_id"] not in test:
            continue
        cur = by_base.get(c["base_case_id"])
        if cur is None or (c["template"] == "T1" and cur["template"] != "T1"):
            by_base[c["base_case_id"]] = c
    return [by_base[k] for k in sorted(by_base)]


def clause_text(c: dict) -> str:
    if c["gold_clause_text"]:
        return c["gold_clause_text"]
    if not c["contract_path"]:
        return ""
    text = unicodedata.normalize("NFC", contract_text(c["contract_path"]))
    if not c["gold_clause_ids"]:
        return text[:12000]  # câu hỏi về cả hợp đồng
    cl = parser_clauses(text)
    return "\n\n".join(cl.get(str(i), "") for i in c["gold_clause_ids"]).strip()


def law_text(repo, doc_id: str, article: int) -> str:
    from app.agents.qa_evidence import _article_text
    return _article_text(repo.find_article_chunks(doc_id, rf"\.D{article}(\.|$)", 64))[:3500]


def cmd_build() -> None:
    from app.agents.qa_evidence import topic_articles
    from app.infrastructure.db.connection import get_db
    from app.infrastructure.retrieval.context import get_legal_chunks
    from evaluation.contract_eval_v1.run import bind

    bind()
    repo = get_legal_chunks()
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_num, doc_id, title FROM legal_documents")
        docs = {n: (i, t) for n, i, t in cur.fetchall()}
    rng = random.Random(20261124)
    cases = base_cases()
    codes = rng.sample(range(100, 1000), len(cases))
    law, items, key = {}, [], {}
    for c, code in zip(cases, codes):
        pid = f"P{code}"
        text = clause_text(c)
        wanted = []
        for g in c["gold_legal_refs"]:
            wanted += [(g["doc"], a) for a in (g["article"] - 1, g["article"], g["article"] + 1) if a > 0]
        if "lao động" in (c["contract_type"] or "").lower():
            wanted += [("45/2019/QH14", a) for a in topic_articles(text or c["question"])]
        refs = []
        for doc, art in dict.fromkeys(wanted):
            k = f"{doc} Điều {art}"
            if k not in law and doc in docs:
                body = law_text(repo, docs[doc][0], art)
                if body:
                    law[k] = f"[{doc}: {docs[doc][1]}]\n{body}"
            if k in law:
                refs.append(k)
        items.append({"pid": pid, "contract_type": c["contract_type"], "as_of_date": c["as_of_date"],
                      "transaction_date": c["transaction_date"], "question": c["question"],
                      "clause_ids": c["gold_clause_ids"], "clause_text": text, "law_refs": sorted(refs)})
        key[pid] = c["base_case_id"]
    OUT.mkdir(parents=True, exist_ok=True)
    items.sort(key=lambda x: x["pid"])
    (OUT / "packet.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")
    (OUT / "law.json").write_text(json.dumps(law, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} items, {len(law)} law articles -> {OUT.relative_to(ROOT)}")


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa cho hai chuỗi nhãn."""
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / n / n
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def fleiss(rows: list[list[str]]) -> float | None:
    n, m = len(rows), len(rows[0]) if rows else 0
    if not n or m < 2:
        return None
    cats = sorted({x for r in rows for x in r})
    p_i = [(sum(r.count(k) ** 2 for k in cats) - m) / (m * (m - 1)) for r in rows]
    p_j = [sum(r.count(k) for r in rows) / (n * m) for k in cats]
    pbar, pe = sum(p_i) / n, sum(p * p for p in p_j)
    return round((pbar - pe) / (1 - pe), 3) if pe < 1 else 1.0


def cmd_merge() -> None:
    key = json.loads((OUT / "key.json").read_text(encoding="utf-8"))
    gold = {c["base_case_id"]: c for c in base_cases()}
    rooms = {}
    for r in ROOMS:
        rows = {x["pid"]: x for x in jl_read(OUT / f"room_{r}.jsonl")}
        missing = set(key) - set(rows)
        bad = [p for p, x in rows.items() if x.get("label") not in LABELS]
        if missing or bad:
            raise SystemExit(f"room {r}: thiếu {sorted(missing)[:5]}, nhãn sai {bad[:5]}")
        rooms[r] = rows
    merged, by_cat = [], Counter()
    for pid, base in sorted(key.items(), key=lambda kv: kv[1]):
        votes = [rooms[r][pid]["label"] for r in ROOMS]
        top, cnt = Counter(votes).most_common(1)[0]
        panel = top if cnt >= 2 else "unclear"
        g = gold[base]
        arts = [{(a.get("doc"), a.get("article")) for a in rooms[r][pid].get("articles") or []} for r in ROOMS]
        gold_a = {(x["doc"], x["article"]) for x in g["gold_legal_refs"]}
        row = {"base_case_id": base, "pid": pid, "source_set": g["source_set"], "rule_id": g["rule_id"],
               "gold_label": g["gold_label"], "votes": dict(zip(ROOMS, votes)), "panel_label": panel,
               "unanimous": cnt == 3, "agrees_with_gold": panel == g["gold_label"],
               "gold_article_cited_by": sum(bool(gold_a & a) for a in arts) if gold_a else None,
               "reasons": {r: rooms[r][pid].get("reason") for r in ROOMS},
               "confidence": {r: rooms[r][pid].get("confidence") for r in ROOMS}}
        merged.append(row)
        by_cat[(g["gold_label"], panel)] += 1
    n = len(merged)
    agree = sum(r["agrees_with_gold"] for r in merged)
    decided = [r for r in merged if r["panel_label"] != "unclear"]
    with_art = [r for r in merged if r["gold_article_cited_by"] is not None]
    metrics = {
        "n_base_cases": n,
        "inter_room": {"fleiss_kappa": fleiss([[r["votes"][x] for x in ROOMS] for r in merged]),
                       "unanimous": sum(r["unanimous"] for r in merged),
                       "pairwise_kappa": {f"{a}-{b}": kappa([(r["votes"][a], r["votes"][b]) for r in merged])
                                          for a, b in (("A", "B"), ("A", "C"), ("B", "C"))}},
        "panel_vs_gold": {"agree": agree, "rate": round(agree / n, 4),
                          "kappa": kappa([(r["panel_label"], r["gold_label"]) for r in merged]),
                          "panel_unclear": n - len(decided),
                          "rate_on_decided": round(sum(r["agrees_with_gold"] for r in decided) / len(decided), 4) if decided else None,
                          "confusion_gold_to_panel": {f"{g}->{p}": k for (g, p), k in sorted(by_cat.items())}},
        "gold_article": {"n": len(with_art), "cited_by_majority": sum(r["gold_article_cited_by"] >= 2 for r in with_art)},
        "by_source": {s: {"n": sum(r["source_set"] == s for r in merged),
                          "agree": sum(r["agrees_with_gold"] for r in merged if r["source_set"] == s)}
                      for s in sorted({r["source_set"] for r in merged})},
        "disagreements": [r["base_case_id"] for r in merged if not r["agrees_with_gold"]],
    }
    (OUT / "merged.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in merged), encoding="utf-8")
    (OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in metrics.items() if k != "disagreements"}, ensure_ascii=False, indent=1))
    print("disagreements:", metrics["disagreements"])


def cmd_sensitivity(run_dir: str) -> None:
    """Chỉ số phát hiện và QA (test) trên toàn bộ và trên tập ca gốc mà hội đồng đồng ý với nhãn bộ test."""
    import csv
    agreed = {r["base_case_id"] for r in jl_read(OUT / "merged.jsonl") if r["agrees_with_gold"]}
    base_of = {c["id"]: c["base_case_id"] for c in jl_read(CASES)}
    with (ROOT / run_dir / "per_case.csv").open(encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == "test"]
    for r in rows:  # QA ghi id ca ở "id", phát hiện ghi ở "case_id"
        r["case_id"] = r["case_id"] or r["id"]

    def summary(sub):
        det = [r for r in sub if r["kind"] == "detect"]
        tp = sum(r["y"] == "True" and r["p"] == "True" for r in det)
        fp = sum(r["y"] == "False" and r["p"] == "True" for r in det)
        pos, neg = sum(r["y"] == "True" for r in det), sum(r["y"] == "False" for r in det)
        p, rc = (tp / (tp + fp) if tp + fp else 0), (tp / pos if pos else 0)
        qa = [r for r in sub if r["kind"] == "qa" and r["judged"] == "True"]
        corr = [float(r["correctness"]) / 2 for r in qa if r["correctness"]]
        concl = [float(r["conclusion_match"]) for r in qa if r["conclusion_match"]]
        return {"detect_n": len(det), "precision": round(p, 4), "recall": round(rc, 4),
                "f1": round(2 * p * rc / (p + rc), 4) if p + rc else 0, "near_miss_fp_rate": round(fp / neg, 4) if neg else None,
                "qa_n": len(qa), "qa_correctness_norm": round(sum(corr) / len(corr), 4) if corr else None,
                "qa_conclusion_match": round(sum(concl) / len(concl), 4) if concl else None}

    out = {"run_dir": run_dir, "all": summary(rows),
           "panel_agreed": summary([r for r in rows if base_of[r["case_id"]] in agreed]), "n_agreed_base_cases": len(agreed)}
    (OUT / "sensitivity.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "merge", "sensitivity"])
    ap.add_argument("--run-dir", default="evaluation_results/runs/contract_eval_v1_20261124")
    a = ap.parse_args()
    cmd_sensitivity(a.run_dir) if a.cmd == "sensitivity" else {"build": cmd_build, "merge": cmd_merge}[a.cmd]()

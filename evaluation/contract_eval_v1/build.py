"""contract_eval_v1: gộp các bộ có sẵn thành một bộ test hợp nhất (nhãn do cấu tạo, câu hỏi theo template).

    python -m evaluation.contract_eval_v1.build      # cần Postgres (map căn cứ luật sang path trong kho)

Đầu ra (cùng thư mục): cases.jsonl, inputs_no_gold.jsonl, gold.jsonl, split.json.
Không dùng LLM. Nhãn suy ra trực tiếp từ cách tạo ca (injection, injection_v2), hoặc giữ nguyên gold (v04, contract_qa).
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INJ = ROOT / "evaluation" / "injection"
INJ2 = ROOT / "evaluation" / "injection_v2"
V04 = ROOT / "evaluation" / "benchmark" / "v04"
QA_FIXTURE = ROOT / "tests" / "fixtures" / "contract_qa_cases.json"
QA_CONTRACT = ROOT / "data" / "demo_contracts" / "CÔNG TY CỔ PHẦN CÔNG NGHỆ TƯƠNG LAI_SAI.md"
REVIEW_CSV = ROOT / "docs" / "bo_test_hoi_dong" / "REVIEW_BO_TEST_HOP_DONG.csv"

CASES = HERE / "cases.jsonl"
INPUTS = HERE / "inputs_no_gold.jsonl"
GOLD = HERE / "gold.jsonl"
SPLIT = HERE / "split.json"
SEED, TEST_FRAC = 42, 0.75
LABOR = "Hợp đồng lao động"

DOC_ALIASES = {"BLLĐ 2019": "45/2019/QH14", "Luật BHXH 2024": "41/2024/QH15"}
TEMPLATES = {
    "T1": "Điều {n} của hợp đồng có trái quy định pháp luật lao động không?",
    "T2": "Điều khoản về {topic} trong hợp đồng cần đối chiếu với điều luật nào?",
    "T3": "Hợp đồng này có điều khoản nào gây rủi ro cho người lao động không?",
}
INPUT_FIELDS = ("id", "contract_path", "contract_type", "question", "as_of_date", "transaction_date")


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def jl_read(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def jl_write(p: Path, rows: list[dict]) -> None:
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8", newline="\n")


# ---------- căn cứ luật ----------
def parse_legal_basis(text: str) -> list[dict]:
    """'BLLĐ 2019 Điều 98 khoản 1 (...); Điều 107 khoản 2 (...)' -> [{doc, article, clause}]."""
    flat = re.sub(r"\([^()]*\)", "", text)
    refs, doc, article = [], None, None
    for seg in flat.split(";"):
        for alias, num in DOC_ALIASES.items():
            if alias in seg:
                doc = num
        m = re.search(r"Điều\s+(\d+)", seg)
        if m:
            article = int(m.group(1))
        k = re.search(r"khoản\s+([\d,\s]+)", seg)
        clauses = [int(x) for x in re.findall(r"\d+", k.group(1))] if k else [None]
        if doc and article and (m or k):
            refs += [{"doc": doc, "article": article, "clause": c} for c in clauses]
    return refs


def ref_lquery(doc_id: str, ref: dict) -> str:
    q = f"{doc_id}.*.D{ref['article']}"
    return q + (f".K{ref['clause']}" if ref.get("clause") else "") + ".*"


def map_refs(cases: list[dict]) -> None:
    """Gắn doc_id + lquery cho từng ref; ref không có trong kho -> unmapped_refs."""
    from app.infrastructure.db.connection import get_db

    docs = {r["doc"] for c in cases for r in c["gold_legal_refs"]}
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT doc_num, doc_id FROM legal_documents WHERE doc_num = ANY(%s)", (sorted(docs),))
        doc_ids = dict(cur.fetchall())
        cache: dict[str, bool] = {}
        for c in cases:
            mapped, unmapped = [], []
            for r in c["gold_legal_refs"]:
                did = doc_ids.get(r["doc"])
                q = ref_lquery(did, r) if did else None
                if q and q not in cache:
                    cur.execute("SELECT EXISTS(SELECT 1 FROM legal_embeddings WHERE path ~ %s::lquery)", (q,))
                    cache[q] = cur.fetchone()[0]
                (mapped if q and cache[q] else unmapped).append({**r, "doc_id": did, "lquery": q})
            c["gold_legal_refs"], c["unmapped_refs"] = mapped, unmapped


# ---------- nguồn ----------
def clause_title(clause_text: str) -> str:
    first = clause_text.strip().splitlines()[0]
    return re.sub(r"^Điều\s+\d+\.\s*", "", first).strip()


def difficulty(label: str, phrasing: str) -> str:
    if label == "compliant":
        return "hard"
    return "easy" if phrasing == "formulaic" else "medium"


def injection_cases(src_dir: Path, source_set: str) -> list[dict]:
    out = []
    for c in jl_read(src_dir / "cases.jsonl"):
        n, viol = int(c["slot"]), c["label"] == "violation"
        refs = parse_legal_basis(c["legal_basis"])
        arts = sorted({r["article"] for r in refs})
        art_txt = ", ".join(f"Điều {a}" for a in arts)
        base = {
            "base_case_id": c["case_id"], "source_set": source_set, "rule_id": c["rule_id"],
            "contract_path": rel(src_dir / "contracts" / f"{c['case_id']}.txt"), "contract_type": LABOR,
            "gold_clause_text": c["clause_text"], "gold_label": c["label"],
            "gold_red_flags": [c["rule_id"]] if viol else [],
            "as_of_date": None, "transaction_date": None,
            "difficulty": difficulty(c["label"], c["phrasing"]),
            "phrasing_type": c.get("negation_form") if c.get("negation_form") not in (None, "none") else c["phrasing"],
        }
        concl = f"Điều {n} {'trái/vi phạm' if viol else 'không trái (hợp lệ với)'} quy định pháp luật lao động"
        topic = clause_title(c["clause_text"]).lower()
        for t, tpl in TEMPLATES.items():
            row = {**base, "id": f"{c['case_id']}-{t}", "template": t, "question": tpl.format(n=n, topic=topic)}
            if t == "T1":
                row.update(gold_clause_ids=[str(n)], gold_legal_refs=refs, gold_key_facts=[concl, f"căn cứ {art_txt} BLLĐ 2019"])
            elif t == "T2":
                row.update(gold_clause_ids=[str(n)], gold_legal_refs=refs, gold_key_facts=[f"đối chiếu {art_txt} BLLĐ 2019"])
                row["gold_label"] = "n/a"  # câu hỏi căn cứ, không hỏi kết luận
            else:  # T3: chấm theo red flag mức tài liệu
                row.update(gold_clause_ids=[str(n)] if viol else [], gold_legal_refs=refs if viol else [],
                           gold_key_facts=[concl] if viol else ["không có điều khoản bơm lỗi vi phạm luật đỏ"])
            out.append(row)
    return out


def rule_basis() -> dict[str, str]:
    return {c["rule_id"]: c["legal_basis"] for c in jl_read(INJ / "cases.jsonl")}


def contract_qa_cases() -> list[dict]:
    basis = rule_basis()
    out = []
    for i, c in enumerate(json.loads(QA_FIXTURE.read_text(encoding="utf-8")), 1):
        flags = c.get("expected_red_flags") or []
        refs = [r for f in flags for r in parse_legal_basis(basis[f])]
        out.append({
            "id": f"QA-{i:02d}", "base_case_id": f"QA-{i:02d}", "fixture_id": c["id"], "source_set": "contract_qa",
            "template": "fixed",
            "rule_id": flags[0] if flags else None, "contract_path": rel(QA_CONTRACT), "contract_type": LABOR,
            "question": c["question"], "gold_clause_ids": [str(x) for x in c.get("expected_source_clauses") or []],
            "gold_clause_text": "", "gold_label": "violation" if flags else "n/a", "gold_red_flags": flags,
            "gold_legal_refs": refs, "gold_key_facts": c.get("required_query_terms") or [],
            "as_of_date": None, "transaction_date": None, "difficulty": "easy", "phrasing_type": "fixture",
        })
    return out


V04_LABEL = {"critical": "violation", "warning": "violation", "ok": "compliant"}


def v04_cases() -> list[dict]:
    data = json.loads((V04 / "MIXED_34_TEST_CASES_V04.json").read_text(encoding="utf-8"))
    contracts = {c["contract_id"]: c for c in data["contracts"]}
    inputs = {q["id"]: q for q in json.loads((V04 / "QUESTIONS_ONLY_NO_GOLD.json").read_text(encoding="utf-8"))}
    out = []
    for c in data["test_cases"]:
        inp, gold, q = c["input"], c["gold"], inputs[c["id"]]
        cid = inp.get("contract_id")
        clause_ids = []
        if cid and inp.get("contract_excerpt_span"):
            s = inp["contract_excerpt_span"]
            for cl in contracts[cid]["clauses"]:
                if cl["start"] <= s["start"] < cl["end"] + 2:
                    clause_ids = [re.sub(r"^(Điều|Khoản|Mục)\s+", "", cl["clause_id"]).strip()]
        ev = {e["provision_id"]: e for e in gold.get("evidence") or []}
        refs = []
        for pid in gold.get("required_provision_ids") or []:
            e = ev.get(pid)
            if e and e.get("law_number") and str(e.get("article") or "").isdigit():
                refs.append({"doc": e["law_number"], "article": int(e["article"]),
                             "clause": int(e["clause"]) if str(e.get("clause") or "").isdigit() else None,
                             "v04_id": pid})
        question = "\n\n".join(str(v) for v in (q.get("scenario"), q["question"]) if v)
        out.append({
            "id": c["id"], "base_case_id": c["id"], "source_set": "v04", "template": "fixed", "rule_id": None,
            "contract_path": rel(V04 / "contracts" / f"{cid}.docx") if cid else None,
            "contract_type": contracts[cid]["contract_type"] if cid else None,
            "question": question, "gold_clause_ids": clause_ids, "gold_clause_text": inp.get("clause_text") or "",
            "gold_label": V04_LABEL.get(gold.get("expected_verdict"), "n/a"), "gold_red_flags": [],
            "gold_legal_refs": refs, "gold_key_facts": [gold.get("expected_answer") or ""],
            "as_of_date": q.get("as_of_date"), "transaction_date": q.get("transaction_date"),
            "difficulty": c["difficulty"]["level"], "phrasing_type": c["task"],
            "v04_required_provision_ids": gold.get("required_provision_ids") or [],
        })
    return out


# ---------- chia dev/test ----------
def make_split(cases: list[dict]) -> dict:
    """Chia theo base_case_id (3 câu template của một ca luôn cùng phía), phân tầng theo nguồn + luật + nhãn."""
    strata: dict[tuple, set] = defaultdict(set)
    label_of = {}
    for c in cases:
        if c.get("template") in ("T1", "fixed"):
            label_of[c["base_case_id"]] = c["gold_label"]
    for c in cases:
        strata[(c["source_set"], c["rule_id"] or "-", label_of.get(c["base_case_id"], "-"))].add(c["base_case_id"])
    rng = random.Random(SEED)
    dev, test = [], []
    for key in sorted(strata, key=str):
        ids = sorted(strata[key])
        rng.shuffle(ids)
        n_dev = int(len(ids) * (1 - TEST_FRAC))  # làm tròn xuống -> test >= 75%
        dev += ids[:n_dev]
        test += ids[n_dev:]
    return {"seed": SEED, "unit": "base_case_id", "stratify": ["source_set", "rule_id", "gold_label"],
            "dev": sorted(dev), "test": sorted(test)}


def main() -> None:
    cases = injection_cases(INJ, "injection") + injection_cases(INJ2, "injection_v2") + contract_qa_cases() + v04_cases()
    map_refs(cases)
    keys = ["id", "source_set", "base_case_id", "template", "rule_id", "contract_path", "contract_type", "question",
            "gold_clause_ids", "gold_clause_text", "gold_label", "gold_red_flags", "gold_legal_refs", "unmapped_refs",
            "gold_key_facts", "as_of_date", "transaction_date", "difficulty", "phrasing_type"]
    cases = [{k: c.get(k) for k in keys} | {k: v for k, v in c.items() if k not in keys} for c in cases]
    jl_write(CASES, cases)
    jl_write(INPUTS, [{k: c[k] for k in INPUT_FIELDS} for c in cases])
    jl_write(GOLD, [{k: v for k, v in c.items() if k not in ("question", "contract_type")} for c in cases])
    split = make_split(cases)
    SPLIT.write_text(json.dumps(split, ensure_ascii=False, indent=1), encoding="utf-8")
    n_unmapped = sum(bool(c["unmapped_refs"]) for c in cases)
    print(f"cases={len(cases)} dev_units={len(split['dev'])} test_units={len(split['test'])} cases_with_unmapped_refs={n_unmapped}")


if __name__ == "__main__":
    main()

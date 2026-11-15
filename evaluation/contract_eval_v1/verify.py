"""contract_eval_v1: tự kiểm nhãn V1–V7 (thay người duyệt), quarantine, rồi đóng băng.

    python -m evaluation.contract_eval_v1.verify            # cần Postgres; V7 gọi Gemini (cache ở v7_cache/)
    python -m evaluation.contract_eval_v1.verify --check-frozen

V7 dùng model khác model sinh của hệ thống: hệ thống chạy Groq gpt-oss-120b (LLM_PROVIDER=groq) nên kiểm chéo bằng Gemini.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from evaluation.contract_eval_v1.build import (CASES, HERE, INPUT_FIELDS, INPUTS, REVIEW_CSV, ROOT, V04,
                                                jl_read, jl_write)
from evaluation.gold.kappa import cohen_kappa

VERIF = HERE / "verification.jsonl"
QUAR = HERE / "quarantine.jsonl"
REPORT = HERE / "VERIFICATION_REPORT.md"
FROZEN = HERE / "FROZEN.json"
V7_CACHE = HERE / "v7_cache"
RULES = ["ot_unpaid", "no_bhxh", "retain_id_papers", "training_cost_flat",
         "fine_deduct_wage", "forfeit_wage_quit", "terminate_pregnancy", "ban_lawsuit"]
REQUIRED = {"id": str, "source_set": str, "contract_path": (str, type(None)), "contract_type": (str, type(None)),
            "question": str, "gold_clause_ids": list, "gold_clause_text": str, "gold_label": str,
            "gold_red_flags": list, "gold_legal_refs": list, "gold_key_facts": list,
            "as_of_date": (str, type(None)), "transaction_date": (str, type(None)),
            "difficulty": str, "phrasing_type": str}
FUZZ_MIN, DUP_MAX, V7_BATCH = 0.8, 0.95, 8


# ---------- tiện ích ----------
def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").lower()
    s = re.sub(r"[\"“”'‘’«»*_#]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def coverage(seg: str, text: str) -> float:
    """Tỷ lệ ký tự của seg khớp theo thứ tự trong text (fuzzy 'chứa')."""
    a, b = norm(seg), norm(text)
    if not a:
        return 1.0
    if a in b:
        return 1.0
    blocks = SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks()
    return sum(x.size for x in blocks if x.size >= 3) / len(a)


def contract_text(path: str) -> str:
    p = ROOT / path
    if p.suffix.lower() == ".docx":
        from app.document.parser import parse_document
        return parse_document(str(p), ".docx")
    return p.read_text(encoding="utf-8")


def parser_clauses(text: str) -> dict[str, str]:
    from app.agents.clause_parser import _extract_clauses
    out: dict[str, str] = {}
    for c in _extract_clauses(unicodedata.normalize("NFC", text)):
        out.setdefault(str(c.clause_number), c.summary)
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def article_texts(lqueries: list[str]) -> dict[str, str]:
    from app.infrastructure.db.connection import get_db
    out = {}
    with get_db() as conn, conn.cursor() as cur:
        for q in sorted(set(lqueries)):
            cur.execute("SELECT chunk_text FROM legal_embeddings WHERE path ~ %s::lquery ORDER BY path", (q,))
            out[q] = "\n".join(r[0] for r in cur.fetchall())
    return out


def article_lquery(ref: dict) -> str:
    return f"{ref['doc_id']}.*.D{ref['article']}.*"


# ---------- Gemini (kiểm chéo / judge) ----------
class Gemini:
    """Gemini nhiệt độ 0, xoay key khi hết quota ngày / key không có quyền model. Hết key -> QuotaStop."""

    class QuotaStop(RuntimeError):
        pass

    FALLBACK = ["gemini-3-flash-preview"]  # quota Gemini miễn phí tính theo model: hết model chính thì sang model sau

    def __init__(self, min_interval: float = 7.0):
        from app.core.settings import get_settings
        s = get_settings()
        self.chain = [s.gemini_model] + [m for m in self.FALLBACK if m != s.gemini_model]
        self.model_name, self.keys, self.i, self.min_interval, self.last = self.chain[0], list(s.gemini_api_keys), 0, min_interval, 0.0
        self.models_used: set[str] = set()
        self.calls, self.tokens = 0, 0
        self._m = None

    def _model(self):
        from langchain_google_genai import ChatGoogleGenerativeAI
        if self._m is None:
            self._m = ChatGoogleGenerativeAI(model=self.model_name, google_api_key=self.keys[self.i], temperature=0,
                                             max_retries=0, timeout=180, response_mime_type="application/json")
        return self._m

    def json(self, prompt: str):
        from app.agents.llm_client import _is_daily_quota, _is_model_unavailable
        for attempt in range(10):
            if self.i >= len(self.keys):
                nxt = self.chain.index(self.model_name) + 1
                if nxt >= len(self.chain):
                    raise Gemini.QuotaStop("hết toàn bộ Gemini key/model")
                self.model_name, self.i, self._m = self.chain[nxt], 0, None
            wait = self.min_interval - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                r = self._model().invoke(prompt)
                self.calls += 1
                self.models_used.add(self.model_name)
                self.tokens += (getattr(r, "usage_metadata", None) or {}).get("total_tokens", 0)
                text = r.content if isinstance(r.content, str) else "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in r.content)
                return json.loads(re.sub(r"^```(json)?|```$", "", text.strip()).strip())
            except json.JSONDecodeError:
                continue
            except Exception as exc:  # noqa: BLE001
                if _is_daily_quota(exc) or _is_model_unavailable(exc):
                    self.i, self._m = self.i + 1, None
                    continue
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc) or "503" in str(exc):
                    time.sleep(60)
                    continue
                raise
        raise RuntimeError("Gemini không trả JSON hợp lệ sau 10 lần")


V7_PROMPT = """Bạn là luật sư lao động Việt Nam. Với MỖI mục dưới đây, chỉ dựa vào điều khoản hợp đồng và trích văn bản luật đi kèm, kết luận điều khoản:
- "vi_pham": trái quy định pháp luật được trích,
- "hop_le": không trái quy định được trích,
- "khong_xac_dinh": không đủ căn cứ để kết luận.
Nêu số Điều luật làm căn cứ chính. Trả về JSON đúng dạng: {{"items": [{{"id": "...", "verdict": "vi_pham|hop_le|khong_xac_dinh", "article": "Điều ..."}}]}}

{items}"""


def v7_units(cases: list[dict], csv_rows: dict[str, dict], law: dict[str, str], clauses_by_path: dict) -> list[dict]:
    v04 = {c["id"]: c for c in json.loads((V04 / "MIXED_34_TEST_CASES_V04.json").read_text(encoding="utf-8"))["test_cases"]}
    units = []
    for c in cases:
        if c["template"] not in ("T1", "fixed") or c["gold_label"] not in ("violation", "compliant"):
            continue
        clause = c["gold_clause_text"]
        if not clause and c["gold_clause_ids"] and c["contract_path"]:
            clause = clauses_by_path.get(c["contract_path"], {}).get(c["gold_clause_ids"][0], "")
        if c["base_case_id"] in csv_rows:
            excerpt = csv_rows[c["base_case_id"]]["Trích văn bản luật đã đối chiếu"]
        elif c["source_set"] == "v04":
            ev = v04[c["id"]]["gold"].get("evidence") or []
            excerpt = "\n".join(f"{e['law_title']} Điều {e['article']}: {e['verbatim_excerpt']}" for e in ev
                                if e.get("evidence_role") == "required")
        else:
            excerpt = "\n".join(law.get(article_lquery(r), "")[:1500] for r in c["gold_legal_refs"])
        if clause and excerpt:
            units.append({"id": c["base_case_id"], "clause": clause, "law": excerpt, "label": c["gold_label"]})
    return units


def run_v7(units: list[dict], run: int, llm: Gemini) -> dict[str, dict]:
    V7_CACHE.mkdir(exist_ok=True)
    f = V7_CACHE / f"run{run}.json"
    done = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    todo = [u for u in units if u["id"] not in done]
    for i in range(0, len(todo), V7_BATCH):
        batch = todo[i:i + V7_BATCH]
        items = "\n\n".join(f"### id: {u['id']}\nĐIỀU KHOẢN HỢP ĐỒNG:\n{u['clause']}\nTRÍCH VĂN BẢN LUẬT:\n{u['law']}"
                            for u in batch)
        out = llm.json(V7_PROMPT.format(items=items))
        for it in (out.get("items") if isinstance(out, dict) else out) or []:
            if isinstance(it, dict) and it.get("id") in {u["id"] for u in batch}:
                done[it["id"]] = {"verdict": it.get("verdict"), "article": it.get("article"), "model": llm.model_name}
        f.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"V7 run{run}: {len(done)}/{len(units)}", flush=True)
    return done


V7_MAP = {"vi_pham": "violation", "hop_le": "compliant"}


# ---------- kiểm ----------
def leak_tokens(c: dict) -> list[str]:
    toks = list(RULES) + ["violation", "compliant"]
    toks += sorted({r["doc"] for r in c["gold_legal_refs"]})
    contract_ids = set(c["gold_clause_ids"])
    for r in c["gold_legal_refs"]:
        if str(r["article"]) not in contract_ids:
            toks.append(f"Điều {r['article']}")
    return toks


def fix_leak(q: str, toks: list[str]) -> str:
    for t in toks:
        q = re.sub(rf"{re.escape(t)}(?!\d)", "điều luật liên quan", q)
    return q


def main(args) -> None:
    if args.check_frozen:
        check_frozen()
        print("FROZEN ok")
        return
    if FROZEN.exists() and not args.force:
        raise SystemExit("Đã đóng băng (FROZEN.json). Không chạy lại verify; dùng --check-frozen.")
    cases = jl_read(CASES)
    csv_rows = {r["Mã ca"]: r for r in csv.DictReader(REVIEW_CSV.open(encoding="utf-8-sig"))}
    res = {c["id"]: {"id": c["id"], "checks": {}, "flags": [], "reasons": []} for c in cases}

    def mark(cid, layer, ok, reason=None, quarantine=False, flag=None):
        r = res[cid]
        r["checks"][layer] = "pass" if ok else "fail"
        if reason:
            r["reasons"].append(f"{layer}: {reason}")
        if flag:
            r["flags"].append(flag)
        if quarantine:
            r["flags"].append("quarantine")
            r.setdefault("quarantine_layers", []).append(layer)

    # V1 schema
    seen = set()
    for c in cases:
        bad = [k for k, t in REQUIRED.items() if not isinstance(c.get(k), t)]
        if c["gold_label"] not in ("violation", "compliant", "n/a"):
            bad.append("gold_label")
        if c["id"] in seen:
            bad.append("duplicate id")
        seen.add(c["id"])
        mark(c["id"], "V1", not bad, ", ".join(bad) or None, quarantine=bool(bad))

    # V2 tồn tại
    texts = {p: contract_text(p) for p in sorted({c["contract_path"] for c in cases if c["contract_path"]})}
    clauses_by_path = {p: parser_clauses(t) for p, t in texts.items()}
    for c in cases:
        if not c["contract_path"]:
            mark(c["id"], "V2", True, "không có hợp đồng (câu hỏi pháp luật thuần)")
            continue
        text, parsed = texts[c["contract_path"]], clauses_by_path[c["contract_path"]]
        probs, flag = [], None
        if c["gold_clause_text"] and coverage(c["gold_clause_text"], text) < 0.98:
            probs.append("gold_clause_text không có trong hợp đồng")
        for cid in c["gold_clause_ids"]:
            if cid not in parsed:
                heading = re.search(rf"^\W*(Điều|Khoản|Mục)\s+{re.escape(cid)}\b", text, re.M)
                if not heading:
                    probs.append(f"Điều/Khoản {cid} không có trong hợp đồng")
                else:
                    flag = "parser_mismatch"  # nhãn đúng, clause_parser không tách ra: lỗi hệ thống (tầng a), không quarantine
        mark(c["id"], "V2", not probs, "; ".join(probs) or flag, quarantine=bool(probs), flag=flag)

    # V3 căn cứ luật
    law = article_texts([article_lquery(r) for c in cases for r in c["gold_legal_refs"]])
    v04 = {c["id"]: c for c in json.loads((V04 / "MIXED_34_TEST_CASES_V04.json").read_text(encoding="utf-8"))["test_cases"]}
    ref_stats = {"refs": 0, "refs_mismatch": 0, "quotes_checked": 0}
    for c in cases:
        refs = c["gold_legal_refs"]
        if not refs:
            mark(c["id"], "V3", True, "không có ref đã map" + (" (unmapped_refs)" if c["unmapped_refs"] else ""))
            continue
        quotes: dict[int, list[str]] = {}
        if c["base_case_id"] in csv_rows:
            src = csv_rows[c["base_case_id"]]["Trích văn bản luật đã đối chiếu"]
            for art, q in re.findall(r"Điều\s+(\d+)[^\"]{0,40}?\"([^\"]+)\"", src):
                quotes.setdefault(int(art), []).append(q)
        elif c["source_set"] == "v04":
            for e in v04[c["id"]]["gold"].get("evidence") or []:
                if str(e.get("article") or "").isdigit():
                    quotes.setdefault(int(e["article"]), []).append(e["verbatim_excerpt"])
        fails, ratios = [], []
        for r in refs:
            text = law.get(article_lquery(r), "")
            segs = [s for q in quotes.get(r["article"], []) for s in re.split(r"\.\.\.|…", q) if len(s.strip()) >= 15]
            rr = [coverage(s, text) for s in segs]
            ratios += rr
            ref_stats["refs"] += 1
            if not text or (rr and min(rr) < FUZZ_MIN):
                fails.append(f"Điều {r['article']}" + (f" (ratio {min(rr):.2f})" if rr else " (không có văn bản)"))
        ref_stats["quotes_checked"] += len(ratios)
        ref_stats["refs_mismatch"] += len(fails)
        mark(c["id"], "V3", not fails, "; ".join(fails) or None,
             quarantine=bool(fails) and len(fails) == len(refs), flag="ref_mismatch" if fails else None)

    # V4 nhất quán
    for c in cases:
        probs, flag, quar = [], None, False
        taxonomy = c["source_set"] in ("injection", "injection_v2", "contract_qa")
        if taxonomy and c["template"] != "T2":
            if c["gold_label"] == "violation" and not c["gold_red_flags"]:
                probs.append("violation nhưng gold_red_flags rỗng")
            if c["gold_label"] == "compliant" and c["gold_red_flags"]:
                probs.append("compliant nhưng có gold_red_flags")
        row = csv_rows.get(c["base_case_id"])
        if row:
            csv_label = {"Vi phạm": "violation", "Hợp lệ": "compliant"}.get(row["Nhãn"])
            base_label = "violation" if c["base_case_id"] in {x["base_case_id"] for x in cases
                                                              if x["gold_red_flags"]} else "compliant"
            if csv_label and csv_label != base_label:
                probs.append(f"nhãn CSV {row['Nhãn']} khác nhãn cấu tạo")
            verdict = row["Kết luận kiểm tra"]
            if "XEM" in verdict:
                probs.append(f"REVIEW CSV: {verdict}")
                quar = True
            elif "LƯU Ý" in verdict:
                flag = "low_confidence"
        mark(c["id"], "V4", not probs, "; ".join(probs) or ("REVIEW CSV: có lưu ý" if flag else None),
             quarantine=quar or any("nhãn" in p or "gold_red_flags" in p for p in probs), flag=flag)

    # V5 rò rỉ: sửa câu hỏi tự động, ghi lại
    fixed = []
    for c in cases:
        toks = [t for t in leak_tokens(c) if re.search(rf"{re.escape(t)}(?!\d)", c["question"])]
        if toks:
            c["question"] = fix_leak(c["question"], toks)
            fixed.append((c["id"], toks))
        mark(c["id"], "V5", not toks, f"đã sửa câu hỏi, bỏ {toks}" if toks else None)
    if fixed:
        jl_write(CASES, cases)
        jl_write(INPUTS, [{k: c[k] for k in INPUT_FIELDS} for c in cases])
    extra = [k for r in jl_read(INPUTS) for k in r if k not in INPUT_FIELDS]
    extra += [f"{r['id']}: {t}" for r in jl_read(INPUTS) for t in RULES + ["violation", "compliant"]
              if t in json.dumps(r, ensure_ascii=False)]
    if extra:
        raise SystemExit(f"inputs_no_gold.jsonl rò rỉ / trường thừa: {extra[:10]}")

    # V6 trùng lặp (mức ca gốc, theo nội dung điều khoản + câu hỏi)
    units: dict[str, str] = {}
    for c in cases:
        if c["template"] in ("T1", "fixed"):
            units[c["base_case_id"]] = (c["gold_clause_text"] or "") + "\n" + (c["question"] if c["template"] == "fixed" else "")
    ids = sorted(units)
    dup_of = {}
    for i, a in enumerate(ids):
        if a in dup_of:
            continue
        for b in ids[i + 1:]:
            if b in dup_of:
                continue
            sm = SequenceMatcher(None, units[a], units[b], autojunk=False)
            if sm.real_quick_ratio() > DUP_MAX and sm.quick_ratio() > DUP_MAX and sm.ratio() > DUP_MAX:
                dup_of[b] = a
    for c in cases:
        d = dup_of.get(c["base_case_id"])
        mark(c["id"], "V6", d is None, f"gần trùng {d} (ratio > {DUP_MAX})" if d else None, quarantine=d is not None)

    # V7 LLM kiểm chéo
    units7 = v7_units(cases, csv_rows, law, clauses_by_path)
    llm = Gemini()
    stop = "bỏ qua V7 (--no-llm)" if args.no_llm else None
    runs = {}
    try:
        for k in ((1, 2) if not args.no_llm else ()):
            runs[k] = run_v7(units7, k, llm)
    except Gemini.QuotaStop as e:
        stop = str(e)
    v7 = {}
    for u in units7:
        vs = [runs.get(k, {}).get(u["id"], {}).get("verdict") for k in (1, 2)]
        opp = "compliant" if u["label"] == "violation" else "violation"
        contra = sum(V7_MAP.get(v) == opp for v in vs)
        unclear = sum(v not in V7_MAP for v in vs)
        v7[u["id"]] = {"label": u["label"], "llm": vs, "contradict": contra, "unclear": unclear}
    for c in cases:
        v = v7.get(c["base_case_id"])
        if v is None:
            mark(c["id"], "V7", True, "không áp dụng (không có nhãn violation/compliant hoặc thiếu điều khoản/luật)")
            res[c["id"]]["checks"]["V7"] = "n/a"
            continue
        if None in v["llm"]:
            mark(c["id"], "V7", True, "chưa chạy đủ 2 lần (hết quota)")
            res[c["id"]]["checks"]["V7"] = "incomplete"
            continue
        mark(c["id"], "V7", v["contradict"] == 0 and v["unclear"] == 0,
             f"LLM {v['llm']} vs nhãn {v['label']}" if v["contradict"] or v["unclear"] else None,
             quarantine=v["contradict"] == 2, flag="low_confidence" if v["contradict"] == 1 or (v["unclear"] and v["contradict"] < 2) else None)

    rows = [res[c["id"]] | {"flags": sorted(set(res[c["id"]]["flags"]))} for c in cases]
    jl_write(VERIF, rows)
    quar_rows = [{"id": r["id"], "layers": r.get("quarantine_layers", []), "reasons": r["reasons"]}
                 for r in rows if "quarantine" in r["flags"]]
    jl_write(QUAR, quar_rows)
    stats = write_report(cases, rows, v7, units7, ref_stats, fixed, dup_of, llm, stop)
    if stop:
        (HERE / "RESUME.md").write_text(f"# Chạy tiếp\n\nV7 dừng: {stop}. Khi quota hồi:\n\n"
                                        "    python -m evaluation.contract_eval_v1.verify\n", encoding="utf-8")
        print("V7 chưa xong (hết quota) -> chưa đóng băng. Xem RESUME.md")
        return
    freeze(stats)
    print(json.dumps(stats, ensure_ascii=False))


def write_report(cases, rows, v7, units7, ref_stats, fixed, dup_of, llm, stop) -> dict:
    layers = ["V1", "V2", "V3", "V4", "V5", "V6", "V7"]
    count = {L: {s: sum(r["checks"].get(L) == s for r in rows) for s in ("pass", "fail", "n/a", "incomplete")} for L in layers}
    quar = [r for r in rows if "quarantine" in r["flags"]]
    low = [r for r in rows if "low_confidence" in r["flags"] and "quarantine" not in r["flags"]]
    stats = {"n_cases": len(cases), "n_base_units": len({c["base_case_id"] for c in cases}),
             "n_quarantine": len(quar), "n_low_confidence": len(low),
             "n_parser_mismatch": sum("parser_mismatch" in r["flags"] for r in rows),
             "n_ref_mismatch_cases": sum("ref_mismatch" in r["flags"] for r in rows),
             "n_unmapped_ref_cases": sum(bool(c["unmapped_refs"]) for c in cases),
             "layers": count, "ref_stats": ref_stats, "v5_fixed": len(fixed), "v6_duplicates": len(dup_of),
             "v7": {"units": len(units7), "gemini_calls": llm.calls, "gemini_tokens": llm.tokens, "model": llm.model_name}}
    complete = [v for v in v7.values() if None not in v["llm"]]
    for k in (0, 1):
        a = [v["label"] for v in complete]
        b = [V7_MAP.get(v["llm"][k], "unclear") for v in complete]
        stats["v7"][f"run{k + 1}_kappa"] = round(cohen_kappa(a, b), 4) if complete else None
        stats["v7"][f"run{k + 1}_agreement"] = round(sum(x == y for x, y in zip(a, b)) / len(a), 4) if complete else None
    stats["v7"]["both_runs_agree_with_label"] = sum(v["contradict"] == 0 and v["unclear"] == 0 for v in complete)
    stats["v7"]["one_run_contradicts"] = sum(v["contradict"] == 1 for v in complete)
    stats["v7"]["both_runs_contradict"] = sum(v["contradict"] == 2 for v in complete)
    stats["v7"]["any_unclear"] = sum(v["unclear"] > 0 for v in complete)
    stats["v7"]["run1_run2_agreement"] = round(sum(v["llm"][0] == v["llm"][1] for v in complete) / len(complete), 4) if complete else None
    stats["v7"]["complete_units"] = len(complete)
    for k in (1, 2):
        f = V7_CACHE / f"run{k}.json"
        cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        stats["v7"][f"run{k}_models"] = sorted({x.get("model", "?") for x in cache.values()})
    reasons: dict[str, int] = {}
    for r in quar:
        for key in r.get("quarantine_layers", []):
            reasons[key] = reasons.get(key, 0) + 1
    stats["quarantine_by_layer"] = reasons
    base_quar = sorted({next(c["base_case_id"] for c in cases if c["id"] == r["id"]) for r in quar})
    stats["quarantine_base_units"] = base_quar
    s7 = stats["v7"]
    lines = [
        "# Báo cáo tự kiểm nhãn contract_eval_v1", "",
        f"- Số ca: **{stats['n_cases']}** (từ {stats['n_base_units']} ca gốc). Quarantine: **{stats['n_quarantine']}** ca "
        f"({len(base_quar)} ca gốc). Gắn cờ `low_confidence` (giữ lại): {stats['n_low_confidence']} ca.",
        f"- Ca có ref không map được vào kho (loại khỏi chấm truy xuất điều luật, vẫn dùng cho Generation): {stats['n_unmapped_ref_cases']}.",
        f"- Ca mà clause_parser không tách được Điều/Khoản gold (nhãn đúng, lỗi hệ thống tầng a, không quarantine): {stats['n_parser_mismatch']}.",
        "", "## Kết quả theo lớp", "", "| Lớp | Pass | Fail | Không áp dụng | Chưa đủ |", "|---|---:|---:|---:|---:|",
        *[f"| {L} | {count[L]['pass']} | {count[L]['fail']} | {count[L]['n/a']} | {count[L]['incomplete']} |" for L in layers],
        "", f"- V3: {ref_stats['refs']} lượt ref kiểm, {ref_stats['quotes_checked']} đoạn trích so với DB (ngưỡng fuzzy {FUZZ_MIN}), "
        f"{ref_stats['refs_mismatch']} ref lệch.",
        f"- V5: {len(fixed)} câu hỏi đã sửa vì chứa thông tin gold.",
        f"- V6: {len(dup_of)} ca gốc gần trùng (ratio > {DUP_MAX}) bị loại: " + ", ".join(f"{b}≈{a}" for b, a in sorted(dup_of.items())),
        "", "## V7: LLM kiểm chéo độc lập", "",
        f"- Model kiểm chéo: Gemini — lần 1 {s7['run1_models']}, lần 2 {s7['run2_models']} (hệ thống sinh bằng Groq `gpt-oss-120b`); nhiệt độ 0, không thấy nhãn; "
        f"{V7_BATCH} ca mỗi lượt gọi. Số lượt gọi: {s7['gemini_calls']}, token: {s7['gemini_tokens']}.",
        f"- Đơn vị kiểm: {s7['units']} ca gốc có nhãn violation/compliant (đủ 2 lần: {s7['complete_units']}).",
        f"- Cohen's kappa nhãn cấu tạo vs LLM: lần 1 **{s7['run1_kappa']}** (đồng thuận {s7['run1_agreement']}), "
        f"lần 2 **{s7['run2_kappa']}** (đồng thuận {s7['run2_agreement']}). Hai lần LLM trùng nhau: {s7['run1_run2_agreement']}.",
        f"- Cả 2 lần khớp nhãn: {s7['both_runs_agree_with_label']}; 1 lần trái nhãn (low_confidence): {s7['one_run_contradicts']}; "
        f"2 lần trái nhãn (quarantine): {s7['both_runs_contradict']}; có lần 'không xác định': {s7['any_unclear']}.",
        "- Kappa tính với 'không xác định' là một nhãn riêng (bị tính là bất đồng).",
        "", "## Quarantine", "", f"Theo lớp gây quarantine (đếm theo ca, một ca có thể nhiều lớp): {json.dumps(reasons, ensure_ascii=False)}", "",
        "| Ca | Lý do |", "|---|---|",
        *[f"| {r['id']} | {'; '.join(x for x in r['reasons'])} |" for r in quar],
    ]
    if stop:
        lines += ["", f"**V7 chưa xong: {stop}.** Chưa đóng băng."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "verification_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    return stats


FROZEN_FILES = ["cases.jsonl", "gold.jsonl", "inputs_no_gold.jsonl", "split.json", "quarantine.jsonl", "verification.jsonl"]


def freeze(stats: dict) -> None:
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    data = {"files": {f: sha(HERE / f) for f in FROZEN_FILES}, "commit_at_freeze": commit,
            "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "n_cases": stats["n_cases"], "n_quarantine": stats["n_quarantine"]}
    FROZEN.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def check_frozen() -> dict:
    if not FROZEN.exists():
        raise SystemExit("Chưa đóng băng: chạy verify trước.")
    data = json.loads(FROZEN.read_text(encoding="utf-8"))
    bad = [f for f, h in data["files"].items() if sha(HERE / f) != h]
    if bad:
        raise SystemExit(f"Hash đóng băng không khớp: {bad}")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-frozen", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="thử V1–V6, không gọi LLM, không đóng băng")
    ap.add_argument("--force", action="store_true", help="chạy lại dù đã đóng băng (chỉ khi FROZEN sai)")
    main(ap.parse_args())
    sys.exit(0)

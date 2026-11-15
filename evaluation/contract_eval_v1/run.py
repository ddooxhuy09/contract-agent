"""contract_eval_v1 runner: gọi code thật của hệ thống, lưu toàn bộ đầu ra thô, có cache/resume, dừng sạch khi hết quota.

    python -m evaluation.contract_eval_v1.run index                     # nạp hợp đồng vào DB (user eval riêng)
    python -m evaluation.contract_eval_v1.run retrieval [--label vector] # Giai đoạn A, không gọi LLM
    LEGAL_RETRIEVAL_MODE=hybrid python -m evaluation.contract_eval_v1.run retrieval --label hybrid
    python -m evaluation.contract_eval_v1.run generation [--limit N]     # Giai đoạn B (LLM hệ thống)
    python -m evaluation.contract_eval_v1.run judge                      # judge Gemini (model khác model sinh)

Host cần DATABASE_URL=postgresql://contractlens:contractlens@127.0.0.1:5433/contractlens.
Thư mục chạy: evaluation_results/runs/contract_eval_v1_<YYYYMMDD>/ (--run-dir để chạy tiếp thư mục cũ).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import time
import unicodedata
import uuid
from pathlib import Path

from evaluation.contract_eval_v1.build import CASES, ROOT, SPLIT, jl_read
from evaluation.contract_eval_v1.verify import QUAR, Gemini, check_frozen, contract_text

RUNS = ROOT / "evaluation_results" / "runs"
EVAL_EMAIL = "contract-eval-v1@example.invalid"


# ---------- chung ----------
def run_dir(arg: str | None) -> Path:
    if arg:
        d = Path(arg)
    else:
        old = sorted(RUNS.glob("contract_eval_v1_*"))
        d = old[-1] if old else RUNS / f"contract_eval_v1_{time.strftime('%Y%m%d')}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def git_state() -> dict:
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"commit": g("rev-parse", "HEAD"), "dirty_app": bool(g("status", "--porcelain", "app"))}


def load_eval_cases() -> tuple[list[dict], dict[str, str]]:
    """Ca không bị quarantine, thứ tự: test trước, dev sau (dừng giữa chừng vẫn có số test)."""
    check_frozen()
    quar = {r["id"] for r in jl_read(QUAR)}
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    side = {u: "test" for u in split["test"]} | {u: "dev" for u in split["dev"]}
    cases = [c for c in jl_read(CASES) if c["id"] not in quar]
    cases.sort(key=lambda c: (side[c["base_case_id"]] != "test", c["base_case_id"], c["id"]))
    return cases, side


def done_ids(path: Path) -> set[str]:
    return {json.loads(x)["id"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()} if path.exists() else set()


def append(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def meta_path(c) -> dict:
    m = c.metadata or {}
    return {"path": m.get("path"), "score": m.get("score"), "role": m.get("role"), "doc_number": m.get("doc_number"),
            "clause_number": m.get("clause_number")}


def bind():
    from app.infrastructure.container import build_container
    from app.infrastructure.retrieval.context import bind_retrieval
    cont = build_container()
    bind_retrieval(cont.contract_search, cont.legal_search, legal_chunks=cont.legal_chunks, contract_chunks=cont.contract_chunks)
    return cont


def contract_map(rd: Path) -> dict[str, str]:
    f = rd / "contract_map.json"
    if not f.exists():
        raise SystemExit("Chưa index: chạy `run index` trước.")
    return json.loads(f.read_text(encoding="utf-8"))


# ---------- index ----------
async def cmd_index(args) -> None:
    from app.application.use_cases.contracts import UploadContract
    from app.document.chunker import chunk_by_clause
    from app.domain.entities.contract import Contract, ContractChunk

    rd = run_dir(args.run_dir)
    cases, _ = load_eval_cases()
    cont = bind()
    user = cont.users.get_by_email(EVAL_EMAIL) or cont.users.create(EVAL_EMAIL, "disabled-evaluation-account")
    f = rd / "contract_map.json"
    cmap = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    paths = sorted({c["contract_path"] for c in cases if c["contract_path"]} - set(cmap))
    uploader = UploadContract(cont.contracts, cont.contract_chunks, cont.storage, cont.embedder)
    for p in paths:
        src = ROOT / p
        if src.suffix.lower() == ".docx":  # đường upload thật
            up = await uploader.execute(src.read_bytes(), src.name, user.id)
            cid = up["contract_id"]
        else:  # .txt/.md: UploadContract chỉ nhận docx/pdf/ảnh; dùng đúng chunker + embedder + repository như upload
            text = unicodedata.normalize("NFC", src.read_text(encoding="utf-8"))
            cid = str(uuid.uuid4())
            docs = chunk_by_clause(text, cid)
            vecs = cont.embedder.embed_documents([d.page_content for d in docs])
            cont.contracts.upsert(Contract(contract_id=cid, user_id=user.id, filename=src.name, file_type=src.suffix,
                                           storage_key=f"eval-inline/{src.name}", full_text=text, status="parsed",
                                           message="contract_eval_v1", chunk_count=len(docs)))
            cont.contract_chunks.replace_for_contract(cid, [
                ContractChunk(contract_id=cid, chunk_index=int(d.metadata.get("chunk_index", i + 1)),
                              clause_number=str(d.metadata.get("clause_number", i + 1)), content=d.page_content,
                              embedding=vecs[i]) for i, d in enumerate(docs)])
        cmap[p] = cid
        f.write_text(json.dumps(cmap, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"indexed {p} -> {cid}", flush=True)
    print(f"contracts indexed: {len(cmap)} (user {EVAL_EMAIL})")


# ---------- Giai đoạn A ----------
def parsed_clauses(path: str) -> list[dict]:
    from app.agents.clause_parser import _extract_clauses
    text = unicodedata.normalize("NFC", contract_text(path))
    return [{"clause_number": str(c.clause_number), "title": c.title, "summary": c.summary} for c in _extract_clauses(text)]


def cmd_retrieval(args) -> None:
    from app.core.settings import get_settings
    from app.infrastructure.retrieval.context import get_graph_rag
    from app.infrastructure.retrieval.query_rewrite import augment_qa_retrieval_query
    from app.vectorstore.retriever import retrieve_contract, retrieve_legal

    rd = run_dir(args.run_dir)
    cases, side = load_eval_cases()
    cmap = contract_map(rd)
    bind()
    rag = get_graph_rag()
    mode = get_settings().legal_retrieval_mode
    if mode != args.label:
        raise SystemExit(f"LEGAL_RETRIEVAL_MODE={mode} khác --label {args.label}")
    out = rd / f"retrieval_{args.label}.jsonl"
    have = done_ids(out)
    clauses = {}
    clause_rag_cache: dict[str, list] = {}
    for c in cases:
        if c["id"] in have:
            continue
        row = {"id": c["id"], "split": side[c["base_case_id"]], "label": args.label, "legal_retrieval_mode": mode}
        t0 = time.perf_counter()
        if c["contract_path"]:
            if c["contract_path"] not in clauses:
                clauses[c["contract_path"]] = parsed_clauses(c["contract_path"])
            row["parsed_clauses"] = [x["clause_number"] for x in clauses[c["contract_path"]]]
            docs = retrieve_contract(c["question"], cmap[c["contract_path"]], k=10)
            row["contract_hits"] = [meta_path(d) for d in docs]
        legal_query = augment_qa_retrieval_query(c["question"], [])
        hits = retrieve_legal(legal_query, k=5, title=legal_query, as_of_date=c["as_of_date"])  # đúng tham số QA
        row["qa_legal_hits"] = [meta_path(d) for d in hits]
        row["qa_legal_query"] = legal_query
        # Đường phân tích (GraphRAG theo điều khoản): theo Điều gold do parser tách, như evaluate_clause
        if c["contract_path"] and c["gold_clause_ids"]:
            key = f"{c['contract_path']}#{c['gold_clause_ids'][0]}#{c['as_of_date']}"
            if key not in clause_rag_cache:
                cl = next((x for x in clauses[c["contract_path"]] if x["clause_number"] == c["gold_clause_ids"][0]), None)
                clause_rag_cache[key] = [] if cl is None else [
                    {"path": h.metadata.get("path"), "score": h.score, "role": h.metadata.get("role")}
                    for h in rag.retrieve_for_clause(cl["title"], cl["summary"], contract_type=c["contract_type"],
                                                     k_seed=4, max_total=10, as_of_date=c["as_of_date"])]
            row["clause_legal_hits"] = clause_rag_cache[key]
        row["retrieval_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        append(out, row)
        print(f"A {c['id']} {row['retrieval_ms']:.0f}ms", flush=True)
    (rd / f"retrieval_{args.label}.meta.json").write_text(json.dumps(
        {"git": git_state(), "frozen": check_frozen(), "mode": mode, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"retrieval rows: {len(done_ids(out))}")


# ---------- Giai đoạn B ----------
class LlmTap:
    """Bọc get_chat_model để ghi token/latency/lỗi của mọi lượt gọi LLM hệ thống (không đổi hành vi)."""

    def __init__(self):
        import app.agents.llm_client as llm
        import app.agents.qa_agent as qa
        self.events: list[dict] = []
        original = llm.get_chat_model
        tap = self

        class Proxy:
            def __init__(self, m):
                self.m = m

            def __getattr__(self, n):
                return getattr(self.m, n)

            def _rec(self, t0, r=None, e=None):
                tap.events.append({"ms": round((time.perf_counter() - t0) * 1000, 1),
                                   "usage": getattr(r, "usage_metadata", None) if r is not None else None,
                                   "error": str(e)[:600] if e else None})

            def invoke(self, *a, **k):
                t0 = time.perf_counter()
                try:
                    r = self.m.invoke(*a, **k)
                    self._rec(t0, r)
                    return r
                except Exception as e:
                    self._rec(t0, e=e)
                    raise

            async def ainvoke(self, *a, **k):
                t0 = time.perf_counter()
                try:
                    r = await self.m.ainvoke(*a, **k)
                    self._rec(t0, r)
                    return r
                except Exception as e:
                    self._rec(t0, e=e)
                    raise

        def get_model(*a, **k):
            return Proxy(original(*a, **k))

        llm.get_chat_model = get_model
        qa.get_chat_model = get_model

    def take(self) -> list[dict]:
        ev, self.events = self.events, []
        return ev


def quota_kind(events: list[dict]) -> str | None:
    blob = " ".join(e["error"] or "" for e in events)
    if not blob:
        return None
    if re.search(r"per\s*day|\(TPD\)|\(RPD\)|daily|spend alert|blocked API access", blob, re.I):
        return "day"
    if re.search(r"\b429\b|rate.?limit|RESOURCE_EXHAUSTED|\(TPM\)|\(RPM\)", blob, re.I):
        return "minute"
    return None


def usage_sum(events: list[dict]) -> dict:
    tok = sum((e["usage"] or {}).get("total_tokens", 0) for e in events)
    return {"llm_calls": len(events), "llm_errors": sum(bool(e["error"]) for e in events), "tokens": tok,
            "llm_ms": round(sum(e["ms"] for e in events), 1)}


def setup_qa():
    """QA graph thật, nhưng checkpointer trong bộ nhớ và tắt bộ nhớ dài hạn: mỗi câu là một hội thoại mới độc lập."""
    import app.agents.qa_agent as qa
    from langgraph.checkpoint.memory import MemorySaver
    cap: dict = {}
    orig_c, orig_l = qa.retrieve_contract, qa.retrieve_legal

    def rc(*a, **k):
        cap["contract"] = orig_c(*a, **k)
        return cap["contract"]

    def rl(*a, **k):
        cap["legal"] = orig_l(*a, **k)
        return cap["legal"]

    async def no_load(*a, **k):
        return ""

    async def no_save(*a, **k):
        return None

    qa.retrieve_contract, qa.retrieve_legal = rc, rl
    qa.load_qa_memory, qa.save_qa_memory = no_load, no_save
    qa._compiled_graph = qa._graph_builder.compile(checkpointer=MemorySaver())
    return qa, cap


def setup_judge_capture():
    import app.agents.risk_flagger as rf
    cap: dict = {}
    orig = rf._retrieve_legal

    def wrapped(*a, **k):
        docs, ctx = orig(*a, **k)
        cap["docs"], cap["ctx"] = docs, ctx
        return docs, ctx

    rf._retrieve_legal = wrapped
    return rf, cap


def citations(risk) -> list[dict]:
    return [{"doc_number": x.doc_number, "article": x.article, "clause": x.clause, "title": x.title,
             "evidence_path": x.evidence_path} for x in (risk.legal_citations or [])]


async def detect_one(c, cid, clause, rf, cap, provider):
    from app.schemas.contract import Clause
    cap.clear()
    risk = rf.evaluate_clause(Clause(clause_number=clause["clause_number"], title=clause["title"], summary=clause["summary"]),
                              provider, contract_id=cid, contract_type=c["contract_type"], as_of_date=c["as_of_date"])
    ctx_docs = cap.get("docs") or []
    return {"severity": getattr(risk, "severity", None), "issue": getattr(risk, "issue", None),
            "title": getattr(risk, "title", None), "legal_basis": getattr(risk, "legal_basis", None),
            "reasons": getattr(risk, "reasons", None), "finding_type": getattr(risk, "finding_type", None),
            "citations": citations(risk) if risk else [], "context_paths": [d.metadata.get("path") for d in ctx_docs],
            "context": cap.get("ctx", "")}


async def qa_one(c, cid, qa, cap, provider):
    cap.clear()
    thread = f"ce1-{c['id']}-{uuid.uuid4().hex[:8]}"
    res = await qa._compiled_graph.ainvoke(qa._qa_input(c["question"], cid or "none", provider, c["as_of_date"]),
                                           config={"recursion_limit": 40, "configurable": {"thread_id": thread}})
    legal = cap.get("legal") or []
    contract = cap.get("contract") or []
    return {"answer": res["messages"][-1].content, "source_clauses": res.get("source_clauses", []),
            "needs_clarification": res.get("needs_clarification", False),
            "context_legal_paths": [d.metadata.get("path") for d in legal],
            "context_contract_clauses": [d.metadata.get("clause_number") for d in contract],
            "context_legal": qa._format_legal_context(legal)[:6000],
            "context_contract": qa._format_contract_context(contract)[:4000]}


def other_test_lock(rd: Path) -> Path | None:
    for d in RUNS.glob("contract_eval_v1_*"):
        if d.resolve() != rd.resolve() and (d / "test.lock").exists():
            return d / "test.lock"
    return None


async def cmd_generation(args) -> None:
    from app.agents.llm_client import DEFAULT_PROVIDER, _use_groq
    from app.core.settings import get_settings
    import app.agents.qa_agent as qa_mod

    rd = run_dir(args.run_dir)
    lock = other_test_lock(rd)
    if lock:
        raise SystemExit(f"Test đã chạy một lần ở {lock}; không chạy lại test (dùng --run-dir thư mục đó để resume).")
    cases, side = load_eval_cases()
    cmap = contract_map(rd)
    bind()
    tap = LlmTap()
    qa, qcap = setup_qa()
    rf, jcap = setup_judge_capture()
    s = get_settings()
    model = f"groq/{s.groq_model}" if _use_groq() else f"gemini/{s.gemini_model}"
    out = rd / "generation.jsonl"
    have = done_ids(out)
    clauses: dict[str, list] = {}
    saved = 0
    for c in cases:
        if args.limit and saved >= args.limit:
            break
        units = []
        det_id = f"{c['base_case_id']}#detect"
        if (c["template"] in ("T1", "fixed") and c["gold_label"] in ("violation", "compliant") and c["contract_path"]
                and c["gold_clause_ids"] and det_id not in have):
            units.append(("detect", det_id))
        if c["id"] not in have:
            units.append(("qa", c["id"]))
        for kind, uid in units:
            for attempt in range(3):
                t0 = time.perf_counter()
                tap.take()
                row = {"id": uid, "case_id": c["id"], "base_case_id": c["base_case_id"], "kind": kind,
                       "split": side[c["base_case_id"]], "model": model, "git": git_state()["commit"]}
                try:
                    cid = cmap.get(c["contract_path"]) if c["contract_path"] else None
                    if kind == "detect":
                        if c["contract_path"] not in clauses:
                            clauses[c["contract_path"]] = parsed_clauses(c["contract_path"])
                        cl = next((x for x in clauses[c["contract_path"]] if x["clause_number"] == c["gold_clause_ids"][0]), None)
                        row["parsed_clause_found"] = cl is not None
                        row.update(await detect_one(c, cid, cl, rf, jcap, DEFAULT_PROVIDER) if cl else {"severity": None})
                    else:
                        row.update(await qa_one(c, cid, qa, qcap, DEFAULT_PROVIDER))
                    row["status"] = "completed"
                except Exception as e:  # noqa: BLE001
                    row["status"], row["error"] = "failed", f"{type(e).__name__}: {str(e)[:600]}"
                ev = tap.take()
                row.update(usage_sum(ev))
                row["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                q = quota_kind(ev) if (row["status"] == "failed" or row.get("answer") == qa_mod._GENERATION_FAILED_ANSWER
                                       or row["llm_errors"]) else None
                if q == "day":
                    err = next((e["error"] for e in ev if e["error"]), "")[:300]
                    write_resume(rd, f"LLM hệ thống ({model}) không phục vụ được (hết quota/bị chặn) tại {uid}: {err}")
                    print(f"STOP: quota ngày tại {uid}. Xem {rd / 'RESUME.md'}")
                    return
                if q == "minute" and attempt < 2:
                    print(f"{uid}: rate limit phút, chờ 65s rồi thử lại", flush=True)
                    time.sleep(65)
                    continue
                append(out, row)
                have.add(uid)
                saved += 1
                print(f"B {uid} {row['status']} sev={row.get('severity')} tok={row['tokens']} {row['total_ms']:.0f}ms", flush=True)
                break
    test_units = {u for c in cases if side[c["base_case_id"]] == "test" for u in [c["id"]]}
    if test_units <= have and not (rd / "test.lock").exists():
        (rd / "test.lock").write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "git": git_state(),
                                                  "frozen": check_frozen()}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("test.lock written")
    (rd / "RESUME.md").unlink(missing_ok=True)
    print(f"generation rows: {len(have)}")


def write_resume(rd: Path, why: str) -> None:
    (rd / "RESUME.md").write_text(
        f"# Chạy tiếp contract_eval_v1\n\nDừng: {why} ({time.strftime('%Y-%m-%d %H:%M')}).\n\n"
        "Khi quota hồi, chạy lại (ca đã lưu được bỏ qua):\n\n"
        f"    python -m evaluation.contract_eval_v1.run generation --run-dir {rd.relative_to(ROOT).as_posix()}\n"
        f"    python -m evaluation.contract_eval_v1.run judge --run-dir {rd.relative_to(ROOT).as_posix()}\n"
        f"    python -m evaluation.contract_eval_v1.score --run-dir {rd.relative_to(ROOT).as_posix()}\n",
        encoding="utf-8")


# ---------- judge (Gemini) ----------
JUDGE_PROMPT = """Bạn là giám khảo chấm câu trả lời của một hệ thống rà soát hợp đồng lao động/thương mại Việt Nam.
Với MỖI mục: (1) tách câu trả lời thành các mệnh đề khẳng định về sự kiện/pháp luật; chấm mỗi mệnh đề supported=1 nếu NGỮ CẢNH ĐÃ TRUY XUẤT (luật + hợp đồng) hỗ trợ trực tiếp, ngược lại 0; (2) chấm correctness theo đáp án tham chiếu: 2 = kết luận khớp và có đủ các ý bắt buộc, 1 = kết luận khớp nhưng thiếu ý, 0 = kết luận sai hoặc không trả lời; (3) ghi kết luận của câu trả lời: "violation" (có trái luật/rủi ro), "compliant" (hợp lệ), "unclear".
Trả JSON: {{"items": [{{"id": "...", "claims": [{{"text": "...", "supported": 0}}], "correctness": 0, "answer_conclusion": "violation|compliant|unclear"}}]}}

{items}"""

LABEL_VI = {"violation": "có điều khoản trái luật/rủi ro", "compliant": "hợp lệ, không trái luật", "n/a": "(không hỏi kết luận)"}


JUDGE_MODEL = "qwen/qwen3.8-27b"  # khác họ model sinh (gpt-oss-120b); Gemini miễn phí không đủ quota cho ~130 lượt


class GroqJudge:
    """Judge nhiệt độ 0, JSON mode, cùng giao diện .json() với verify.Gemini."""

    QuotaStop = Gemini.QuotaStop

    def __init__(self, model: str = JUDGE_MODEL):
        from app.core.settings import get_settings
        from groq import Groq
        self.client, self.model_name, self.calls, self.tokens = Groq(api_key=get_settings().groq_api_key), model, 0, 0

    def json(self, prompt: str):
        for attempt in range(5):
            try:
                r = self.client.chat.completions.create(model=self.model_name, temperature=0, reasoning_format="hidden",
                                                        response_format={"type": "json_object"},
                                                        messages=[{"role": "user", "content": prompt}])
                self.calls += 1
                self.tokens += r.usage.total_tokens
                return json.loads(r.choices[0].message.content)
            except json.JSONDecodeError:
                continue
            except Exception as exc:  # noqa: BLE001
                if re.search(r"per\s*day|spend alert|blocked API access", str(exc), re.I):
                    raise GroqJudge.QuotaStop(str(exc)[:200])
                if "429" in str(exc) or "503" in str(exc) or "500" in str(exc):
                    time.sleep(30)
                    continue
                raise
        raise RuntimeError("judge không trả JSON hợp lệ sau 5 lần")


def judge_item(uid, question, answer, ctx, label, facts) -> str:
    return (f"### id: {uid}\nCÂU HỎI: {question}\nNGỮ CẢNH ĐÃ TRUY XUẤT:\n{ctx[:7000]}\nCÂU TRẢ LỜI CỦA HỆ THỐNG:\n{answer[:3000]}\n"
            f"ĐÁP ÁN THAM CHIẾU: kết luận = {LABEL_VI[label]}; ý bắt buộc = {facts}")


def cmd_judge(args) -> None:
    rd = run_dir(args.run_dir)
    cases = {c["id"]: c for c in jl_read(CASES)}
    gen = [json.loads(x) for x in (rd / "generation.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    gen = [g for g in gen if g["kind"] == "qa" and g["status"] == "completed"]
    gen.sort(key=lambda g: g["split"] != "test")
    out = rd / "judge.jsonl"
    have = done_ids(out)
    llm = GroqJudge()
    items = []
    for g in gen:
        if g["id"] in have:
            continue
        c = cases[g["case_id"]]
        ctx = f"[LUẬT]\n{g.get('context_legal', '')}\n[HỢP ĐỒNG]\n{g.get('context_contract', '')}"
        items.append((g["id"], judge_item(g["id"], c["question"], g["answer"], ctx, c["gold_label"], c["gold_key_facts"])))
    # hiệu chuẩn: 20 ca nhãn chắc chắn (V7 2 lần khớp, không low_confidence), câu trả lời tham chiếu đúng/sai biết trước
    cal = calibration_items(cases, rd)
    items += [(u, t) for u, t, _ in cal if u not in have]
    try:
        for i in range(0, len(items), 3):
            batch = items[i:i + 3]
            resp = llm.json(JUDGE_PROMPT.format(items="\n\n".join(t for _, t in batch)))
            got = {it.get("id"): it for it in ((resp.get("items") if isinstance(resp, dict) else resp) or []) if isinstance(it, dict)}
            for uid, _ in batch:
                if uid in got:
                    append(out, {"id": uid, **{k: got[uid].get(k) for k in ("claims", "correctness", "answer_conclusion")},
                                 "judge_model": f"groq/{llm.model_name}"})
            print(f"judge {min(i + 3, len(items))}/{len(items)}", flush=True)
    except GroqJudge.QuotaStop as e:
        write_resume(rd, f"judge: {e}")
        print("STOP judge: hết quota")
    (rd / "calibration_key.json").write_text(json.dumps({u: exp for u, _, exp in cal}, ensure_ascii=False, indent=1), encoding="utf-8")


def calibration_items(cases: dict, rd: Path) -> list[tuple[str, str, int]]:
    from evaluation.contract_eval_v1.verify import VERIF
    import random
    ver = {r["id"]: r for r in jl_read(VERIF)}
    sure = sorted(c["id"] for c in cases.values() if c["template"] == "T1" and c["gold_label"] in ("violation", "compliant")
                  and not ({"low_confidence", "quarantine", "ref_mismatch"} & set(ver[c["id"]]["flags"]))
                  and ver[c["id"]]["checks"].get("V7") == "pass")
    pick = random.Random(42).sample(sure, min(20, len(sure)))
    out = []
    for i, cid in enumerate(pick):
        c = cases[cid]
        n = c["gold_clause_ids"][0]
        arts = ", ".join(f"Điều {r['article']}" for r in c["gold_legal_refs"])
        right = i % 2 == 0
        concl = c["gold_label"] if right else ("compliant" if c["gold_label"] == "violation" else "violation")
        ans = (f"Điều {n} của hợp đồng {'trái quy định pháp luật lao động' if concl == 'violation' else 'không trái quy định pháp luật lao động'}"
               f", căn cứ {arts} Bộ luật Lao động 2019.")
        ctx = f"[HỢP ĐỒNG]\n{c['gold_clause_text']}"
        out.append((f"CAL-{cid}", judge_item(f"CAL-{cid}", c["question"], ans, ctx, c["gold_label"], c["gold_key_facts"]),
                    2 if right else 0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["index", "retrieval", "generation", "judge"])
    ap.add_argument("--run-dir")
    ap.add_argument("--label", default="vector", choices=["vector", "hybrid"])
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.cmd == "index":
        asyncio.run(cmd_index(args))
    elif args.cmd == "retrieval":
        cmd_retrieval(args)
    elif args.cmd == "generation":
        asyncio.run(cmd_generation(args))
    else:
        cmd_judge(args)


if __name__ == "__main__":
    main()

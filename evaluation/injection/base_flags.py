"""Run the full pipeline once on the clean base contract and dump every flag (no injected clause).

  LLM_PROVIDER=groq python -m evaluation.injection.base_flags
"""
from __future__ import annotations

import asyncio
import json

from evaluation.injection.run import BASE, OUT, _commit, _llm_name


def main() -> None:
    from app.agents.workflow import run_analysis_workflow
    from app.infrastructure.container import build_container
    from app.infrastructure.retrieval.context import bind_retrieval

    cont = build_container()
    bind_retrieval(cont.contract_search, cont.legal_search, cont.graph,
                   legal_chunks=cont.legal_chunks, contract_chunks=cont.contract_chunks)
    analysis, risks = asyncio.run(run_analysis_workflow(BASE.read_text(encoding="utf-8"), "inj-BASE"))
    out = {"llm": _llm_name(), "commit": _commit(), "coverage": analysis.coverage,
           "risks": [r.model_dump(mode="json") for r in risks]}
    (OUT / "base_contract_flags.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(risks)} risk item(s):", [(r.clause_ref, r.severity) for r in risks])


if __name__ == "__main__":
    main()

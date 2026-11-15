"""contract_eval_v1: schema, rò rỉ gold, hash đóng băng, và hàm chấm trên ví dụ nhỏ (không cần DB/LLM)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evaluation.contract_eval_v1.build import INPUT_FIELDS, TEMPLATES, parse_legal_basis
from evaluation.contract_eval_v1.score import (bootstrap, cited_key, dedupe, hits_at, law_citations_in_text, path_key, prf,
                                               rank_metrics)
from evaluation.contract_eval_v1.verify import REQUIRED, RULES, coverage, fix_leak, leak_tokens

HERE = Path(__file__).resolve().parents[2] / "evaluation" / "contract_eval_v1"


def _jl(name):
    return [json.loads(x) for x in (HERE / name).read_text(encoding="utf-8").splitlines() if x.strip()]


@pytest.fixture(scope="module")
def cases():
    if not (HERE / "cases.jsonl").exists():
        pytest.skip("chưa build")
    return _jl("cases.jsonl")


def test_schema_and_unique_ids(cases):
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        for k, t in REQUIRED.items():
            assert isinstance(c[k], t), (c["id"], k)
        assert c["gold_label"] in ("violation", "compliant", "n/a")
        if c["source_set"].startswith("injection") and c["template"] != "T2":
            assert (c["gold_label"] == "violation") == bool(c["gold_red_flags"]), c["id"]


def test_inputs_have_no_gold(cases):
    inputs = _jl("inputs_no_gold.jsonl")
    assert [r["id"] for r in inputs] == [c["id"] for c in cases]
    by_id = {c["id"]: c for c in cases}
    for r in inputs:
        assert set(r) == set(INPUT_FIELDS)
        blob = json.dumps(r, ensure_ascii=False)
        assert not any(rule in blob for rule in RULES)
        assert "violation" not in blob and "compliant" not in blob
        q = r["question"]
        for t in leak_tokens(by_id[r["id"]]):
            assert not re.search(re.escape(t) + r"(?!\d)", q), (r["id"], t)


def test_frozen_hashes_match():
    if not (HERE / "FROZEN.json").exists():
        pytest.skip("chưa đóng băng")
    from evaluation.contract_eval_v1.verify import check_frozen
    check_frozen()


def test_split_disjoint_and_test_majority():
    if not (HERE / "split.json").exists():
        pytest.skip("chưa build")
    s = json.loads((HERE / "split.json").read_text(encoding="utf-8"))
    assert not set(s["dev"]) & set(s["test"])
    assert len(s["test"]) / (len(s["dev"]) + len(s["test"])) >= 0.7


def test_parse_legal_basis():
    refs = parse_legal_basis("BLLĐ 2019 Điều 168 khoản 1 (NSDLĐ ...); khoản 3 (NLĐ không thuộc đối tượng)")
    assert refs == [{"doc": "45/2019/QH14", "article": 168, "clause": 1}, {"doc": "45/2019/QH14", "article": 168, "clause": 3}]
    refs = parse_legal_basis("BLLĐ 2019 Điều 62 khoản 1, 3 (đào tạo); Điều 40 khoản 3 (hoàn trả)")
    assert [(r["article"], r["clause"]) for r in refs] == [(62, 1), (62, 3), (40, 3)]
    assert parse_legal_basis("BLLĐ 2019 Điều 179 (tranh chấp)") == [{"doc": "45/2019/QH14", "article": 179, "clause": None}]


def test_templates_do_not_leak():
    for tpl in TEMPLATES.values():
        assert not any(r in tpl for r in RULES)


def test_fix_leak_and_coverage():
    assert fix_leak("Theo Điều 98 thì sao?", ["Điều 98"]) == "Theo điều luật liên quan thì sao?"
    assert fix_leak("Điều 980", ["Điều 98"]) == "Điều 980"
    assert coverage("làm thêm  giờ", "NLĐ làm thêm giờ ngày thường") == 1.0
    assert coverage("abc xyz", "") < 0.5


def test_path_key_and_rank_metrics():
    assert path_key("139264.C6.D98.K1.b") == ("139264", 98)
    assert path_key("139264.C6.D98.K1.b", "clause") == ("139264", 98, 1)
    assert path_key("152668.PREAMBLE") is None
    ranked = dedupe([path_key(p) for p in ["1.D5.K1", "1.D5.K2", "1.D7", "2.D9"]])
    assert ranked == [("1", 5), ("1", 7), ("2", 9)]
    m = rank_metrics(ranked, {("1", 7), ("3", 1)})
    assert m["recall@1"] == 0 and m["recall@3"] == 0.5 and m["mrr"] == 0.5 and m["hit@5"] == 1.0
    assert m["precision@5"] == pytest.approx(0.2)
    assert hits_at(["3", "2"], {"2"}) == {"hit@1": 0.0, "hit@3": 1.0, "hit@5": 1.0}


def test_prf_and_bootstrap():
    assert prf(2, 1, 1)["f1"] == pytest.approx(2 / 3)
    assert prf(0, 0, 0)["precision"] is None
    ci = bootstrap([1, 1, 0, 0], lambda s: sum(s) / len(s), n=200)
    assert 0 <= ci[0] <= 0.5 <= ci[1] <= 1


def test_law_citations_in_text():
    ans = "Điều 2 của hợp đồng trái Điều 98 Bộ luật Lao động 2019 và Điều 107."
    assert law_citations_in_text(ans, {"1", "2", "3"}) == [98, 107]


def test_cited_key():
    num2id = {"45/2019/QH14": "139264"}
    assert cited_key({"evidence_path": "139264.C12.D168.K1", "article": "Điều 168"}, num2id) == ("139264", 168)
    assert cited_key({"doc_number": "45/2019/QH14", "article": "Điều 98"}, num2id) == ("139264", 98)
    assert cited_key({"article": "Điều 98"}, num2id) is None

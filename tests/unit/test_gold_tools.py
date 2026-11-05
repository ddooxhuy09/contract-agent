import pytest

from evaluation.gold.kappa import cohen_kappa, compute, render
from evaluation.gold.make_split import split_contracts


def test_kappa_perfect_agreement_and_chance_level():
    assert cohen_kappa(["1", "0", "1", "0"], ["1", "0", "1", "0"]) == 1.0
    # Agree on half the items with balanced labels = chance level.
    assert cohen_kappa(["1", "1", "0", "0"], ["1", "0", "1", "0"]) == pytest.approx(0.0)


def test_kappa_known_value():
    # 2x2 table [[20, 5], [10, 15]] -> observed .70, expected .50, kappa .40
    a = ["1"] * 25 + ["0"] * 25
    b = ["1"] * 20 + ["0"] * 5 + ["1"] * 10 + ["0"] * 15
    assert cohen_kappa(a, b) == pytest.approx(0.4)


def test_compute_ignores_unlabeled_rows_and_lists_disagreements():
    rows = [
        {"unit_id": "U1", "ann1_co_rui_ro": "1", "ann2_co_rui_ro": "1", "ann1_luat_dau_ra": "no_bhxh", "ann2_luat_dau_ra": "no_bhxh"},
        {"unit_id": "U2", "ann1_co_rui_ro": "0", "ann2_co_rui_ro": "1", "ann1_luat_dau_ra": "", "ann2_luat_dau_ra": "khac"},
        {"unit_id": "U3", "ann1_co_rui_ro": "0", "ann2_co_rui_ro": "0", "ann1_luat_dau_ra": "", "ann2_luat_dau_ra": ""},
        {"unit_id": "U4", "ann1_co_rui_ro": "1", "ann2_co_rui_ro": "", "ann1_luat_dau_ra": "", "ann2_luat_dau_ra": ""},
    ]
    res = compute(rows)
    assert res["units_total"] == 4 and res["units_labeled_by_both"] == 3
    assert res["disagreements"] == ["U2"]
    assert "U2" in render(res)


def test_compute_with_no_labels_gives_none():
    res = compute([{"unit_id": "U1", "ann1_co_rui_ro": "", "ann2_co_rui_ro": ""}])
    assert res["kappa_co_rui_ro"] is None and "n/a" in render(res)


def test_split_is_by_contract_deterministic_and_disjoint():
    ids = [f"HDLD{i:02d}" for i in range(1, 7)] * 5  # 5 units per contract
    a, b = split_contracts(ids, 2, 1), split_contracts(ids, 2, 1)
    assert a == b
    assert len(a["dev"]) == 2 and len(a["test"]) == 4
    assert not set(a["dev"]) & set(a["test"])
    assert sorted(a["dev"] + a["test"]) == sorted(set(ids))


def test_split_rejects_degenerate_sizes():
    with pytest.raises(ValueError):
        split_contracts(["A", "B"], 2, 1)


# --- evaluation/run_eval.py pure helpers ---------------------------------------------------

from evaluation.run_eval import bootstrap_ci, confusion, evaluate, gold_label, positive_dieu, scores


def test_gold_label_prefers_expert_then_consensus():
    assert gold_label({"expert_final": "1:no_bhxh", "ann1_co_rui_ro": "0", "ann2_co_rui_ro": "0"}) == 1
    assert gold_label({"expert_final": "", "ann1_co_rui_ro": "1", "ann2_co_rui_ro": "1"}) == 1
    assert gold_label({"expert_final": "", "ann1_co_rui_ro": "1", "ann2_co_rui_ro": "0"}) is None
    assert gold_label({"ann1_co_rui_ro": "", "ann2_co_rui_ro": ""}) is None


def test_positive_dieu_only_counts_actionable_risks():
    risks = [
        {"clause_ref": "Điều 5", "severity": "critical"},
        {"clause_ref": "Điều 7", "severity": "ok"},
        {"clause_ref": "Điều 12", "severity": "warning"},
        {"clause_ref": "Phần mở đầu", "severity": "warning"},
    ]
    assert positive_dieu(risks) == {"5", "12"}


def test_scores_and_confusion():
    c = confusion([1, 1, 0, 0, 1], [1, 0, 1, 0, 1])
    assert c == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}
    s = scores(c)
    assert s["precision"] == pytest.approx(2 / 3) and s["recall"] == pytest.approx(2 / 3)
    assert s["f1"] == pytest.approx(2 / 3) and s["false_rate"] == pytest.approx(1 / 3)
    assert scores({"tp": 0, "fp": 0, "fn": 0, "tn": 3})["precision"] is None


def test_bootstrap_ci_is_deterministic_and_brackets_the_point_estimate():
    y = [1] * 10 + [0] * 10
    p = [1] * 8 + [0] * 2 + [1] * 3 + [0] * 7
    a, b = bootstrap_ci(y, p, 300, seed=1), bootstrap_ci(y, p, 300, seed=1)
    assert a == b
    point = scores(confusion(y, p))["f1"]
    assert a["f1"]["low"] <= point <= a["f1"]["high"]


def test_evaluate_excludes_unresolved_and_reports_coverage():
    units = [
        {"unit_id": "A_D01", "contract_id": "A", "dieu": "1", "expert_final": "", "ann1_co_rui_ro": "1", "ann2_co_rui_ro": "1"},
        {"unit_id": "A_D02", "contract_id": "A", "dieu": "2", "expert_final": "", "ann1_co_rui_ro": "0", "ann2_co_rui_ro": "0"},
        {"unit_id": "A_D03", "contract_id": "A", "dieu": "3", "expert_final": "", "ann1_co_rui_ro": "1", "ann2_co_rui_ro": "0"},
    ]
    preds = {"A": {"risks": [{"clause_ref": "Điều 1", "severity": "critical"}], "coverage": {"da_kiem": 2, "tong_so_dieu": 3}}}
    res = evaluate(units, preds, iterations=50)
    assert res["n_unresolved"] == 1
    assert res["confusion"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 1}
    assert res["coverage"] == {"da_kiem": 2, "tong_so_dieu": 3}


from evaluation.gold.draw_citations import collect, sample, summarize


def test_citation_sampling_and_summary():
    result = {"units": [{"unit_id": "A_D01", "risks": [
        {"clause_ref": "Điều 1", "issue": "x", "legal_citations": [
            {"doc_number": "45/2019/QH14", "article": "21"}, {"doc_number": "45/2019/QH14", "article": "98"}]},
        {"clause_ref": "Điều 1", "issue": "y", "legal_citations": None},
    ]}]}
    rows = collect(result)
    assert len(rows) == 2 and rows[0]["unit_id"] == "A_D01"
    picked = sample(rows, 50, 1)
    assert [p["citation_id"] for p in picked] == ["C001", "C002"] or len(picked) == 2
    picked[0].update(ann1_ton_tai="1", ann2_ton_tai="1", ann1_ho_tro="0", ann2_ho_tro="1")
    s = summarize(picked)
    assert s["n"] == 2 and s["ann1_ton_tai"] == {"n": 1, "rate": 1.0}
    assert s["agreed_ton_tai"]["rate"] == 1.0 and s["agreed_ho_tro"]["n"] == 0

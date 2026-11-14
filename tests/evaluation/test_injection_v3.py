from evaluation.injection_v3 import run as v3


def test_cases_balanced_and_buildable():
    cases = v3.load_cases()
    assert len(cases) == 48
    for c in cases:
        text = v3.build_contract(v3.base_text(c["base"]), c)
        n = v3.slot_of(c)
        first_line = c["body"].replace("{n}", str(n)).splitlines()[0]
        assert first_line in text  # body landed in the slot
        assert text.count(f"\nĐiều {n}. ") == 1  # heading kept once
    for b in v3.SLOTS:
        assert sum(c["base"] == b for c in cases) == 16


def test_score_counts_slot_and_other_flags():
    cases = [{"case_id": "x", "label": "violation", "rule_id": "no_bhxh", "kind": "V-a"},
             {"case_id": "y", "label": "compliant", "rule_id": "no_bhxh", "kind": "C-a"}]
    pred = {"x": {"slot_flagged": True, "slot_unchecked": False, "other_clause_flags": ["2"]},
            "y": {"slot_flagged": True, "slot_unchecked": False, "other_clause_flags": []}}
    s = v3.score(cases, pred, n_boot=10)
    assert (s["micro"]["tp"], s["micro"]["fp"], s["micro"]["fn"]) == (1, 1, 0)
    assert s["other_flags_mean"] == 0.5

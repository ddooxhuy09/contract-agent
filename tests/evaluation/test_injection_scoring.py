from evaluation.injection.run import (
    RULES, build_contract, load_cases, prf, sample_ids, score_clause_level, score_rule_level, BASE,
)


def _case(cid, rule, label):
    return {"case_id": cid, "rule_id": rule, "label": label, "slot": 2}


def test_prf_handles_empty_denominators():
    assert prf(0, 0, 0)["precision"] is None and prf(0, 0, 0)["recall"] is None
    assert prf(2, 2, 2)["precision"] == 0.5 and prf(2, 0, 2)["recall"] == 0.5


def test_rule_level_counts_cross_rule_firing_as_false_positive():
    cases = [_case("a", "ot_unpaid", "violation"), _case("b", "ot_unpaid", "compliant"), _case("c", "no_bhxh", "violation")]
    fired = {"a": {"ot_unpaid", "no_bhxh"}, "b": {"ot_unpaid"}, "c": set()}
    s = score_rule_level(cases, fired, n_boot=5)
    ot, bh = s["per_rule"]["ot_unpaid"], s["per_rule"]["no_bhxh"]
    assert (ot["tp"], ot["fp"], ot["fn"]) == (1, 1, 0)      # b is a near-miss that fired its own rule
    assert ot["near_miss_false_positive"] == 1 and ot["near_miss_n"] == 1
    assert (bh["tp"], bh["fp"], bh["fn"]) == (0, 1, 1)      # fired on a (other rule's violation), missed c
    assert s["micro"]["tp"] == 1 and s["micro"]["fp"] == 2 and s["micro"]["fn"] == 1


def test_clause_level_unchecked_is_negative_and_counted():
    cases = [_case("a", "ot_unpaid", "violation"), _case("b", "ot_unpaid", "compliant")]
    pred = {"a": {"slot_flagged": False, "slot_unchecked": True}, "b": {"slot_flagged": False, "slot_unchecked": False}}
    m = score_clause_level(cases, pred, n_boot=5)["micro"]
    assert (m["tp"], m["fn"], m["tn"], m["unchecked"]) == (0, 1, 1, 1)


def test_frozen_cases_are_complete_and_buildable():
    cases = load_cases()
    base = BASE.read_text(encoding="utf-8")
    assert len(cases) == 80 and len({c["case_id"] for c in cases}) == 80
    for r in RULES:
        mine = [c for c in cases if c["rule_id"] == r]
        assert sum(c["label"] == "violation" for c in mine) == 5 and sum(c["label"] == "compliant" for c in mine) == 5
    c = cases[0]
    built = build_contract(base, c)
    assert c["clause_text"].splitlines()[1] in built
    assert built.count("\nĐiều ") + built.startswith("Điều ") == 11  # exactly one Điều replaced, still 11 headings


def test_sample_is_deterministic_balanced_and_interleaved():
    cases = load_cases()
    s = sample_ids(cases)
    assert s == sample_ids(cases) and len(s) == len(set(s)) == 48
    by = {c["case_id"]: c for c in cases}
    assert sum(by[i]["label"] == "violation" for i in s) == 24
    first_round = s[:16]  # one violation + one compliant per rule before any rule repeats
    assert {by[i]["rule_id"] for i in first_round} == set(RULES)

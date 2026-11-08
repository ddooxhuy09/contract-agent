"""Coverage counts every unchecked clause, even when clause numbers repeat."""

from app.agents.workflow import _with_coverage
from app.schemas.contract import Clause, ContractAnalysis


def test_repeated_clause_number_counts_each_unchecked_clause():
    clauses = [Clause(clause_number="1", summary="a"), Clause(clause_number="1", summary="b"),
               Clause(clause_number="2", summary="c")]
    analysis = ContractAnalysis(contract_id="c1", clauses=clauses)
    unchecked = [{"clause_ref": "Điều 1", "status": "unchecked_error"},
                 {"clause_ref": "Điều 1", "status": "unparsable"}]
    coverage = _with_coverage(analysis, unchecked).coverage
    assert (coverage["tong_so_dieu"], coverage["da_kiem"], coverage["chua_kiem"]) == (3, 1, 2)
    assert coverage["chua_kiem_chi_tiet"] == unchecked

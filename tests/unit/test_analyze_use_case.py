"""AnalyzeContract: failed or partial analyses must not be saved as, or served as, final."""

import asyncio
from types import SimpleNamespace

import pytest

from app.application.use_cases.contracts import AnalyzeContract, _is_complete
from app.domain.errors import AnalysisFailedError
from app.schemas.contract import Clause, ContractAnalysis

_FULL = {"clauses": [{"clause_number": "1"}], "coverage": {"chua_kiem": 0}}
_PARTIAL = {"clauses": [{"clause_number": "1"}], "coverage": {"chua_kiem": 1}}


class FakeContracts:
    def __init__(self, contract):
        self.contract = contract
        self.saved = []

    def get_owned(self, contract_id, user_id):
        return self.contract

    def save_analysis(self, contract_id, analysis, risks):
        self.saved.append((contract_id, analysis, risks))


class FakePipeline:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.runs = result, error, 0

    async def run(self, text, contract_id, provider):
        self.runs += 1
        if self.error:
            raise self.error
        return self.result


def _use_case(contracts, pipeline):
    return AnalyzeContract(contracts, SimpleNamespace(list_contents=lambda cid: []), pipeline)


def _contract(analysis):
    return SimpleNamespace(analysis=analysis, risks=[], full_text="HỢP ĐỒNG LAO ĐỘNG")


def _analysis(chua_kiem=0):
    return ContractAnalysis(
        contract_id="c1",
        clauses=[Clause(clause_number="1", title="T", summary="S")],
        coverage={"chua_kiem": chua_kiem},
    )


@pytest.mark.parametrize(
    "analysis, expected",
    [(None, False), ({}, False), ({"clauses": []}, False), (_PARTIAL, False), (_FULL, True), ({"clauses": [{}]}, True)],
)
def test_is_complete(analysis, expected):
    assert _is_complete(analysis) is expected


def test_complete_analysis_is_served_from_cache():
    pipeline = FakePipeline()
    result = asyncio.run(_use_case(FakeContracts(_contract(_FULL)), pipeline).execute("c1", "u1"))
    assert result["analysis"] == _FULL
    assert pipeline.runs == 0


def test_partial_analysis_is_rerun_not_served():
    contracts = FakeContracts(_contract(_PARTIAL))
    pipeline = FakePipeline(result=(_analysis(0), []))
    asyncio.run(_use_case(contracts, pipeline).execute("c1", "u1"))
    assert pipeline.runs == 1
    assert contracts.saved[0][1]["coverage"]["chua_kiem"] == 0


def test_failed_analysis_is_not_saved():
    contracts = FakeContracts(_contract(None))
    pipeline = FakePipeline(error=AnalysisFailedError("no clauses"))
    with pytest.raises(AnalysisFailedError):
        asyncio.run(_use_case(contracts, pipeline).execute("c1", "u1"))
    assert contracts.saved == []

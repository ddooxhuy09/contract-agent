"""A per-day quota stop must not be recorded as a case failure (it would block --resume)."""

import app.agents.llm_client as llm
from evaluation.run_benchmark import quota_exhausted

_PER_DAY = {
    "type": "ResourceExhausted",
    "message": "429 RESOURCE_EXHAUSTED ... Generate content requests per day limit exceeded "
               "on Free Tier. Please retry in 4h46m51s.",
}


def _keys(monkeypatch, count, index):
    class _S:
        gemini_api_keys = [f"k{i}" for i in range(count)]

    monkeypatch.setattr(llm, "get_settings", lambda: _S())
    monkeypatch.setattr(llm, "_key_index", index)


def test_stops_when_last_key_is_out_of_daily_quota(monkeypatch):
    _keys(monkeypatch, 3, 2)
    assert quota_exhausted({"execution_status": "failed", "error": _PER_DAY}) is True
    assert quota_exhausted({"execution_status": "failed", "error": None,
                            "trace": [{"stage": "llm", "error": _PER_DAY}]}) is True


def test_keeps_going_while_another_key_is_left(monkeypatch):
    _keys(monkeypatch, 3, 0)
    assert llm.keys_remaining() == 2
    assert quota_exhausted({"execution_status": "failed", "error": _PER_DAY}) is False


def test_other_failures_are_recorded_normally(monkeypatch):
    _keys(monkeypatch, 3, 2)
    pipeline_failure = {"type": "AnalysisFailedError", "message": "no clauses could be extracted"}
    assert quota_exhausted({"execution_status": "failed", "error": pipeline_failure}) is False
    # A per-minute limit is retried in-process, so it is a real result, not a quota stop.
    per_minute = {"type": "ResourceExhausted", "message": "429 requests per minute limit exceeded"}
    assert quota_exhausted({"execution_status": "failed", "error": per_minute}) is False
    assert quota_exhausted({"execution_status": "completed", "error": _PER_DAY}) is False

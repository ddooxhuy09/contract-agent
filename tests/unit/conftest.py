import pytest


@pytest.fixture
def stub_deterministic_checks(monkeypatch):
    """Isolate workflow tests from the deterministic pre-pass.

    `_deterministic_node` imports these checkers lazily; they query Postgres via
    labor_code_resolver and add their own risks. They have dedicated tests, so
    graph-flow tests stub them out.
    """
    import app.agents.labor_completeness as completeness
    import app.agents.labor_red_flags as red_flags
    import app.agents.preamble_citations as preamble

    monkeypatch.setattr(red_flags, "check_labor_red_flags", lambda *a, **k: [])
    monkeypatch.setattr(completeness, "check_labor_completeness", lambda *a, **k: [])
    monkeypatch.setattr(preamble, "check_preamble_citations", lambda *a, **k: [])

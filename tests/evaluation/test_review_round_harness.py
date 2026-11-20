import asyncio
import sys

from evaluation.contract_eval_v2 import research_round as engine


def test_async_clients_keep_one_event_loop_across_dataset_splits(monkeypatch):
    loops, paths = [], []

    async def run(path, stage):
        loops.append(asyncio.get_running_loop())
        paths.append(path)
        assert stage == "qa"

    monkeypatch.setattr(engine, "check_protocol", lambda: {})
    monkeypatch.setattr(engine, "install_variant", lambda: None)
    monkeypatch.setattr(engine.exp, "run", run)
    monkeypatch.setattr(sys, "argv", ["research_round", "qa"])
    engine.main()
    assert paths == [engine.OUTPUT / split for split in engine.SPLITS]
    assert all(loop is loops[0] for loop in loops)

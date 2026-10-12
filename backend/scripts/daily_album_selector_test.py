"""Tests for the manual daily-album-selector script.

Per-group failure handling lives in ``app/services/scheduled_jobs.py`` and is
tested there. What remains here is the script's contract with whoever runs it: a
run that skipped any group must exit non-zero and say so.

``scripts/`` is not a package, so the module is loaded by path.
"""

import importlib.util
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.scheduled_jobs import JobReport

_SPEC = importlib.util.spec_from_file_location(
    "daily_album_selector", Path(__file__).with_name("daily_album_selector.py")
)
das = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(das)


@pytest.fixture
def stub_run(monkeypatch):
    def install(report: JobReport) -> MagicMock:
        stub = MagicMock(return_value=report)
        monkeypatch.setattr(das, "run_daily_selection", stub)
        return stub
    return install


class TestExitStatus:
    def test_a_partial_run_exits_non_zero_and_says_so(self, stub_run, caplog):
        stub_run(JobReport(done=[2], failed={1: "boom"}))

        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as exit_info:
                das.run(n=None, group_id=None, db=MagicMock())

        assert exit_info.value.code == 1
        assert "1 of 2 group(s) skipped" in caplog.text

    def test_a_rejected_group_also_counts_as_skipped(self, stub_run):
        stub_run(JobReport(rejected={1: "No eligible albums"}))
        with pytest.raises(SystemExit):
            das.run(n=None, group_id=None, db=MagicMock())

    def test_a_clean_run_does_not_exit_non_zero(self, stub_run):
        stub = stub_run(JobReport(done=[1, 2]))
        das.run(n=3, group_id=None, db=MagicMock())  # must not raise SystemExit
        stub.assert_called_once()
        assert stub.call_args.kwargs == {"n": 3}

    def test_unknown_group_exits_non_zero(self, stub_run):
        stub = stub_run(JobReport())
        db = MagicMock()
        db.get.return_value = None
        with pytest.raises(SystemExit):
            das.run(n=None, group_id=42, db=db)
        stub.assert_not_called()

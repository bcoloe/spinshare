"""Tests for the manual weekly-recap script's exit status.

Per-group failure handling lives in ``app/services/scheduled_jobs.py`` and is
tested there. ``scripts/`` is not a package, so the module is loaded by path.
"""

import importlib.util
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.scheduled_jobs import JobReport

_SPEC = importlib.util.spec_from_file_location(
    "weekly_recap_generator", Path(__file__).with_name("weekly_recap_generator.py")
)
wrg = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(wrg)


def _run(monkeypatch, report: JobReport) -> None:
    monkeypatch.setattr(wrg, "run_weekly_recaps", MagicMock(return_value=report))
    wrg.run(group_id=None, week_start=None, force=False, db=MagicMock())


class TestExitStatus:
    def test_a_partial_run_exits_non_zero_and_says_so(self, monkeypatch, caplog):
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as exit_info:
                _run(monkeypatch, JobReport(done=[2], failed={1: "boom"}))
        assert exit_info.value.code == 1
        assert "1 of 2 group(s) skipped" in caplog.text

    def test_a_rejected_group_also_counts_as_skipped(self, monkeypatch):
        with pytest.raises(SystemExit):
            _run(monkeypatch, JobReport(rejected={1: "not eligible"}))

    def test_a_clean_run_does_not_exit_non_zero(self, monkeypatch):
        _run(monkeypatch, JobReport(done=[1, 2]))  # must not raise SystemExit

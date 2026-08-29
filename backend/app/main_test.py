"""Tests for the startup worker-count guard.

The guard exists because the deployed unit file drifted to ``--workers 2`` and
served that way unnoticed: presence and chat fan-out are per-process, so the
only symptom was rooms quietly looking empty to half their members.
"""

import logging

from app.main import configured_worker_count, warn_if_sharded


class TestConfiguredWorkerCount:
    def test_defaults_to_one_when_unspecified(self):
        assert configured_worker_count(argv=["uvicorn", "app.main:app"], env={}) == 1

    def test_reads_separate_argument(self):
        argv = ["uvicorn", "app.main:app", "--workers", "2"]
        assert configured_worker_count(argv=argv, env={}) == 2

    def test_reads_equals_form(self):
        argv = ["uvicorn", "app.main:app", "--workers=3"]
        assert configured_worker_count(argv=argv, env={}) == 3

    def test_falls_back_to_web_concurrency(self):
        argv = ["uvicorn", "app.main:app"]
        assert configured_worker_count(argv=argv, env={"WEB_CONCURRENCY": "4"}) == 4

    def test_command_line_beats_environment(self):
        argv = ["uvicorn", "app.main:app", "--workers", "1"]
        assert configured_worker_count(argv=argv, env={"WEB_CONCURRENCY": "8"}) == 1

    def test_unparseable_value_counts_as_one(self):
        """The guard must never become a new way to fail to boot."""
        argv = ["uvicorn", "app.main:app", "--workers", "many"]
        assert configured_worker_count(argv=argv, env={}) == 1

    def test_trailing_flag_without_value_counts_as_one(self):
        argv = ["uvicorn", "app.main:app", "--workers"]
        assert configured_worker_count(argv=argv, env={}) == 1


class TestWarnIfSharded:
    def test_single_worker_is_silent(self, caplog):
        with caplog.at_level(logging.ERROR):
            assert warn_if_sharded(1) is False
        assert caplog.records == []

    def test_multiple_workers_log_an_error(self, caplog):
        with caplog.at_level(logging.ERROR):
            assert warn_if_sharded(2) is True

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "2 uvicorn workers" in message
        assert "--workers 1" in message

    def test_zero_workers_is_not_treated_as_sharded(self, caplog):
        with caplog.at_level(logging.ERROR):
            assert warn_if_sharded(0) is False
        assert caplog.records == []

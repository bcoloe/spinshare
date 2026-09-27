"""Tests for the nightly daily-album-selector cron.

These drive ``run()`` with a stubbed Session and service rather than the test
database: what is under test is the loop's failure handling, not the selection
itself, and the bug being guarded against is precisely that a *database* error
in one iteration poisons the shared Session for every later one.

``scripts/`` is not a package, so the module is loaded by path.
"""

import importlib.util
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "daily_album_selector", Path(__file__).with_name("daily_album_selector.py")
)
das = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(das)


def _group(group_id: int, name: str, daily_album_count: int = 1) -> MagicMock:
    group = MagicMock()
    group.id = group_id
    group.name = name
    group.settings.daily_album_count = daily_album_count
    return group


def _selection(title: str) -> MagicMock:
    selected = MagicMock()
    selected.albums.title = title
    return selected


@pytest.fixture
def db(request):
    """A stub Session whose ``query(Group).all()`` yields the requested groups."""
    groups = getattr(request, "param", [])
    session = MagicMock()
    session.query.return_value.all.return_value = groups
    return session


class TestRunFailureIsolation:
    """One failing group must not silently cancel every group after it."""

    @pytest.mark.parametrize(
        "db", [[_group(1, "Alpha"), _group(2, "Bravo"), _group(3, "Charlie")]], indirect=True
    )
    def test_a_failing_group_does_not_stop_the_ones_after_it(self, db, monkeypatch):
        svc = MagicMock()
        svc.select_daily_albums.side_effect = [
            [_selection("Kid A")],
            RuntimeError("deadlock detected"),
            [_selection("Spiderland")],
        ]
        monkeypatch.setattr(das, "GroupAlbumService", lambda _db: svc)

        with pytest.raises(SystemExit) as exit_info:
            das.run(n=None, group_id=None, db=db)

        # Every group was attempted — the third is the one that used to be lost.
        assert [c.args[0] for c in svc.select_daily_albums.call_args_list] == [1, 2, 3]
        assert exit_info.value.code == 1

    @pytest.mark.parametrize("db", [[_group(1, "Alpha"), _group(2, "Bravo")]], indirect=True)
    def test_a_failure_rolls_the_shared_session_back(self, db, monkeypatch):
        """Without this the Session stays in pending-rollback for every later group."""
        svc = MagicMock()
        svc.select_daily_albums.side_effect = [RuntimeError("boom"), [_selection("Loveless")]]
        monkeypatch.setattr(das, "GroupAlbumService", lambda _db: svc)

        with pytest.raises(SystemExit):
            das.run(n=None, group_id=None, db=db)

        db.rollback.assert_called_once()

    @pytest.mark.parametrize("db", [[_group(1, "Alpha"), _group(2, "Bravo")]], indirect=True)
    def test_a_partial_run_exits_non_zero_and_says_so(self, db, monkeypatch, caplog):
        """A run that spun nothing for a group must not look like a clean run."""
        svc = MagicMock()
        svc.select_daily_albums.side_effect = [RuntimeError("boom"), [_selection("Loveless")]]
        monkeypatch.setattr(das, "GroupAlbumService", lambda _db: svc)

        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit) as exit_info:
                das.run(n=None, group_id=None, db=db)

        assert exit_info.value.code == 1
        assert "1 of 2 group(s) skipped" in caplog.text

    @pytest.mark.parametrize("db", [[_group(1, "Alpha"), _group(2, "Bravo")]], indirect=True)
    def test_a_clean_run_does_not_exit_non_zero(self, db, monkeypatch):
        svc = MagicMock()
        svc.select_daily_albums.side_effect = [[_selection("Kid A")], [_selection("Loveless")]]
        monkeypatch.setattr(das, "GroupAlbumService", lambda _db: svc)

        das.run(n=None, group_id=None, db=db)  # must not raise SystemExit

        db.rollback.assert_not_called()

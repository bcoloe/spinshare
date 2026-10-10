"""Guards on the profiling harness: route coverage and the awake-time arithmetic.

``scripts/`` is not a package, so the module is loaded by path.
"""

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app

_SPEC = importlib.util.spec_from_file_location("profile_db", Path(__file__).with_name("profile_db.py"))
profile_db = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(profile_db)


def _get_route_shapes() -> set[str]:
    return {
        profile_db.route_shape(r.path)
        for r in app.routes
        if isinstance(r, APIRoute) and "GET" in r.methods
    }


class TestRouteCoverage:
    """Every GET route is either profiled or explicitly excused, so none goes unmeasured by accident."""

    def test_every_get_route_is_classified(self):
        unclassified = _get_route_shapes() - profile_db.profiled_get_shapes() - set(profile_db.UNPROFILED_GETS)
        assert not unclassified, (
            f"New GET routes {sorted(unclassified)}: add each to a scenario in "
            "scripts/profile_db.py or to UNPROFILED_GETS with a reason."
        )

    def test_no_route_is_both_profiled_and_excused(self):
        assert not profile_db.profiled_get_shapes() & set(profile_db.UNPROFILED_GETS)

    def test_no_stale_excuses(self):
        stale = set(profile_db.UNPROFILED_GETS) - _get_route_shapes()
        assert not stale, f"UNPROFILED_GETS lists routes that no longer exist: {sorted(stale)}"

    def test_scenarios_only_reference_real_routes(self):
        assert profile_db.profiled_get_shapes() <= _get_route_shapes()


class TestRouteShape:
    def test_blanks_placeholders_and_drops_query(self):
        assert profile_db.route_shape("/groups/{g}/albums/{group_album_id}?x={u}") == "/groups/{}/albums/{}"


T0 = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)


class TestAwakeIntervals:
    def test_touches_within_the_window_share_one_wake(self):
        summary = profile_db.summarize_touches([T0, T0 + minutes(4), T0 + minutes(8)])
        assert summary["wakes"] == 1
        assert summary["awake_minutes"] == 13  # last touch at +8, awake until +13

    def test_touches_further_apart_each_wake(self):
        summary = profile_db.summarize_touches([T0, T0 + minutes(6)])
        assert summary["wakes"] == 2
        assert summary["awake_minutes"] == 10

    def test_order_does_not_matter(self):
        touches = [T0 + minutes(20), T0, T0 + minutes(2)]
        assert profile_db.awake_intervals(touches) == [(T0, T0 + minutes(7)), (T0 + minutes(20), T0 + minutes(25))]

    def test_no_touches_no_time(self):
        assert profile_db.summarize_touches([]) == {"touches": 0, "connections": 0, "wakes": 0, "awake_minutes": 0}


class TestLegacyCron:
    def test_monday_has_selection_and_recap(self):
        assert len(profile_db.legacy_cron_touches(date(2026, 10, 12))) == 2

    def test_other_days_have_selection_only(self):
        assert len(profile_db.legacy_cron_touches(date(2026, 10, 13))) == 1

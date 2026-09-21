# backend/app/schemas/group_test.py
#
# Validation tests for the group schemas. These are pure Pydantic checks — no
# database and no HTTP — so they run fast and pin the contract the service layer
# is allowed to assume.

import pytest
from pydantic import ValidationError

from app.schemas.group import (
    MAX_PRIORITY_PICK_THRESHOLD,
    AddMemberRequest,
    GroupSettingsUpdate,
    JoinGroupRequest,
)


class TestPriorityPickThreshold:
    """The threshold is a credit *cost*, so it must be a positive, storable int."""

    def test_none_is_allowed_and_disables_the_feature(self):
        assert GroupSettingsUpdate(priority_pick_threshold=None).priority_pick_threshold is None

    @pytest.mark.parametrize("value", [1, 3, 10, MAX_PRIORITY_PICK_THRESHOLD])
    def test_accepts_sensible_values(self, value):
        assert GroupSettingsUpdate(priority_pick_threshold=value).priority_pick_threshold == value

    @pytest.mark.parametrize("value", [-5, -1, 0])
    def test_rejects_zero_and_negatives(self, value):
        """A negative threshold inverts every credit comparison downstream.

        ``_feature_threshold`` would report -5 as *enabled* (truthy), the
        ``credits < threshold`` guard would pass for a member with zero credits,
        and claiming the pick would compute ``max(0, credits - (-5))`` — paying
        the member five credits for spending them.
        """
        with pytest.raises(ValidationError):
            GroupSettingsUpdate(priority_pick_threshold=value)

    @pytest.mark.parametrize("value", [MAX_PRIORITY_PICK_THRESHOLD + 1, 99999999999])
    def test_rejects_values_above_the_cap(self, value):
        """Above int4 the write raises DataError, which the service's IntegrityError
        handler does not catch — a 500 instead of a 422."""
        with pytest.raises(ValidationError):
            GroupSettingsUpdate(priority_pick_threshold=value)


class TestSettingsBoundsAreComplete:
    """Every numeric settings field is bounded, so none can overflow its column."""

    @pytest.mark.parametrize(
        "field",
        [
            "daily_album_count",
            "guess_user_cap",
            "daily_nomination_limit",
            "dealer_rolls_per_day",
            "priority_pick_threshold",
        ],
    )
    def test_out_of_range_int_is_rejected(self, field):
        with pytest.raises(ValidationError):
            GroupSettingsUpdate(**{field: 99999999999})

    @pytest.mark.parametrize(
        "field",
        [
            "daily_album_count",
            "guess_user_cap",
            "daily_nomination_limit",
            "dealer_rolls_per_day",
            "priority_pick_threshold",
        ],
    )
    def test_negative_int_is_rejected(self, field):
        with pytest.raises(ValidationError):
            GroupSettingsUpdate(**{field: -1})


class TestIdRequests:
    def test_valid_id_accepted(self):
        assert AddMemberRequest(user_id=7).user_id == 7
        assert JoinGroupRequest(id=7).id == 7

    @pytest.mark.parametrize("value", [0, -1, 99999999999])
    def test_non_primary_key_values_rejected(self, value):
        with pytest.raises(ValidationError):
            AddMemberRequest(user_id=value)
        with pytest.raises(ValidationError):
            JoinGroupRequest(id=value)

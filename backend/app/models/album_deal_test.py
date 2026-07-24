"""Unit tests for the AlbumDeal model."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import AlbumDeal, GroupSettings


class TestAlbumDealModel:
    def test_create_deal_defaults(self, db_session, creators, sample_album):
        user = creators.users(["dealer"])[0]
        group = creators.group("Dealer Group", user)

        deal = AlbumDeal(group_id=group.id, user_id=user.id, album_id=sample_album.id)
        db_session.add(deal)
        db_session.commit()
        db_session.refresh(deal)

        assert deal.dealt_at is not None
        assert deal.revealed_at is None

    def test_unique_deal_per_user_album(self, db_session, creators, sample_album):
        user = creators.users(["dealer"])[0]
        group = creators.group("Dealer Group", user)

        db_session.add(AlbumDeal(group_id=group.id, user_id=user.id, album_id=sample_album.id))
        db_session.commit()

        db_session.add(AlbumDeal(group_id=group.id, user_id=user.id, album_id=sample_album.id))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_album_dealable_to_multiple_users(self, db_session, creators, sample_album):
        users = creators.users(["dealer_a", "dealer_b"])
        group = creators.group("Dealer Group", users[0])

        db_session.add_all(
            [
                AlbumDeal(group_id=group.id, user_id=u.id, album_id=sample_album.id)
                for u in users
            ]
        )
        db_session.commit()

        deals = db_session.query(AlbumDeal).filter(AlbumDeal.group_id == group.id).all()
        assert len(deals) == 2

    def test_same_album_dealable_in_multiple_groups(self, db_session, creators, sample_album):
        user = creators.users(["dealer"])[0]
        group_a = creators.group("Group A", user)
        group_b = creators.group("Group B", user)

        db_session.add_all(
            [
                AlbumDeal(group_id=g.id, user_id=user.id, album_id=sample_album.id)
                for g in (group_a, group_b)
            ]
        )
        db_session.commit()

        deals = db_session.query(AlbumDeal).filter(AlbumDeal.user_id == user.id).all()
        assert len(deals) == 2


class TestGroupSettingsDealerDefaults:
    def test_dealer_defaults(self, db_session, creators):
        user = creators.users(["owner"])[0]
        group = creators.group("Defaults Group", user)

        settings = GroupSettings(group_id=group.id)
        db_session.add(settings)
        db_session.commit()
        db_session.refresh(settings)

        assert settings.dealer_mode is False
        assert settings.dealer_rolls_per_day == 1

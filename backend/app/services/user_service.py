"""User interface service"""

from datetime import UTC, datetime, timedelta

from app.models import (
    Album,
    AlbumDeal,
    Group,
    GroupAlbum,
    GroupInvitation,
    GroupInviteLink,
    GroupParticipation,
    NominationGuess,
    PriorityReviewCredit,
    Review,
    SpotifyConnection,
    User,
)
from app.models.group import group_members
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.utils import security
from fastapi import HTTPException, status
from sqlalchemy import delete as sa_delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload


class UserService:
    """Service layer for User operations"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user with hashed password.

        Raises:
            HTTPException 409: If email or username already exists
            HTTPException 400: If password does not meet strength requirements
        """
        # Check if email already exists
        existing_user = self.db.query(User).filter(User.email == user_data.email.lower()).first()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )

        # Check if username already exists
        existing_username = (
            self.db.query(User).filter(User.username == user_data.username.lower()).first()
        )

        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
            )

        # Validate password
        is_password_valid, reasons = security.validate_password_strength(user_data.password)
        if not is_password_valid:
            reasons_str = "\n".join([" * " + x for x in reasons])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reasons_str)

        # Create user with hashed password
        user = User(
            email=user_data.email.lower(),
            username=user_data.username.lower(),
            password_hash=security.hash_password(user_data.password),
            first_name=user_data.first_name or None,
            last_name=user_data.last_name or None,
        )

        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User creation failed due to constraint violation",
            ) from None

        # Auto-enroll in the global group if it exists
        from app.services import group_service as gs_module
        gs = gs_module.GroupService(self.db)
        global_group = gs.get_global_group()
        if global_group:
            gs.add_user(global_group.id, user.id)

        return user

    # ==================== READ ====================

    def get_user_by_id(self, user_id: int) -> User:
        """Get user by ID.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Get user by email (case-insensitive)"""
        return self.db.query(User).filter(User.email == email.lower()).first()

    def get_user_by_username(self, username: str) -> User | None:
        """Get user by username (case-insensitive)"""
        return self.db.query(User).filter(User.username == username.lower()).first()

    def get_all_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all users with pagination"""
        return self.db.query(User).offset(skip).limit(limit).all()

    def search_users(self, query: str, limit: int = 10) -> list[User]:
        """Search users by username or email"""
        search_pattern = f"%{query.lower()}%"
        return (
            self.db.query(User)
            .filter((User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern)))
            .limit(limit)
            .all()
        )

    def get_public_profile(self, username: str) -> dict:
        """Get public-facing profile stats for a user by username.

        Deliberately omits ``email``: this endpoint is readable by any authenticated
        user, and the address is private. ``is_admin`` stays — the admin badge and
        the grant/revoke control are deliberately public-facing.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Three integers used to cost three relationship loads, each materialising
        # every Review / Group / GroupAlbum row in full just to call len() on it.
        # One round trip of scalar counts replaces them.
        published_reviews, group_count, nomination_count = self.db.execute(
            select(
                self._count_published_reviews(user.id),
                self._count_memberships(user.id),
                self._count_nominations(user.id),
            )
        ).one()

        return {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name if user.name_is_public else None,
            "last_name": user.last_name if user.name_is_public else None,
            "is_admin": user.is_admin,
            "member_since": user.created_at,
            "total_reviews": published_reviews,
            "total_groups": group_count,
            "albums_nominated": nomination_count,
        }

    # ---- Count subqueries -------------------------------------------------
    #
    # Each mirrors exactly one relationship walk, so a caller can ask the
    # database for the integer instead of loading the rows and calling len().

    @staticmethod
    def _count_memberships(user_id: int):
        """``len(user.groups)`` — joined through to ``groups`` like the relationship."""
        return (
            select(func.count())
            .select_from(group_members)
            .join(Group, Group.id == group_members.c.group_id)
            .where(group_members.c.user_id == user_id)
            .scalar_subquery()
        )

    @staticmethod
    def _count_created_groups(user_id: int):
        """``len(user.created_groups)``"""
        return (
            select(func.count())
            .select_from(Group)
            .where(Group.created_by == user_id)
            .scalar_subquery()
        )

    @staticmethod
    def _count_reviews(user_id: int):
        """``len(user.reviews)`` — drafts included, as the relationship is."""
        return (
            select(func.count())
            .select_from(Review)
            .where(Review.user_id == user_id)
            .scalar_subquery()
        )

    @staticmethod
    def _count_published_reviews(user_id: int):
        """``sum(1 for r in user.reviews if not r.is_draft)``"""
        return (
            select(func.count())
            .select_from(Review)
            .where(Review.user_id == user_id, Review.is_draft == False)  # noqa: E712
            .scalar_subquery()
        )

    @staticmethod
    def _count_nominations(user_id: int):
        """``len(user.added_albums)``"""
        return (
            select(func.count())
            .select_from(GroupAlbum)
            .where(GroupAlbum.added_by == user_id)
            .scalar_subquery()
        )

    def get_user_reviews_for_profile(self, username: str) -> list[dict]:
        """Get all published reviews for a user with flat album metadata.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Without the eager loads this is 1 + 2N round trips: every row below
        # walks r.albums and then r.albums.genres.
        reviews = (
            self.db.query(Review)
            .options(selectinload(Review.albums).selectinload(Album.genres))
            .filter(Review.user_id == user.id, Review.is_draft == False)  # noqa: E712
            .all()
        )

        return [
            {
                "review_id": r.id,
                "album_id": r.album_id,
                "title": r.albums.title,
                "artist": r.albums.artist,
                "cover_url": r.albums.cover_url,
                "release_date": r.albums.release_date,
                "genres": [g.name for g in r.albums.genres],
                "rating": r.rating,
                "comment": r.comment,
                "reviewed_at": r.reviewed_at,
            }
            for r in reviews
        ]

    def get_nomination_decade_breakdown(self, username: str) -> dict:
        """Get nomination count and release-decade breakdown for a user.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Only the release date is needed, so ask for that column alone rather
        # than loading every nomination the user has ever made and lazy-loading
        # its album one row at a time. The join is outer so a nomination whose
        # album row is missing still counts, exactly as the relationship walk
        # (``if nomination.albums else None``) did.
        release_dates = (
            self.db.execute(
                select(Album.release_date)
                .select_from(GroupAlbum)
                .outerjoin(Album, Album.id == GroupAlbum.album_id)
                .where(GroupAlbum.added_by == user.id)
            )
            .scalars()
            .all()
        )

        decade_counts: dict[str, int] = {}
        for release_date in release_dates:
            try:
                year = int(str(release_date)[:4])
                decade = f"{(year // 10) * 10}s"
            except (TypeError, ValueError):
                decade = "Unknown"
            decade_counts[decade] = decade_counts.get(decade, 0) + 1

        breakdown = sorted(
            [{"decade": d, "count": c} for d, c in decade_counts.items()],
            key=lambda x: x["decade"],
        )

        return {
            "total_nominations": len(release_dates),
            "decade_breakdown": breakdown,
        }

    def get_groups_for_public_profile(self, username: str, viewer_id: int) -> list[dict]:
        """Return groups visible to a viewer on another user's public profile.

        Includes public non-global groups and private groups the viewer shares
        with the target user.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Still 404s for an unknown viewer, but the viewer's memberships are read
        # as (group_id, role) pairs in one statement. That single read answers
        # both "which groups does the viewer share?" and "what is the viewer's
        # role here?" — the latter used to be one query per group in the loop.
        self.get_user_by_id(viewer_id)
        viewer_roles = {
            group_id: role
            for group_id, role in self.db.execute(
                select(group_members.c.group_id, group_members.c.role).where(
                    group_members.c.user_id == viewer_id
                )
            ).all()
        }

        visible = [
            group
            for group in user.groups
            if not group.is_global and (group.is_public or group.id in viewer_roles)
        ]

        # One grouped count instead of materialising every member of every group
        # to take its length.
        member_counts = self._member_counts([g.id for g in visible])

        result = [
            {
                "id": group.id,
                "name": group.name,
                "member_count": member_counts.get(group.id, 0),
                "current_user_role": viewer_roles.get(group.id),
            }
            for group in visible
        ]

        return sorted(result, key=lambda x: x["name"])

    def _member_counts(self, group_ids: list[int]) -> dict[int, int]:
        """Member count per group id, in a single round trip."""
        if not group_ids:
            return {}
        rows = self.db.execute(
            select(group_members.c.group_id, func.count())
            .select_from(group_members)
            .join(User, User.id == group_members.c.user_id)
            .where(group_members.c.group_id.in_(group_ids))
            .group_by(group_members.c.group_id)
        ).all()
        return {group_id: count for group_id, count in rows}

    def get_review_stats(self, username: str) -> dict:
        """Get review statistics for a user's public profile.

        Returns average rating, rating histogram (buckets of size 1), average
        rating per release decade, and nominator-guess accuracy.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Every statistic below needs exactly two values per review — the rating
        # and the album's release date — so both are read in one statement.
        # Walking ``r.albums`` per row instead cost a round trip per review.
        # The rating filter and the outer join reproduce the previous Python
        # filtering (``rating is not None``) and null handling (``if r.albums``).
        rated = self.db.execute(
            select(Review.rating, Album.release_date)
            .select_from(Review)
            .outerjoin(Album, Album.id == Review.album_id)
            .where(
                Review.user_id == user.id,
                Review.is_draft == False,  # noqa: E712
                Review.rating.isnot(None),
            )
        ).all()

        average_rating = (
            round(sum(rating for rating, _ in rated) / len(rated), 2) if rated else None
        )

        histogram: dict[int, int] = {b: 0 for b in range(0, 11)}
        decade_ratings: dict[str, list[float]] = {}
        for rating, release_date in rated:
            histogram[int(rating)] = histogram.get(int(rating), 0) + 1
            try:
                year = int(str(release_date)[:4])
                decade = f"{(year // 10) * 10}s"
            except (TypeError, ValueError):
                continue
            decade_ratings.setdefault(decade, []).append(rating)

        rating_histogram = [{"bucket": b, "count": histogram[b]} for b in range(0, 11)]
        avg_by_decade = sorted(
            [
                {"decade": d, "avg_rating": round(sum(rs) / len(rs), 2)}
                for d, rs in decade_ratings.items()
            ],
            key=lambda x: x["decade"],
        )

        # Two integers, counted in the database rather than by loading every
        # guess row the user has ever made.
        total_guesses, correct_guesses = self.db.execute(
            select(
                func.count(),
                func.count().filter(NominationGuess.correct),
            )
            .select_from(NominationGuess)
            .where(NominationGuess.guessing_user_id == user.id)
        ).one()
        guess_pct = round(correct_guesses / total_guesses * 100, 1) if total_guesses > 0 else None

        return {
            "average_rating": average_rating,
            "rating_histogram": rating_histogram,
            "avg_rating_by_decade": avg_by_decade,
            "guess_accuracy": {
                "total": total_guesses,
                "correct": correct_guesses,
                "pct": guess_pct,
            },
        }

    # ==================== UPDATE ====================

    def update_user(self, user_id: int, user_data: UserUpdate) -> User:
        """Update user information.

        Raises:
            HTTPException 404: If user not found
            HTTPException 409: If new email/username already exists
            HTTPException 400: If password does not meet strength requirements
        """
        user = self.get_user_by_id(user_id)

        # Update email if provided
        if user_data.email and user_data.email != user.email:
            existing = self.get_user_by_email(user_data.email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already in use"
                )
            user.email = user_data.email.lower()

        # Update username if provided
        if user_data.username and user_data.username != user.username:
            existing = self.get_user_by_username(user_data.username)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
                )
            user.username = user_data.username.lower()

        # Update name fields if provided (can be set to None to clear)
        if "first_name" in user_data.model_fields_set:
            user.first_name = user_data.first_name
        if "last_name" in user_data.model_fields_set:
            user.last_name = user_data.last_name
        if "name_is_public" in user_data.model_fields_set and user_data.name_is_public is not None:
            user.name_is_public = user_data.name_is_public

        # Update password if provided
        if user_data.password:
            # Validate password
            is_password_valid, reasons = security.validate_password_strength(user_data.password)
            if not is_password_valid:
                reasons_str = "\n".join([" * " + x for x in reasons])
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reasons_str)

            user.password_hash = security.hash_password(user_data.password)

        try:
            self.db.commit()
            self.db.refresh(user)
            return user
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Update failed due to constraint violation",
            ) from None

    # ==================== ADMIN ====================

    def set_admin_status(self, granting_user_id: int, target_user_id: int, is_admin: bool) -> User:
        """Grant or revoke admin status for a user.

        Raises:
            HTTPException 403: If the granting user is not an admin
            HTTPException 404: If target user not found
            HTTPException 400: If attempting to modify own admin status
        """
        granting_user = self.get_user_by_id(granting_user_id)
        if not granting_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )
        if granting_user_id == target_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify your own admin status",
            )
        target_user = self.get_user_by_id(target_user_id)
        target_user.is_admin = is_admin
        self.db.commit()
        self.db.refresh(target_user)
        return target_user

    # ==================== DELETE ====================

    def delete_user(self, user_id: int):
        """Delete a user account.

        Pending nominations are removed from their groups. Already-selected
        nominations — and pending nominations for albums already dealt to a
        member (dealer mode) — are preserved but anonymized (added_by set to
        NULL). Reviews, nomination guesses, and album deals are deleted.
        Created groups remain.

        Participation state (per-group credits / queued priority pick) and the
        credit ledger are the user's own records and go with the account. Sent
        invitations and the invite links the user created are deleted rather than
        anonymized: ``group_invitations.invited_by`` and
        ``group_invite_links.created_by`` are both NOT NULL with no ON DELETE
        behaviour, so there is no null to fall back to. Invitations *addressed to*
        this user's email go too — they carry the address of an account that no
        longer exists, and honouring one would hand the group to whoever next
        registers it.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_id(user_id)
        user_email = user.email
        # Delete nomination guesses made by or about this user
        self.db.query(NominationGuess).filter(
            (NominationGuess.guessing_user_id == user_id)
            | (NominationGuess.guessed_user_id == user_id)
        ).delete(synchronize_session=False)

        # Delete reviews written by this user
        self.db.query(Review).filter(
            Review.user_id == user_id
        ).delete(synchronize_session=False)

        # Delete the user's album deals first so the anonymization check below
        # only considers deals held by *other* members
        self.db.query(AlbumDeal).filter(
            AlbumDeal.user_id == user_id
        ).delete(synchronize_session=False)

        # Pending nominations for albums already dealt to a member (dealer mode)
        # stay in the group anonymized; the rest are removed
        dealt_in_group = exists().where(
            AlbumDeal.group_id == GroupAlbum.group_id,
            AlbumDeal.album_id == GroupAlbum.album_id,
        )
        self.db.query(GroupAlbum).filter(
            GroupAlbum.added_by == user_id,
            GroupAlbum.selected_date.is_(None),
            dealt_in_group,
        ).update({"added_by": None}, synchronize_session=False)
        self.db.query(GroupAlbum).filter(
            GroupAlbum.added_by == user_id,
            GroupAlbum.selected_date.is_(None),
            ~dealt_in_group,
        ).delete(synchronize_session=False)

        # Anonymize already-selected nominations so the album stays in the group
        self.db.query(GroupAlbum).filter(
            GroupAlbum.added_by == user_id,
            GroupAlbum.selected_date.isnot(None),
        ).update({"added_by": None}, synchronize_session=False)

        # Preserve groups but remove creator attribution
        self.db.query(Group).filter(
            Group.created_by == user_id
        ).update({"created_by": None}, synchronize_session=False)

        # Delete Spotify connection (nullable FK would orphan it otherwise)
        self.db.query(SpotifyConnection).filter(
            SpotifyConnection.user_id == user_id
        ).delete(synchronize_session=False)

        # Delete per-group participation state and the credit ledger. Both FK to
        # users.id with no ON DELETE, so leaving them behind made the final commit
        # fail with a 409 for any user who had ever earned a single credit.
        self.db.query(GroupParticipation).filter(
            GroupParticipation.user_id == user_id
        ).delete(synchronize_session=False)
        self.db.query(PriorityReviewCredit).filter(
            PriorityReviewCredit.user_id == user_id
        ).delete(synchronize_session=False)

        # Delete invitations sent by this user and invitations addressed to their
        # email. invited_by is NOT NULL, so the attribution cannot be anonymized.
        self.db.query(GroupInvitation).filter(
            (GroupInvitation.invited_by == user_id) | (GroupInvitation.invited_email == user_email)
        ).delete(synchronize_session=False)

        # Delete invite links created by this user. created_by is NOT NULL too, and
        # the table is unique per group, so the group can simply mint a fresh link.
        self.db.query(GroupInviteLink).filter(
            GroupInviteLink.created_by == user_id
        ).delete(synchronize_session=False)

        # Remove group memberships (many-to-many secondary table)
        self.db.execute(sa_delete(group_members).where(group_members.c.user_id == user_id))

        # Delete the user (notifications cascade via ondelete="CASCADE")
        self.db.query(User).filter(User.id == user_id).delete(synchronize_session=False)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete user due to existing dependencies",
            ) from None

    # ==================== PASSWORD RESET ====================

    def request_password_reset(self, email: str) -> None:
        """Initiate a password reset by sending a reset link to the given email.

        Always returns silently regardless of whether the email is registered —
        callers must never reveal to the client whether an address exists.

        When SMTP is disabled (dev/test) the reset URL is logged instead.
        """
        from app.config import get_settings
        from app.utils.email import send_password_reset_email

        user = self.get_user_by_email(email)
        if not user:
            # Silently no-op — do not leak email existence.
            return

        token = security.create_password_reset_token(user.email)
        settings = get_settings()
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        send_password_reset_email(to_email=user.email, reset_url=reset_url)

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        """Complete a password reset by verifying the token and updating the password.

        Raises:
            HTTPException 400: If the token is invalid or expired.
            HTTPException 400: If the new password does not meet strength requirements.
            HTTPException 400: If the embedded email no longer maps to a user.
        """
        payload = security.decode_password_reset_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token",
            )

        email: str | None = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token",
            )

        user = self.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token",
            )

        is_valid, reasons = security.validate_password_strength(new_password)
        if not is_valid:
            reasons_str = "\n".join([" * " + x for x in reasons])
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reasons_str)

        user.password_hash = security.hash_password(new_password)
        self.db.commit()

    # ==================== AUTHENTICATION ====================

    def authenticate_user(
        self, password: str, email: str | None = None, username: str | None = None
    ) -> User | None:
        """Authenticate user with email and password.

        Returns:
            None if authentication fails.

        Raises:
            HTTPException 404: If username or email are not associated with user.
        """
        if email:
            user = self.get_user_by_email(email)
        elif username:
            user = self.get_user_by_username(username)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="email or username not provided."
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect username or email"
            )

        if not security.verify_password(password, user.password_hash):
            return None

        return user

    def _access_token_data(self, user: User) -> dict:
        """Claims for an access token.

        ``username`` and ``groups`` are carried so that minting a chat ticket —
        which a reconnecting client does continuously — needs no database read.

        ``groups`` is the one claim here that can go stale. A membership change
        reaches a chat socket only when that socket next reconnects carrying a
        token minted after the change, so the worst case is one access-token
        lifetime (15 minutes) plus however long the current socket survives. An
        open socket was already pinned to the membership it resolved at connect
        time, so this widens an existing window rather than opening a new one;
        reloading the page mints a fresh token and clears it either way.

        The ``groups`` claim is read as bare ids from the association table.
        Walking ``user.groups`` selected every column of every Group row on
        every login and every refresh to build a list of integers.
        """
        group_ids = self.db.execute(
            select(group_members.c.group_id)
            .select_from(group_members)
            .join(Group, Group.id == group_members.c.group_id)
            .where(group_members.c.user_id == user.id)
        ).scalars()
        return {
            "sub": str(user.id),
            "email": user.email,
            "username": user.username,
            "groups": sorted(group_ids),
        }

    @staticmethod
    def _refresh_token_data(user: User) -> dict:
        return {"sub": str(user.id), "email": user.email}

    def login(self, request: LoginRequest) -> LoginResponse:
        """
        Login user and return access token.

        Raises:
            HTTPException 401: If credentials are invalid
        """
        user = self.authenticate_user(request.password, email=request.email, username=request.username)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create tokens
        access_token = security.create_access_token(data=self._access_token_data(user))
        refresh_token = security.create_refresh_token(data=self._refresh_token_data(user))

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    def refresh(self, refresh_token: str) -> RefreshResponse:
        payload = security.decode_refresh_token(refresh_token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
            )

        # The user is loaded rather than reconstructed from the refresh token's
        # own claims, because the new access token has to carry current group
        # membership. This is the only point in a long session where that claim
        # gets corrected, which is what bounds its staleness to 15 minutes. One
        # read per refresh is affordable; the read per socket reconnect that
        # this replaces was not.
        try:
            user = self.get_user_by_id(int(user_id))
        except (HTTPException, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            ) from None

        return RefreshResponse(
            access_token=security.create_access_token(data=self._access_token_data(user)),
            refresh_token=security.create_refresh_token(data=self._refresh_token_data(user)),
            token_type="bearer",
        )

    # ==================== USER RELATIONSHIPS ====================

    def get_user_groups(self, user_id: int) -> list[Group]:
        """Get all groups user is a member of"""
        user = self.get_user_by_id(user_id)
        return user.groups

    def get_user_created_groups(self, user_id: int) -> list[Group]:
        """Get all groups created by user"""
        user = self.get_user_by_id(user_id)
        return user.created_groups

    def get_user_reviews(self, user_id: int) -> list[Review]:
        """Get all reviews by user"""
        user = self.get_user_by_id(user_id)
        return user.reviews

    # ==================== SPOTIFY ====================

    def has_spotify_connected(self, user_id: int) -> bool:
        """Check if user has Spotify connected"""
        user = self.get_user_by_id(user_id)
        return user.spotify_connection is not None

    def get_spotify_connection(self, user_id: int) -> SpotifyConnection | None:
        """Get user's Spotify connection"""
        user = self.get_user_by_id(user_id)
        return user.spotify_connection

    def connect_spotify(
        self,
        user_id: int,
        spotify_user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> SpotifyConnection:
        """
        Connect Spotify account to user.

        Raises:
            HTTPException 409: If Spotify account already connected to another user
        """
        # Check if Spotify account already connected to another user
        existing = (
            self.db.query(SpotifyConnection)
            .filter(SpotifyConnection.spotify_user_id == spotify_user_id)
            .first()
        )

        if existing and existing.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Spotify account is already connected to another user",
            )

        # Check if user already has a connection
        user = self.get_user_by_id(user_id)

        if user.spotify_connection:
            # Update existing connection
            connection = user.spotify_connection
            connection.spotify_user_id = spotify_user_id
            connection.access_token = access_token  # Should be encrypted
            connection.refresh_token = refresh_token  # Should be encrypted
            connection.token_expires_at = expires_at
            connection.last_refreshed_at = datetime.now(UTC)
        else:
            # Create new connection
            connection = SpotifyConnection(
                user_id=user_id,
                spotify_user_id=spotify_user_id,
                access_token=access_token,  # Should be encrypted
                refresh_token=refresh_token,  # Should be encrypted
                token_expires_at=expires_at,
                last_refreshed_at=datetime.now(UTC),
            )
            self.db.add(connection)

        try:
            self.db.commit()
            self.db.refresh(connection)
            return connection
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Failed to connect Spotify account"
            ) from None

    def get_valid_spotify_token(self, user_id: int) -> str:
        """Return a valid Spotify access token for the user, refreshing if within 5 minutes of expiry.

        Raises:
            HTTPException 404: If user has no Spotify connection.
            HTTPException 401: If the refresh token has been revoked (propagated from spotify_client).
        """
        from app.utils import spotify_client

        connection = self.get_spotify_connection(user_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Spotify account connected",
            )

        needs_refresh = (
            connection.token_expires_at is None
            or connection.token_expires_at <= datetime.now(UTC) + timedelta(minutes=5)
        )

        if needs_refresh:
            refreshed = spotify_client.refresh_access_token(connection.refresh_token)
            connection.access_token = refreshed["access_token"]
            connection.token_expires_at = refreshed["expires_at"]
            connection.last_refreshed_at = datetime.now(UTC)
            if "refresh_token" in refreshed:
                connection.refresh_token = refreshed["refresh_token"]
            self.db.commit()
            self.db.refresh(connection)

        return connection.access_token

    def disconnect_spotify(self, user_id: int) -> None:
        """
        Disconnect Spotify account from user.

        Raises:
            HTTPException 404: If user has no Spotify connection
        """
        user = self.get_user_by_id(user_id)

        if not user.spotify_connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No Spotify account connected"
            )

        self.db.delete(user.spotify_connection)
        self.db.commit()

    # ==================== STATS ====================

    def get_user_stats(self, user_id: int) -> dict:
        """Get user statistics"""
        user = self.get_user_by_id(user_id)

        # Five relationship loads used to produce five scalars, pulling whole
        # result sets across the wire to call len() on them. One round trip now.
        groups, created, reviews, nominations, has_spotify = self.db.execute(
            select(
                self._count_memberships(user_id),
                self._count_created_groups(user_id),
                self._count_reviews(user_id),
                self._count_nominations(user_id),
                select(exists().where(SpotifyConnection.user_id == user_id)).scalar_subquery(),
            )
        ).one()

        return {
            "total_groups": groups,
            "created_groups": created,
            "total_reviews": reviews,
            "albums_added": nominations,
            "has_spotify": has_spotify,
            "member_since": user.created_at,
        }

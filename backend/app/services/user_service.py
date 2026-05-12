"""User interface service"""

from datetime import UTC, datetime, timedelta

from app.models import Group, GroupAlbum, NominationGuess, Review, SpotifyConnection, User
from app.models.group import group_members
from app.schemas.user import LoginRequest, LoginResponse, UserCreate, UserResponse, UserUpdate
from app.utils import security
from fastapi import HTTPException, status
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


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

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {
            "username": user.username,
            "first_name": user.first_name if user.name_is_public else None,
            "last_name": user.last_name if user.name_is_public else None,
            "email": user.email,
            "member_since": user.created_at,
            "total_reviews": sum(1 for r in user.reviews if not r.is_draft),
            "total_groups": len(user.groups),
            "albums_nominated": len(user.added_albums),
        }

    def get_user_reviews_for_profile(self, username: str) -> list[dict]:
        """Get all published reviews for a user with flat album metadata.

        Raises:
            HTTPException 404: If user not found
        """
        user = self.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        reviews = (
            self.db.query(Review)
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

        nominations = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.added_by == user.id)
            .all()
        )

        decade_counts: dict[str, int] = {}
        for nomination in nominations:
            release_date = nomination.albums.release_date if nomination.albums else None
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
            "total_nominations": len(nominations),
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

        viewer = self.get_user_by_id(viewer_id)
        viewer_group_ids = {g.id for g in viewer.groups}

        result = []
        for group in user.groups:
            if group.is_global:
                continue
            if not group.is_public and group.id not in viewer_group_ids:
                continue
            role_stmt = select(group_members.c.role).where(
                group_members.c.user_id == viewer_id,
                group_members.c.group_id == group.id,
            )
            viewer_role = self.db.execute(role_stmt).scalar()
            result.append(
                {
                    "id": group.id,
                    "name": group.name,
                    "member_count": len(group.members),
                    "current_user_role": viewer_role,
                }
            )

        return sorted(result, key=lambda x: x["name"])

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

        reviews = (
            self.db.query(Review)
            .filter(Review.user_id == user.id, Review.is_draft == False)  # noqa: E712
            .all()
        )

        rated = [r for r in reviews if r.rating is not None]
        average_rating = round(sum(r.rating for r in rated) / len(rated), 2) if rated else None

        histogram: dict[int, int] = {b: 0 for b in range(0, 11)}
        decade_ratings: dict[str, list[float]] = {}
        for r in rated:
            histogram[int(r.rating)] = histogram.get(int(r.rating), 0) + 1
            release_date = r.albums.release_date if r.albums else None
            try:
                year = int(str(release_date)[:4])
                decade = f"{(year // 10) * 10}s"
            except (TypeError, ValueError):
                continue
            decade_ratings.setdefault(decade, []).append(r.rating)

        rating_histogram = [{"bucket": b, "count": histogram[b]} for b in range(0, 11)]
        avg_by_decade = sorted(
            [
                {"decade": d, "avg_rating": round(sum(rs) / len(rs), 2)}
                for d, rs in decade_ratings.items()
            ],
            key=lambda x: x["decade"],
        )

        guesses = (
            self.db.query(NominationGuess)
            .filter(NominationGuess.guessing_user_id == user.id)
            .all()
        )
        total_guesses = len(guesses)
        correct_guesses = sum(1 for g in guesses if g.correct)
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

    # ==================== DELETE ====================

    def delete_user(self, user_id: int):
        """Delete a user account.

        Pending nominations are removed from their groups. Already-selected
        nominations are preserved but anonymized (added_by set to NULL).
        Reviews and nomination guesses are deleted. Created groups remain.

        Raises:
            HTTPException 404: If user not found
        """
        self.get_user_by_id(user_id)

        # Delete nomination guesses made by or about this user
        self.db.query(NominationGuess).filter(
            (NominationGuess.guessing_user_id == user_id)
            | (NominationGuess.guessed_user_id == user_id)
        ).delete(synchronize_session=False)

        # Delete reviews written by this user
        self.db.query(Review).filter(
            Review.user_id == user_id
        ).delete(synchronize_session=False)

        # Remove pending nominations from groups
        self.db.query(GroupAlbum).filter(
            GroupAlbum.added_by == user_id,
            GroupAlbum.selected_date.is_(None),
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

    @staticmethod
    def _access_token_data(user: User) -> dict:
        return {"sub": str(user.id), "email": user.email}

    @staticmethod
    def _refresh_token_data(user: User) -> dict:
        return {"sub": str(user.id)}

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

    def refresh(self, refresh_token: str) -> LoginResponse:
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

        # Verify user existence
        try:
            user = self.get_user_by_id(int(user_id))
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            ) from None

        # Create new access token
        new_access_token = security.create_access_token(data=self._access_token_data(user))

        return LoginResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
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

    def get_user_albums_added(self, user_id: int) -> list[dict]:
        """Get all albums added by user across all groups"""
        user = self.get_user_by_id(user_id)

        # Return list of (group, album, added_at) tuples
        result = []
        for group_album in user.added_albums:
            result.append(
                {
                    "group": group_album.group,
                    "album": group_album.albums,
                    "added_at": group_album.added_at,
                    "status": group_album.status,
                }
            )
        return result

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

        return {
            "total_groups": len(user.groups),
            "created_groups": len(user.created_groups),
            "total_reviews": len(user.reviews),
            "albums_added": len(user.added_albums),
            "has_spotify": user.spotify_connection is not None,
            "member_since": user.created_at,
        }

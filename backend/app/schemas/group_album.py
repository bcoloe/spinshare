"""Schemas for the GroupAlbum workflow: daily selection, dealing, guessing, and instant reveal."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.album import GroupAlbumResponse


class NominationGuessCreate(BaseModel):
    guessed_user_id: int | None  # None means guessing "chaos" (outside-of-group pick)


class NominationGuessResponse(BaseModel):
    id: int
    group_album_id: int
    guessing_user_id: int
    guessed_user_id: int | None  # None for chaos guesses
    correct: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckGuessResponse(BaseModel):
    """Instant feedback returned when a user submits their nomination guess."""

    guess: NominationGuessResponse
    correct: bool
    nominator_user_ids: list[int]
    nominator_usernames: list[str]
    is_chaos_selection: bool
    guessed_username: str | None = None  # None for chaos guesses


class NominationCountResponse(BaseModel):
    pending_count: int
    today_count: int = 0


class GuessOptionUser(BaseModel):
    user_id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None


class GuessOptionsResponse(BaseModel):
    """Deterministic, capped list of users to present as nomination-guess candidates."""

    options: list[GuessOptionUser]
    has_chaos_option: bool


class DealRollResponse(BaseModel):
    """Result of rolling the dice in a dealer-mode group."""

    deal: GroupAlbumResponse
    rolls_used_today: int
    rolls_per_day: int
    pool_remaining: int


class DealsTodayResponse(BaseModel):
    """The caller's deals revealed today plus roll accounting."""

    deals: list[GroupAlbumResponse]
    rolls_used_today: int
    rolls_per_day: int
    pool_remaining: int

"""Schemas for the GroupAlbum workflow: daily selection, guessing, and instant reveal."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class NominationCountResponse(BaseModel):
    pending_count: int
    today_count: int = 0


class GuessOptionUser(BaseModel):
    user_id: int
    username: str
    display_name: str | None = None


class GuessOptionsResponse(BaseModel):
    """Deterministic, capped list of users to present as nomination-guess candidates."""

    options: list[GuessOptionUser]
    has_chaos_option: bool

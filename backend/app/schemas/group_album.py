"""Schemas for the GroupAlbum workflow: daily selection, guessing, and instant reveal."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NominationGuessCreate(BaseModel):
    guessed_user_id: int


class NominationGuessResponse(BaseModel):
    id: int
    group_album_id: int
    guessing_user_id: int
    guessed_user_id: int
    correct: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CheckGuessResponse(BaseModel):
    """Instant feedback returned when a user submits their nomination guess."""

    guess: NominationGuessResponse
    correct: bool
    nominator_user_ids: list[int]
    nominator_usernames: list[str]


class NominationCountResponse(BaseModel):
    pending_count: int


class GuessOptionUser(BaseModel):
    user_id: int
    username: str


class GuessOptionsResponse(BaseModel):
    """Deterministic, capped list of users to present as nomination-guess candidates."""

    options: list[GuessOptionUser]

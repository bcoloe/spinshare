"""Schemas for the GroupAlbum workflow: selection, guessing, and nomination reveal."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SelectAlbumRequest(BaseModel):
    """Request to select a group album as the daily spin.
    If group_album_id is omitted, a random pending album is chosen.
    """

    group_album_id: int | None = None


class NominationGuessCreate(BaseModel):
    guessed_user_id: int


class NominationGuessResponse(BaseModel):
    id: int
    group_album_id: int
    guessing_user_id: int
    guessed_user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GuessResultResponse(BaseModel):
    """One member's guess result after the nomination is revealed."""

    guessing_user_id: int
    guessing_username: str
    guessed_user_id: int
    guessed_username: str
    correct: bool


class NominationRevealResponse(BaseModel):
    """Full reveal: who nominated the album, and how each member's guess fared."""

    group_album_id: int
    nominator_user_id: int
    nominator_username: str
    guesses: list[GuessResultResponse]

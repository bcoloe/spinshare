"""Schemas for group and album statistics."""

from pydantic import BaseModel


class UserGuessStatsResponse(BaseModel):
    user_id: int
    group_id: int
    total_guesses: int
    correct_guesses: int
    accuracy: float


class MemberGuessResult(BaseModel):
    guessing_user_id: int
    guessing_username: str
    guessed_user_id: int
    guessed_username: str
    correct: bool


class AlbumGuessStatsResponse(BaseModel):
    group_album_id: int
    nominator_user_id: int
    nominator_username: str
    total_guesses: int
    correct_guesses: int
    guesses: list[MemberGuessResult]


class AlbumReviewStatsResponse(BaseModel):
    album_id: int
    review_count: int
    avg_rating: float | None
    min_rating: float | None
    max_rating: float | None

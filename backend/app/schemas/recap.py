"""Schemas for the weekly group recap.

``RecapData`` is the frozen payload persisted in ``GroupRecap.data``; the other
models wrap it for API responses and the login pop-up.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LeaderboardEntry(BaseModel):
    username: str
    count: int


class RecapAlbumCard(BaseModel):
    album_id: int
    spotify_album_id: str | None = None
    title: str
    artist: str | None = None
    cover_url: str | None = None
    avg_rating: float
    review_count: int
    weighted_score: float


class MemberGuessAccuracy(BaseModel):
    username: str
    total: int
    correct: int
    pct: float


class GuessAccuracy(BaseModel):
    total_guesses: int
    correct_guesses: int
    pct: float
    per_member: list[MemberGuessAccuracy]


class RecapData(BaseModel):
    """The immutable computed payload stored on a recap."""

    albums_added: list[LeaderboardEntry]
    albums_reviewed: list[LeaderboardEntry]
    favorite_album: RecapAlbumCard | None
    least_favorite_album: RecapAlbumCard | None
    guess_accuracy: GuessAccuracy


class RecapResponse(BaseModel):
    id: int
    group_id: int
    week_start: date
    week_end: date
    generated_at: datetime
    data: RecapData
    seen: bool

    model_config = ConfigDict(from_attributes=True)


class RecapSummary(BaseModel):
    """Lightweight recap descriptor for the pending-recaps pop-up and lists."""

    id: int
    group_id: int
    group_name: str
    week_start: date
    week_end: date

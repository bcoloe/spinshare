"""Schemas for the anonymous-visitor public daily draw."""

from datetime import date

from pydantic import BaseModel

from app.schemas.album import GroupAlbumResponse


class PublicSpinResponse(BaseModel):
    draw_date: date
    albums: list[GroupAlbumResponse]

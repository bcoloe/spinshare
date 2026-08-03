# backend/app/routers/artists.py

from app.dependencies import get_artist_service, get_current_user_optional
from app.models import User
from app.schemas.artist import ArtistOverviewResponse
from app.services.artist_service import ArtistService
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/artists", tags=["artists"])


@router.get("/overview", response_model=ArtistOverviewResponse)
def get_artist_overview(
    name: str = Query(..., min_length=1),
    _current_user: User | None = Depends(get_current_user_optional),
    artist_service: ArtistService = Depends(get_artist_service),
):
    """Return aggregate stats for an artist across their nominated albums.

    The artist is matched case-insensitively by name. Publicly readable — no
    authentication required. Returns 404 if the artist has no nominated albums.
    """
    return artist_service.get_artist_overview(name)

# backend/app/routers/public.py

from app.dependencies import get_public_spin_service
from app.schemas.public_spin import PublicSpinResponse
from app.services.public_spin_service import PublicSpinService
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/spin", response_model=PublicSpinResponse)
def get_public_spin(svc: PublicSpinService = Depends(get_public_spin_service)):
    """Today's shared 3-album draw shown to anonymous visitors. Same for
    everyone, cached for the day, no authentication required."""
    return svc.get_or_create_todays_draw()

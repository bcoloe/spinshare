# backend/app/routers/notifications.py

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_notification_service
from app.models import User
from app.schemas.notification import NotificationResponse
from app.services.notification_service import NotificationService

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationResponse])
def get_unread_notifications(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
):
    return notification_service.get_unread(current_user)


@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
):
    notification_service.mark_all_read(current_user)


@router.get("/notifications/history", response_model=list[NotificationResponse])
def get_notification_history(
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
):
    return notification_service.get_all(current_user)


@router.post("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    notification_service: NotificationService = Depends(get_notification_service),
):
    return notification_service.mark_read(notification_id, current_user)

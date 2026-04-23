# backend/app/routers/invitations.py

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_group_service, get_invitation_service
from app.models import User
from app.schemas.invitation import InvitationCreate, InvitationResponse
from app.services.group_service import GroupService
from app.services.invitation_service import InvitationService

router = APIRouter(tags=["invitations"])


@router.post(
    "/groups/{group_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_invitation(
    group_id: int,
    data: InvitationCreate,
    current_user: User = Depends(get_current_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
    group_service: GroupService = Depends(get_group_service),
):
    return invitation_service.create_invitation(group_id, data, current_user, group_service)


@router.get(
    "/groups/{group_id}/invitations",
    response_model=list[InvitationResponse],
)
def list_invitations(
    group_id: int,
    current_user: User = Depends(get_current_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
    group_service: GroupService = Depends(get_group_service),
):
    return invitation_service.get_group_invitations(group_id, current_user, group_service)


@router.delete(
    "/groups/{group_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_invitation(
    group_id: int,
    invitation_id: int,
    current_user: User = Depends(get_current_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
    group_service: GroupService = Depends(get_group_service),
):
    invitation_service.revoke_invitation(invitation_id, current_user, group_service)


@router.get(
    "/invitations/pending",
    response_model=list[InvitationResponse],
)
def get_my_pending_invitations(
    current_user: User = Depends(get_current_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
):
    return invitation_service.get_user_pending_invitations(current_user)


@router.get(
    "/invitations/{token}",
    response_model=InvitationResponse,
)
def get_invitation(
    token: str,
    invitation_service: InvitationService = Depends(get_invitation_service),
):
    return invitation_service.get_invitation_by_token(token)


@router.post(
    "/invitations/{token}/accept",
    response_model=InvitationResponse,
)
def accept_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
    group_service: GroupService = Depends(get_group_service),
):
    return invitation_service.accept_invitation(token, current_user, group_service)


@router.post(
    "/invitations/{token}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
)
def decline_invitation(
    token: str,
    current_user: User = Depends(get_current_user),
    invitation_service: InvitationService = Depends(get_invitation_service),
):
    invitation_service.decline_invitation(token, current_user)

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_group_service, get_invite_link_service
from app.models import User
from app.schemas.invite_link import InviteLinkResponse
from app.services.group_service import GroupService
from app.services.invite_link_service import InviteLinkService

router = APIRouter(tags=["invite-links"])


@router.get(
    "/groups/{group_id}/invite-link",
    response_model=InviteLinkResponse | None,
)
def get_invite_link(
    group_id: int,
    current_user: User = Depends(get_current_user),
    invite_link_service: InviteLinkService = Depends(get_invite_link_service),
    group_service: GroupService = Depends(get_group_service),
):
    return invite_link_service.get_link(group_id, current_user, group_service)


@router.post(
    "/groups/{group_id}/invite-link",
    response_model=InviteLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_or_rotate_invite_link(
    group_id: int,
    current_user: User = Depends(get_current_user),
    invite_link_service: InviteLinkService = Depends(get_invite_link_service),
    group_service: GroupService = Depends(get_group_service),
):
    return invite_link_service.create_or_rotate_link(group_id, current_user, group_service)


@router.delete(
    "/groups/{group_id}/invite-link",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_invite_link(
    group_id: int,
    current_user: User = Depends(get_current_user),
    invite_link_service: InviteLinkService = Depends(get_invite_link_service),
    group_service: GroupService = Depends(get_group_service),
):
    invite_link_service.revoke_link(group_id, current_user, group_service)


@router.get(
    "/join/{token}",
    response_model=InviteLinkResponse,
)
def get_invite_link_by_token(
    token: str,
    invite_link_service: InviteLinkService = Depends(get_invite_link_service),
):
    return invite_link_service.get_link_by_token(token)


@router.post(
    "/join/{token}/accept",
    response_model=InviteLinkResponse,
)
def accept_invite_link(
    token: str,
    current_user: User = Depends(get_current_user),
    invite_link_service: InviteLinkService = Depends(get_invite_link_service),
    group_service: GroupService = Depends(get_group_service),
):
    return invite_link_service.accept_link(token, current_user, group_service)

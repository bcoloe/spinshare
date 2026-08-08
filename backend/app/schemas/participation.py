"""Schemas for the priority-pick participation feature."""

from pydantic import BaseModel, ConfigDict

from app.schemas.album import GroupAlbumResponse


class PriorityPickRequest(BaseModel):
    """Body for promoting one of the caller's pending nominations."""

    group_album_id: int


class ParticipationResponse(BaseModel):
    """The caller's priority-pick standing in a group.

    threshold is None when the feature is disabled for the group. can_pick is
    True when the caller has enough credits and no pick is currently queued.

    When the caller has a pick queued, queue_position is its 1-based place in line
    (draws consume picks in queue-time order) and queue_size is the total number of
    picks queued in the group; both describe the shared priority queue, not just the
    caller. queue_position is None when the caller has no pick standing.
    """

    threshold: int | None = None
    credits: int = 0
    can_pick: bool = False
    pending_pick: GroupAlbumResponse | None = None
    queue_position: int | None = None
    queue_size: int = 0

    model_config = ConfigDict(from_attributes=True)

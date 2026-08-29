import logging
import os
import sys
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.realtime.connection_manager import manager as connection_manager
from app.routers import groups, users
from app.routers.admin import router as admin_router
from app.routers.albums import albums_router, group_albums_router
from app.routers.artists import router as artists_router
from app.routers.explore import router as explore_router
from app.routers.feedback import router as feedback_router
from app.routers.group_albums import router as group_album_workflow_router
from app.routers.invitations import router as invitations_router
from app.routers.invite_links import router as invite_links_router
from app.routers.link_reports import router as link_reports_router
from app.routers.messages import router as messages_router
from app.routers.notifications import router as notifications_router
from app.routers.public import router as public_router
from app.routers.recaps import router as recaps_router
from app.routers.stats import router as stats_router
from app.routers.ws import router as ws_router

settings = get_settings()

logger = logging.getLogger(__name__)


def configured_worker_count(
    argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None
) -> int:
    """How many uvicorn workers this process was launched with.

    Reads the command line the way uvicorn does, falling back to
    ``WEB_CONCURRENCY``, and defaulting to one. Anything unparseable counts as
    one: this exists to raise an alarm, not to become a new way to fail to boot.
    """
    argv = list(sys.argv if argv is None else argv)
    env = os.environ if env is None else env

    for index, arg in enumerate(argv):
        value = None
        if arg.startswith("--workers="):
            value = arg.split("=", 1)[1]
        elif arg == "--workers" and index + 1 < len(argv):
            value = argv[index + 1]
        if value is not None:
            try:
                return int(value)
            except ValueError:
                return 1

    try:
        return int(env.get("WEB_CONCURRENCY", 1))
    except ValueError:
        return 1


def warn_if_sharded(workers: int) -> bool:
    """Log an alarm when more than one worker will serve chat. Returns True if so.

    Presence and message fan-out are held in process memory (see
    ``app/realtime/connection_manager.py``), so a second worker is an island:
    members whose sockets land on different workers never see each other online
    and never receive each other's messages. Nothing about that failure is
    visible from the outside — the room simply looks empty.

    The deployed unit file drifted to ``--workers 2`` once already and ran that
    way unnoticed, which is why this is asserted at startup rather than left to
    code review. It warns rather than exits: a chat room that is split is bad,
    but an API that refuses to boot is worse.
    """
    if workers <= 1:
        return False

    logger.error(
        "Starting with %d uvicorn workers, but chat presence and message fan-out "
        "are per-process. Members whose sockets land on different workers will "
        "not see each other online and will not receive each other's messages. "
        "Restart with --workers 1, or move fan-out to a shared broker.",
        workers,
    )
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    warn_if_sharded(configured_worker_count())
    # Hand the connection manager a reference to the serving event loop. Route
    # handlers are sync `def` (threadpool-executed) and need it to schedule chat
    # fanout back onto the loop that owns the sockets.
    connection_manager.bind_loop()
    yield


app = FastAPI(title="SpinShare API", lifespan=lifespan)


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(groups.router)
app.include_router(admin_router)
# Registered before albums_router so /albums/{id}/link-reports isn't shadowed by
# any broader /albums/{id}/... pattern there.
app.include_router(link_reports_router)
app.include_router(albums_router)
app.include_router(artists_router)
# Workflow router registered first so /selected and /select beat /{group_album_id}
app.include_router(group_album_workflow_router)
app.include_router(group_albums_router)
app.include_router(invitations_router)
app.include_router(invite_links_router)
app.include_router(notifications_router)
app.include_router(stats_router)
app.include_router(recaps_router)
app.include_router(explore_router)
app.include_router(feedback_router)
app.include_router(public_router)
app.include_router(messages_router)
app.include_router(ws_router)

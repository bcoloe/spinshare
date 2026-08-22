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


@asynccontextmanager
async def lifespan(app: FastAPI):
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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.routers import groups, users
from app.routers.albums import albums_router, group_albums_router
from app.routers.group_albums import router as group_album_workflow_router
from app.routers.invite_links import router as invite_links_router
from app.routers.invitations import router as invitations_router
from app.routers.notifications import router as notifications_router
from app.routers.explore import router as explore_router
from app.routers.feedback import router as feedback_router
from app.routers.stats import router as stats_router

settings = get_settings()

app = FastAPI(title="SpinShare API")


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
app.include_router(albums_router)
# Workflow router registered first so /selected and /select beat /{group_album_id}
app.include_router(group_album_workflow_router)
app.include_router(group_albums_router)
app.include_router(invitations_router)
app.include_router(invite_links_router)
app.include_router(notifications_router)
app.include_router(stats_router)
app.include_router(explore_router)
app.include_router(feedback_router)

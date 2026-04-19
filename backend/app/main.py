from fastapi import FastAPI

from app.routers import groups, users
from app.routers.albums import albums_router, group_albums_router
from app.routers.group_albums import router as group_album_workflow_router

app = FastAPI(title="SpinShare API")

app.include_router(users.router)
app.include_router(groups.router)
app.include_router(albums_router)
# Workflow router registered first so /selected and /select beat /{group_album_id}
app.include_router(group_album_workflow_router)
app.include_router(group_albums_router)

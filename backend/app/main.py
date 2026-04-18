from fastapi import FastAPI

from app.routers import groups, users
from app.routers.albums import albums_router, group_albums_router

app = FastAPI(title="SpinShare API")

app.include_router(users.router)
app.include_router(groups.router)
app.include_router(albums_router)
app.include_router(group_albums_router)

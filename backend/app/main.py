from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import groups, users
from app.routers.albums import albums_router, group_albums_router

app = FastAPI(title="SpinShare API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(groups.router)
app.include_router(albums_router)
app.include_router(group_albums_router)

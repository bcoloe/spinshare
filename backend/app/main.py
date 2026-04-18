from fastapi import FastAPI

from app.routers import groups, users

app = FastAPI(title="SpinShare API")

app.include_router(users.router)
app.include_router(groups.router)

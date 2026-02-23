from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import ws as ws_router
from app.api.v1 import auth as auth_router
from app.api.v1 import friends as friends_router
from app.api.v1 import public_wishlists as public_wishlists_router
from app.api.v1 import wishlists as wishlists_router
from app.db.base import Base
from app.db.session import engine


app = FastAPI(title=settings.project_name)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ws_router.router)
app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(wishlists_router.router, prefix="/api/v1")
app.include_router(friends_router.router, prefix="/api/v1")
app.include_router(public_wishlists_router.router, prefix="/api/v1")

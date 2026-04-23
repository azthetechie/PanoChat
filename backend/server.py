"""Main FastAPI app."""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os  # noqa: E402
import logging  # noqa: E402
from fastapi import FastAPI, APIRouter  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from db import init_db, ensure_indexes, close_db  # noqa: E402
from seed import seed_admin_and_defaults  # noqa: E402
from routes.auth_routes import router as auth_router  # noqa: E402
from routes.users import router as users_router  # noqa: E402
from routes.channels import router as channels_router  # noqa: E402
from routes.messages import router as messages_router  # noqa: E402
from routes.uploads import router as uploads_router  # noqa: E402
from routes.giphy import router as giphy_router  # noqa: E402
from routes.websocket import router as websocket_router  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("server")

app = FastAPI(title="Panorama Comms")

# Build CORS origin list
_origins_env = os.environ.get("CORS_ORIGINS", "*").strip()
frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if _origins_env == "*" or not _origins_env:
    # When credentials are required, "*" is not allowed. Fall back to FRONTEND_URL if set.
    if frontend_url:
        allow_origins = [frontend_url]
    else:
        allow_origins = ["http://localhost:3000"]
else:
    allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]
    if frontend_url and frontend_url not in allow_origins:
        allow_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "panorama-comms", "status": "ok"}


@api_router.get("/health")
async def health():
    return {"status": "ok"}


api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(channels_router)
api_router.include_router(messages_router)
api_router.include_router(uploads_router)
api_router.include_router(giphy_router)
api_router.include_router(websocket_router)  # /api/ws

app.include_router(api_router)


@app.on_event("startup")
async def on_startup():
    init_db()
    await ensure_indexes()
    await seed_admin_and_defaults()
    logger.info("Startup complete. Admin seeded. Indexes ensured.")


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()

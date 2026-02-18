from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, players, plans, shares, teams, user, team, threads, dm, health
from app.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.ws import init_redis
    init_redis()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="BuzzerBeater Manager API",
    description="Backend API for BuzzerBeater Manager application",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# New routers matching Spring API paths (for Angular compatibility)
app.include_router(user.router, prefix="/api/v1/user", tags=["User"])
app.include_router(team.router, prefix="/api/v1/team", tags=["Team"])

# Original routers (keep for backwards compatibility)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(teams.router, prefix="/api/v1/teams", tags=["Teams"])
app.include_router(players.router, prefix="/api/v1/players", tags=["Players"])
app.include_router(shares.router, prefix="/api/v1/shares", tags=["Player Sharing"])
app.include_router(threads.router, prefix="/api/v1/threads", tags=["Player Threads"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["Training Plans"])
app.include_router(dm.router, prefix="/api/v1/dm", tags=["Direct Messages"])
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/v1/admin/sync-all-rosters")
async def trigger_roster_sync():
    """Manually trigger roster sync for all users (admin endpoint)."""
    from app.scheduler import sync_all_rosters
    import asyncio
    # Run in background so we don't timeout
    asyncio.create_task(sync_all_rosters())
    return {"success": True, "message": "Roster sync started in background"}

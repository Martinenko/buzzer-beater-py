from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, players, shares, teams, user, team

settings = get_settings()

app = FastAPI(
    title="BuzzerBeater Manager API",
    description="Backend API for BuzzerBeater Manager application",
    version="1.0.0"
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


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

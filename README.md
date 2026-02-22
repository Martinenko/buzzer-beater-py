# BuzzerBeater Manager - Python Backend

FastAPI backend for BuzzerBeater Manager application.

## Requirements

- Python 3.11+
- PostgreSQL (Supabase)

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. Run database migrations:
```bash
alembic upgrade head
```

5. Run development server:
```bash
uvicorn app.main:app --reload --port 8000
```

## Google Drive Backups (Railway)

This project can run automated MySQL backups to Google Drive using `rclone`.

Required env vars:
- `RCLONE_CONFIG_B64`: Base64-encoded rclone config (preferred)
- `RCLONE_REMOTE_NAME`: Remote name in the rclone config (default: `gdrive`)
- `RCLONE_REMOTE_DIR`: Folder name in Drive (default: `bbscout-backups`)
- `RCLONE_RETENTION_COUNT`: How many backups to keep (default: `7`)
- `BACKUP_CRON_SCHEDULE`: Cron schedule in UTC (default: `0 3 * * *`)

The backup script uses `DATABASE_URL` to connect and dumps the database daily.

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
app/
├── main.py           # FastAPI application
├── config.py         # Settings/configuration
├── database.py       # Database connection
├── dependencies.py   # Dependency injection
├── models/           # SQLAlchemy models
├── schemas/          # Pydantic schemas
├── routers/          # API routes
└── services/         # Business logic
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - Login with BuzzerBeater credentials
- `POST /api/v1/auth/logout` - Logout

### Teams
- `GET /api/v1/teams/` - Get user's teams
- `POST /api/v1/teams/switch/{team_id}` - Switch active team
- `GET /api/v1/teams/economy` - Get team economy

### Players
- `GET /api/v1/players/roster` - Get team roster
- `POST /api/v1/players/sync` - Sync roster from BuzzerBeater

### Player Sharing
- `POST /api/v1/shares/` - Share players with another user
- `GET /api/v1/shares/received` - Get players shared with me
- `GET /api/v1/shares/sent` - Get players I shared
- `DELETE /api/v1/shares/{share_id}` - Remove a share
- `GET /api/v1/shares/users/search` - Search users for sharing

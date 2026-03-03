from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.season import Season
from app.routers.user import get_current_user_from_cookie
from app.services.bb_api import BBApiClient

router = APIRouter()


@router.get("/seasons")
async def get_seasons(
    request: Request,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Global seasons endpoint for UI dropdown.
    Refresh from BB API when DB is empty or no active season exists for today.
    """
    try:
        user = await get_current_user_from_cookie(request, db)

        if not user.bb_key:
            return []

        today = datetime.now(timezone.utc).date()

        stmt = select(Season).order_by(Season.number.desc())
        result = await db.execute(stmt)
        cached_seasons = result.scalars().all()

        def _is_active(season_row: Season) -> bool:
            if season_row.start_date and season_row.end_date:
                return season_row.start_date <= today <= season_row.end_date
            if season_row.start_date and not season_row.end_date:
                return season_row.start_date <= today
            if season_row.end_date and not season_row.start_date:
                return today <= season_row.end_date
            return False

        has_active_season = any(_is_active(s) for s in cached_seasons)
        should_refresh_from_bb = refresh or len(cached_seasons) == 0 or not has_active_season

        if should_refresh_from_bb:
            bb_client = BBApiClient(user.bb_key)
            seasons_data = await bb_client.get_seasons(username=user.login_name)

            if seasons_data:
                def _parse_bb_date(value: Optional[str]):
                    if not value:
                        return None
                    try:
                        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                    except ValueError:
                        return None

                for season_data in seasons_data:
                    season_num = season_data.get("number")
                    if season_num is None:
                        continue

                    stmt = select(Season).where(Season.number == season_num)
                    existing_season = (await db.execute(stmt)).scalar_one_or_none()

                    parsed_start_date = _parse_bb_date(season_data.get("startDate"))
                    parsed_end_date = _parse_bb_date(season_data.get("endDate"))

                    if existing_season:
                        existing_season.start_date = parsed_start_date
                        existing_season.end_date = parsed_end_date
                    else:
                        db.add(
                            Season(
                                number=season_num,
                                start_date=parsed_start_date,
                                end_date=parsed_end_date,
                            )
                        )

                await db.commit()

                stmt = select(Season).order_by(Season.number.desc())
                result = await db.execute(stmt)
                cached_seasons = result.scalars().all()
            elif len(cached_seasons) == 0:
                raise HTTPException(
                    status_code=502,
                    detail="BB seasons API returned no data. Please re-login and try again."
                )

        return [
            {
                "season": s.number,
                "number": s.number,
                "startDate": s.start_date.isoformat() if s.start_date else None,
                "endDate": s.end_date.isoformat() if s.end_date else None,
            }
            for s in cached_seasons
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading seasons: {str(e)}")

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from pydantic import BaseModel
class FetchNTMatchesRequest(BaseModel):
    start_match_id: int
    fetch_type: str = "forward"
    batch_size: int = 10
    pause_seconds: int = 5
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
import asyncio

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_snapshot import PlayerSnapshot
from app.services.bb_api import BBApiClient
from app.models.match_boxscore import MatchBoxscore

router = APIRouter()

ADMIN_EMAIL = "martinenko.ivan@gmail.com"  # Change to your admin email


def _parse_iso_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _get_bb_week_for_date(match_datetime: datetime | None) -> tuple[int, int]:
    reference = match_datetime or datetime.now(timezone.utc)
    if reference.tzinfo is not None:
        reference = reference.astimezone(timezone.utc).replace(tzinfo=None)
    days_since_friday = (reference.weekday() - 4) % 7
    start_of_week = reference - timedelta(days=days_since_friday)
    iso = start_of_week.isocalendar()
    return iso[0], iso[1]


async def _upsert_nt_player_profile(
    db: AsyncSession,
    nt_player: dict,
    nt_team: dict,
    nt_year: int,
    nt_week: int,
):
    bb_player_id = nt_player.get("player_id")
    if not bb_player_id:
        return

    first_name = (nt_player.get("first_name") or "").strip()
    last_name = (nt_player.get("last_name") or "").strip()
    full_name = " ".join([part for part in [first_name, last_name] if part]).strip() or f"Player {bb_player_id}"

    nt_team_id = nt_team.get("team_id")
    nt_team_name = nt_team.get("team_name")

    mapped_team_uuid = None
    if nt_team_id:
        mapped_team_result = await db.execute(select(Team).where(Team.team_id == nt_team_id))
        mapped_team = mapped_team_result.scalar_one_or_none()
        mapped_team_uuid = mapped_team.id if mapped_team else None

    player_result = await db.execute(select(Player).where(Player.player_id == bb_player_id))
    player = player_result.scalar_one_or_none()

    if player:
        if nt_team_name:
            player.team_name = nt_team_name
        if mapped_team_uuid:
            player.current_team_id = mapped_team_uuid
    else:
        player = Player(
            player_id=bb_player_id,
            name=full_name,
            country="Unknown",
            team_name=nt_team_name,
            age=None,
            height=0,
            potential=0,
            game_shape=0,
            salary=None,
            dmi=None,
            best_position=None,
            active=False,
            current_team_id=mapped_team_uuid,
        )
        db.add(player)
        await db.flush()

    if not mapped_team_uuid:
        return

    existing_snapshot_result = await db.execute(
        select(PlayerSnapshot).where(
            PlayerSnapshot.player_id == player.id,
            PlayerSnapshot.year == nt_year,
            PlayerSnapshot.week_of_year == nt_week,
        )
    )
    existing_snapshot = existing_snapshot_result.scalar_one_or_none()
    if existing_snapshot:
        existing_snapshot.played_nt_match = True
        return

    db.add(
        PlayerSnapshot(
            player_id=player.id,
            bb_player_id=player.player_id,
            team_id=mapped_team_uuid,
            year=nt_year,
            week_of_year=nt_week,
            name=player.name,
            country=player.country,
            age=player.age,
            height=player.height,
            potential=player.potential,
            game_shape=player.game_shape,
            salary=player.salary,
            dmi=player.dmi,
            best_position=player.best_position,
            jump_shot=player.jump_shot,
            jump_range=player.jump_range,
            outside_defense=player.outside_defense,
            handling=player.handling,
            driving=player.driving,
            passing=player.passing,
            inside_shot=player.inside_shot,
            inside_defense=player.inside_defense,
            rebounding=player.rebounding,
            shot_blocking=player.shot_blocking,
            stamina=player.stamina,
            free_throws=player.free_throws,
            experience=player.experience,
            played_nt_match=True,
        )
    )

async def get_admin_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    from app.routers.user import get_current_user_from_cookie
    user = await get_current_user_from_cookie(request, db)
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access only")
    return user

@router.post("/admin/fetch-nt-matches")
async def fetch_nt_matches(
    request: Request,
    body: FetchNTMatchesRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin endpoint to fetch NT matches in batch. Only accessible to admin user.
    Params:
      - start_season, end_season: restrict by season (optional)
      - batch_size: number of matches per batch
      - pause_seconds: pause between batches
      - start_match_id: match ID to start from (required)
      - direction: 'forward' or 'backward'
    """
    admin_user = await get_admin_user(request, db)
    if not body.start_match_id:
        raise HTTPException(status_code=400, detail="start_match_id required")
    if body.fetch_type not in ("forward", "backward", "single"):
        raise HTTPException(status_code=400, detail="fetch_type must be 'forward', 'backward', or 'single'")
    if not admin_user.bb_key or not admin_user.login_name:
        raise HTTPException(status_code=400, detail="Admin user is missing BB credentials")

    bb_client = BBApiClient(admin_user.bb_key)
    fetched = 0
    match_id = body.start_match_id
    stop = False
    results = []
    debug = []
    direction = body.fetch_type if body.fetch_type in ("forward", "backward") else "forward"
    batch_size = body.batch_size
    pause_seconds = body.pause_seconds

    while not stop:
        if body.fetch_type == "single":
            ids = [match_id]
        else:
            ids = []
            for _ in range(batch_size):
                ids.append(match_id)
                match_id = match_id + 1 if direction == "forward" else match_id - 1
        for mid in ids:
            dbg = {"match_id": mid}
            try:
                # Skip _raw_boxscore_xml (not needed)
                boxscore = await bb_client.get_boxscore(mid, username=admin_user.login_name)
                dbg["boxscore_keys"] = list(boxscore.keys()) if boxscore else None
                dbg["boxscore_type"] = boxscore.get("type") if boxscore else None
                match_type = (boxscore.get("type") or "").lower()
                is_nt_match = (
                    "nt" in match_type
                    or "national" in match_type
                    or "u21" in match_type
                )
                if not boxscore or not is_nt_match:
                    dbg["skipped"] = True
                    debug.append(dbg)
                    continue
                nt_match_dt = _parse_iso_datetime(boxscore.get("start_time"))
                nt_year, nt_week = _get_bb_week_for_date(nt_match_dt)
                # Save to NT tables if not exists
                from app.models.nt_match_boxscore import NTMatchBoxscore, NTMatchTeamBoxscore, NTMatchPlayerBoxscore
                exists = await db.execute(select(NTMatchBoxscore).where(NTMatchBoxscore.match_id == mid))
                if not exists.scalar_one_or_none():
                    match_obj = NTMatchBoxscore(
                        match_id=mid,
                        match_type=boxscore.get("type"),
                        start_time=_parse_iso_datetime(boxscore.get("start_time")),
                        end_time=_parse_iso_datetime(boxscore.get("end_time")),
                        retrieved_at=datetime.utcnow(),
                        # Add more fields as needed
                    )
                    db.add(match_obj)
                    await db.commit()
                    # Insert teams
                    for is_home, team_key in [(True, "home_team"), (False, "away_team")]:
                        team = boxscore.get(team_key)
                        if not team:
                            continue
                        team_obj = NTMatchTeamBoxscore(
                            match_id=mid,
                            is_home=is_home,
                            team_id=team.get("team_id"),
                            team_name=team.get("team_name"),
                            short_name=team.get("short_name"),
                            score=team.get("score"),
                            partial_q1=team.get("score_partials")[0] if team.get("score_partials") and len(team.get("score_partials")) > 0 else None,
                            partial_q2=team.get("score_partials")[1] if team.get("score_partials") and len(team.get("score_partials")) > 1 else None,
                            partial_q3=team.get("score_partials")[2] if team.get("score_partials") and len(team.get("score_partials")) > 2 else None,
                            partial_q4=team.get("score_partials")[3] if team.get("score_partials") and len(team.get("score_partials")) > 3 else None,
                            off_strategy=team.get("off_strategy"),
                            def_strategy=team.get("def_strategy"),
                            effort=team.get("effort"),
                            ratings_outside_scoring=team.get("ratings", {}).get("outside_scoring"),
                            ratings_inside_scoring=team.get("ratings", {}).get("inside_scoring"),
                            ratings_outside_defense=team.get("ratings", {}).get("outside_defense"),
                            ratings_inside_defense=team.get("ratings", {}).get("inside_defense"),
                            ratings_rebounding=team.get("ratings", {}).get("rebounding"),
                            ratings_offensive_flow=team.get("ratings", {}).get("offensive_flow"),
                            efficiency_pg=team.get("efficiency", {}).get("pg"),
                            efficiency_sg=team.get("efficiency", {}).get("sg"),
                            efficiency_sf=team.get("efficiency", {}).get("sf"),
                            efficiency_pf=team.get("efficiency", {}).get("pf"),
                            efficiency_c=team.get("efficiency", {}).get("c"),
                            gdp_focus=team.get("gdp_focus"),
                            gdp_pace=team.get("gdp_pace"),
                            gdp_focus_hit=team.get("gdp_focus_hit"),
                            gdp_pace_hit=team.get("gdp_pace_hit"),
                            totals_fgm=team.get("boxscore", {}).get("totals", {}).get("fgm"),
                            totals_fga=team.get("boxscore", {}).get("totals", {}).get("fga"),
                            totals_tpm=team.get("boxscore", {}).get("totals", {}).get("tpm"),
                            totals_tpa=team.get("boxscore", {}).get("totals", {}).get("tpa"),
                            totals_ftm=team.get("boxscore", {}).get("totals", {}).get("ftm"),
                            totals_fta=team.get("boxscore", {}).get("totals", {}).get("fta"),
                            totals_oreb=team.get("boxscore", {}).get("totals", {}).get("oreb"),
                            totals_reb=team.get("boxscore", {}).get("totals", {}).get("reb"),
                            totals_ast=team.get("boxscore", {}).get("totals", {}).get("ast"),
                            totals_to=team.get("boxscore", {}).get("totals", {}).get("to"),
                            totals_stl=team.get("boxscore", {}).get("totals", {}).get("stl"),
                            totals_blk=team.get("boxscore", {}).get("totals", {}).get("blk"),
                            totals_pf=team.get("boxscore", {}).get("totals", {}).get("pf"),
                            totals_pts=team.get("boxscore", {}).get("totals", {}).get("pts"),
                        )
                        db.add(team_obj)
                        await db.commit()
                        # Insert players
                        for player in team.get("boxscore", {}).get("players", []):
                            player_obj = NTMatchPlayerBoxscore(
                                match_id=mid,
                                team_id=team.get("team_id"),
                                player_id=player.get("player_id"),
                                first_name=player.get("first_name"),
                                last_name=player.get("last_name"),
                                is_starter=player.get("is_starter"),
                                minutes_pg=player.get("minutes", {}).get("pg"),
                                minutes_sg=player.get("minutes", {}).get("sg"),
                                minutes_sf=player.get("minutes", {}).get("sf"),
                                minutes_pf=player.get("minutes", {}).get("pf"),
                                minutes_c=player.get("minutes", {}).get("c"),
                                fgm=player.get("performance", {}).get("fgm"),
                                fga=player.get("performance", {}).get("fga"),
                                tpm=player.get("performance", {}).get("tpm"),
                                tpa=player.get("performance", {}).get("tpa"),
                                ftm=player.get("performance", {}).get("ftm"),
                                fta=player.get("performance", {}).get("fta"),
                                oreb=player.get("performance", {}).get("oreb"),
                                reb=player.get("performance", {}).get("reb"),
                                ast=player.get("performance", {}).get("ast"),
                                to=player.get("performance", {}).get("to"),
                                stl=player.get("performance", {}).get("stl"),
                                blk=player.get("performance", {}).get("blk"),
                                pf=player.get("performance", {}).get("pf"),
                                pts=player.get("performance", {}).get("pts"),
                                rating=player.get("performance", {}).get("rating"),
                            )
                            db.add(player_obj)
                            await _upsert_nt_player_profile(db, player, team, nt_year, nt_week)
                        await db.commit()
                else:
                    for team_key in ["home_team", "away_team"]:
                        team = boxscore.get(team_key)
                        if not team:
                            continue
                        for player in team.get("boxscore", {}).get("players", []):
                            await _upsert_nt_player_profile(db, player, team, nt_year, nt_week)
                    await db.commit()
                results.append(mid)
                fetched += 1
                dbg["saved"] = True
            except Exception as e:
                dbg["error"] = str(e)
                stop = True
                debug.append(dbg)
                break
            debug.append(dbg)
        if stop:
            break
        if body.fetch_type == "single":
            break
        await asyncio.sleep(pause_seconds)
        break
    return {"success": True, "fetched": fetched, "match_ids": results, "debug": debug}

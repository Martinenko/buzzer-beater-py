from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import asyncio

from app.database import get_db
from app.models.user import User
from app.models.team import Team
from app.models.player import Player
from app.models.player_snapshot import PlayerSnapshot
from app.models.schedule_match import ScheduleMatch
from app.models.match_boxscore import MatchBoxscore, MatchTeamBoxscore, MatchPlayerBoxscore
from app.services.bb_api import BBApiClient
from app.schemas.team import ScheduleResponse
from app.routers.user import get_current_user_from_cookie, get_current_team_id_from_cookie, get_current_team_type_from_cookie

router = APIRouter()

# Global state for tracking boxscore fetch progress
fetch_state = {
    "current_match_id": None,
    "current_match_name": None,
    "total_matches": 0,
    "fetched_count": 0,
    "in_progress": False,
}


def get_current_bb_week() -> tuple[int, int, str, str]:
    """Get current BB week info. Returns (year, week_of_year, start_date, end_date).
    BB week starts on Friday and ends on Thursday."""
    now = datetime.now(timezone.utc)
    days_since_friday = (now.weekday() - 4) % 7
    start_of_week = now - timedelta(days=days_since_friday)
    end_of_week = start_of_week + timedelta(days=6)
    year = start_of_week.isocalendar()[0]
    week = start_of_week.isocalendar()[1]
    return year, week, start_of_week.strftime("%Y-%m-%d"), end_of_week.strftime("%Y-%m-%d")


@router.get("/economy")
async def get_economy(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get team economy from BuzzerBeater API (matches Spring API)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)
    team_type = get_current_team_type_from_cookie(request)
    is_utopia = (team_type == "UTOPIA")

    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    bb_client = BBApiClient(user.bb_key)
    economy = await bb_client.get_economy(current_team_id, username=user.login_name, is_utopia=is_utopia)

    return economy


@router.get("/roster")
async def get_roster(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get team roster (matches Spring API)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)
    print(f"DEBUG roster: user={user.username}, team_id={current_team_id}")

    # Get team
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()
    print(f"DEBUG roster: team found={team is not None}")

    if not team:
        return []

    # Get players
    stmt = select(Player).where(Player.current_team_id == team.id, Player.active == True)
    result = await db.execute(stmt)
    players = result.scalars().all()
    print(f"DEBUG roster: players count={len(players)}")

    # Return in Spring format
    return [
        {
            "id": str(player.id),  # UUID for internal use
            "playerId": player.player_id,  # BB player ID for links
            "name": player.name,
            "country": player.country,
            "age": player.age,
            "height": player.height,
            "salary": player.salary,
            "dmi": player.dmi,
            "bestPosition": player.best_position,
            "potential": player.potential,
            "gameShape": player.game_shape,
            "jumpShot": player.jump_shot,
            "jumpRange": player.jump_range,
            "outsideDefense": player.outside_defense,
            "handling": player.handling,
            "driving": player.driving,
            "passing": player.passing,
            "insideShot": player.inside_shot,
            "insideDefense": player.inside_defense,
            "rebounding": player.rebounding,
            "shotBlocking": player.shot_blocking,
            "stamina": player.stamina,
            "freeThrows": player.free_throws,
            "experience": player.experience,
            "archived": not player.active
        }
        for player in players
    ]


@router.get("/roster/sync")
async def sync_roster(
    request: Request,
    teamId: int = None,
    db: AsyncSession = Depends(get_db)
):
    """Sync roster from BuzzerBeater API (matches Spring API - GET not POST)"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = teamId or await get_current_team_id_from_cookie(request)

    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    # Get team from database
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Check if this is a UTOPIA team (needs secondteam=1 for BB API)
    is_utopia = (team.team_type.value == "UTOPIA")

    # Fetch roster from BB API
    bb_client = BBApiClient(user.bb_key)
    bb_players = await bb_client.get_roster(current_team_id, username=user.login_name, is_utopia=is_utopia)

    # Get current player IDs from BB
    bb_player_ids = {p["player_id"] for p in bb_players}

    # Mark players not in roster as inactive
    stmt = select(Player).where(Player.current_team_id == team.id)
    result = await db.execute(stmt)
    existing_players = result.scalars().all()

    for player in existing_players:
        if player.player_id not in bb_player_ids:
            player.active = False

    # Update or create players
    synced_count = 0
    for bb_player in bb_players:
        stmt = select(Player).where(Player.player_id == bb_player["player_id"])
        result = await db.execute(stmt)
        player = result.scalar_one_or_none()

        if player:
            # Update existing player
            player.name = bb_player["name"]
            player.country = bb_player["nationality"]
            player.age = bb_player["age"]
            player.height = bb_player["height"]
            player.potential = bb_player["potential"]
            player.salary = bb_player["salary"]
            player.dmi = bb_player["dmi"]
            player.best_position = bb_player["best_position"]
            player.game_shape = bb_player["game_shape"]
            player.jump_shot = bb_player["jump_shot"]
            player.jump_range = bb_player["jump_range"]
            player.outside_defense = bb_player["outside_defense"]
            player.handling = bb_player["handling"]
            player.driving = bb_player["driving"]
            player.passing = bb_player["passing"]
            player.inside_shot = bb_player["inside_shot"]
            player.inside_defense = bb_player["inside_defense"]
            player.rebounding = bb_player["rebounding"]
            player.shot_blocking = bb_player["shot_blocking"]
            player.stamina = bb_player["stamina"]
            player.free_throws = bb_player["free_throws"]
            player.experience = bb_player["experience"]
            player.current_team_id = team.id
            player.active = True
        else:
            # Create new player
            player = Player(
                player_id=bb_player["player_id"],
                name=bb_player["name"],
                country=bb_player["nationality"],
                age=bb_player["age"],
                height=bb_player["height"],
                potential=bb_player["potential"],
                salary=bb_player["salary"],
                dmi=bb_player["dmi"],
                best_position=bb_player["best_position"],
                game_shape=bb_player["game_shape"],
                jump_shot=bb_player["jump_shot"],
                jump_range=bb_player["jump_range"],
                outside_defense=bb_player["outside_defense"],
                handling=bb_player["handling"],
                driving=bb_player["driving"],
                passing=bb_player["passing"],
                inside_shot=bb_player["inside_shot"],
                inside_defense=bb_player["inside_defense"],
                rebounding=bb_player["rebounding"],
                shot_blocking=bb_player["shot_blocking"],
                stamina=bb_player["stamina"],
                free_throws=bb_player["free_throws"],
                experience=bb_player["experience"],
                current_team_id=team.id,
                active=True
            )
            db.add(player)

        synced_count += 1

    # Create snapshots for current week
    year, week, _, _ = get_current_bb_week()

    # Re-fetch players to get their UUIDs
    stmt = select(Player).where(Player.current_team_id == team.id, Player.active == True)
    result = await db.execute(stmt)
    players = result.scalars().all()

    for player in players:
        # Check if snapshot already exists for this week
        stmt = select(PlayerSnapshot).where(
            PlayerSnapshot.player_id == player.id,
            PlayerSnapshot.year == year,
            PlayerSnapshot.week_of_year == week
        )
        result = await db.execute(stmt)
        existing_snapshot = result.scalar_one_or_none()

        if existing_snapshot:
            # Update existing snapshot
            existing_snapshot.name = player.name
            existing_snapshot.country = player.country
            existing_snapshot.age = player.age
            existing_snapshot.height = player.height
            existing_snapshot.potential = player.potential
            existing_snapshot.game_shape = player.game_shape
            existing_snapshot.salary = player.salary
            existing_snapshot.dmi = player.dmi
            existing_snapshot.best_position = player.best_position
            existing_snapshot.jump_shot = player.jump_shot
            existing_snapshot.jump_range = player.jump_range
            existing_snapshot.outside_defense = player.outside_defense
            existing_snapshot.handling = player.handling
            existing_snapshot.driving = player.driving
            existing_snapshot.passing = player.passing
            existing_snapshot.inside_shot = player.inside_shot
            existing_snapshot.inside_defense = player.inside_defense
            existing_snapshot.rebounding = player.rebounding
            existing_snapshot.shot_blocking = player.shot_blocking
            existing_snapshot.stamina = player.stamina
            existing_snapshot.free_throws = player.free_throws
            existing_snapshot.experience = player.experience
        else:
            # Create new snapshot
            snapshot = PlayerSnapshot(
                player_id=player.id,
                bb_player_id=player.player_id,
                team_id=team.id,
                year=year,
                week_of_year=week,
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
            )
            db.add(snapshot)

    await db.commit()

    return {"success": True, "message": f"Synced {synced_count} players"}


async def _fetch_boxscores_background(match_ids: List[int], bb_key: str, login_name: str, current_team_id: int, is_utopia: bool):
    """Background task to fetch boxscores for multiple matches and update database."""
    global fetch_state
    
    fetch_state["in_progress"] = True
    fetch_state["total_matches"] = len(match_ids)
    fetch_state["fetched_count"] = 0
    fetch_state["current_match_id"] = None
    fetch_state["current_match_name"] = None
    
    db = None
    try:
        # Get fresh database session for background task using the configured session maker
        from app.database import async_session
        
        async with async_session() as db:
            bb_client = BBApiClient(bb_key)
            
            for i, match_id in enumerate(match_ids):
                # Re-fetch match from database in this session
                match = await db.get(ScheduleMatch, match_id)
                if not match:
                    fetch_state["fetched_count"] = i + 1
                    continue
                
                fetch_state["current_match_id"] = match_id
                fetch_state["current_match_name"] = f"{match.home_team_name} vs {match.away_team_name}"
                fetch_state["fetched_count"] = i
                
                try:
                    details = await bb_client.get_boxscore(match_id, username=login_name, is_utopia=is_utopia)
                    
                    # Check if BB API returned an authorization error - stop fetching
                    if details.get("error") == "NotAuthorised":
                        print(f"NotAuthorised error in background fetch - stopping")
                        fetch_state["in_progress"] = False
                        return
                    
                    # Mark that we've attempted to fetch this boxscore
                    match.boxscore_fetched = True
                    
                    if details:
                        home = details.get("home_team") or {}
                        away = details.get("away_team") or {}

                        is_home = match.home_team_id == current_team_id
                        opponent = away if is_home else home
                        my_team = home if is_home else away

                        # My team strategies and predictions
                        match.my_off_strategy = my_team.get("off_strategy")
                        match.my_def_strategy = my_team.get("def_strategy")
                        match.my_effort = my_team.get("effort")
                        
                        # My team's predictions (GDP = what we predicted before the match)
                        match.predicted_focus = my_team.get("gdp_focus")
                        match.predicted_pace = my_team.get("gdp_pace")
                        match.predicted_focus_hit = my_team.get("gdp_focus_hit")
                        match.predicted_pace_hit = my_team.get("gdp_pace_hit")

                        # Opponent strategies and their predictions (not derived, but from their GDP)
                        match.opponent_off_strategy = opponent.get("off_strategy")
                        match.opponent_def_strategy = opponent.get("def_strategy")
                        match.opponent_effort = opponent.get("effort")
                        match.opponent_focus = opponent.get("gdp_focus")
                        match.opponent_pace = opponent.get("gdp_pace")
                        match.opponent_focus_hit = opponent.get("gdp_focus_hit")
                        match.opponent_pace_hit = opponent.get("gdp_pace_hit")
                        match.effort_delta = details.get("effort_delta")

                        retrieved = details.get("retrieved")
                        match.details_retrieved_at = None
                        if retrieved:
                            try:
                                match.details_retrieved_at = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
                            except:
                                match.details_retrieved_at = datetime.now(timezone.utc)
                        else:
                            match.details_retrieved_at = datetime.now(timezone.utc)

                        # Persist full boxscore for detail page
                        await _store_boxscore_details(db, match_id, details)
                    
                    await db.commit()
                except Exception as e:
                    print(f"Error fetching boxscore for match {match_id}: {e}")
                    match.boxscore_fetched = True
                    try:
                        await db.commit()
                    except Exception as commit_err:
                        print(f"Error committing boxscore fetch for match {match_id}: {commit_err}")
    except Exception as e:
        print(f"Error in background boxscore fetch: {e}")
    finally:
        fetch_state["in_progress"] = False
        fetch_state["current_match_id"] = None
        fetch_state["current_match_name"] = None


async def _fetch_opponent_boxscores_background(match_ids: List[int], bb_key: str, login_name: str):
    """Background task to fetch opponent boxscores and update global fetch progress."""
    global fetch_state

    fetch_state["in_progress"] = True
    fetch_state["total_matches"] = len(match_ids)
    fetch_state["fetched_count"] = 0
    fetch_state["current_match_id"] = None
    fetch_state["current_match_name"] = None

    try:
        from app.database import async_session

        async with async_session() as db:
            bb_client = BBApiClient(bb_key)

            for i, match_id in enumerate(match_ids):
                fetch_state["current_match_id"] = match_id
                fetch_state["current_match_name"] = f"Match #{match_id}"
                fetch_state["fetched_count"] = i

                try:
                    match = await db.get(ScheduleMatch, match_id)
                    if not match:
                        fetch_state["fetched_count"] = i + 1
                        continue

                    details = await bb_client.get_boxscore(match_id, username=login_name, is_utopia=False)

                    if details.get("error") == "NotAuthorised":
                        fetch_state["in_progress"] = False
                        return

                    if details:
                        home_team = details.get("home_team") or {}
                        away_team = details.get("away_team") or {}
                        home_name = home_team.get("team_name") or "Home"
                        away_name = away_team.get("team_name") or "Away"
                        fetch_state["current_match_name"] = f"{home_name} vs {away_name}"

                        is_home = match.home_team_id == match.team_id
                        my_team = home_team if is_home else away_team
                        opponent = away_team if is_home else home_team

                        match.boxscore_fetched = True
                        match.my_off_strategy = my_team.get("off_strategy")
                        match.my_def_strategy = my_team.get("def_strategy")
                        match.my_effort = my_team.get("effort")
                        match.predicted_focus = my_team.get("gdp_focus")
                        match.predicted_pace = my_team.get("gdp_pace")
                        match.predicted_focus_hit = my_team.get("gdp_focus_hit")
                        match.predicted_pace_hit = my_team.get("gdp_pace_hit")

                        match.opponent_off_strategy = opponent.get("off_strategy")
                        match.opponent_def_strategy = opponent.get("def_strategy")
                        match.opponent_effort = opponent.get("effort")
                        match.opponent_focus = opponent.get("gdp_focus")
                        match.opponent_pace = opponent.get("gdp_pace")
                        match.opponent_focus_hit = opponent.get("gdp_focus_hit")
                        match.opponent_pace_hit = opponent.get("gdp_pace_hit")
                        match.effort_delta = details.get("effort_delta")

                        retrieved = details.get("retrieved")
                        match.details_retrieved_at = None
                        if retrieved:
                            try:
                                match.details_retrieved_at = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
                            except Exception:
                                match.details_retrieved_at = datetime.now(timezone.utc)
                        else:
                            match.details_retrieved_at = datetime.now(timezone.utc)

                        try:
                            await _store_boxscore_details(db, match_id, details)
                        except Exception as store_err:
                            print(f"Error storing opponent boxscore details for match {match_id}: {store_err}")

                        await db.commit()
                except Exception as e:
                    print(f"Error fetching opponent boxscore for match {match_id}: {e}")
                    try:
                        if 'match' in locals() and match is not None:
                            match.boxscore_fetched = True
                            await db.commit()
                    except Exception as commit_err:
                        print(f"Error committing opponent fetch fallback for match {match_id}: {commit_err}")

            fetch_state["fetched_count"] = len(match_ids)
    except Exception as e:
        print(f"Error in opponent background boxscore fetch: {e}")
    finally:
        fetch_state["in_progress"] = False
        fetch_state["current_match_id"] = None
        fetch_state["current_match_name"] = None


async def _store_boxscore_details(db: AsyncSession, match_id: int, details: dict) -> None:
    def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    boxscore = await db.get(MatchBoxscore, match_id)
    if not boxscore:
        boxscore = MatchBoxscore(match_id=match_id)
        db.add(boxscore)

    boxscore.retrieved_at = parse_iso(details.get("retrieved"))
    boxscore.match_type = details.get("type")
    boxscore.neutral = bool(details.get("neutral")) if details.get("neutral") is not None else None
    boxscore.start_time = parse_iso(details.get("start_time"))
    boxscore.end_time = parse_iso(details.get("end_time"))
    boxscore.effort_delta = details.get("effort_delta")
    attendance = details.get("attendance") or {}
    boxscore.attendance_bleachers = attendance.get("bleachers")
    boxscore.attendance_lower_tier = attendance.get("lower_tier")
    boxscore.attendance_courtside = attendance.get("courtside")
    boxscore.attendance_luxury = attendance.get("luxury")

    await db.execute(delete(MatchTeamBoxscore).where(MatchTeamBoxscore.match_id == match_id))
    await db.execute(delete(MatchPlayerBoxscore).where(MatchPlayerBoxscore.match_id == match_id))

    def insert_team(team_data: dict, is_home: bool):
        partials = team_data.get("score_partials") or []
        totals = (team_data.get("boxscore") or {}).get("totals") or {}
        ratings = team_data.get("ratings") or {}
        efficiency = team_data.get("efficiency") or {}
        gdp_focus = team_data.get("gdp_focus")
        gdp_pace = team_data.get("gdp_pace")
        gdp_focus_hit = team_data.get("gdp_focus_hit")
        gdp_pace_hit = team_data.get("gdp_pace_hit")

        team_row = MatchTeamBoxscore(
            match_id=match_id,
            is_home=is_home,
            team_id=team_data.get("team_id"),
            team_name=team_data.get("team_name"),
            short_name=team_data.get("short_name"),
            score=team_data.get("score"),
            partial_q1=partials[0] if len(partials) > 0 else None,
            partial_q2=partials[1] if len(partials) > 1 else None,
            partial_q3=partials[2] if len(partials) > 2 else None,
            partial_q4=partials[3] if len(partials) > 3 else None,
            off_strategy=team_data.get("off_strategy"),
            def_strategy=team_data.get("def_strategy"),
            effort=team_data.get("effort"),
            ratings_outside_scoring=ratings.get("outside_scoring"),
            ratings_inside_scoring=ratings.get("inside_scoring"),
            ratings_outside_defense=ratings.get("outside_defense"),
            ratings_inside_defense=ratings.get("inside_defense"),
            ratings_rebounding=ratings.get("rebounding"),
            ratings_offensive_flow=ratings.get("offensive_flow"),
            efficiency_pg=efficiency.get("pg"),
            efficiency_sg=efficiency.get("sg"),
            efficiency_sf=efficiency.get("sf"),
            efficiency_pf=efficiency.get("pf"),
            efficiency_c=efficiency.get("c"),
            gdp_focus=gdp_focus,
            gdp_pace=gdp_pace,
            gdp_focus_hit=gdp_focus_hit,
            gdp_pace_hit=gdp_pace_hit,
            totals_fgm=totals.get("fgm"),
            totals_fga=totals.get("fga"),
            totals_tpm=totals.get("tpm"),
            totals_tpa=totals.get("tpa"),
            totals_ftm=totals.get("ftm"),
            totals_fta=totals.get("fta"),
            totals_oreb=totals.get("oreb"),
            totals_reb=totals.get("reb"),
            totals_ast=totals.get("ast"),
            totals_to=totals.get("to"),
            totals_stl=totals.get("stl"),
            totals_blk=totals.get("blk"),
            totals_pf=totals.get("pf"),
            totals_pts=totals.get("pts"),
        )
        db.add(team_row)

        for player in (team_data.get("boxscore") or {}).get("players", []):
            minutes = player.get("minutes") or {}
            perf = player.get("performance") or {}
            db.add(MatchPlayerBoxscore(
                match_id=match_id,
                team_id=team_data.get("team_id"),
                player_id=player.get("player_id"),
                first_name=player.get("first_name"),
                last_name=player.get("last_name"),
                is_starter=player.get("is_starter"),
                minutes_pg=minutes.get("pg"),
                minutes_sg=minutes.get("sg"),
                minutes_sf=minutes.get("sf"),
                minutes_pf=minutes.get("pf"),
                minutes_c=minutes.get("c"),
                fgm=perf.get("fgm"),
                fga=perf.get("fga"),
                tpm=perf.get("tpm"),
                tpa=perf.get("tpa"),
                ftm=perf.get("ftm"),
                fta=perf.get("fta"),
                oreb=perf.get("oreb"),
                reb=perf.get("reb"),
                ast=perf.get("ast"),
                to=perf.get("to"),
                stl=perf.get("stl"),
                blk=perf.get("blk"),
                pf=perf.get("pf"),
                pts=perf.get("pts"),
                rating=perf.get("rating"),
            ))

    home_team = details.get("home_team") or {}
    away_team = details.get("away_team") or {}
    if home_team:
        insert_team(home_team, True)
    if away_team:
        insert_team(away_team, False)


@router.get("/schedule/fetch-status")
async def get_fetch_status(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get current boxscore fetch progress status."""
    global fetch_state
    
    await get_current_user_from_cookie(request, db)  # Verify auth
    
    return {
        "in_progress": fetch_state["in_progress"],
        "current_match_id": fetch_state["current_match_id"],
        "current_match_name": fetch_state["current_match_name"],
        "total_matches": fetch_state["total_matches"],
        "fetched_count": fetch_state["fetched_count"],
    }






@router.get("/schedule/match/{match_id}")
async def get_schedule_match_detail(
    match_id: int,
    request: Request,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get full boxscore details for a single match, cached in DB."""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)
    team_type = get_current_team_type_from_cookie(request)
    is_utopia = (team_type == "UTOPIA")

    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    stmt = select(ScheduleMatch).where(
        ScheduleMatch.match_id == match_id,
        ScheduleMatch.team_id == current_team_id
    )
    schedule_match = (await db.execute(stmt)).scalar_one_or_none()
    if not schedule_match:
        raise HTTPException(status_code=404, detail="Match not found for current team")

    def build_response(boxscore: MatchBoxscore, teams: list[MatchTeamBoxscore], players: list[MatchPlayerBoxscore]):
        team_map = {"home": None, "away": None}
        for team in teams:
            partials = [p for p in [team.partial_q1, team.partial_q2, team.partial_q3, team.partial_q4] if p is not None]
            team_payload = {
                "teamId": team.team_id,
                "teamName": team.team_name,
                "shortName": team.short_name,
                "score": team.score,
                "scorePartials": partials,
                "offStrategy": team.off_strategy,
                "defStrategy": team.def_strategy,
                "effort": team.effort,
                "ratings": {
                    "outsideScoring": team.ratings_outside_scoring,
                    "insideScoring": team.ratings_inside_scoring,
                    "outsideDefense": team.ratings_outside_defense,
                    "insideDefense": team.ratings_inside_defense,
                    "rebounding": team.ratings_rebounding,
                    "offensiveFlow": team.ratings_offensive_flow,
                },
                "efficiency": {
                    "pg": team.efficiency_pg,
                    "sg": team.efficiency_sg,
                    "sf": team.efficiency_sf,
                    "pf": team.efficiency_pf,
                    "c": team.efficiency_c,
                },
                "gdp": {
                    "focus": team.gdp_focus,
                    "pace": team.gdp_pace,
                    "focusHit": team.gdp_focus_hit,
                    "paceHit": team.gdp_pace_hit,
                },
                "boxscore": {
                    "players": [],
                    "totals": {
                        "fgm": team.totals_fgm,
                        "fga": team.totals_fga,
                        "tpm": team.totals_tpm,
                        "tpa": team.totals_tpa,
                        "ftm": team.totals_ftm,
                        "fta": team.totals_fta,
                        "oreb": team.totals_oreb,
                        "reb": team.totals_reb,
                        "ast": team.totals_ast,
                        "to": team.totals_to,
                        "stl": team.totals_stl,
                        "blk": team.totals_blk,
                        "pf": team.totals_pf,
                        "pts": team.totals_pts,
                    },
                },
            }

            key = "home" if team.is_home else "away"
            team_map[key] = team_payload

        for player in players:
            team_key = None
            if team_map["home"] and player.team_id == team_map["home"]["teamId"]:
                team_key = "home"
            elif team_map["away"] and player.team_id == team_map["away"]["teamId"]:
                team_key = "away"

            if team_key is None:
                continue

            team_map[team_key]["boxscore"]["players"].append({
                "playerId": player.player_id,
                "firstName": player.first_name,
                "lastName": player.last_name,
                "isStarter": player.is_starter,
                "minutes": {
                    "pg": player.minutes_pg,
                    "sg": player.minutes_sg,
                    "sf": player.minutes_sf,
                    "pf": player.minutes_pf,
                    "c": player.minutes_c,
                },
                "performance": {
                    "fgm": player.fgm,
                    "fga": player.fga,
                    "tpm": player.tpm,
                    "tpa": player.tpa,
                    "ftm": player.ftm,
                    "fta": player.fta,
                    "oreb": player.oreb,
                    "reb": player.reb,
                    "ast": player.ast,
                    "to": player.to,
                    "stl": player.stl,
                    "blk": player.blk,
                    "pf": player.pf,
                    "pts": player.pts,
                    "rating": player.rating,
                },
            })

        return {
            "matchId": boxscore.match_id,
            "retrieved": boxscore.retrieved_at.isoformat() if boxscore.retrieved_at else None,
            "type": boxscore.match_type,
            "neutral": boxscore.neutral,
            "startTime": boxscore.start_time.isoformat() if boxscore.start_time else None,
            "endTime": boxscore.end_time.isoformat() if boxscore.end_time else None,
            "effortDelta": boxscore.effort_delta,
            "attendance": {
                "bleachers": boxscore.attendance_bleachers,
                "lowerTier": boxscore.attendance_lower_tier,
                "courtside": boxscore.attendance_courtside,
                "luxury": boxscore.attendance_luxury,
            },
            "homeTeam": team_map["home"],
            "awayTeam": team_map["away"],
        }

    def build_response_from_details(details: dict):
        def map_team(team_data: dict):
            if not team_data:
                return None
            totals = (team_data.get("boxscore") or {}).get("totals") or {}
            return {
                "teamId": team_data.get("team_id"),
                "teamName": team_data.get("team_name"),
                "shortName": team_data.get("short_name"),
                "score": team_data.get("score"),
                "scorePartials": team_data.get("score_partials") or [],
                "offStrategy": team_data.get("off_strategy"),
                "defStrategy": team_data.get("def_strategy"),
                "effort": team_data.get("effort"),
                "ratings": {
                    "outsideScoring": (team_data.get("ratings") or {}).get("outside_scoring"),
                    "insideScoring": (team_data.get("ratings") or {}).get("inside_scoring"),
                    "outsideDefense": (team_data.get("ratings") or {}).get("outside_defense"),
                    "insideDefense": (team_data.get("ratings") or {}).get("inside_defense"),
                    "rebounding": (team_data.get("ratings") or {}).get("rebounding"),
                    "offensiveFlow": (team_data.get("ratings") or {}).get("offensive_flow"),
                },
                "efficiency": {
                    "pg": (team_data.get("efficiency") or {}).get("pg"),
                    "sg": (team_data.get("efficiency") or {}).get("sg"),
                    "sf": (team_data.get("efficiency") or {}).get("sf"),
                    "pf": (team_data.get("efficiency") or {}).get("pf"),
                    "c": (team_data.get("efficiency") or {}).get("c"),
                },
                "gdp": {
                    "focus": team_data.get("gdp_focus"),
                    "pace": team_data.get("gdp_pace"),
                    "focusHit": team_data.get("gdp_focus_hit"),
                    "paceHit": team_data.get("gdp_pace_hit"),
                },
                "boxscore": {
                    "players": [
                        {
                            "playerId": player.get("player_id"),
                            "firstName": player.get("first_name"),
                            "lastName": player.get("last_name"),
                            "isStarter": player.get("is_starter"),
                            "minutes": player.get("minutes") or {},
                            "performance": player.get("performance") or {},
                        }
                        for player in (team_data.get("boxscore") or {}).get("players", [])
                    ],
                    "totals": totals,
                },
            }

        return {
            "matchId": details.get("match_id"),
            "retrieved": details.get("retrieved"),
            "type": details.get("type"),
            "neutral": bool(details.get("neutral")) if details.get("neutral") is not None else None,
            "startTime": details.get("start_time"),
            "endTime": details.get("end_time"),
            "effortDelta": details.get("effort_delta"),
            "attendance": {
                "bleachers": (details.get("attendance") or {}).get("bleachers"),
                "lowerTier": (details.get("attendance") or {}).get("lower_tier"),
                "courtside": (details.get("attendance") or {}).get("courtside"),
                "luxury": (details.get("attendance") or {}).get("luxury"),
            },
            "homeTeam": map_team(details.get("home_team") or {}),
            "awayTeam": map_team(details.get("away_team") or {}),
        }

    try:
        boxscore = await db.get(MatchBoxscore, match_id)
        team_rows = (
            await db.execute(
                select(MatchTeamBoxscore).where(MatchTeamBoxscore.match_id == match_id)
            )
        ).scalars().all()
    except SQLAlchemyError as e:
        # Likely missing boxscore tables; fall back to live BB API response.
        bb_client = BBApiClient(user.bb_key)
        details = await bb_client.get_boxscore(match_id, username=user.login_name, is_utopia=is_utopia)
        if details.get("error") == "NotAuthorised":
            raise HTTPException(status_code=401, detail="BB API authorization expired. Please login again.")
        if not details:
            raise HTTPException(status_code=502, detail="Boxscore not available yet")
        print(f"WARN schedule/match: boxscore tables unavailable ({e}); returning live data")
        return build_response_from_details(details)

    if not boxscore or refresh or not team_rows:
        bb_client = BBApiClient(user.bb_key)
        details = await bb_client.get_boxscore(match_id, username=user.login_name, is_utopia=is_utopia)
        if details.get("error") == "NotAuthorised":
            raise HTTPException(status_code=401, detail="BB API authorization expired. Please login again.")

        if not details:
            raise HTTPException(status_code=502, detail="Boxscore not available yet")

        try:
            await _store_boxscore_details(db, match_id, details)
            await db.commit()
        except SQLAlchemyError as e:
            print(f"WARN schedule/match: failed to store boxscore ({e}); returning live data")
            return build_response_from_details(details)

    teams = (await db.execute(select(MatchTeamBoxscore).where(MatchTeamBoxscore.match_id == match_id))).scalars().all()
    players = (await db.execute(select(MatchPlayerBoxscore).where(MatchPlayerBoxscore.match_id == match_id))).scalars().all()
    return build_response(boxscore, teams, players)


@router.get("/snapshots")
async def get_snapshots(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get synced weeks/snapshots for current team"""
    current_team_id = await get_current_team_id_from_cookie(request)

    # Get team
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        return []

    # Get distinct weeks with snapshots for this team
    stmt = select(
        PlayerSnapshot.year,
        PlayerSnapshot.week_of_year
    ).where(
        PlayerSnapshot.team_id == team.id
    ).distinct().order_by(
        PlayerSnapshot.year.desc(),
        PlayerSnapshot.week_of_year.desc()
    )
    result = await db.execute(stmt)
    weeks = result.all()

    # Convert to response format with dates
    snapshots = []
    for year, week in weeks:
        # Calculate start/end dates for this week
        # Find the Friday of that ISO week
        jan4 = datetime(year, 1, 4)  # Jan 4 is always in week 1
        start_of_year_week1 = jan4 - timedelta(days=jan4.weekday())  # Monday of week 1
        friday_of_week = start_of_year_week1 + timedelta(weeks=week-1, days=4)  # Friday
        end_of_week = friday_of_week + timedelta(days=6)  # Thursday

        snapshots.append({
            "year": year,
            "weekOfYear": week,
            "startDate": friday_of_week.strftime("%Y-%m-%d"),
            "endDate": end_of_week.strftime("%Y-%m-%d")
        })

    return snapshots


@router.get("/roster/week")
async def get_roster_for_week(
    year: int,
    weekOfYear: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get roster snapshot for specific week"""
    current_team_id = await get_current_team_id_from_cookie(request)

    # Get team
    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    if not team:
        return []

    # Get snapshots for this week
    stmt = (
        select(PlayerSnapshot)
        .options(selectinload(PlayerSnapshot.player))
        .where(
            PlayerSnapshot.team_id == team.id,
            PlayerSnapshot.year == year,
            PlayerSnapshot.week_of_year == weekOfYear
        )
        .order_by(PlayerSnapshot.name)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()

    # Track which players we already have
    seen_player_ids = {s.player_id for s in snapshots}

    # Find archived players (inactive) who have snapshots for this team but not this week
    # Get their most recent snapshot instead
    stmt = (
        select(Player)
        .where(
            Player.current_team_id == team.id,
            Player.active == False,
            Player.id.notin_(seen_player_ids) if seen_player_ids else True
        )
    )
    result = await db.execute(stmt)
    archived_players = result.scalars().all()

    archived_snapshots = []
    for player in archived_players:
        # Get latest snapshot for this player on this team
        stmt = (
            select(PlayerSnapshot)
            .where(
                PlayerSnapshot.player_id == player.id,
                PlayerSnapshot.team_id == team.id,
            )
            .order_by(PlayerSnapshot.year.desc(), PlayerSnapshot.week_of_year.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        last_snapshot = result.scalar_one_or_none()
        if last_snapshot:
            archived_snapshots.append(last_snapshot)

    def _snapshot_to_dict(snapshot, archived, snapshot_label=None):
        return {
            "id": str(snapshot.player_id),
            "playerId": snapshot.bb_player_id,
            "firstName": snapshot.name.split()[0] if snapshot.name else "",
            "lastName": " ".join(snapshot.name.split()[1:]) if snapshot.name and len(snapshot.name.split()) > 1 else "",
            "name": snapshot.name,
            "country": snapshot.country,
            "age": snapshot.age,
            "height": snapshot.height,
            "salary": snapshot.salary,
            "dmi": snapshot.dmi,
            "bestPosition": snapshot.best_position,
            "potential": snapshot.potential,
            "gameShape": snapshot.game_shape,
            "jumpShot": snapshot.jump_shot,
            "jumpRange": snapshot.jump_range,
            "outsideDefense": snapshot.outside_defense,
            "handling": snapshot.handling,
            "driving": snapshot.driving,
            "passing": snapshot.passing,
            "insideShot": snapshot.inside_shot,
            "insideDefense": snapshot.inside_defense,
            "rebounding": snapshot.rebounding,
            "shotBlocking": snapshot.shot_blocking,
            "stamina": snapshot.stamina,
            "freeThrows": snapshot.free_throws,
            "experience": snapshot.experience,
            "archived": archived,
            "snapshotWeek": snapshot_label,
        }

    results = []
    for s in snapshots:
        is_archived = not s.player.active if s.player else True
        results.append(_snapshot_to_dict(s, is_archived))
    for s in archived_snapshots:
        label = f"W{s.week_of_year} {s.year}"
        results.append(_snapshot_to_dict(s, True, label))

    results.sort(key=lambda x: x["name"] or "")
    return results


@router.get("/schedule", response_model=ScheduleResponse)
async def get_schedule(
    request: Request,
    season: int = None,
    types: Optional[str] = None,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get team schedule for a season"""
    user = await get_current_user_from_cookie(request, db)
    current_team_id = await get_current_team_id_from_cookie(request)
    team_type = get_current_team_type_from_cookie(request)
    is_utopia = (team_type == "UTOPIA")

    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    bb_client = BBApiClient(user.bb_key)

    def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def derive_pace_focus(off_strategy: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not off_strategy:
            return None, None

        normalized = off_strategy.replace(" ", "").lower()
        mapping = {
            "runandgun": ("Fast", "Outside"),
            "motion": ("Normal", "Outside"),
            "princeton": ("Slow", "Outside"),
            "base": ("Normal", "Neutral"),
            "baseoffense": ("Normal", "Neutral"),
            "outsideisolation": ("Normal", "Neutral"),
            "insideisolation": ("Normal", "Neutral"),
            "pushtheball": ("Fast", "Neutral"),
            "patient": ("Slow", "Neutral"),
            "lowpost": ("Slow", "Inside"),
            "lookinside": ("Fast", "Inside"),
        }

        return mapping.get(normalized, (None, None))

    def effort_rank(effort_str: Optional[str]) -> Optional[int]:
        if not effort_str:
            return None
        normalized = effort_str.replace(" ", "").lower()
        if "takeiteasy" in normalized:
            return 0
        if "normal" in normalized:
            return 1
        if "crunchtime" in normalized:
            return 2
        return None

    def normalize_types(types_param: Optional[str]) -> List[str]:
        if not types_param:
            return []
        return [t.strip().lower() for t in types_param.split(",") if t.strip()]

    def build_type_filters(type_list: List[str]):
        filters = []
        if not type_list:
            return filters
        if "league" in type_list:
            filters.append(ScheduleMatch.match_type.like("league%"))
        if "cup" in type_list:
            filters.append(ScheduleMatch.match_type == "cup")
        if "bbm" in type_list:
            filters.append(ScheduleMatch.match_type == "bbm")
        if "friendly" in type_list:
            filters.append(ScheduleMatch.match_type == "friendly")
        return filters

    type_list = normalize_types(types)

    season_value = season
    if season_value is None:
        stmt = select(func.max(ScheduleMatch.season)).where(ScheduleMatch.team_id == current_team_id)
        result = await db.execute(stmt)
        season_value = result.scalar_one_or_none()

    needs_refresh = refresh or season_value is None

    schedule_data = {}
    if needs_refresh:
        try:
            schedule_data = await bb_client.get_schedule(current_team_id, season=season, username=user.login_name, is_utopia=is_utopia)
            
            # Check if BB API returned an authorization error
            if schedule_data.get("error") == "NotAuthorised":
                raise HTTPException(status_code=401, detail="BB API authorization expired. Please login again.")
            if schedule_data.get("error"):
                print(f"BB API error: {schedule_data.get('message')}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error fetching schedule from BB API: {e}")
            schedule_data = {}
        
        if schedule_data:
            season_value = schedule_data.get("season")

            retrieved_at = parse_iso(schedule_data.get("retrieved"))
            for match in schedule_data.get("matches", []):
                match_id = match.get("match_id")
                if match_id is None:
                    continue

                existing = await db.get(ScheduleMatch, match_id)
                if not existing:
                    existing = ScheduleMatch(match_id=match_id)
                    db.add(existing)

                home_team = match.get("home_team") or {}
                away_team = match.get("away_team") or {}

                existing.team_id = current_team_id
                existing.season = season_value
                existing.match_type = match.get("type") or ""
                existing.start_time = parse_iso(match.get("start"))
                existing.retrieved_at = retrieved_at

                existing.home_team_id = home_team.get("team_id")
                existing.home_team_name = home_team.get("team_name")
                existing.home_score = home_team.get("score")

                existing.away_team_id = away_team.get("team_id")
                existing.away_team_name = away_team.get("team_name")
                existing.away_score = away_team.get("score")

                if existing.home_team_id == current_team_id:
                    existing.opponent_team_id = existing.away_team_id
                    existing.opponent_team_name = existing.away_team_name
                else:
                    existing.opponent_team_id = existing.home_team_id
                    existing.opponent_team_name = existing.home_team_name

            await db.commit()

            team_info = await bb_client.get_team_info(current_team_id)
            rival_id = team_info.get("rival_id") if team_info else None
            rival_name = team_info.get("rival_name") if team_info else None

            stmt = select(Team).where(Team.team_id == current_team_id)
            result = await db.execute(stmt)
            team = result.scalar_one_or_none()

            if team and (rival_id or rival_name):
                team.rival_id = rival_id
                team.rival_name = rival_name
                await db.commit()
        else:
            # If refresh failed, fallback to last known season
            if season_value is None:
                stmt = select(func.max(ScheduleMatch.season)).where(ScheduleMatch.team_id == current_team_id)
                result = await db.execute(stmt)
                season_value = result.scalar_one_or_none()

    stmt = select(ScheduleMatch).where(
        ScheduleMatch.team_id == current_team_id,
        ScheduleMatch.season == season_value
    )

    type_filters = build_type_filters(type_list)
    if type_filters:
        stmt = stmt.where(or_(*type_filters))

    stmt = stmt.order_by(ScheduleMatch.start_time.asc())
    result = await db.execute(stmt)
    matches = result.scalars().all()

    match_ids = [m.match_id for m in matches]
    boxscore_teams_by_match = {}
    boxscore_effort_delta_by_match = {}
    if match_ids:
        try:
            boxscore_rows = (
                await db.execute(
                    select(MatchBoxscore).where(MatchBoxscore.match_id.in_(match_ids))
                )
            ).scalars().all()
            for box_row in boxscore_rows:
                boxscore_effort_delta_by_match[box_row.match_id] = box_row.effort_delta

            team_rows = (
                await db.execute(
                    select(MatchTeamBoxscore).where(MatchTeamBoxscore.match_id.in_(match_ids))
                )
            ).scalars().all()
            for team_row in team_rows:
                boxscore_teams_by_match.setdefault(team_row.match_id, []).append(team_row)
        except SQLAlchemyError as e:
            # If boxscore tables are not migrated yet, skip and fall back to schedule_match fields.
            print(f"WARN schedule: boxscore tables unavailable ({e}); using schedule_match data")

    # Get list of matches needing boxscore data (but don't fetch yet - let's return immediately)
    # Normalize datetimes to UTC-aware to avoid naive/aware comparison errors.
    now = datetime.now(timezone.utc)
    
    # PASS 1: Fetch boxscore for matches that came from recent schedule refresh
    # (these are the primary target for regular updates)
    matches_needing_boxscore = []
    for match in matches:
        # Skip if match hasn't happened yet
        match_time = match.start_time
        if match_time is not None:
            if match_time.tzinfo is None:
                match_time = match_time.replace(tzinfo=timezone.utc)
            else:
                match_time = match_time.astimezone(timezone.utc)

        if match_time is None or match_time > now:
            continue
        
        # Skip if we have all the data we need
        if match.details_retrieved_at is not None and match.my_off_strategy is not None and match.my_def_strategy is not None:
            continue
        
        # Skip if match not finished yet
        if match.home_score is None or match.away_score is None:
            continue
            
        matches_needing_boxscore.append(match)
    
    # PASS 2: Also get old matches that have scores but haven't been fetched yet
    # (in case they were skipped before or GDP wasn't parsed when boxscore was fetched)
    stmt_old = select(ScheduleMatch).where(
        ScheduleMatch.team_id == current_team_id,
        ScheduleMatch.season == season_value,
        ScheduleMatch.home_score.isnot(None),  # Has score (match finished)
        ScheduleMatch.away_score.isnot(None),
        ScheduleMatch.boxscore_fetched == False  # Haven't attempted fetch yet
    )
    if type_filters:
        stmt_old = stmt_old.where(or_(*type_filters))
    
    result_old = await db.execute(stmt_old)
    old_matches = result_old.scalars().all()
    
    # Add old matches that aren't already in the list
    old_match_ids = {m.match_id for m in old_matches}
    for full_match in matches:
        if full_match.match_id in old_match_ids and full_match not in matches_needing_boxscore:
            matches_needing_boxscore.append(full_match)

    # Trigger background fetch if there are matches to fetch (don't wait for it)
    # Only trigger if not already in progress to prevent duplicate tasks
    if matches_needing_boxscore and not fetch_state["in_progress"]:
        # Extract just the match IDs to avoid serialization issues with SQLAlchemy objects
        # Also extract only the user data we need (not the User object itself which gets detached)
        match_ids = [m.match_id for m in matches_needing_boxscore]
        asyncio.create_task(_fetch_boxscores_background(
            match_ids,
            user.bb_key,
            user.login_name,
            current_team_id,
            is_utopia
        ))

    stmt = select(Team).where(Team.team_id == current_team_id)
    result = await db.execute(stmt)
    team = result.scalar_one_or_none()

    # If we still don't have a season, that means no data in database and BB API failed
    if season_value is None:
        raise HTTPException(status_code=400, detail="No schedule data available. Please try logging in again or refreshing.")

    retrieved_at = None
    for match in matches:
        match_retrieved_at = match.retrieved_at
        if match_retrieved_at is not None:
            if match_retrieved_at.tzinfo is None:
                match_retrieved_at = match_retrieved_at.replace(tzinfo=timezone.utc)
            else:
                match_retrieved_at = match_retrieved_at.astimezone(timezone.utc)

        if match_retrieved_at and (retrieved_at is None or match_retrieved_at > retrieved_at):
            retrieved_at = match_retrieved_at

    response_matches = []
    schedule_effort_backfilled = False
    for match in matches:
        boxscore_teams = boxscore_teams_by_match.get(match.match_id, [])
        my_team_box = next(
            (team for team in boxscore_teams if team.team_id == current_team_id),
            None
        )
        opponent_team_box = next(
            (team for team in boxscore_teams if team.team_id != current_team_id),
            None
        )

        my_off_strategy = my_team_box.off_strategy if my_team_box else match.my_off_strategy
        my_def_strategy = my_team_box.def_strategy if my_team_box else match.my_def_strategy
        my_effort = my_team_box.effort if my_team_box else match.my_effort
        predicted_focus = my_team_box.gdp_focus if my_team_box else match.predicted_focus
        predicted_pace = my_team_box.gdp_pace if my_team_box else match.predicted_pace
        predicted_focus_hit = my_team_box.gdp_focus_hit if my_team_box else match.predicted_focus_hit
        predicted_pace_hit = my_team_box.gdp_pace_hit if my_team_box else match.predicted_pace_hit

        opponent_off_strategy = opponent_team_box.off_strategy if opponent_team_box else match.opponent_off_strategy
        opponent_def_strategy = opponent_team_box.def_strategy if opponent_team_box else match.opponent_def_strategy
        opponent_effort = opponent_team_box.effort if opponent_team_box else match.opponent_effort
        opponent_focus = opponent_team_box.gdp_focus if opponent_team_box else match.opponent_focus
        opponent_pace = opponent_team_box.gdp_pace if opponent_team_box else match.opponent_pace
        opponent_focus_hit = opponent_team_box.gdp_focus_hit if opponent_team_box else match.opponent_focus_hit
        opponent_pace_hit = opponent_team_box.gdp_pace_hit if opponent_team_box else match.opponent_pace_hit

        # Clear opponent_focus and opponent_pace if they don't have hit data (means they're derived, not real GDP)
        opponent_focus = opponent_focus if opponent_focus_hit is not None else None
        opponent_pace = opponent_pace if opponent_pace_hit is not None else None
        
        effort_delta = match.effort_delta
        if effort_delta is None:
            effort_delta = boxscore_effort_delta_by_match.get(match.match_id)
            if effort_delta is not None:
                match.effort_delta = effort_delta
                schedule_effort_backfilled = True
        if effort_delta is None and my_effort and opponent_effort:
            my_rank = effort_rank(my_effort)
            opponent_rank = effort_rank(opponent_effort)
            if my_rank is not None and opponent_rank is not None:
                is_my_team_away = match.away_team_id == current_team_id
                if is_my_team_away:
                    effort_delta = opponent_rank - my_rank  # home - away
                else:
                    effort_delta = my_rank - opponent_rank  # home - away
                match.effort_delta = effort_delta
                schedule_effort_backfilled = True
        
        response_matches.append({
            "matchId": match.match_id,
            "start": match.start_time.isoformat() if match.start_time else "",
            "type": match.match_type,
            "homeTeam": {
                "teamId": match.home_team_id,
                "teamName": match.home_team_name,
                "score": match.home_score,
            } if match.home_team_id else None,
            "awayTeam": {
                "teamId": match.away_team_id,
                "teamName": match.away_team_name,
                "score": match.away_score,
            } if match.away_team_id else None,
            "myOffStrategy": my_off_strategy,
            "myDefStrategy": my_def_strategy,
            "myEffort": my_effort,
            "effortDelta": effort_delta,
            "opponentFocus": opponent_focus,
            "opponentPace": opponent_pace,
            "opponentFocusHit": opponent_focus_hit,
            "opponentPaceHit": opponent_pace_hit,
            "opponentOffStrategy": opponent_off_strategy,
            "opponentDefStrategy": opponent_def_strategy,
            "opponentEffort": opponent_effort,
            "predictedFocus": predicted_focus,
            "predictedPace": predicted_pace,
            "predictedFocusHit": predicted_focus_hit,
            "predictedPaceHit": predicted_pace_hit,
        })

    if schedule_effort_backfilled:
        await db.commit()

    return {
        "teamId": current_team_id,
        "season": season_value,
        "retrieved": retrieved_at.isoformat() if retrieved_at else datetime.now(timezone.utc).isoformat(),
        "matches": response_matches,
        "rivalTeamId": team.rival_id if team else None,
        "rivalTeamName": team.rival_name if team else None,
    }


@router.get("/opponent/{team_id}/overview")
async def get_opponent_overview(
    team_id: int,
    request: Request,
    season: int = None,
    types: Optional[str] = None,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get opponent team schedule overview."""
    user = await get_current_user_from_cookie(request, db)
    if not user.bb_key:
        raise HTTPException(status_code=400, detail="BB key not available")

    bb_client = BBApiClient(user.bb_key)

    def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
        if not dt_str:
            return None
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def normalize_types(types_param: Optional[str]) -> List[str]:
        if not types_param:
            return []
        return [t.strip().lower() for t in types_param.split(",") if t.strip()]

    def build_type_filters(type_list: List[str]):
        filters = []
        if not type_list:
            return filters
        if "league" in type_list:
            filters.append(ScheduleMatch.match_type.like("league%"))
        if "cup" in type_list:
            filters.append(ScheduleMatch.match_type == "cup")
        if "bbm" in type_list:
            filters.append(ScheduleMatch.match_type == "bbm")
        if "friendly" in type_list:
            filters.append(ScheduleMatch.match_type == "friendly")
        return filters

    type_list = normalize_types(types)

    season_value = season
    if season_value is None:
        stmt = select(func.max(ScheduleMatch.season)).where(ScheduleMatch.team_id == team_id)
        result = await db.execute(stmt)
        season_value = result.scalar_one_or_none()

    needs_refresh = refresh or season_value is None

    if needs_refresh:
        schedule_data = {}
        try:
            schedule_data = await bb_client.get_schedule(team_id, season=season, username=user.login_name, is_utopia=False)
        except Exception:
            schedule_data = {}

        if isinstance(schedule_data, dict) and not schedule_data.get("error"):
            season_value = schedule_data.get("season")
            retrieved_at = parse_iso(schedule_data.get("retrieved"))

            for match in schedule_data.get("matches", []):
                match_id = match.get("match_id")
                if match_id is None:
                    continue

                existing = await db.get(ScheduleMatch, match_id)
                if not existing:
                    existing = ScheduleMatch(match_id=match_id)
                    db.add(existing)

                home_team = match.get("home_team") or {}
                away_team = match.get("away_team") or {}

                existing.team_id = team_id
                existing.season = season_value
                existing.match_type = match.get("type") or ""
                existing.start_time = parse_iso(match.get("start"))
                existing.retrieved_at = retrieved_at

                existing.home_team_id = home_team.get("team_id")
                existing.home_team_name = home_team.get("team_name")
                existing.home_score = home_team.get("score")

                existing.away_team_id = away_team.get("team_id")
                existing.away_team_name = away_team.get("team_name")
                existing.away_score = away_team.get("score")

                if existing.home_team_id == team_id:
                    existing.opponent_team_id = existing.away_team_id
                    existing.opponent_team_name = existing.away_team_name
                else:
                    existing.opponent_team_id = existing.home_team_id
                    existing.opponent_team_name = existing.home_team_name

            await db.commit()
        else:
            if season_value is None:
                stmt = select(func.max(ScheduleMatch.season)).where(ScheduleMatch.team_id == team_id)
                result = await db.execute(stmt)
                season_value = result.scalar_one_or_none()

    if season_value is None:
        raise HTTPException(status_code=400, detail="No schedule data available for this team.")

    stmt = select(ScheduleMatch).where(
        ScheduleMatch.team_id == team_id,
        ScheduleMatch.season == season_value,
    )
    type_filters = build_type_filters(type_list)
    if type_filters:
        stmt = stmt.where(or_(*type_filters))

    stmt = stmt.order_by(ScheduleMatch.start_time.asc())
    result = await db.execute(stmt)
    matches = result.scalars().all()

    if refresh and matches and not fetch_state["in_progress"]:
        played_match_ids = [
            m.match_id
            for m in matches
            if m.match_id is not None and m.home_score is not None and m.away_score is not None
        ]
        if played_match_ids:
            asyncio.create_task(
                _fetch_opponent_boxscores_background(
                    played_match_ids,
                    user.bb_key,
                    user.login_name,
                )
            )

    match_ids = [m.match_id for m in matches if m.match_id is not None]
    boxscore_effort_delta_by_match = {}
    boxscore_teams_by_match = {}
    if match_ids:
        try:
            boxscore_rows = (
                await db.execute(
                    select(MatchBoxscore).where(MatchBoxscore.match_id.in_(match_ids))
                )
            ).scalars().all()
            for box_row in boxscore_rows:
                boxscore_effort_delta_by_match[box_row.match_id] = box_row.effort_delta

            team_rows = (
                await db.execute(
                    select(MatchTeamBoxscore).where(MatchTeamBoxscore.match_id.in_(match_ids))
                )
            ).scalars().all()
            for team_row in team_rows:
                boxscore_teams_by_match.setdefault(team_row.match_id, []).append(team_row)
        except SQLAlchemyError as e:
            print(f"WARN opponent overview: boxscore tables unavailable ({e}); using schedule-only data")

    response_matches = []
    for match in matches:
        match_id = match.match_id

        my_off_strategy = match.my_off_strategy
        my_def_strategy = match.my_def_strategy
        my_effort = match.my_effort
        predicted_focus = match.predicted_focus
        predicted_pace = match.predicted_pace
        predicted_focus_hit = match.predicted_focus_hit
        predicted_pace_hit = match.predicted_pace_hit

        opponent_off_strategy = match.opponent_off_strategy
        opponent_def_strategy = match.opponent_def_strategy
        opponent_effort = match.opponent_effort
        opponent_focus = match.opponent_focus
        opponent_pace = match.opponent_pace
        opponent_focus_hit = match.opponent_focus_hit
        opponent_pace_hit = match.opponent_pace_hit
        effort_delta = match.effort_delta if match.effort_delta is not None else boxscore_effort_delta_by_match.get(match_id)

        boxscore_teams = boxscore_teams_by_match.get(match_id, [])
        my_team_box = next((team_row for team_row in boxscore_teams if team_row.team_id == team_id), None)
        opponent_team_box = next((team_row for team_row in boxscore_teams if team_row.team_id != team_id), None)

        if my_team_box:
            my_off_strategy = my_team_box.off_strategy
            my_def_strategy = my_team_box.def_strategy
            my_effort = my_team_box.effort
            predicted_focus = my_team_box.gdp_focus
            predicted_pace = my_team_box.gdp_pace
            predicted_focus_hit = my_team_box.gdp_focus_hit
            predicted_pace_hit = my_team_box.gdp_pace_hit

        if opponent_team_box:
            opponent_off_strategy = opponent_team_box.off_strategy
            opponent_def_strategy = opponent_team_box.def_strategy
            opponent_effort = opponent_team_box.effort
            opponent_focus = opponent_team_box.gdp_focus
            opponent_pace = opponent_team_box.gdp_pace
            opponent_focus_hit = opponent_team_box.gdp_focus_hit
            opponent_pace_hit = opponent_team_box.gdp_pace_hit

        opponent_focus = opponent_focus if opponent_focus_hit is not None else None
        opponent_pace = opponent_pace if opponent_pace_hit is not None else None

        response_matches.append(
            {
                "matchId": match_id,
                "start": match.start_time.isoformat() if match.start_time else "",
                "type": match.match_type,
                "homeTeam": {
                    "teamId": match.home_team_id,
                    "teamName": match.home_team_name,
                    "score": match.home_score,
                } if match.home_team_id else None,
                "awayTeam": {
                    "teamId": match.away_team_id,
                    "teamName": match.away_team_name,
                    "score": match.away_score,
                } if match.away_team_id else None,
                "myOffStrategy": my_off_strategy,
                "myDefStrategy": my_def_strategy,
                "myEffort": my_effort,
                "effortDelta": effort_delta,
                "opponentFocus": opponent_focus,
                "opponentPace": opponent_pace,
                "opponentFocusHit": opponent_focus_hit,
                "opponentPaceHit": opponent_pace_hit,
                "opponentOffStrategy": opponent_off_strategy,
                "opponentDefStrategy": opponent_def_strategy,
                "opponentEffort": opponent_effort,
                "predictedFocus": predicted_focus,
                "predictedPace": predicted_pace,
                "predictedFocusHit": predicted_focus_hit,
                "predictedPaceHit": predicted_pace_hit,
            }
        )

    team_name = None
    retrieved_at = None
    for match in matches:
        if match.home_team_id == team_id and match.home_team_name:
            team_name = match.home_team_name
            break
        if match.away_team_id == team_id and match.away_team_name:
            team_name = match.away_team_name
            break

    for match in matches:
        match_retrieved = match.retrieved_at
        if not match_retrieved:
            continue
        if match_retrieved.tzinfo is None:
            match_retrieved = match_retrieved.replace(tzinfo=timezone.utc)
        else:
            match_retrieved = match_retrieved.astimezone(timezone.utc)
        if retrieved_at is None or match_retrieved > retrieved_at:
            retrieved_at = match_retrieved

    if not team_name:
        try:
            team_info = await bb_client.get_team_info(team_id)
            team_name = team_info.get("name") if isinstance(team_info, dict) else None
        except Exception:
            team_name = None

    return {
        "teamId": team_id,
        "teamName": team_name or f"Team {team_id}",
        "shortName": None,
        "season": season_value,
        "retrieved": retrieved_at.isoformat() if retrieved_at else datetime.now(timezone.utc).isoformat(),
        "matches": response_matches,
        "roster": [],
    }

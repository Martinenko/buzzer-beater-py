import httpx
from lxml import etree
from typing import Optional, Dict, Any, List
from app.config import get_settings

settings = get_settings()


class BBApiClient:
    """Client for BuzzerBeater API (XML-based)"""

    def __init__(self, bb_key: Optional[str] = None):
        self.base_url = settings.bb_api_url
        self.bb_key = bb_key

    def _parse_xml(self, xml_text: str) -> etree._Element:
        return etree.fromstring(xml_text.encode())

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login to BuzzerBeater and get access key"""
        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            # Step 1: Verify login credentials
            response = await client.get(
                f"{self.base_url}/login.aspx",
                params={"login": username, "code": password}
            )
            root = self._parse_xml(response.text)

            # Check for errors
            error = root.find(".//error")
            if error is not None:
                return {"success": False, "message": error.text}

            # Check if logged in
            logged_in = root.find(".//loggedIn")
            if logged_in is None:
                return {"success": False, "message": "Login failed"}

            teams = []

            # Step 2: Get MAIN team info with quickinfo
            main_response = await client.get(
                f"{self.base_url}/login.aspx",
                params={"login": username, "code": password, "quickinfo": "1"}
            )
            main_root = self._parse_xml(main_response.text)
            main_team = main_root.find(".//team")
            owner_username = None
            if main_team is not None:
                team_name = main_team.findtext("teamName", "Unknown")
                owner_elem = main_team.find("owner")
                if owner_elem is not None:
                    owner_text = owner_elem.text
                    # Only use owner if it's different from team name
                    if owner_text and owner_text != team_name:
                        owner_username = owner_text
                teams.append({
                    "team_id": int(main_team.get("id")),
                    "name": team_name,
                    "team_type": "MAIN"
                })

            # Step 3: Get UTOPIA team info with quickinfo + secondteam
            utopia_response = await client.get(
                f"{self.base_url}/login.aspx",
                params={"login": username, "code": password, "quickinfo": "1", "secondteam": "1"}
            )
            utopia_root = self._parse_xml(utopia_response.text)
            utopia_team = utopia_root.find(".//team")
            if utopia_team is not None:
                utopia_id = int(utopia_team.get("id"))
                # Only add if different from main team
                if not teams or utopia_id != teams[0]["team_id"]:
                    teams.append({
                        "team_id": utopia_id,
                        "name": utopia_team.findtext("teamName", "Unknown"),
                        "team_type": "UTOPIA"
                    })

            return {
                "success": True,
                "bb_key": password,  # Use the code as bb_key
                "user_id": logged_in.get("userId"),
                "login_name": logged_in.get("userName") or username,  # Private login name
                "username": owner_username or username,  # Public username from <owner> element
                "supporter": logged_in.get("supporter") in ("1", "true", "True"),
                "teams": teams
            }

    def _parse_teams(self, logged_in: etree._Element) -> List[Dict[str, Any]]:
        """Parse teams from login response"""
        teams = []
        for team in logged_in.findall(".//team"):
            teams.append({
                "team_id": int(team.get("id")),
                "name": team.text,
                "team_type": "UTOPIA" if team.get("utopia") == "true" else "MAIN"
            })
        return teams

    async def login_with_client(self, username: str, password: str, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Login using an existing HTTP client (for session reuse)"""
        response = await client.get(
            f"{self.base_url}/login.aspx",
            params={"login": username, "code": password}
        )
        root = self._parse_xml(response.text)

        error = root.find(".//error")
        if error is not None:
            return {"success": False, "message": error.text}

        logged_in = root.find(".//loggedIn")
        if logged_in is None:
            return {"success": False, "message": "Login failed"}

        return {"success": True, "user_id": logged_in.get("userId")}

    async def get_roster_with_client(
        self,
        team_id: int,
        username: str,
        is_utopia: bool,
        client: httpx.AsyncClient
    ) -> List[Dict[str, Any]]:
        """Get roster using an existing HTTP client. Performs login for session."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        # Login to establish session (with secondteam=1 for UTOPIA)
        login_params = {"login": username, "code": self.bb_key}
        if is_utopia:
            login_params["secondteam"] = "1"
        await client.get(f"{self.base_url}/login.aspx", params=login_params)

        # Now get roster
        response = await client.get(
            f"{self.base_url}/roster.aspx",
            params={"teamid": team_id}
        )
        root = self._parse_xml(response.text)

        players = []
        for player in root.findall(".//player"):
            players.append(self._parse_player(player))
        return players

    async def get_roster(self, team_id: int, username: str = None, is_utopia: bool = False) -> List[Dict[str, Any]]:
        """Get team roster. For UTOPIA teams, use secondteam=1 to get full skills."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            # First establish session by calling login
            # For UTOPIA teams, include secondteam=1 to authenticate for that team
            if username:
                login_params = {"login": username, "code": self.bb_key}
                if is_utopia:
                    login_params["secondteam"] = "1"
                await client.get(
                    f"{self.base_url}/login.aspx",
                    params=login_params
                )

            response = await client.get(
                f"{self.base_url}/roster.aspx",
                params={"teamid": team_id}
            )
            root = self._parse_xml(response.text)

            players = []
            for player in root.findall(".//player"):
                players.append(self._parse_player(player))
            return players

    def _parse_player(self, player: etree._Element) -> Dict[str, Any]:
        """Parse player from XML"""
        skills = player.find("skills")
        return {
            "player_id": int(player.get("id")),
            "first_name": player.findtext("firstName", ""),
            "last_name": player.findtext("lastName", ""),
            "name": f"{player.findtext('firstName', '')} {player.findtext('lastName', '')}",
            "nationality": player.findtext("nationality", ""),
            "age": int(player.findtext("age", 0)),
            "height": round(int(player.findtext("height", 0)) * 2.54),  # Convert inches to cm
            "potential": self._get_skill(skills, "potential"),
            "salary": int(player.findtext("salary", 0)),
            "dmi": int(player.findtext("dmi", 0)) if player.findtext("dmi") else None,
            "best_position": player.findtext("bestPosition", ""),
            "game_shape": self._get_skill(skills, "gameShape"),
            # Skills - BB API uses short tag names
            "jump_shot": self._get_skill(skills, "jumpShot"),
            "jump_range": self._get_skill(skills, "range"),
            "outside_defense": self._get_skill(skills, "outsideDef"),
            "handling": self._get_skill(skills, "handling"),
            "driving": self._get_skill(skills, "driving"),
            "passing": self._get_skill(skills, "passing"),
            "inside_shot": self._get_skill(skills, "insideShot"),
            "inside_defense": self._get_skill(skills, "insideDef"),
            "rebounding": self._get_skill(skills, "rebound"),
            "shot_blocking": self._get_skill(skills, "block"),
            "stamina": self._get_skill(skills, "stamina"),
            "free_throws": self._get_skill(skills, "freeThrow"),
            "experience": self._get_skill(skills, "experience"),
        }

    def _get_skill(self, skills: Optional[etree._Element], name: str) -> Optional[int]:
        """Get skill value from skills element"""
        if skills is None:
            return None
        skill = skills.find(name)
        if skill is not None and skill.text:
            return int(skill.text)
        return None

    async def get_team_info(self, team_id: int) -> Dict[str, Any]:
        """Get team information"""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            response = await client.get(
                f"{self.base_url}/teaminfo.aspx",
                params={"accessKey": self.bb_key, "teamid": team_id}
            )
            root = self._parse_xml(response.text)

            team = root.find(".//team")
            if team is None:
                return {}

            rival_elem = team.find("rivalTeam")
            if rival_elem is None:
                rival_elem = team.find("rival")
            if rival_elem is None:
                rival_elem = root.find(".//rivalTeam")
            if rival_elem is None:
                rival_elem = root.find(".//rival")

            rival_id = None
            rival_name = None

            if rival_elem is not None:
                rival_id_text = (
                    rival_elem.get("id")
                    or rival_elem.get("teamid")
                    or rival_elem.get("teamId")
                    or rival_elem.findtext("teamId")
                    or rival_elem.findtext("rivalTeamId")
                )
                if rival_id_text:
                    try:
                        rival_id = int(rival_id_text)
                    except ValueError:
                        rival_id = None

                rival_name = (
                    rival_elem.findtext("teamName")
                    or rival_elem.findtext("rivalTeamName")
                )
                if rival_name is None and rival_elem.text:
                    rival_name = rival_elem.text.strip()

            if rival_id is None:
                rival_id_text = root.findtext(".//rivalTeamId") or root.findtext(".//rivalId")
                if rival_id_text:
                    try:
                        rival_id = int(rival_id_text)
                    except ValueError:
                        rival_id = None

            if rival_name is None:
                rival_name = root.findtext(".//rivalTeamName") or root.findtext(".//rivalName")

            return {
                "team_id": int(team.get("id")),
                "name": team.findtext("teamName", ""),
                "short_name": team.findtext("shortName", ""),
                "country_id": int(team.findtext("country", 0)),
                "country_name": team.find("country").get("name") if team.find("country") is not None else None,
                "rival_id": rival_id,
                "rival_name": rival_name,
            }

    async def get_economy(self, team_id: int, username: str = None, is_utopia: bool = False) -> Dict[str, Any]:
        """Get team economy data (full format matching Spring). For UTOPIA teams, use secondteam=1."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            # First establish session by calling login
            # For UTOPIA teams, include secondteam=1 to authenticate for that team
            if username:
                login_params = {"login": username, "code": self.bb_key}
                if is_utopia:
                    login_params["secondteam"] = "1"
                await client.get(
                    f"{self.base_url}/login.aspx",
                    params=login_params
                )

            response = await client.get(
                f"{self.base_url}/economy.aspx",
                params={"teamid": team_id}
            )
            root = self._parse_xml(response.text)

            economy = root.find(".//economy")
            if economy is None:
                return {}

            def parse_week(week_elem) -> Dict[str, Any]:
                if week_elem is None:
                    return {}

                def parse_value_with_date(elem):
                    if elem is None:
                        return {"date": None, "value": 0}
                    return {
                        "date": elem.get("date"),
                        "value": int(elem.text) if elem.text else 0
                    }

                def parse_match_revenues(week):
                    revenues = []
                    for mr in week.findall("matchRevenue"):
                        revenues.append({
                            "matchid": mr.get("matchid"),
                            "date": mr.get("date"),
                            "value": int(mr.text) if mr.text else 0
                        })
                    return revenues if revenues else None

                def parse_transfers(week):
                    transfers = []
                    for tr in week.findall("transfer"):
                        transfers.append({
                            "playerid": tr.get("playerid"),
                            "date": tr.get("date"),
                            "value": int(tr.text) if tr.text else 0
                        })
                    return transfers if transfers else None

                return {
                    "start": week_elem.get("start"),
                    "initial": int(week_elem.findtext("initial", 0)),
                    "finalAmount": int(week_elem.findtext("final", 0)),
                    "current": int(week_elem.findtext("current", 0)),
                    "playerSalaries": parse_value_with_date(week_elem.find("playerSalaries")),
                    "staffSalaries": parse_value_with_date(week_elem.find("staffSalaries")),
                    "merchandise": parse_value_with_date(week_elem.find("merchandise")),
                    "scouting": parse_value_with_date(week_elem.find("scouting")),
                    "tvMoney": parse_value_with_date(week_elem.find("tvMoney")),
                    "unknown": parse_value_with_date(week_elem.find("unknown")),
                    "matchRevenues": parse_match_revenues(week_elem),
                    "transfers": parse_transfers(week_elem),
                }

            return {
                "retrieved": economy.get("retrieved"),
                "lastWeek": parse_week(economy.find("lastWeek")),
                "thisWeek": parse_week(economy.find("thisWeek")),
            }

    async def get_schedule(self, team_id: int, season: Optional[int] = None, username: str = None, is_utopia: bool = False) -> Dict[str, Any]:
        """Get team schedule for a season. For UTOPIA teams, use secondteam=1."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            # First establish session by calling login
            # For UTOPIA teams, include secondteam=1 to authenticate for that team
            if username:
                login_params = {"login": username, "code": self.bb_key}
                if is_utopia:
                    login_params["secondteam"] = "1"
                await client.get(
                    f"{self.base_url}/login.aspx",
                    params=login_params
                )

            # Build schedule request params
            params = {"teamid": team_id}
            if season is not None:
                params["season"] = season

            response = await client.get(
                f"{self.base_url}/schedule.aspx",
                params=params
            )
            root = self._parse_xml(response.text)

            # Check for error response
            error = root.find(".//error")
            if error is not None:
                error_msg = error.text or "Unknown error"
                if "NotAuthorised" in error_msg or "not authorized" in error_msg.lower():
                    return {"error": "NotAuthorised", "message": error_msg}
                return {"error": error_msg, "message": error_msg}

            schedule = root.find(".//schedule")
            if schedule is None:
                return {}

            matches = []
            for match in schedule.findall("match"):
                home_team = match.find("homeTeam")
                away_team = match.find("awayTeam")
                
                match_data = {
                    "match_id": int(match.get("id")),
                    "start": match.get("start"),
                    "type": match.get("type"),
                }
                
                if home_team is not None:
                    match_data["home_team"] = {
                        "team_id": int(home_team.get("id")),
                        "team_name": home_team.findtext("teamName", ""),
                        "score": int(home_team.findtext("score")) if home_team.findtext("score") else None
                    }
                
                if away_team is not None:
                    match_data["away_team"] = {
                        "team_id": int(away_team.get("id")),
                        "team_name": away_team.findtext("teamName", ""),
                        "score": int(away_team.findtext("score")) if away_team.findtext("score") else None
                    }
                
                matches.append(match_data)

            return {
                "team_id": int(schedule.get("teamid")),
                "season": int(schedule.get("season")),
                "retrieved": schedule.get("retrieved"),
                "matches": matches
            }

    async def get_boxscore(self, match_id: int, username: str = None, is_utopia: bool = False) -> Dict[str, Any]:
        """Get match boxscore and extract full match details."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            # First establish session by calling login
            if username:
                login_params = {"login": username, "code": self.bb_key}
                if is_utopia:
                    login_params["secondteam"] = "1"
                await client.get(
                    f"{self.base_url}/login.aspx",
                    params=login_params
                )

            response = await client.get(
                f"{self.base_url}/boxscore.aspx",
                params={"matchid": match_id}
            )
            root = self._parse_xml(response.text)
            
            # Check for error response
            error = root.find(".//error")
            if error is not None:
                error_msg = error.text or "Unknown error"
                if "NotAuthorised" in error_msg or "not authorized" in error_msg.lower():
                    return {"error": "NotAuthorised", "message": error_msg}
                return {"error": error_msg, "message": error_msg}
            
            match = root.find(".//match")
            if match is None:
                return {}

            def parse_int(value: Optional[str]) -> Optional[int]:
                if value is None:
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            def parse_float(value: Optional[str]) -> Optional[float]:
                if value is None:
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            def parse_team(team_elem: etree._Element) -> Dict[str, Any]:
                if team_elem is None:
                    return {}

                gdp = team_elem.find("gdp")
                focus_elem = gdp.find("focus") if gdp is not None else None
                pace_elem = gdp.find("pace") if gdp is not None else None

                def parse_gdp_value(elem: Optional[etree._Element]) -> tuple[Optional[str], Optional[bool]]:
                    """Parse GDP element which may contain value + '.hit|miss' suffix.
                    Examples: 'Balanced.hit' → ('Balanced', True), 'outside.miss' → ('Outside', False), 'Slow' → ('Slow', None), 'N/A' → (None, None)
                    """
                    if elem is None or elem.text is None:
                        return None, None
                    
                    text = elem.text.strip()
                    if text == 'N/A':
                        return None, None
                    
                    is_hit = None
                    if text.endswith('.hit'):
                        is_hit = True
                        text = text[:-4]  # Remove '.hit' suffix
                    elif text.endswith('.miss'):
                        is_hit = False
                        text = text[:-5]  # Remove '.miss' suffix
                    
                    # Normalize text to proper case for focus values (outside → Outside, etc.)
                    if text:
                        text = text.capitalize()
                    
                    return text if text else None, is_hit

                focus_value, focus_hit = parse_gdp_value(focus_elem)
                pace_value, pace_hit = parse_gdp_value(pace_elem)

                score_elem = team_elem.find("score")
                partials_raw = score_elem.get("partials") if score_elem is not None else None
                partials = []
                if partials_raw:
                    for part in partials_raw.split(","):
                        part_value = parse_int(part.strip())
                        if part_value is not None:
                            partials.append(part_value)

                def parse_player(player_elem: etree._Element) -> Dict[str, Any]:
                    minutes_elem = player_elem.find("minutes")
                    perf_elem = player_elem.find("performance")

                    return {
                        "player_id": parse_int(player_elem.get("id")),
                        "first_name": player_elem.findtext("firstName", ""),
                        "last_name": player_elem.findtext("lastName", ""),
                        "is_starter": (player_elem.findtext("isStarter") or "").lower() == "true",
                        "minutes": {
                            "pg": parse_int(minutes_elem.findtext("PG")) if minutes_elem is not None else None,
                            "sg": parse_int(minutes_elem.findtext("SG")) if minutes_elem is not None else None,
                            "sf": parse_int(minutes_elem.findtext("SF")) if minutes_elem is not None else None,
                            "pf": parse_int(minutes_elem.findtext("PF")) if minutes_elem is not None else None,
                            "c": parse_int(minutes_elem.findtext("C")) if minutes_elem is not None else None,
                        },
                        "performance": {
                            "fgm": parse_int(perf_elem.findtext("fgm")) if perf_elem is not None else None,
                            "fga": parse_int(perf_elem.findtext("fga")) if perf_elem is not None else None,
                            "tpm": parse_int(perf_elem.findtext("tpm")) if perf_elem is not None else None,
                            "tpa": parse_int(perf_elem.findtext("tpa")) if perf_elem is not None else None,
                            "ftm": parse_int(perf_elem.findtext("ftm")) if perf_elem is not None else None,
                            "fta": parse_int(perf_elem.findtext("fta")) if perf_elem is not None else None,
                            "oreb": parse_int(perf_elem.findtext("oreb")) if perf_elem is not None else None,
                            "reb": parse_int(perf_elem.findtext("reb")) if perf_elem is not None else None,
                            "ast": parse_int(perf_elem.findtext("ast")) if perf_elem is not None else None,
                            "to": parse_int(perf_elem.findtext("to")) if perf_elem is not None else None,
                            "stl": parse_int(perf_elem.findtext("stl")) if perf_elem is not None else None,
                            "blk": parse_int(perf_elem.findtext("blk")) if perf_elem is not None else None,
                            "pf": parse_int(perf_elem.findtext("pf")) if perf_elem is not None else None,
                            "pts": parse_int(perf_elem.findtext("pts")) if perf_elem is not None else None,
                            "rating": parse_float(perf_elem.findtext("rating")) if perf_elem is not None else None,
                        },
                    }

                boxscore_elem = team_elem.find("boxscore")
                players = []
                team_totals = {}
                if boxscore_elem is not None:
                    for player_elem in boxscore_elem.findall("player"):
                        players.append(parse_player(player_elem))

                    totals_elem = boxscore_elem.find("teamTotals")
                    if totals_elem is not None:
                        team_totals = {
                            "fgm": parse_int(totals_elem.findtext("fgm")),
                            "fga": parse_int(totals_elem.findtext("fga")),
                            "tpm": parse_int(totals_elem.findtext("tpm")),
                            "tpa": parse_int(totals_elem.findtext("tpa")),
                            "ftm": parse_int(totals_elem.findtext("ftm")),
                            "fta": parse_int(totals_elem.findtext("fta")),
                            "oreb": parse_int(totals_elem.findtext("oreb")),
                            "reb": parse_int(totals_elem.findtext("reb")),
                            "ast": parse_int(totals_elem.findtext("ast")),
                            "to": parse_int(totals_elem.findtext("to")),
                            "stl": parse_int(totals_elem.findtext("stl")),
                            "blk": parse_int(totals_elem.findtext("blk")),
                            "pf": parse_int(totals_elem.findtext("pf")),
                            "pts": parse_int(totals_elem.findtext("pts")),
                        }

                ratings_elem = team_elem.find("ratings")
                ratings = {}
                if ratings_elem is not None:
                    ratings = {
                        "outside_scoring": parse_float(ratings_elem.findtext("outsideScoring")),
                        "inside_scoring": parse_float(ratings_elem.findtext("insideScoring")),
                        "outside_defense": parse_float(ratings_elem.findtext("outsideDefense")),
                        "inside_defense": parse_float(ratings_elem.findtext("insideDefense")),
                        "rebounding": parse_float(ratings_elem.findtext("rebounding")),
                        "offensive_flow": parse_float(ratings_elem.findtext("offensiveFlow")),
                    }

                efficiency_elem = team_elem.find("efficiency")
                efficiency = {}
                if efficiency_elem is not None:
                    efficiency = {
                        "pg": parse_float(efficiency_elem.findtext("PG")),
                        "sg": parse_float(efficiency_elem.findtext("SG")),
                        "sf": parse_float(efficiency_elem.findtext("SF")),
                        "pf": parse_float(efficiency_elem.findtext("PF")),
                        "c": parse_float(efficiency_elem.findtext("C")),
                    }

                return {
                    "team_id": parse_int(team_elem.get("id")),
                    "team_name": team_elem.findtext("teamName", ""),
                    "short_name": team_elem.findtext("shortName", ""),
                    "score": parse_int(score_elem.text if score_elem is not None else None),
                    "score_partials": partials,
                    "off_strategy": team_elem.findtext("offStrategy"),
                    "def_strategy": team_elem.findtext("defStrategy"),
                    "effort": team_elem.findtext("effort"),
                    "gdp_focus": focus_value,
                    "gdp_pace": pace_value,
                    "gdp_focus_hit": focus_hit,
                    "gdp_pace_hit": pace_hit,
                    "ratings": ratings,
                    "efficiency": efficiency,
                    "boxscore": {
                        "players": players,
                        "totals": team_totals,
                    },
                }

            return {
                "match_id": int(match.get("id")),
                "retrieved": match.get("retrieved"),
                "type": match.get("type"),
                "neutral": parse_int(match.findtext("neutral")),
                "start_time": match.findtext("startTime"),
                "end_time": match.findtext("endTime"),
                "effort_delta": parse_int(match.findtext("effortDelta")),
                "attendance": {
                    "bleachers": parse_int(match.findtext("attendance/bleachers")),
                    "lower_tier": parse_int(match.findtext("attendance/lowerTier")),
                    "courtside": parse_int(match.findtext("attendance/courtside")),
                    "luxury": parse_int(match.findtext("attendance/luxury")),
                },
                "home_team": parse_team(match.find("homeTeam")),
                "away_team": parse_team(match.find("awayTeam")),
            }

    async def get_seasons(self, username: Optional[str] = None, is_utopia: bool = False) -> List[Dict[str, Any]]:
        """Get all available seasons from BB API."""
        if not self.bb_key:
            print("DEBUG get_seasons: no bb_key")
            return []

        print(f"DEBUG get_seasons: calling BB API /seasons.aspx")
        async with httpx.AsyncClient(verify=settings.bb_api_verify_ssl) as client:
            # BB endpoints in this app typically require login session first.
            if username:
                login_params = {"login": username, "code": self.bb_key}
                if is_utopia:
                    login_params["secondteam"] = "1"
                await client.get(
                    f"{self.base_url}/login.aspx",
                    params=login_params
                )

            # Prefer session-based call. Keep access-key fallback for compatibility.
            response = await client.get(f"{self.base_url}/seasons.aspx")
            if response.status_code >= 400:
                response = await client.get(
                    f"{self.base_url}/seasons.aspx",
                    params={"key": self.bb_key}
                )
            print(f"DEBUG get_seasons: BB API response status={response.status_code}")
            root = self._parse_xml(response.text)

            # Check for errors
            error = root.find(".//error")
            if error is not None:
                error_msg = error.get("message") or error.text or "Unknown error"
                print(f"DEBUG get_seasons: BB API error={error_msg}")
                return []

            seasons = []
            seasons_elem = root.find(".//seasons")
            print(f"DEBUG get_seasons: seasons_elem found={seasons_elem is not None}")
            if seasons_elem is not None:
                for season in seasons_elem.findall("season"):
                    try:
                        # BB seasons endpoint format:
                        # <season id='71'><start>...</start><finish>...</finish><inProgress/></season>
                        # Keep backward compatibility with any older format too.
                        raw_number = season.get("id") or season.get("number")
                        season_num = int(raw_number)

                        start_date = season.findtext("start") or season.get("startDate")
                        end_date = season.findtext("finish") or season.get("endDate")

                        # If season is currently in progress, finish may be missing.
                        in_progress = season.find("inProgress") is not None
                        if in_progress and not end_date:
                            end_date = None

                        seasons.append({
                            "number": season_num,
                            "startDate": start_date,
                            "endDate": end_date,
                            "inProgress": in_progress,
                        })
                    except (ValueError, TypeError):
                        continue
            
            print(f"DEBUG get_seasons: returning {len(seasons)} seasons")
            return seasons

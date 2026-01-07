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
        async with httpx.AsyncClient() as client:
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

    async def get_roster(self, team_id: int, username: str = None, is_utopia: bool = False) -> List[Dict[str, Any]]:
        """Get team roster. For UTOPIA teams, use secondteam=1 to get full skills."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient() as client:
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

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/teaminfo.aspx",
                params={"accessKey": self.bb_key, "teamid": team_id}
            )
            root = self._parse_xml(response.text)

            team = root.find(".//team")
            if team is None:
                return {}

            return {
                "team_id": int(team.get("id")),
                "name": team.findtext("teamName", ""),
                "short_name": team.findtext("shortName", ""),
                "country_id": int(team.findtext("country", 0)),
                "country_name": team.find("country").get("name") if team.find("country") is not None else None,
            }

    async def get_economy(self, team_id: int, username: str = None, is_utopia: bool = False) -> Dict[str, Any]:
        """Get team economy data (full format matching Spring). For UTOPIA teams, use secondteam=1."""
        if not self.bb_key:
            raise ValueError("BB key required for this operation")

        async with httpx.AsyncClient() as client:
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

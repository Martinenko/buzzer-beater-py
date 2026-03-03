from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from app.models.team import TeamType


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase"""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class TeamInfo(BaseModel):
    team_id: int
    name: str
    short_name: str
    team_type: TeamType
    active: bool = False

    class Config:
        from_attributes = True


class TeamResponse(BaseModel):
    id: UUID
    team_id: int
    name: str
    short_name: str
    team_type: TeamType
    league_name: Optional[str] = None
    country_name: Optional[str] = None

    class Config:
        from_attributes = True


class MatchTeam(BaseModel):
    team_id: int = Field(..., alias="teamId")
    team_name: str = Field(..., alias="teamName")
    score: Optional[int] = None

    class Config:
        populate_by_name = True
        alias_generator = to_camel


class Match(BaseModel):
    match_id: int = Field(..., alias="matchId")
    start: str
    type: str
    home_team: Optional[MatchTeam] = Field(None, alias="homeTeam")
    away_team: Optional[MatchTeam] = Field(None, alias="awayTeam")
    my_off_strategy: Optional[str] = Field(None, alias="myOffStrategy")
    my_def_strategy: Optional[str] = Field(None, alias="myDefStrategy")
    my_effort: Optional[str] = Field(None, alias="myEffort")
    effort_delta: Optional[int] = Field(None, alias="effortDelta")
    opponent_focus: Optional[str] = Field(None, alias="opponentFocus")
    opponent_pace: Optional[str] = Field(None, alias="opponentPace")
    opponent_focus_hit: Optional[bool] = Field(None, alias="opponentFocusHit")
    opponent_pace_hit: Optional[bool] = Field(None, alias="opponentPaceHit")
    opponent_off_strategy: Optional[str] = Field(None, alias="opponentOffStrategy")
    opponent_def_strategy: Optional[str] = Field(None, alias="opponentDefStrategy")
    opponent_effort: Optional[str] = Field(None, alias="opponentEffort")
    predicted_focus: Optional[str] = Field(None, alias="predictedFocus")
    predicted_pace: Optional[str] = Field(None, alias="predictedPace")
    predicted_focus_hit: Optional[bool] = Field(None, alias="predictedFocusHit")
    predicted_pace_hit: Optional[bool] = Field(None, alias="predictedPaceHit")
    opponent_predicted_focus: Optional[str] = Field(None, alias="opponentPredictedFocus")
    opponent_predicted_pace: Optional[str] = Field(None, alias="opponentPredictedPace")
    opponent_predicted_focus_hit: Optional[bool] = Field(None, alias="opponentPredictedFocusHit")
    opponent_predicted_pace_hit: Optional[bool] = Field(None, alias="opponentPredictedPaceHit")

    class Config:
        populate_by_name = True
        alias_generator = to_camel


class ScheduleResponse(BaseModel):
    team_id: int = Field(..., alias="teamId")
    season: int
    retrieved: str
    matches: List[Match]
    rival_team_id: Optional[int] = Field(None, alias="rivalTeamId")
    rival_team_name: Optional[str] = Field(None, alias="rivalTeamName")

    class Config:
        populate_by_name = True
        alias_generator = to_camel

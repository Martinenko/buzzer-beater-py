from sqlalchemy import Column, String, Integer, DateTime, Boolean
from app.database import Base


class ScheduleMatch(Base):
    __tablename__ = "schedule_match"

    match_id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, nullable=False, index=True)
    season = Column(Integer, nullable=False, index=True)
    match_type = Column(String(32), nullable=False)
    start_time = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, nullable=True)

    home_team_id = Column(Integer, nullable=True)
    home_team_name = Column(String(100), nullable=True)
    home_score = Column(Integer, nullable=True)

    away_team_id = Column(Integer, nullable=True)
    away_team_name = Column(String(100), nullable=True)
    away_score = Column(Integer, nullable=True)

    opponent_team_id = Column(Integer, nullable=True)
    opponent_team_name = Column(String(100), nullable=True)

    my_off_strategy = Column(String(32), nullable=True)
    my_def_strategy = Column(String(32), nullable=True)
    my_effort = Column(String(32), nullable=True)

    opponent_focus = Column(String(32), nullable=True)
    opponent_pace = Column(String(32), nullable=True)
    opponent_focus_hit = Column(Boolean, nullable=True)
    opponent_pace_hit = Column(Boolean, nullable=True)
    opponent_off_strategy = Column(String(32), nullable=True)
    opponent_def_strategy = Column(String(32), nullable=True)
    opponent_effort = Column(String(32), nullable=True)
    effort_delta = Column(Integer, nullable=True)

    predicted_focus = Column(String(32), nullable=True)
    predicted_pace = Column(String(32), nullable=True)
    predicted_focus_hit = Column(Boolean, nullable=True)
    predicted_pace_hit = Column(Boolean, nullable=True)

    boxscore_fetched = Column(Boolean, default=False, nullable=False)
    details_retrieved_at = Column(DateTime, nullable=True)

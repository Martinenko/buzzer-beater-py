from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database import Base


class MatchBoxscore(Base):
    __tablename__ = "match_boxscore"

    match_id = Column(Integer, primary_key=True, index=True)
    retrieved_at = Column(DateTime, nullable=True)
    match_type = Column(String(32), nullable=True)
    neutral = Column(Boolean, nullable=True)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    effort_delta = Column(Integer, nullable=True)

    attendance_bleachers = Column(Integer, nullable=True)
    attendance_lower_tier = Column(Integer, nullable=True)
    attendance_courtside = Column(Integer, nullable=True)
    attendance_luxury = Column(Integer, nullable=True)

    teams = relationship("MatchTeamBoxscore", back_populates="match", cascade="all, delete-orphan")
    players = relationship("MatchPlayerBoxscore", back_populates="match", cascade="all, delete-orphan")


class MatchTeamBoxscore(Base):
    __tablename__ = "match_team_boxscore"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("match_boxscore.match_id", ondelete="CASCADE"), nullable=False, index=True)
    is_home = Column(Boolean, nullable=False)

    team_id = Column(Integer, nullable=True)
    team_name = Column(String(100), nullable=True)
    short_name = Column(String(16), nullable=True)
    score = Column(Integer, nullable=True)
    partial_q1 = Column(Integer, nullable=True)
    partial_q2 = Column(Integer, nullable=True)
    partial_q3 = Column(Integer, nullable=True)
    partial_q4 = Column(Integer, nullable=True)

    off_strategy = Column(String(32), nullable=True)
    def_strategy = Column(String(32), nullable=True)
    effort = Column(String(32), nullable=True)

    ratings_outside_scoring = Column(Float, nullable=True)
    ratings_inside_scoring = Column(Float, nullable=True)
    ratings_outside_defense = Column(Float, nullable=True)
    ratings_inside_defense = Column(Float, nullable=True)
    ratings_rebounding = Column(Float, nullable=True)
    ratings_offensive_flow = Column(Float, nullable=True)

    efficiency_pg = Column(Float, nullable=True)
    efficiency_sg = Column(Float, nullable=True)
    efficiency_sf = Column(Float, nullable=True)
    efficiency_pf = Column(Float, nullable=True)
    efficiency_c = Column(Float, nullable=True)

    gdp_focus = Column(String(32), nullable=True)
    gdp_pace = Column(String(32), nullable=True)
    gdp_focus_hit = Column(Boolean, nullable=True)
    gdp_pace_hit = Column(Boolean, nullable=True)

    totals_fgm = Column(Integer, nullable=True)
    totals_fga = Column(Integer, nullable=True)
    totals_tpm = Column(Integer, nullable=True)
    totals_tpa = Column(Integer, nullable=True)
    totals_ftm = Column(Integer, nullable=True)
    totals_fta = Column(Integer, nullable=True)
    totals_oreb = Column(Integer, nullable=True)
    totals_reb = Column(Integer, nullable=True)
    totals_ast = Column(Integer, nullable=True)
    totals_to = Column(Integer, nullable=True)
    totals_stl = Column(Integer, nullable=True)
    totals_blk = Column(Integer, nullable=True)
    totals_pf = Column(Integer, nullable=True)
    totals_pts = Column(Integer, nullable=True)

    match = relationship("MatchBoxscore", back_populates="teams")


class MatchPlayerBoxscore(Base):
    __tablename__ = "match_player_boxscore"

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey("match_boxscore.match_id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = Column(Integer, nullable=True, index=True)
    player_id = Column(Integer, nullable=True, index=True)

    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_starter = Column(Boolean, nullable=True)

    minutes_pg = Column(Integer, nullable=True)
    minutes_sg = Column(Integer, nullable=True)
    minutes_sf = Column(Integer, nullable=True)
    minutes_pf = Column(Integer, nullable=True)
    minutes_c = Column(Integer, nullable=True)

    fgm = Column(Integer, nullable=True)
    fga = Column(Integer, nullable=True)
    tpm = Column(Integer, nullable=True)
    tpa = Column(Integer, nullable=True)
    ftm = Column(Integer, nullable=True)
    fta = Column(Integer, nullable=True)
    oreb = Column(Integer, nullable=True)
    reb = Column(Integer, nullable=True)
    ast = Column(Integer, nullable=True)
    to = Column(Integer, nullable=True)
    stl = Column(Integer, nullable=True)
    blk = Column(Integer, nullable=True)
    pf = Column(Integer, nullable=True)
    pts = Column(Integer, nullable=True)
    rating = Column(Float, nullable=True)

    match = relationship("MatchBoxscore", back_populates="players")

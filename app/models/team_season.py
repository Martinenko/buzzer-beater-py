from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from app.database import Base


class TeamSeason(Base):
    __tablename__ = 'team_seasons'

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, nullable=False, index=True)
    season = Column(Integer, nullable=False, index=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint('team_id', 'season', name='uq_team_season'),
    )

    def __repr__(self):
        return f"<TeamSeason(team_id={self.team_id}, season={self.season})>"

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Uuid
from sqlalchemy.orm import relationship
import uuid
import enum
from datetime import datetime
from app.database import Base


class TeamType(str, enum.Enum):
    MAIN = "MAIN"
    UTOPIA = "UTOPIA"


class Team(Base):
    __tablename__ = "team"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id = Column(Integer, unique=True, nullable=False, index=True)  # BuzzerBeater team ID
    name = Column(String(100), nullable=False)
    short_name = Column(String(20), nullable=False)
    team_type = Column(Enum(TeamType), nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow)

    # League info (embedded in Java, separate columns here)
    league_id = Column(Integer, nullable=True)
    league_name = Column(String(100), nullable=True)
    league_level = Column(Integer, nullable=True)

    # Country info
    country_id = Column(Integer, nullable=True)
    country_name = Column(String(50), nullable=True)

    # Rival info
    rival_id = Column(Integer, nullable=True)
    rival_name = Column(String(100), nullable=True)

    # Foreign keys
    coach_id = Column(Uuid, ForeignKey("users.id"), nullable=False)

    # Relationships
    coach = relationship("User", back_populates="teams")
    players = relationship("Player", back_populates="current_team")

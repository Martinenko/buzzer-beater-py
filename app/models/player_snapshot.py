from sqlalchemy import Column, String, Integer, ForeignKey, Uuid, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class PlayerSnapshot(Base):
    """Weekly snapshot of player skills - stores historical data per week."""
    __tablename__ = "player_snapshot"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)

    # Reference to player
    player_id = Column(Uuid, ForeignKey("player.id"), nullable=False)

    # Week info
    year = Column(Integer, nullable=False)
    week_of_year = Column(Integer, nullable=False)

    # Team at time of snapshot
    team_id = Column(Uuid, ForeignKey("team.id"), nullable=False)

    # Basic info at time of snapshot
    name = Column(String(100), nullable=False)
    country = Column(String(50), nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Integer, nullable=False)
    potential = Column(Integer, nullable=False)
    game_shape = Column(Integer, nullable=False)
    salary = Column(Integer, nullable=True)
    dmi = Column(Integer, nullable=True)
    best_position = Column(String(10), nullable=True)

    # Skills at time of snapshot
    jump_shot = Column(Integer, nullable=True)
    jump_range = Column(Integer, nullable=True)
    outside_defense = Column(Integer, nullable=True)
    handling = Column(Integer, nullable=True)
    driving = Column(Integer, nullable=True)
    passing = Column(Integer, nullable=True)
    inside_shot = Column(Integer, nullable=True)
    inside_defense = Column(Integer, nullable=True)
    rebounding = Column(Integer, nullable=True)
    shot_blocking = Column(Integer, nullable=True)
    stamina = Column(Integer, nullable=True)
    free_throws = Column(Integer, nullable=True)
    experience = Column(Integer, nullable=True)

    # Relationships
    player = relationship("Player", backref="snapshots")
    team = relationship("Team")

    # Ensure one snapshot per player per week
    __table_args__ = (
        UniqueConstraint('player_id', 'year', 'week_of_year', name='uq_player_week'),
    )

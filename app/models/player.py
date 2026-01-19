from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Uuid
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class Player(Base):
    __tablename__ = "player"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    player_id = Column(Integer, unique=True, nullable=False, index=True)  # BuzzerBeater player ID

    # Basic info
    name = Column(String(100), nullable=False)
    country = Column(String(50), nullable=False)
    team_name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    height = Column(Integer, nullable=False)
    potential = Column(Integer, nullable=False)
    game_shape = Column(Integer, nullable=False)
    salary = Column(Integer, nullable=True)
    dmi = Column(Integer, nullable=True)
    best_position = Column(String(10), nullable=True)
    active = Column(Boolean, default=True)

    # Skills
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

    # Foreign keys
    current_team_id = Column(Uuid, ForeignKey("team.id"), nullable=True)

    # Relationships
    current_team = relationship("Team", back_populates="players")
    shares = relationship("PlayerShare", back_populates="player")
    threads = relationship("PlayerThread", back_populates="player")

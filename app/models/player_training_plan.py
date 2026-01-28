"""Training plan for a player: target skills at end of training."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base


class PlayerTrainingPlan(Base):
    __tablename__ = "player_training_plan"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    player_id = Column(Uuid, ForeignKey("player.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Target skills (1–20). Null = no target for that skill.
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

    player = relationship("Player", back_populates="training_plan")

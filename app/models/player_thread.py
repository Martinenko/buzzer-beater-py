from sqlalchemy import Column, DateTime, ForeignKey, Boolean, Uuid, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class PlayerThread(Base):
    """Thread for communication about a player between owner and another manager."""
    __tablename__ = "player_thread"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Foreign keys
    player_id = Column(Uuid, ForeignKey("player.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Uuid, ForeignKey("users.id"), nullable=False)  # Owner at time of thread creation
    participant_id = Column(Uuid, ForeignKey("users.id"), nullable=False)  # Other manager

    # Unique constraint - one active thread per player-owner-participant combination
    __table_args__ = (
        UniqueConstraint("player_id", "owner_id", "participant_id", name="unique_player_thread"),
    )

    # Relationships
    player = relationship("Player", back_populates="threads")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="threads_as_owner")
    participant = relationship("User", foreign_keys=[participant_id], back_populates="threads_as_participant")
    messages = relationship("PlayerMessage", back_populates="thread", cascade="all, delete-orphan", order_by="PlayerMessage.created_at")

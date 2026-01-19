from sqlalchemy import Column, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class PlayerMessage(Base):
    """Message in a player thread."""
    __tablename__ = "player_message"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    content = Column(Text, nullable=False)

    # Foreign keys
    thread_id = Column(Uuid, ForeignKey("player_thread.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Uuid, ForeignKey("users.id"), nullable=False)

    # Relationships
    thread = relationship("PlayerThread", back_populates="messages")
    sender = relationship("User", back_populates="player_messages")

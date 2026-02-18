from sqlalchemy import Column, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class UserMessage(Base):
    """Message in a direct user-to-user thread."""
    __tablename__ = "user_message"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    content = Column(Text, nullable=False)
    read_at = Column(DateTime, nullable=True, default=None)

    # Foreign keys
    thread_id = Column(Uuid, ForeignKey("user_thread.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(Uuid, ForeignKey("users.id"), nullable=False)

    # Relationships
    thread = relationship("UserThread", back_populates="messages")
    sender = relationship("User", back_populates="dm_messages")

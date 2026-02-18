from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, Uuid, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class UserThread(Base):
    """Direct message thread between two users."""
    __tablename__ = "user_thread"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Participants (unordered pair stored as user_a_id < user_b_id by convention)
    user_a_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    user_b_id = Column(Uuid, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="unique_user_thread"),
    )

    user_a = relationship("User", foreign_keys=[user_a_id], back_populates="dm_threads_as_a")
    user_b = relationship("User", foreign_keys=[user_b_id], back_populates="dm_threads_as_b")
    messages = relationship("UserMessage", back_populates="thread", cascade="all, delete-orphan", order_by="UserMessage.created_at")

from sqlalchemy import Column, String, Boolean, Uuid, Integer, DateTime
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from app.utils.crypto import EncryptedString


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    login_name = Column(String(100), unique=True, nullable=False, index=True)  # Private, for login
    username = Column(String(100), nullable=True, index=True)  # Public, visible to others
    bb_key = Column(EncryptedString(512), nullable=True)  # BuzzerBeater API key (encrypted at rest)
    name = Column(String(100), nullable=True)
    supporter = Column(Boolean, default=False)
    auto_sync_enabled = Column(Boolean, default=True)  # Enable automatic weekly roster sync
    email = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False)
    unread_reminder_enabled = Column(Boolean, default=False)
    unread_reminder_delay_min = Column(Integer, default=60)
    last_unread_reminder_sent_at = Column(DateTime, nullable=True)

    # Relationships
    teams = relationship("Team", back_populates="coach")
    shares_sent = relationship("PlayerShare", foreign_keys="PlayerShare.owner_id", back_populates="owner")
    shares_received = relationship("PlayerShare", foreign_keys="PlayerShare.recipient_id", back_populates="recipient")
    threads_as_owner = relationship("PlayerThread", foreign_keys="PlayerThread.owner_id", back_populates="owner")
    threads_as_participant = relationship("PlayerThread", foreign_keys="PlayerThread.participant_id", back_populates="participant")
    player_messages = relationship("PlayerMessage", back_populates="sender")
    # Direct messages
    dm_threads_as_a = relationship("UserThread", foreign_keys="UserThread.user_a_id", back_populates="user_a")
    dm_threads_as_b = relationship("UserThread", foreign_keys="UserThread.user_b_id", back_populates="user_b")
    dm_messages = relationship("UserMessage", back_populates="sender")

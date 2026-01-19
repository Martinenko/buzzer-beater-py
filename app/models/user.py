from sqlalchemy import Column, String, Boolean, Uuid
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    login_name = Column(String(100), unique=True, nullable=False, index=True)  # Private, for login
    username = Column(String(100), nullable=True, index=True)  # Public, visible to others
    bb_key = Column(String(255), nullable=True)  # BuzzerBeater API key
    name = Column(String(100), nullable=True)
    supporter = Column(Boolean, default=False)
    auto_sync_enabled = Column(Boolean, default=True)  # Enable automatic weekly roster sync

    # Relationships
    teams = relationship("Team", back_populates="coach")
    shares_sent = relationship("PlayerShare", foreign_keys="PlayerShare.owner_id", back_populates="owner")
    shares_received = relationship("PlayerShare", foreign_keys="PlayerShare.recipient_id", back_populates="recipient")
    threads_as_owner = relationship("PlayerThread", foreign_keys="PlayerThread.owner_id", back_populates="owner")
    threads_as_participant = relationship("PlayerThread", foreign_keys="PlayerThread.participant_id", back_populates="participant")
    player_messages = relationship("PlayerMessage", back_populates="sender")

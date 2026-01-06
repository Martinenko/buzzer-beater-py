from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from app.database import Base


class PlayerShare(Base):
    __tablename__ = "player_share"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Foreign keys
    player_id = Column(Uuid, ForeignKey("player.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(Uuid, ForeignKey("users.id"), nullable=False)

    # Unique constraint - player can only be shared once with same recipient
    __table_args__ = (
        UniqueConstraint("player_id", "recipient_id", name="unique_player_share"),
    )

    # Relationships
    player = relationship("Player", back_populates="shares")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="shares_sent")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="shares_received")

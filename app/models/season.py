from sqlalchemy import Column, Integer, Date, DateTime
from datetime import datetime, timezone
from app.database import Base


class Season(Base):
    __tablename__ = 'seasons'

    id = Column(Integer, primary_key=True)
    number = Column(Integer, unique=True, nullable=False, index=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<Season(number={self.number}, start_date={self.start_date}, end_date={self.end_date})>"

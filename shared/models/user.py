# shared/models/user.py
import uuid
from sqlalchemy import Column, String, BigInteger, Boolean, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin
from .enums import UserRole

class User(Base, TimestampMixin):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    role = Column(String(20), default=UserRole.USER, nullable=False)
    preferences = Column(JSON, default=dict)  # {"city": "Moscow", "categories": ["cafe", "park"]}
    is_active = Column(Boolean, default=True)
    
    # Связи
    reviews = relationship("Review", back_populates="user", foreign_keys="Review.user_id")
    moderated_reviews = relationship("Review", back_populates="moderator", foreign_keys="Review.moderated_by")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, role={self.role})>"
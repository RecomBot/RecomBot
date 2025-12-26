# shared/models/review.py
import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin
from .enums import ModerationStatus

class Review(Base, TimestampMixin):
    """Модель отзыва"""
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    place_id = Column(UUID(as_uuid=True), ForeignKey("places.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text, nullable=False)
    summary = Column(Text)  # Суммаризация от LLM
    moderation_status = Column(String(20), default=ModerationStatus.PENDING, nullable=False)
    moderated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    moderation_notes = Column(Text)
    llm_check = Column(JSONB)  # Результат проверки LLM
    photos = Column(JSONB)  # Ссылки на фотографии
    
    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="reviews")
    moderator = relationship("User", foreign_keys=[moderated_by], back_populates="moderated_reviews")
    place = relationship("Place", back_populates="reviews")
    
    def __repr__(self):
        return f"<Review(id={self.id}, rating={self.rating}, status={self.moderation_status})>"
# shared/models/place.py
import uuid
from sqlalchemy import Column, String, Text, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from .base import Base, TimestampMixin
from .enums import PlaceCategory, SourceType

class Place(Base, TimestampMixin):
    """Модель места/мероприятия"""
    __tablename__ = "places"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    category = Column(String(50), default=PlaceCategory.OTHER, nullable=False)
    city = Column(String(100), default="Moscow", nullable=False)
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)
    price_level = Column(Integer, default=2)  # 1-5
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    source = Column(String(50), default=SourceType.USER, nullable=False)
    external_id = Column(String(255))  # ID из внешнего источника
    external_url = Column(Text)
    additional_data = Column(JSONB)  # Дополнительные данные
    is_active = Column(Boolean, default=True)
    
    # Связи
    reviews = relationship("Review", back_populates="place")
    
    def __repr__(self):
        return f"<Place(id={self.id}, name={self.name[:30]}, category={self.category})>"
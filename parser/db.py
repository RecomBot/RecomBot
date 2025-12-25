# db.py
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean,
    SmallInteger, Numeric, ForeignKey, DateTime
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from shared.config import config
DATABASE_URL = config.DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

# ----- enum-таблицы -----

class UserRoleEnum(Base):
    __tablename__ = "user_role_enum"
    value = Column(String(20), primary_key=True)


class PlaceTypeEnum(Base):
    __tablename__ = "place_type_enum"
    value = Column(String(20), primary_key=True)


class SourceEnum(Base):
    __tablename__ = "source_enum"
    value = Column(String(50), primary_key=True)


class ModerationStatusEnum(Base):
    __tablename__ = "moderation_status_enum"
    value = Column(String(20), primary_key=True)


# ----- основные таблицы -----

class Place(Base):
    __tablename__ = "place"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    type = Column(String(20), ForeignKey("place_type_enum.value"))
    price_level = Column(SmallInteger)
    avg_rating = Column(Numeric(3, 2), default=0)
    rating_count = Column(Integer, default=0)
    source = Column(String(50), ForeignKey("source_enum.value"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    categories = relationship("PlaceCategory", back_populates="place")
    reviews = relationship("Review", back_populates="place")
    interactions = relationship("UserInteraction", back_populates="place")


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer)
    username = Column(Text)
    role = Column(String(20), ForeignKey("user_role_enum.value"))
    preferences = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # отзывы, где пользователь автор
    reviews = relationship(
        "Review",
        back_populates="user",
        foreign_keys="Review.user_id",
    )
    # отзывы, которые этот пользователь модерировал
    moderated_reviews = relationship(
        "Review",
        back_populates="moderator",
        foreign_keys="Review.moderated_by",
    )

    interactions = relationship("UserInteraction", back_populates="user")



class Review(Base):
    __tablename__ = "review"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    place_id = Column(Integer, ForeignKey("place.id"), nullable=False)
    rating = Column(SmallInteger)
    text = Column(Text)
    moderation_status = Column(
        String(20), ForeignKey("moderation_status_enum.value")
    )
    moderated_by = Column(Integer, ForeignKey("user.id"))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="reviews",
    )
    moderator = relationship(
        "User",
        foreign_keys=[moderated_by],
        back_populates="moderated_reviews",
    )
    place = relationship("Place", back_populates="reviews")
    photos = relationship("ReviewPhoto", back_populates="review")



class Category(Base):
    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)

    places = relationship("PlaceCategory", back_populates="category")


class PlaceCategory(Base):
    __tablename__ = "place_category"

    place_id = Column(Integer, ForeignKey("place.id"), primary_key=True)
    category_id = Column(Integer, ForeignKey("category.id"), primary_key=True)

    place = relationship("Place", back_populates="categories")
    category = relationship("Category", back_populates="places")


class ReviewPhoto(Base):
    __tablename__ = "review_photo"

    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("review.id"), nullable=False)
    file_path = Column(Text)
    telegram_file_id = Column(Text)

    review = relationship("Review", back_populates="photos")


class UserInteraction(Base):
    __tablename__ = "user_interaction"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    place_id = Column(Integer, ForeignKey("place.id"), nullable=False)
    interaction_type = Column(Text)    # click, open_url и т.п.
    meta = Column("metadata", JSONB)

    user = relationship("User", back_populates="interactions")
    place = relationship("Place", back_populates="interactions")


class LLMDynamicCache(Base):
    __tablename__ = "llm_dynamic_cache"

    id = Column(Integer, primary_key=True)
    response = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    prompt_hash = Column(String(64))
    user_profile_hash = Column(String(64))


def init_db():
    """Создаёт таблицы и заполняет базовые enum‑значения."""
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # заполним enum‑значения, если их ещё нет
        defaults_user_roles = ["user", "admin", "moderator"]
        for r in defaults_user_roles:
            if not session.get(UserRoleEnum, r):
                session.add(UserRoleEnum(value=r))

        defaults_place_types = ["concert", "theatre", "art", "cinema",
                                "excursions", "quest"]
        for t in defaults_place_types:
            if not session.get(PlaceTypeEnum, t):
                session.add(PlaceTypeEnum(value=t))

        defaults_sources = ["yandex_afisha"]
        for s in defaults_sources:
            if not session.get(SourceEnum, s):
                session.add(SourceEnum(value=s))

        defaults_moderation = ["pending", "approved", "rejected"]
        for m in defaults_moderation:
            if not session.get(ModerationStatusEnum, m):
                session.add(ModerationStatusEnum(value=m))

        session.commit()
    finally:
        session.close()

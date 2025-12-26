# bot/models/place.py
from typing import Optional

class Place:
    def __init__(self, id: int, name: str, description: str, category: str, address: str, rating_avg: float, rating_count: int):
        self.id = id
        self.name = name
        self.description = description
        self.category = category
        self.address = address
        self.rating_avg = rating_avg
        self.rating_count = rating_count
    
    @property
    def rating_stars(self) -> str:
        """Возвращает ⭐ 4.7 (23)"""
        full_stars = int(self.rating_avg)
        half_star = "½" if self.rating_avg - full_stars >= 0.5 else ""
        return f"{'⭐' * full_stars}{half_star} {self.rating_avg:.1f} ({self.rating_count})"
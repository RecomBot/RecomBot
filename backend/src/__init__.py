# backend/src/__init__.py
"""
Пакет backend
"""

import os
import sys

# Добавляем текущую директорию в путь для корректных импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
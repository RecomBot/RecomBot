# backend/test_modular_final.py
"""
Скрипт для проверки работоспособности модульной структуры
"""

import sys
import os

# Добавляем src в путь Python
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def test_imports():
    """Проверка импортов всех модулей"""
    print("🔍 Проверка импортов модулей...")
    
    modules_to_test = [
        "config",
        "database",
        "dependencies",
        "main",
        "services.llm_service",
        "routers.auth",
        "routers.places",
        "routers.reviews",
        "routers.moderation",
        "routers.recommendations",
        "utils.rating_updater",
    ]
    
    for module_path in modules_to_test:
        try:
            __import__(module_path)
            print(f"  ✅ {module_path}")
        except ImportError as e:
            print(f"  ❌ {module_path}: {e}")
            return False
    
    print("\n✅ Все модули импортируются корректно!")
    return True


def check_file_structure():
    """Проверка структуры файлов"""
    print("\n📁 Проверка структуры файлов...")
    
    expected_files = [
        "src/main.py",
        "src/config.py",
        "src/database.py",
        "src/dependencies.py",
        "src/models/__init__.py",
        "src/schemas/__init__.py",
        "src/schemas/user.py",
        "src/schemas/place.py",
        "src/schemas/review.py",
        "src/schemas/recommendation.py",
        "src/services/__init__.py",
        "src/services/llm_service.py",
        "src/routers/__init__.py",
        "src/routers/auth.py",
        "src/routers/places.py",
        "src/routers/reviews.py",
        "src/routers/moderation.py",
        "src/routers/recommendations.py",
        "src/utils/__init__.py",
        "src/utils/rating_updater.py",
    ]
    
    missing_files = []
    for file_path in expected_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print(f"  ❌ Отсутствуют файлы:")
        for file in missing_files:
            print(f"     - {file}")
        return False
    else:
        print("  ✅ Все файлы на месте")
        return True


def main():
    print("=" * 60)
    print("ПРОВЕРКА МОДУЛЬНОЙ СТРУКТУРЫ ПРОЕКТА")
    print("=" * 60)
    
    results = []
    
    # Проверяем импорты
    results.append(("Проверка импортов", test_imports()))
    
    # Проверяем структуру файлов
    results.append(("Проверка структуры файлов", check_file_structure()))
    
    print("\n" + "=" * 60)
    print("ИТОГИ:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ ПРОЙДЕНО" if result else "❌ НЕ ПРОЙДЕНО"
        print(f"{name}: {status}")
    
    print(f"\nПроцент успеха: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 МОДУЛЬНАЯ СТРУКТУРА ГОТОВА К ИСПОЛЬЗОВАНИЮ!")
        print("\nСледующие шаги:")
        print("1. Запустите: docker-compose up -d")
        print("2. Проверьте API: http://localhost:8000/docs")
        print("3. Удалите старый main_single.py (если уверены)")
    else:
        print("\n⚠️  НЕОБХОДИМО ИСПРАВИТЬ ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ")

if __name__ == "__main__":
    main()
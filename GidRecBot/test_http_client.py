# GidRecBot/test_http_client.py
import asyncio
import sys
import os

# Добавляем путь к shared
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bot.utils.http_client import http_client

async def test_http_client():
    print("🧪 Тестирование HTTP клиента...")
    
    # 1. Проверка health
    print("1. Проверка health...")
    health = await http_client.health_check()
    print(f"   Health: {'✅' if health else '❌'}")
    
    if not health:
        print("   API недоступен, пропускаем остальные тесты")
        return
    
    # 2. Проверка LLM статуса
    print("2. Проверка LLM статуса...")
    llm_status = await http_client.llm_status()
    print(f"   LLM: {llm_status.get('status', 'unknown')}")
    
    # 3. Регистрация тестового пользователя
    print("3. Регистрация пользователя...")
    try:
        user = await http_client.register_user(
            tg_id=999999999,  # Тестовый ID
            location="Moscow",
            username="test_user"
        )
        print(f"   ✅ Пользователь создан: {user.get('id')}")
        
        # 4. Получение пользователя
        print("4. Получение пользователя...")
        user2 = await http_client.get_user_by_tg_id(999999999)
        print(f"   ✅ Пользователь найден: {user2.get('id')}")
        
        # 5. Получение мест
        print("5. Получение мест...")
        places = await http_client.get_places(city="Moscow", limit=3)
        print(f"   ✅ Найдено мест: {len(places)}")
        
        if places:
            # 6. Получение деталей места
            print("6. Получение деталей места...")
            place = await http_client.get_place(places[0]["id"])
            print(f"   ✅ Место: {place.get('name')}")
        
        # 7. Рекомендации
        print("7. Тест рекомендаций...")
        try:
            recs = await http_client.recommend(
                tg_id=999999999,
                query="кафе в Москве"
            )
            print(f"   ✅ Рекомендации получены: {len(recs.get('places', []))} мест")
        except Exception as e:
            print(f"   ⚠️ Рекомендации не работают: {e}")
        
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    finally:
        # Закрываем клиент
        await http_client.close()
        print("✅ HTTP клиент закрыт")

if __name__ == "__main__":
    asyncio.run(test_http_client())
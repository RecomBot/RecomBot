# test_backend.py
import asyncio
import httpx
import json

async def test_backend():
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🧪 Тестирование Backend API...")
        
        # 1. Health check
        try:
            resp = await client.get(f"{base_url}/health")
            print(f"✅ Health: {resp.status_code} - {resp.json().get('status')}")
        except Exception as e:
            print(f"❌ Health failed: {e}")
            return
        
        # 2. Создание тестового пользователя
        print("\n2. Тестирование регистрации пользователя...")
        try:
            resp = await client.post(
                f"{base_url}/api/v1/auth/",
                json={
                    "telegram_id": 999999999,
                    "location": "Moscow",
                    "username": "test_user"
                }
            )
            user = resp.json()
            print(f"✅ User created: {user.get('id')}")
        except Exception as e:
            print(f"❌ User creation failed: {e}")
        
        # 3. Получение пользователя
        print("\n3. Получение пользователя...")
        try:
            resp = await client.get(f"{base_url}/api/v1/auth/by_tg/999999999")
            print(f"✅ User retrieved: {resp.status_code}")
        except Exception as e:
            print(f"❌ User retrieval failed: {e}")
        
        # 4. Получение списка мест
        print("\n4. Получение мест...")
        try:
            resp = await client.get(f"{base_url}/api/v1/places/?city=Moscow&limit=3")
            places = resp.json()
            print(f"✅ Places found: {len(places)}")
            
            if places:
                # 5. Детали места
                place_id = places[0]["id"]
                resp = await client.get(f"{base_url}/api/v1/places/{place_id}")
                print(f"✅ Place details: {resp.json().get('name')}")
        except Exception as e:
            print(f"❌ Places failed: {e}")
        
        # 6. Тестирование рекомендаций
        print("\n6. Тестирование рекомендаций...")
        try:
            resp = await client.post(
                f"{base_url}/api/v1/recommendations/search",
                json={
                    "query": "кафе в Москве",
                    "telegram_id": 999999999,
                    "limit": 3
                }
            )
            recs = resp.json()
            print(f"✅ Recommendations: {len(recs.get('places', []))} places")
        except Exception as e:
            print(f"⚠️ Recommendations failed (maybe LLM issue): {e}")
        
        print("\n✅ Backend тестирование завершено!")

if __name__ == "__main__":
    asyncio.run(test_backend())
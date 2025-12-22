# mock_server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockServer")

users = {}
user_id_counter = 1

PLACES = [
    {
        "id": 1,
        "name": "Кофейня у Патриарших",
        "description": "Уютное место с домашней выпечкой и ароматным кофе.",
        "category": "cafe",
        "address": "Тверская, 12",
        "rating_avg": 4.7,
        "rating_count": 23
    },
    {
        "id": 2,
        "name": "Музей современного искусства",
        "description": "Интерактивные выставки и лекции от художников.",
        "category": "museum",
        "address": "Петровка, 25",
        "rating_avg": 4.5,
        "rating_count": 41
    },
    {
        "id": 3,
        "name": "Парк Горького",
        "description": "Зелёная зона с прокатом велосипедов и летней верандой.",
        "category": "park",
        "address": "Крымский Вал, 9",
        "rating_avg": 4.8,
        "rating_count": 156
    }
]

class MockHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):  # ✅ ИСПРАВЛЕНО:  dict
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_POST(self):
        if self.path == "/api/users/":
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            global user_id_counter
            user_id = user_id_counter
            data["id"] = user_id
            users[user_id] = data
            user_id_counter += 1
            
            self._send_json(201, data)  # ✅ Теперь data определён
            logger.info(f"✅ Пользователь {data.get('tg_id')} → id={user_id} (город: {data.get('location')})")
        
        elif self.path == "/api/llm/recommend":
            response = {
                "text": "Вот 3 места, которые подойдут вам:",
                "places": PLACES[:3]
            }
            self._send_json(200, response)
            logger.info("🧠 LLM-рекомендация: отправлено")
        
        else:
            self._send_json(404, {"detail": "Not found"})

    def do_GET(self):
        if self.path.startswith("/api/users/by_tg/"):
            tg_id = int(self.path.split("/")[-1])
            for user in users.values():
                if user.get("tg_id") == tg_id:
                    self._send_json(200, user)  # ✅ Теперь работает
                    return
            self._send_json(404, {"detail": "Not found"})
        
        elif self.path.startswith("/api/places"):
            self._send_json(200, PLACES)
        
        else:
            self._send_json(404, {"detail": "Not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(("localhost", 8000), MockHandler)
    logger.info("🚀 Mock-сервер запущен на http://localhost:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("🛑 Mock-сервер остановлен")
        server.server_close()
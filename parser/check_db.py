# reset_db.py
from db import engine, Base

if __name__ == "__main__":
    # удалить ВСЕ таблицы, описанные в db.Base
    Base.metadata.drop_all(bind=engine)
    print("Все таблицы из моделей удалены")

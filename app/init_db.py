from app.db.database import create_tables, SessionLocal
from app.db import crud

# 1. Создаём таблицы users и messages
create_tables()
print("Таблицы созданы!")

# 2. Тестовый прогон всех CRUD-функций
db = SessionLocal()
try:
    user = crud.get_or_create_user(db, telegram_id=123456789, username="test_dev", first_name="Тест")
    print(f"Пользователь -> id={user.id}, telegram_id={user.telegram_id}, username={user.username}")

    crud.add_message(db, user.id, "user", "Как создать лид через API Bitrix24?")
    crud.add_message(db, user.id, "assistant", "Используйте метод crm.lead.add с полями TITLE, NAME...")
    print("Сообщений добавлено: 2")

    print("История диалога:")
    for m in crud.get_user_history(db, user.id):
        print(f"  [{m.role}] {m.content}")
finally:
    db.close()

print("Проверка БД пройдена!")
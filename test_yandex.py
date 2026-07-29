import asyncio
from app.rag.yandex_assistant import answer, get_kb, retrieve

async def main():
    kb = get_kb()
    print("Методов в базе знаний:", len(kb))
    if not kb:
        print("ПУСТО! Проверь, что bitrix_api_docs.json лежит в корне проекта.")
        return

    # Показываем, что нашёл retrieval
    q1 = "Как добавить лид в CRM?"
    print("\n=== Вопрос:", q1)
    print("Retrieval нашёл:", [d["title"] for d in retrieve(q1)])
    print("Ответ YandexGPT:\n", await answer(q1))

    q2 = "Расскажи про метод im.chat.add"
    print("\n=== Вопрос:", q2)
    print("Retrieval нашёл:", [d["title"] for d in retrieve(q2)])
    print("Ответ YandexGPT:\n", await answer(q2))

asyncio.run(main())

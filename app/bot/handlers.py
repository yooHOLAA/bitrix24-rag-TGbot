import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes
from ..db.database import SessionLocal
from ..db import crud
from ..rag.yandex_assistant import answer, update_kb_via_parser

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие + регистрация пользователя в БД."""
    user = update.effective_user
    db = SessionLocal()
    try:
        crud.get_or_create_user(db, telegram_id=user.id, username=user.username, first_name=user.first_name)
    finally:
        db.close()
    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я — интеллектуальный помощник по REST API Битрикс24. 🤖\n"
        "Задай вопрос по документации, например:\n"
        "• Как добавить лид в CRM?\n"
        "• Расскажи про метод im.chat.add\n"
        "• Какие параметры у crm.item.add?\n\n"
        "Команды:\n"
        "/update — обновить базу знаний (перепарсить документацию)\n"
        "/start — это сообщение"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик: вопрос -> RAG (поиск + YandexGPT) -> ответ."""
    question = update.message.text
    tg_user = update.effective_user

    # 1. Сохраняем вопрос пользователя в БД (история взаимодействий)
    db = SessionLocal()
    try:
        user = crud.get_or_create_user(
            db, telegram_id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name
        )
        crud.add_message(db, user.id, "user", question)
        user_id = user.id
    finally:
        db.close()

    # 2. Показываем "печатает...", пока мозг думает
    await update.effective_chat.send_action(ChatAction.TYPING)

    # 3. RAG: поиск по базе знаний + генерация ответа через YandexGPT
    response = await answer(question)

    # 4. Сохраняем ответ бота в БД
    db = SessionLocal()
    try:
        crud.add_message(db, user_id, "assistant", response)
    finally:
        db.close()

    # 5. Отправляем ответ
    await update.message.reply_text(response)


async def update_kb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /update: перепарсить документацию и обновить базу знаний на лету."""
    await update.message.reply_text(
        "🔄 Обновляю базу знаний: парсю документацию Bitrix24...\n"
        "Это займёт 1–2 минуты, подожди. ⏳"
    )
    await update.effective_chat.send_action(ChatAction.TYPING)
    try:
        count = await update_kb_via_parser()
        await update.message.reply_text(f"✅ База знаний обновлена! Теперь в ней {count} методов API.")
    except Exception as e:
        logger.exception("Ошибка обновления базы знаний: %s", e)
        await update.message.reply_text(f"⚠️ Не удалось обновить базу знаний: {type(e).__name__}: {e}")

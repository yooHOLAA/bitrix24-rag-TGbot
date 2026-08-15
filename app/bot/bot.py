import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from ..config import get_settings
from .handlers import start, handle_message, update_kb

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def error_handler(update, context):
    """Аккуратно логируем ошибки, чтобы бот не падал."""
    logger.error("Ошибка при обработке обновления: %s", context.error)


def main():
    # Увеличенные таймауты - спасение при нестабильной сети
    request = HTTPXRequest(
        connect_timeout=30, read_timeout=30, write_timeout=30, pool_timeout=30
    )

    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .request(request)
        .get_updates_request(request)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("update", update_kb))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    logger.info("Бот запущен и ждёт сообщений...")
    application.run_polling(bootstrap_retries=-1)


if __name__ == "__main__":
    main()

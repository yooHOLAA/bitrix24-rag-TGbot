import os
import re
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# --- Настройки YandexGPT ---
FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")
API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEXGPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
# Актуальная модель. Для YandexGPT 5 явно: f"gpt://{FOLDER_ID}/yandexgpt-5/latest"
MODEL_URI = f"gpt://{FOLDER_ID}/yandexgpt/latest"

# Путь к базе знаний (корень проекта, независимо от cwd)
KB_PATH = Path(__file__).resolve().parents[2] / "bitrix_api_docs.json"

# Стоп-слова, которые шумят при поиске (применяются только к вопросу)
STOP_WORDS = {
    "как", "что", "где", "когда", "почему", "зачем", "какой", "какая", "какие",
    "мне", "можно", "нужно", "через", "метод", "метода", "методы", "api",
    "битрикс", "bitrix", "битрикс24", "the", "a", "an", "is", "to", "of", "in",
    "и", "в", "на", "с", "по", "для", "или", "не", "это", "его", "её",
}

# База знаний в памяти (ленивая загрузка)
_KB = None


def _flatten_params(params, max_params=15):
    """Превращает список параметров в читаемый текст (обрезаем, чтобы не раздувать промпт)."""
    lines = []
    for p in params[:max_params]:
        name = p.get("name", "").strip()
        ptype = p.get("type", "").strip()
        desc = (p.get("description", "") or "").strip().replace("\n", " ")[:120]
        if name:
            lines.append(f"  - {name} ({ptype}): {desc}" if ptype else f"  - {name}: {desc}")
    return "\n".join(lines)


def get_kb():
    """Загружает базу знаний из JSON в память (один раз)."""
    global _KB
    if _KB is not None:
        return _KB
    _KB = []
    if not KB_PATH.exists():
        logger.warning("База знаний не найдена: %s", KB_PATH)
        return _KB
    with open(KB_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for section_title, section in data.items():
        for method in section.get("methods", []):
            params_text = _flatten_params(method.get("params", []))
            _KB.append({
                "section": section_title,
                "title": method.get("title", ""),
                "url": method.get("url", ""),
                "description": method.get("description", ""),
                "params_text": params_text,
                # Текст для поиска по ключевым словам
                "search_text": (
                    method.get("title", "") + " " +
                    method.get("description", "") + " " +
                    params_text
                ).lower(),
            })
    logger.info("База знаний загружена: %d методов", len(_KB))
    return _KB


def reload_kb():
    """Перечитывает базу знаний с диска (после обновления парсером)."""
    global _KB
    _KB = None
    return get_kb()


def _tokens(text):
    """Токены вопроса без стоп-слов."""
    words = re.findall(r"[a-zа-яё0-9_]+", text.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]


def retrieve(question, top_k=3):
    """R = Retrieval: ищем релевантные методы по ключевым словам."""
    kb = get_kb()
    if not kb:
        return []

    q_tokens = _tokens(question)
    # Если в вопросе есть явное имя метода (crm.lead.add) — даём ему огромный приоритет
    method_in_q = re.search(r"[a-zа-яё]+\.[a-zа-яё]+(?:\.[a-zа-яё]+)+", question, re.IGNORECASE)
    method_name = method_in_q.group(0).lower() if method_in_q else None

    scored = []
    for doc in kb:
        score = 0
        if method_name and method_name in doc["title"].lower():
            score += 1000  # точное попадание по имени метода
        for w in q_tokens:
            if w in doc["search_text"]:
                score += 1
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


def _build_context(docs):
    """Собираем текст контекста из найденных методов."""
    blocks = []
    for i, doc in enumerate(docs, 1):
        block = (
            f"[{i}] Раздел: {doc['section']}\n"
            f"Метод: {doc['title']}\n"
            f"Описание: {doc['description'] or '(нет)'}\n"
        )
        if doc["params_text"]:
            block += f"Параметры:\n{doc['params_text']}\n"
        blocks.append(block)
    return "\n---\n".join(blocks)


SYSTEM_PROMPT = (
    "Ты — эксперт по REST API Битрикс24. Ты отвечаешь разработчикам на вопросы "
    "СТРОГО на основе предоставленной ниже документации. Правила:\n"
    "1. Отвечай только по фактам из документации. Не придумывай методы и параметры.\n"
    "2. Если в документации нет ответа — прямо скажи: «В доступной документации этого нет».\n"
    "3. Отвечай кратко, по делу, на русском языке. Приводи имена методов и параметров.\n"
    "4. Если уместно — покажи короткий пример структуры запроса."
)


async def ask_yandexgpt(question, context):
    """G = Generation: отправляем контекст + вопрос в YandexGPT."""
    if not API_KEY or not FOLDER_ID:
        return "⚠️ В .env не заданы YANDEX_API_KEY или YANDEX_FOLDER_ID."

    user_text = (
        f"ДОКУМЕНТАЦИЯ:\n{context}\n\n"
        f"ВОПРОС РАЗРАБОТЧИКА: {question}\n\n"
        f"ОТВЕТ:"
    )
    payload = {
        "modelUri": MODEL_URI,
        "completionOptions": {"stream": False, "temperature": 0.3},
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": user_text},
        ],
    }
    headers = {
        "Authorization": f"Api-Key {API_KEY}",
        "x-folder-id": FOLDER_ID,
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(YANDEXGPT_URL, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["result"]["alternatives"][0]["message"]["text"].strip()
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300]
        logger.error("YandexGPT HTTP %s: %s", e.response.status_code, body)
        if e.response.status_code in (401, 403):
            return ("⚠️ Ошибка доступа к YandexGPT (401/403). Проверь: "
                    "1) API-ключ в .env; 2) у сервисного аккаунта роль ai.editor; "
                    "3) у ключа область действия yc.ai.foundationModels.execute.")
        return f"⚠️ YandexGPT вернул ошибку {e.response.status_code}: {body}"
    except Exception as e:
        logger.exception("Ошибка YandexGPT: %s", e)
        return f"⚠️ Не удалось получить ответ от YandexGPT: {type(e).__name__}"


async def answer(question):
    """Главная функция: RAG = retrieve + generate."""
    docs = retrieve(question)
    if not docs:
        return ("🤔 В базе знаний не нашёл методов по этому вопросу. "
                "Попробуй указать имя метода (например, crm.lead.add) или "
                "обнови базу командой /update.")
    context = _build_context(docs)
    return await ask_yandexgpt(question, context)


async def update_kb_via_parser():
    """Обновление базы знаний: запускает парсер и перечитывает JSON."""
    import asyncio
    from ..parser.bitrix_parser import main as parser_main
    await asyncio.to_thread(parser_main)  # парсер синхронный -> в отдельный поток
    kb = reload_kb()
    return len(kb)

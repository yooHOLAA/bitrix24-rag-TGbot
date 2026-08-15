"""Модуль Yandex Assistant: RAG с векторным поиском (embeddings).

Эмбеддинги базы знаний хранятся в векторном хранилище (vector_store.json)
и загружаются при старте, чтобы бот отвечал мгновенно.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict

import httpx
import numpy as np

from ..config import get_settings

logger = logging.getLogger(__name__)

KB_PATH = Path(__file__).resolve().parents[2] / "bitrix_api_docs.json"
CACHE_PATH = Path(__file__).resolve().parents[2] / "vector_store.json"

_EMBEDDINGS_CACHE = None


def get_settings_safe():
    return get_settings()


def _flatten_params(params, max_params=15):
    lines = []
    for p in params[:max_params]:
        name = p.get("name", "").strip()
        ptype = p.get("type", "").strip()
        desc = (p.get("description", "") or "").strip().replace("\n", " ")[:120]
        if name:
            lines.append(f"  - {name} ({ptype}): {desc}" if ptype else f"  - {name}: {desc}")
    return "\n".join(lines)


def get_kb():
    if not KB_PATH.exists():
        logger.warning("База знаний не найдена: %s", KB_PATH)
        return []
    with open(KB_PATH, encoding="utf-8") as f:
        data = json.load(f)
    kb = []
    for section_title, section in data.items():
        for method in section.get("methods", []):
            params_text = _flatten_params(method.get("params", []))
            kb.append({
                "section": section_title,
                "title": method.get("title", ""),
                "url": method.get("url", ""),
                "description": method.get("description", ""),
                "params_text": params_text,
            })
    logger.info("База знаний загружена: %d методов", len(kb))
    return kb


async def get_embedding(text: str, model_uri: str, max_retries: int = 3) -> np.ndarray:
    settings = get_settings_safe()
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"
    headers = {
        "Authorization": f"Api-Key {settings.YANDEX_API_KEY}",
        "x-folder-id": settings.YANDEX_FOLDER_ID,
    }
    payload = {"modelUri": model_uri, "text": text}
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                emb = r.json().get("embedding", [])
                if emb:
                    return np.array(emb, dtype=np.float32)
                return np.array([], dtype=np.float32)
        except Exception as e:
            logger.warning("Эмбеддинг, попытка %d/%d: %s", attempt + 1, max_retries, type(e).__name__)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return np.array([], dtype=np.float32)


def _save_cache():
    global _EMBEDDINGS_CACHE
    data = [{"doc": i["doc"], "embedding": i["embedding"].tolist()} for i in (_EMBEDDINGS_CACHE or [])]
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    logger.info("Векторное хранилище сохранено: %s (%d векторов)", CACHE_PATH, len(data))


def _load_cache():
    if not CACHE_PATH.exists():
        return None
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        cache = [{"doc": i["doc"], "embedding": np.array(i["embedding"], dtype=np.float32)} for i in data]
        logger.info("Векторное хранилище загружено из файла: %d векторов", len(cache))
        return cache
    except Exception as e:
        logger.warning("Не удалось загрузить кэш: %s", e)
        return None


async def build_embeddings_cache(force: bool = False):
    """Загружает кэш из файла, либо строит с нуля и сохраняет."""
    global _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is not None:
        return _EMBEDDINGS_CACHE
    if not force:
        cached = _load_cache()
        if cached:
            _EMBEDDINGS_CACHE = cached
            return _EMBEDDINGS_CACHE

    logger.info("Строю векторное хранилище с нуля...")
    settings = get_settings_safe()
    kb = get_kb()
    _EMBEDDINGS_CACHE = []
    total = len(kb)
    for i, doc in enumerate(kb, 1):
        text = f"{doc['title']}. {doc['description']} {doc['params_text'][:300]}"
        emb = await get_embedding(text, settings.embedding_doc_uri)
        if emb.size > 0:
            _EMBEDDINGS_CACHE.append({"doc": doc, "embedding": emb})
        if i % 10 == 0 or i == total:
            logger.info("Прогресс: %d/%d", i, total)
        if i < total:
            await asyncio.sleep(0.3)
    _save_cache()
    return _EMBEDDINGS_CACHE


def cosine_similarity(a, b):
    if a.size == 0 or b.size == 0:
        return 0.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


async def retrieve_embeddings(question: str, top_k: int = 3):
    cache = await build_embeddings_cache()
    if not cache:
        return []
    settings = get_settings_safe()
    q_emb = await get_embedding(question, settings.embedding_query_uri)
    if q_emb.size == 0:
        return []
    scored = sorted(
        ((cosine_similarity(q_emb, item["embedding"]), item["doc"]) for item in cache),
        key=lambda x: x[0], reverse=True,
    )
    return [doc for _, doc in scored[:top_k]]


def _build_context(docs: List[Dict]) -> str:
    blocks = []
    for i, doc in enumerate(docs, 1):
        block = f"[{i}] Раздел: {doc['section']}\nМетод: {doc['title']}\nОписание: {doc['description'] or '(нет)'}\n"
        if doc["params_text"]:
            block += f"Параметры:\n{doc['params_text']}\n"
        blocks.append(block)
    return "\n---\n".join(blocks)


SYSTEM_PROMPT = (
    "Ты — эксперт по REST API Битрикс24. Отвечай СТРОГО по предоставленной документации. "
    "Не придумывай методы. Если ответа нет — скажи «В доступной документации этого нет». "
    "Отвечай кратко, на русском, приводи имена методов и параметров."
)


async def ask_yandexgpt(question: str, context: str) -> str:
    settings = get_settings_safe()
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    payload = {
        "modelUri": settings.yandexgpt_model_uri,
        "completionOptions": {"stream": False, "temperature": 0.3},
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": f"ДОКУМЕНТАЦИЯ:\n{context}\n\nВОПРОС: {question}\n\nОТВЕТ:"},
        ],
    }
    headers = {
        "Authorization": f"Api-Key {settings.YANDEX_API_KEY}",
        "x-folder-id": settings.YANDEX_FOLDER_ID,
    }
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(url, json=payload, headers=headers)
                r.raise_for_status()
                return r.json()["result"]["alternatives"][0]["message"]["text"].strip()
        except httpx.HTTPStatusError as e:
            logger.error("YandexGPT HTTP %s: %s", e.response.status_code, e.response.text[:300])
            return f"⚠️ YandexGPT вернул ошибку {e.response.status_code}."
        except Exception as e:
            logger.warning("YandexGPT попытка %d/3: %s", attempt + 1, type(e).__name__)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    return "⚠️ Не удалось связаться с YandexGPT (сеть нестабильна). Попробуй ещё раз через пару секунд."


async def answer(question: str) -> str:
    docs = await retrieve_embeddings(question)
    if not docs:
        return ("🤔 В базе знаний не нашёл методов по этому вопросу. "
                "Попробуй указать имя метода (например, crm.lead.add).")
    return await ask_yandexgpt(question, _build_context(docs))


async def update_kb_via_parser():
    from ..parser.bitrix_parser import main as parser_main
    await asyncio.to_thread(parser_main)
    global _EMBEDDINGS_CACHE
    _EMBEDDINGS_CACHE = None
    await build_embeddings_cache(force=True)
    return len(get_kb())

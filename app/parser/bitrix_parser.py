"""Полный парсер документации Bitrix24 API (Selenium + fallback requests).

Парсит ВСЕ разделы и ВСЕ методы API, сохраняет в bitrix_api_docs.json.
С логированием, обработкой ошибок и ретраями.
"""
import json
import re
import time
import logging
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

BASE_URL = "https://apidocs.bitrix24.ru"
OUTPUT_FILE = "bitrix_api_docs.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
METHOD_PATTERN = re.compile(r"\w+\.\w+\.\w+")
SKIP_HREFS = ["data-types", "rest-v3", "developing-with-rest-api", "limits", "error-codes"]

# Настройка логирования (в файл и в консоль)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("parser.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def create_driver():
    """Запускает headless Chrome (Selenium)."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def _fetch_requests(url):
    """Резервный канал: обычный HTTP, если Selenium не смог."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = "utf-8"
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        logger.warning("requests fallback не сработал для %s: %s", url, type(e).__name__)
        return None


def get_soup(driver, url):
    """Selenium (основной) -> при неудаче fallback на requests."""
    try:
        driver.get(url)
        time.sleep(2)
        html = driver.page_source
        if html and len(html) > 2000:
            return BeautifulSoup(html, "html.parser")
    except WebDriverException as e:
        logger.warning("Selenium таймаут/ошибка на %s -> fallback requests", url)
    return _fetch_requests(url)


def parse_api_sections(driver):
    """Парсит главную страницу -> список разделов API."""
    soup = get_soup(driver, BASE_URL)
    if not soup:
        return []
    sections, seen = [], set()
    for a in soup.find_all("a", href=True):
        href, text = a["href"], a.get_text(strip=True)
        if "/api-reference/" in href and "index.html" in href and text:
            full = urljoin(BASE_URL, href)
            if full not in seen:
                seen.add(full)
                sections.append({"title": text, "url": full})
    return sections


def parse_section_methods(driver, section_url):
    """Парсит страницу раздела -> список ВСЕХ методов (без ограничений)."""
    soup = get_soup(driver, section_url)
    if not soup:
        return []
    section_base = section_url.rsplit("index.html", 1)[0]
    methods, seen = [], set()
    for a in soup.find_all("a", href=True):
        href, text = a["href"], a.get_text(strip=True)
        if not (text and href.endswith(".html") and "index.html" not in href):
            continue
        if href.startswith("#") or href.startswith("http"):
            continue
        if any(s in href for s in SKIP_HREFS):
            continue
        if not METHOD_PATTERN.search(text):
            continue
        full = (BASE_URL + "/" + href) if href.startswith("api-reference/") else urljoin(section_url, href)
        if full.startswith(section_base) and full not in seen:
            seen.add(full)
            methods.append({"title": text, "url": full})
    return methods


def parse_method_details(driver, method_url):
    """Парсит страницу метода -> описание + параметры."""
    soup = get_soup(driver, method_url)
    if not soup:
        return None
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else "Unknown"
    description = ""
    if h1:
        for sib in h1.find_next_siblings(["p", "div"]):
            t = sib.get_text(strip=True)
            if t and len(t) > 20:
                description = t[:500]
                break
    params = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                params.append({
                    "name": cells[0].get_text(strip=True),
                    "type": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                    "description": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                })
    return {"title": title, "url": method_url, "description": description, "params": params}


def main():
    logger.info("=" * 60)
    logger.info("ПОЛНЫЙ ПАРСЕР ДОКУМЕНТАЦИИ BITRIX24 API")
    logger.info("=" * 60)
    driver = create_driver()
    try:
        logger.info("Парсю разделы API...")
        sections = parse_api_sections(driver)
        logger.info("Найдено разделов: %d", len(sections))
        api_sections = [s for s in sections if "Справочник" not in s["title"] and "Права" not in s["title"]]
        logger.info("Разделов с методами: %d", len(api_sections))

        result = {}
        total_methods = 0
        for i, section in enumerate(api_sections, 1):
            logger.info("[%d/%d] Раздел: %s", i, len(api_sections), section["title"])
            methods = parse_section_methods(driver, section["url"])
            logger.info("  Найдено методов: %d", len(methods))
            
            detailed = []
            for j, m in enumerate(methods, 1):
                logger.info("  [%d/%d] %s", j, len(methods), m["title"])
                d = parse_method_details(driver, m["url"])
                if d:
                    detailed.append(d)
                else:
                    logger.warning("    Пропускаю (не удалось загрузить): %s", m["title"])
                time.sleep(0.5)  # пауза между запросами
            
            result[section["title"]] = {"url": section["url"], "methods": detailed}
            total_methods += len(detailed)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("=" * 60)
        logger.info("ГОТОВО! Разделов: %d, методов с деталями: %d", len(result), total_methods)
        logger.info("Файл: %s", OUTPUT_FILE)
        logger.info("=" * 60)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

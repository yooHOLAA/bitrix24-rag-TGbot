from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
driver.get("https://apidocs.bitrix24.ru/")
time.sleep(5)  # ждём, пока JS отрендерит контент

html = driver.page_source
soup = BeautifulSoup(html, "html.parser")

print("=" * 60)
print("ЗАГОЛОВОК:", soup.title.string if soup.title else "Нет")
print("=" * 60)

# Все ссылки
links = soup.find_all("a", href=True)
print(f"\nВсего ссылок: {len(links)}")
print("\nПервые 40 ссылок (текст -> href):")
for i, a in enumerate(links[:40]):
    text = a.get_text(strip=True)[:60]
    href = a["href"][:80]
    print(f"  {i+1}. {text} -> {href}")

# Заголовки
print("\n" + "=" * 60)
print("Заголовки h1-h3:")
for tag in soup.find_all(["h1", "h2", "h3"]):
    print(f"  <{tag.name}> {tag.get_text(strip=True)[:80]}")

# Таблицы
tables = soup.find_all("table")
print(f"\nТаблиц на странице: {len(tables)}")

driver.quit()
print("\nРазведка завершена!")

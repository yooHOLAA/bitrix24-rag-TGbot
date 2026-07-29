from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

print("Запускаю браузер...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get("https://apidocs.bitrix24.ru/")
print("Заголовок страницы:", driver.title)
print("URL:", driver.current_url)
print("Длина HTML:", len(driver.page_source), "символов")
driver.quit()
print("Selenium работает!")

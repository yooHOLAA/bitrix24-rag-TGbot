# Telegram RAG-бот по API Bitrix24

Интеллектуальный чат-бот в Telegram, который отвечает разработчикам на вопросы
по документации REST API Битрикс24. Бот понимает вопрос на естественном языке,
находит релевантные методы API в базе знаний и формирует точный ответ с помощью
**YandexGPT** по архитектуре **RAG** (Retrieval-Augmented Generation).

- **База знаний (источник):** https://apidocs.bitrix24.ru/
- **Теги проекта:** чат-бот, telegram, yandex, assistant, rag, kbqa, parsing

---

## Как это работает (RAG)

1. **Парсинг.** Модуль документации (Selenium) скачивает страницы
   `apidocs.bitrix24.ru` и извлекает методы API (название, описание, параметры)
   в файл `bitrix_api_docs.json` — локальную базу знаний.
2. **Retrieval (поиск).** На вопрос пользователя модуль Yandex Assistant ищет
   релевантные методы в базе знаний: лексический поиск по описаниям/параметрам
   + точное совпадение по имени метода (например, `crm.lead.add`).
3. **Generation (генерация).** Найденные методы передаются в **YandexGPT**
   (Foundation Models REST API) вместе с вопросом — модель отвечает строго
   по предоставленной документации, не выдумывая фактов.
4. **История.** Вопросы (`role=user`) и ответы (`role=assistant`) сохраняются
   в PostgreSQL — формируется история взаимодействий с пользователем.

---

## Архитектура проекта (модульная)

Проект разделён на независимые модули, каждый из которых отвечает за свою зону:

```
bitrix24-rag-bot/
├── app/
│   ├── bot/                    # 1. Модуль интеграции с Telegram
│   │   ├── bot.py              #    запуск бота, регистрация обработчиков
│   │   └── handlers.py         #    /start, /update, обработка вопросов (RAG)
│   ├── db/                     # 2. Модуль интеграции с базой данных
│   │   ├── database.py         #    engine, SessionLocal, Base, get_db
│   │   ├── models.py           #    модели User, Message
│   │   └── crud.py             #    функции работы с БД
│   ├── parser/                 # 3. Модуль интеграции с документацией
│   │   └── bitrix_parser.py    #    парсинг apidocs.bitrix24.ru (Selenium)
│   ├── rag/                    # 4. Модуль интеграции с Yandex Assistant
│   │   └── yandex_assistant.py #    RAG: retrieval + генерация YandexGPT
│   ├── main.py                 # 5. Общий модуль - точка входа (соединяет модули)
│   └── init_db.py              #    создание таблиц + тестовые данные
├── bitrix_api_docs.json        # база знаний (результат парсинга)
├── requirements.txt
├── .gitignore
└── README.md
```

| № | Модуль | Путь | Ответственность |
|---|--------|------|-----------------|
| 1 | Telegram | `app/bot/` | Получение сообщений, команды `/start`, `/update`, отправка ответов |
| 2 | База данных | `app/db/` | Пользователи и история диалогов (PostgreSQL + SQLAlchemy) |
| 3 | Документация | `app/parser/` | Парсинг API-документации через Selenium (+ резервный канал requests) |
| 4 | Yandex Assistant | `app/rag/` | Поиск по базе знаний + генерация ответа YandexGPT, обновление базы знаний |
| 5 | Общий модуль | `app/main.py` | Соединение модулей и запуск приложения |

---

## Технологии

- **Python 3**
- **python-telegram-bot** — интеграция с Telegram (асинхронная)
- **PostgreSQL** + **SQLAlchemy** — хранение пользователей и истории
- **Selenium** + **BeautifulSoup** — парсинг документации (рендеринг JavaScript)
- **YandexGPT** — генерация ответов (Foundation Models REST API, клиент `httpx`)
- **python-dotenv** — загрузка секретов из `.env`

---

## Установка

```bash
git clone https://github.com/yooHOLAA/bitrix24-rag-TGbot.git
cd bitrix24-rag-TGbot
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Для работы Selenium нужен браузер **Google Chrome**.
В WSL/Linux:

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
```

---

## Настройка `.env`

Все секретные данные передаются через файл **`.env`** в корне проекта и загружаются
в программу командой **`load_dotenv()`**. Файл `.env` **не попадает в репозиторий**
(исключён в `.gitignore`).

### Список полей, их описания и где взять

| Поле | Описание | Где взять |
|------|----------|-----------|
| `DB_HOST` | Хост сервера PostgreSQL | Обычно `localhost` |
| `DB_PORT` | Порт сервера PostgreSQL | Обычно `5432` |
| `DB_NAME` | Имя базы данных проекта | Создаётся при настройке БД (см. ниже) |
| `DB_USER` | Имя пользователя PostgreSQL | Создаётся при настройке БД |
| `DB_PASSWORD` | Пароль пользователя PostgreSQL | Задаётся при создании пользователя |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота | [@BotFather](https://t.me/BotFather) → команда `/newbot` |
| `YANDEX_FOLDER_ID` | Идентификатор каталога Yandex Cloud (`b1g...`) | Консоль Yandex Cloud → страница каталога → «Идентификатор» |
| `YANDEX_API_KEY` | API-ключ сервисного аккаунта (`AQVN...`) | Yandex Cloud → сервисный аккаунт → «Создать API-ключ» |

### Пример заполнения

```env
# === PostgreSQL ===
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bitrix_rag_db
DB_USER=bitrix_user
DB_PASSWORD=your_db_password_here

# === Telegram Bot ===
TELEGRAM_BOT_TOKEN=1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === Yandex Cloud ===
YANDEX_FOLDER_ID=b1gxxxxxxxxxxxxxxxx
YANDEX_API_KEY=AQVNxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Важно для Yandex Cloud:**
> - у сервисного аккаунта должна быть роль **`ai.editor`** на каталог;
> - у API-ключа область действия — **`yc.ai.foundationModels.execute`**;
> - к облаку должен быть привязан **платёжный аккаунт** (или активирован
>   стартовый грант) — иначе YandexGPT вернёт ошибку доступа `403`.

---

## Настройка базы данных (PostgreSQL)

Создание пользователя и базы:

```bash
sudo -u postgres psql -c "CREATE USER bitrix_user WITH PASSWORD 'your_db_password_here';"
sudo -u postgres psql -c "CREATE DATABASE bitrix_rag_db OWNER bitrix_user;"
sudo -u postgres psql -d bitrix_rag_db -c "GRANT ALL ON SCHEMA public TO bitrix_user;"
```

Создание таблиц (`users`, `messages`) и тестовых данных:

```bash
python3 -m app.init_db
```

### Схема данных

- **users** — пользователи бота: `id`, `telegram_id`, `username`, `first_name`, `created_at`, `updated_at`.
- **messages** — история взаимодействий: `id`, `user_id` (FK → users), `role` (`user`/`assistant`), `content`, `created_at`.
  При удалении пользователя его история удаляется каскадно.

---

## Запуск

```bash
# 1. (один раз) создать таблицы БД
python3 -m app.init_db

# 2. (один раз / по необходимости) спарсить документацию в базу знаний
python3 -m app.parser.bitrix_parser

# 3. запустить бота (единая точка входа)
python3 -m app.main
```

### Команды бота в Telegram

| Команда | Действие |
|---------|----------|
| `/start` | Приветствие и справка по использованию |
| `/update` | Обновить базу знаний — перепарсить документацию на лету |
| любой текст | Вопрос по API Bitrix24 → ответ YandexGPT по документации |

---

## Примеры вопросов

- «Как добавить лид в CRM?»
- «Расскажи про метод im.chat.add»
- «Какие параметры у crm.item.add?»
- «Как получить список задач?»

---

## Обоснование технологических решений

- **SQLAlchemy** — выбран в соответствии с требованием к проекту; обеспечивает
  ORM-доступ к PostgreSQL и декларативное описание моделей.
- **python-telegram-bot** — рекомендован методическими материалами проекта;
  асинхронный, с удобной системой обработчиков и фильтров.
- **YandexGPT через REST API (`httpx`)** вместо `yandexcloud` SDK — официальный
  endpoint Foundation Models (`/foundationModels/v1/completion`) полностью
  покрывает задачу и не требует тяжёлых gRPC-зависимостей SDK, что упрощает
  развёртывание и уменьшает число зависимостей.
- **Selenium + BeautifulSoup** для парсинга — документация рендерится JavaScript'ом,
  поэтому требуется реальный браузер; `requests` оставлен как резервный канал
  для отказоустойчивости при нестабильной сети.
- **Лексический RAG-поиск** вместо векторной БД — для структурированной базы знаний
  (имена методов + описания + параметры) поиск по ключевым словам и точное
  совпадение имени метода дают высокую точность без внешних векторных сервисов;
  при необходимости решение легко расширяется до эмбеддингов.

---

## Демонстрация

Видео-демонстрация работы проекта приложена отдельно: запуск бота, ответы
на вопросы по документации Bitrix24, обновление базы знаний командой `/update`,
история взаимодействий в PostgreSQL.
# Структура проекта

## Дерево файлов

```
telegram-channel-meaning/
├── main.py                    # Точка входа, разбор аргументов
├── requirements.txt           # Зависимости Python
├── README.md                  # Описание проекта
├── .gitignore                 # Игнорируемые файлы Git
│
├── config.json               # Конфигурация (создаётся при работе)
├── data.db                   # SQLite база (создаётся при работе)
├── session.session           # Telethon сессия (создаётся при авторизации)
│
├── core/                     # Ядро приложения
│   ├── __init__.py
│   ├── telegram_client.py    # Обёртка над Telethon
│   ├── database.py           # Работа с SQLite
│   └── config.py             # Работа с JSON конфигурацией
│
├── modes/                    # Режимы работы
│   ├── __init__.py
│   ├── interactive.py        # Интерактивное меню
│   ├── command.py            # Обработка CLI команд
│   └── webhook.py            # FastAPI вебхук сервер
│
├── utils/                    # Утилиты
│   ├── __init__.py
│   ├── message_chains.py     # Логика цепочек сообщений
│   └── formatters.py         # Форматирование вывода
│
└── docs/                     # Документация
    ├── architecture.md       # Архитектура приложения
    ├── structure.md          # Структура проекта (этот файл)
    ├── database.md           # Схема базы данных
    └── implementation.md     # Детали реализации
```

## Описание директорий

### `/core` - Ядро приложения

Содержит основную бизнес-логику и работу с данными.

| Файл | Описание |
|------|----------|
| `telegram_client.py` | Класс `TelegramClientWrapper` - обёртка над Telethon для работы с Telegram API |
| `database.py` | Класс `Database` - работа с SQLite, CRUD операции |
| `config.py` | Класс `Config` - чтение/запись JSON конфигурации |

### `/modes` - Режимы работы

Реализация различных пользовательских интерфейсов.

| Файл | Описание |
|------|----------|
| `interactive.py` | Класс `InteractiveMode` - текстовое меню с навигацией |
| `command.py` | Класс `CommandHandler` - обработка CLI команд |
| `webhook.py` | FastAPI приложение - HTTP API для отправки сообщений |

### `/utils` - Утилиты

Вспомогательные функции.

| Файл | Описание |
|------|----------|
| `message_chains.py` | Функции для работы с цепочками сообщений (reply threads) |
| `formatters.py` | Функции форматирования вывода (text, JSON) |

## Файлы данных (создаются при работе)

| Файл | Описание |
|------|----------|
| `config.json` | Конфигурация: выбранные каналы, настройки вебхука |
| `data.db` | SQLite база данных с сообщениями и отправителями |
| `session.session` | Файл сессии Telethon (авторизация Telegram) |

## Зависимости

### Основные

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `telethon` | >=1.34.0 | Работа с Telegram API |
| `fastapi` | >=0.109.0 | HTTP сервер для вебхука |
| `uvicorn` | >=0.27.0 | ASGI сервер для FastAPI |
| `httpx` | >=0.26.0 | HTTP клиент для отправки данных |

### Опциональные

| Пакет | Версия | Назначение |
|-------|--------|------------|
| `python-dotenv` | >=1.0.0 | Загрузка переменных из .env файла |

## Импорты между модулями

```
main.py
├── modes.interactive → core.telegram_client, core.database, core.config
├── modes.command → core.telegram_client, core.database, core.config, utils.*
└── modes.webhook → core.telegram_client, core.config

utils.formatters → utils.message_chains
```

# Telegram Channel Manager

CLI приложение для работы с Telegram каналами через Telegram API (Telethon).

## Возможности

- **Интерактивный режим** - удобное меню для управления каналами
- **Командный режим** - CLI команды для автоматизации
- **Вебхук режим** - FastAPI сервер для отправки сообщений через HTTP API

### Функции

- Просмотр информации об аккаунте и каналах
- Получение сообщений из каналов с фильтрацией по периоду
- Группировка сообщений в цепочки (по reply_to)
- Отслеживание изменений реакций
- Сохранение в SQLite базу данных
- Экспорт в JSON формат
- Отправка данных по URL (webhook)
- HTTP API для отправки сообщений

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/YOUR_USERNAME/telegram-channel-meaning.git
cd telegram-channel-meaning

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/macOS
# или
.\venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

## Настройка

1. Получите API credentials на https://my.telegram.org/apps

2. Настройте переменные окружения (выберите один из способов):

### Способ 1: Файл .env (рекомендуется)

Скопируйте файл примера и заполните своими данными:

```bash
# Windows
copy .env.example .env

# Linux/macOS
cp .env.example .env
```

Затем отредактируйте `.env` и укажите свои credentials:

```env
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here

# (опционально) Настройки интерактивного режима
# Количество диалогов на странице при просмотре списка каналов/чатов
DIALOGS_PER_PAGE=20
# Ширина столбца "Название" в таблице списка каналов/чатов
DIALOGS_NAME_COL_WIDTH=30

# (опционально) Временная зона для вывода дат и для --period-dates (IANA, например Europe/Moscow).
# Если не задано — используется UTC (GMT+0).
TIMEZONE=UTC
```

### Способ 2: Переменные окружения системы

```bash
# Windows (PowerShell)
$env:TELEGRAM_API_ID="your_api_id"
$env:TELEGRAM_API_HASH="your_api_hash"

# Linux/macOS
export TELEGRAM_API_ID="your_api_id"
export TELEGRAM_API_HASH="your_api_hash"
```

**Примечание:** Для использования `.env` файла установите `python-dotenv`:
```bash
pip install python-dotenv
```
(уже включено в `requirements.txt`)

## Использование

### Интерактивный режим

```bash
python main.py
```

При первом запуске потребуется авторизация через номер телефона и код из Telegram.

### Командный режим

```bash
# Получить сообщения за последние 24 часа
python main.py --fetch --period-offset 86400 0

# Получить из конкретного канала
python main.py --fetch-channel -1001234567890 --period-offset 3600 0

# Сортировка вывода сообщений (переопределяет настройку в config.json)
python main.py --fetch --period-offset 86400 0 --messages-sort id_asc

# С отслеживанием реакций
python main.py --fetch --track-reactions --output json-reactions

# Отправить результат по URL
python main.py --fetch --output json --send-url https://example.com/webhook

# Очистить старые сообщения (старше 7 дней)
python main.py --clear --clear-period 999999999 604800
```

### Вебхук режим

```bash
# Запустить сервер
python main.py --webhook --port 8080
```

API эндпоинты:
- `GET /health` - проверка работоспособности
- `GET /channels` - список выбранных каналов
- `POST /send` - отправка сообщения (channel_id в JSON)
- `POST /send/{channel_id}` - отправка в указанный канал

Документация API: http://localhost:8080/docs

## Структура проекта

```
telegram-channel-meaning/
├── main.py                    # Точка входа
├── requirements.txt           # Зависимости
├── core/
│   ├── config.py              # JSON конфигурация
│   ├── database.py            # SQLite база данных
│   └── telegram_client.py     # Обёртка над Telethon
├── modes/
│   ├── interactive.py         # Интерактивное меню
│   ├── command.py             # CLI команды
│   └── webhook.py             # FastAPI сервер
├── utils/
│   ├── message_chains.py      # Логика цепочек сообщений
│   ├── formatters.py          # Форматирование вывода
│   └── timezone.py             # Временная зона из .env (TIMEZONE)
└── docs/                      # Документация
    ├── architecture.md        # Архитектура приложения
    ├── structure.md           # Структура проекта
    ├── database.md            # Схема базы данных
    └── implementation.md      # Детали реализации
```

## Документация

Подробная документация находится в директории [docs/](docs/):

- [Архитектура приложения](docs/architecture.md) - диаграммы и описание компонентов
- [Структура проекта](docs/structure.md) - описание файлов и директорий
- [Схема базы данных](docs/database.md) - ER-диаграмма и SQL-схема
- [Детали реализации](docs/implementation.md) - описание API всех модулей

## Аргументы командной строки

| Аргумент | Описание |
|----------|----------|
| `--interactive`, `-i` | Интерактивный режим (по умолчанию) |
| `--webhook`, `-w` | Запустить вебхук-сервер |
| `--port`, `-p` | Порт для вебхук-сервера (8080) |
| `--fetch`, `-f` | Получить сообщения |
| `--fetch-channel ID` | Получить из конкретного канала |
| `--period-offset START END` | Период смещениями в секундах |
| `--period-dates FROM TO` | Период датами (ISO формат); даты интерпретируются в зоне TIMEZONE из .env |
| `--track-reactions` | Отслеживать изменения лайков |
| `--fetch-chains` | Получить начала цепочек |
| `--output FORMAT` | Формат: text, json, json-no-chains, json-reactions |
| `--messages-sort ORDER` | Сортировка сообщений в выводе: `telegram`, `id_asc`, `id_desc` (CLI имеет приоритет над конфигом) |
| `--send-url URL` | Отправить результат по URL |
| `--clear` | Очистить сообщения |
| `--clear-channel ID` | Очистить для канала |
| `--clear-period FROM TO` | Очистить за период |

## Примечания по структуре вывода (несколько каналов)

Если в результате есть сообщения **из нескольких каналов**, вывод группируется по `channel_id`:

- **`--output text`**: печатает отдельные блоки по каналам.
- **`--output json`**: возвращает объект вида:

```json
{
  "channels": [
    {
      "channel_id": 123,
      "standalone_messages": [],
      "chains": [
        { "root": {}, "replies": [] }
      ]
    }
  ]
}
```

- **`--output json-no-chains`**: возвращает объект вида:

```json
{
  "channels": [
    { "channel_id": 123, "messages": [] }
  ]
}
```

При выводе сообщений **только одного канала** структура `json/json-no-chains` остаётся прежней (без обёртки `channels`).

## Лицензия

MIT

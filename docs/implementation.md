# Детали реализации

## Модули ядра

### 1. TelegramClientWrapper (core/telegram_client.py)

Обёртка над `TelethonClient` для упрощения работы с Telegram API.

#### Методы

| Метод | Описание |
|-------|----------|
| `authorize()` | Интерактивная авторизация (телефон + код + 2FA) |
| `get_me()` | Информация о текущем аккаунте |
| `get_dialogs(limit)` | Список каналов/чатов/личных сообщений |
| `get_dialog_info(id)` | Подробная информация о канале/чате |
| `fetch_messages(channel_id, offset_start, offset_end)` | Получение сообщений по смещению |
| `fetch_messages_by_date(channel_id, date_from, date_to, limit, pause_seconds)` | Получение сообщений по датам; при заданном `pause_seconds` — постраничное получение до конца диапазона с паузой между порциями |
| `send_message(channel_id, text)` | Отправка сообщения |

#### Пример использования

```python
async with TelegramClientWrapper(api_id, api_hash) as tg:
    if not await tg.is_authorized():
        await tg.authorize()
    
    me = await tg.get_me()
    print(f"Авторизован как {me['first_name']}")
    
    messages = await tg.fetch_messages_by_date(
        channel_id=-1001234567890,
        date_from=datetime.now() - timedelta(days=1),
        date_to=datetime.now()
    )
```

### 2. Database (core/database.py)

Работа с SQLite базой данных.

#### Методы для отправителей

| Метод | Описание |
|-------|----------|
| `get_or_create_sender(telegram_id, ...)` | Получить или создать отправителя |
| `get_senders_list()` | Список всех отправителей с количеством сообщений |
| `get_sender_by_telegram_id(id)` | Найти отправителя по Telegram ID |

#### Методы для сообщений

| Метод | Описание |
|-------|----------|
| `save_message(...)` | Сохранить или обновить сообщение |
| `get_message(id)` | Получить сообщение по ID |
| `get_messages(channel_id, date_from, date_to)` | Получить сообщения с фильтрацией |
| `get_messages_with_senders(...)` | Сообщения с JOIN на отправителей |
| `clear_messages(channel_id, date_from, date_to)` | Удалить сообщения |

#### Методы для реакций

| Метод | Описание |
|-------|----------|
| `save_reactions_snapshot(message_id, count)` | Сохранить снимок реакций |
| `get_messages_with_reaction_changes(hours)` | Сообщения с изменениями реакций |
| `get_reaction_history(message_id)` | История реакций сообщения |

#### Статистика

| Метод | Описание |
|-------|----------|
| `get_message_counts_by_channel()` | Количество сообщений по каналам |
| `get_statistics()` | Общая статистика базы данных |

### 3. Config (core/config.py)

Работа с JSON конфигурацией.

#### Структура config.json

```json
{
  "selected_channels": [123456, 789012],
  "webhook_default_channel": null,
  "channels_sort_type": "none",
  "messages_sort_order": "telegram"
}
```

Лимиты получения сообщений задаются переменными окружения `FETCH_MESSAGES_LIMIT` и `FETCH_MESSAGES_PAUSE_SECONDS` (см. .env.example).

#### Значения channels_sort_type

- `none` — без сортировки
- `type` — по типу (внутри типа по названию)
- `id` — по ID
- `name` — по названию
- `selected` — выбранные в начале списка
- `type_id` — по типу + по ID
- `type_name` — по типу + по названию
- `type_selected` — по типу + по выбранным (внутри подгрупп по ID)

#### Методы

| Метод | Описание |
|-------|----------|
| `get_selected_channels()` | Список ID выбранных каналов |
| `add_channel(id)` | Добавить канал в выбранные |
| `remove_channel(id)` | Удалить канал из выбранных |
| `set_selected_channels(ids)` | Установить список каналов |
| `get_webhook_default_channel()` | Канал по умолчанию для вебхука |
| `set_webhook_default_channel(id)` | Установить канал для вебхука |
| `get_channels_sort_type()` | Текущий вид сортировки каналов/чатов |
| `set_channels_sort_type(type)` | Установить вид сортировки каналов/чатов |
| `get_fetch_messages_limit()` | Лимит сообщений за один запрос по каналу (из переменной окружения FETCH_MESSAGES_LIMIT) |
| `get_fetch_messages_pause_seconds()` | Пауза между порциями в секундах (из переменной окружения FETCH_MESSAGES_PAUSE_SECONDS) |

---

## Режимы работы

### 4. Interactive Mode (modes/interactive.py)

Многоуровневое меню с нумерацией пунктов.

#### Структура меню

```
=== Главное меню ===
1. Информация об аккаунте
2. Каналы и чаты
3. Отправители
4. Статистика сообщений
0. Выход

Выберите пункт: _
```

При получении сообщений в подменю «Получить сообщения» используется постраничное получение до конца выбранного периода с паузой между порциями (из конфига `fetch_messages_pause_seconds`).

#### Подменю "Каналы и чаты"

```
=== Каналы и чаты ===
1. Показать все каналы/чаты
2. Информация о канале/чате
3. Управление выбранными каналами
4. Получить сообщения
0. Назад
```

### 5. Command Mode (modes/command.py)

Обработка CLI аргументов. При получении сообщений используется постраничное получение до конца диапазона дат с паузой между порциями (из конфига `fetch_messages_pause_seconds`).

#### Аргументы

| Аргумент | Описание |
|----------|----------|
| `--help` | Справка с информацией об аккаунте |
| `--fetch` | Получить сообщения из выбранных каналов |
| `--fetch-channel ID` | Получить из конкретного канала |
| `--limit`, `-l N` | Максимум сообщений за один запрос по каналу (переопределяет конфиг) |
| `--period-offset START END` | Период смещениями в секундах |
| `--period-dates FROM TO` | Период датами (ISO формат); даты интерпретируются в зоне TIMEZONE из .env |
| `--track-reactions` | Отслеживать изменения лайков |
| `--fetch-chains` | Получить начала цепочек |
| `--output FORMAT` | Формат: text, json, json-no-chains, json-reactions |
| `--send-url URL` | Отправить результат по URL |
| `--clear` | Очистить сообщения |
| `--clear-channel ID` | Очистить для канала |
| `--clear-period FROM TO` | Очистить за период |

### 6. Webhook Mode (modes/webhook.py)

FastAPI HTTP сервер.

#### Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/health` | Проверка работоспособности |
| GET | `/channels` | Список выбранных каналов |
| POST | `/send` | Отправка сообщения (channel_id в JSON) |
| POST | `/send/{channel_id}` | Отправка в указанный канал |

#### Модели запросов

```python
class SendMessageRequest(BaseModel):
    channel_id: Optional[int] = None
    message: str
```

#### Пример запроса

```bash
curl -X POST http://localhost:8080/send \
  -H "Content-Type: application/json" \
  -d '{"channel_id": -1001234567890, "message": "Hello!"}'
```

---

## Утилиты

### 7. Message Chains (utils/message_chains.py)

Логика определения цепочек сообщений (reply threads).

#### Функции

| Функция | Описание |
|---------|----------|
| `find_chain_roots(messages)` | Найти корневые сообщения цепочек |
| `build_chains(messages)` | Сгруппировать сообщения в цепочки |
| `separate_standalone_and_chains(messages)` | Разделить на одиночные и цепочки |
| `get_chain_depth(chain)` | Глубина вложенности цепочки |
| `get_chain_statistics(chains)` | Статистика по цепочкам |

#### Логика определения цепочек

1. Сообщение является **корнем** цепочки, если:
   - На него есть ответы (reply)
   - Оно само не является ответом ИЛИ его родитель не в списке

2. Цепочка строится рекурсивно от корня через `reply_to_msg_id`

3. Сообщение **одиночное**, если:
   - На него нет ответов
   - Оно не является ответом на другое сообщение из списка

### 8. Formatters (utils/formatters.py)

Форматирование вывода.

#### Функции

| Функция | Описание |
|---------|----------|
| `format_messages(messages, include_chains)` | Текстовый вывод с цепочками |
| `format_message_json(msg)` | Сообщение в JSON формате |
| `format_reactions_json(msg)` | Сообщение с информацией о реакциях |
| `format_channels_list(channels)` | Список каналов текстом |
| `format_statistics(stats)` | Статистика текстом |

#### Форматы вывода

- **text** - человекочитаемый текст с группировкой по цепочкам
- **json** - JSON с разделением на standalone и chains
- **json-no-chains** - плоский JSON список сообщений
- **json-reactions** - JSON только с изменениями реакций

Даты в выводе (текст и JSON) переводятся в временную зону из переменной окружения **TIMEZONE** (по умолчанию UTC).

### 9. Timezone (utils/timezone.py)

Централизованное получение временной зоны из `.env`.

| Функция | Описание |
|---------|----------|
| `get_timezone()` | Возвращает `ZoneInfo` для зоны из переменной `TIMEZONE`; при пустом или невалидном значении — UTC |

Используется при форматировании дат сообщений и при интерпретации диапазона `--period-dates` (даты считаются в указанной зоне, затем переводятся в UTC для API и БД).

---

## Примеры использования

### Интерактивный режим

```bash
python main.py
```

### Получить сообщения за последние 24 часа

```bash
python main.py --fetch --period-offset 86400 0
```

### Получить не более 500 сообщений по каналу

```bash
python main.py --fetch --limit 500
```

### Получить сообщения с отслеживанием лайков

```bash
python main.py --fetch --track-reactions --output json-reactions
```

### Отправить результат по URL

```bash
python main.py --fetch --output json --send-url https://example.com/hook
```

### Запустить вебхук-сервер

```bash
python main.py --webhook --port 8080
```

### Очистить сообщения старше 7 дней

```bash
python main.py --clear --clear-period 999999999 604800
```

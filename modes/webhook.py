"""
Вебхук режим работы приложения.

FastAPI сервер для отправки сообщений в Telegram каналы через HTTP API.

Эндпоинты:
- POST /send - отправка с channel_id в JSON
- POST /send/{channel_id} - отправка с channel_id в URL
- GET /health - проверка работоспособности
- GET /channels - список выбранных каналов
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn

from core.telegram_client import TelegramClientWrapper
from core.config import Config
from typing import List


# Глобальные переменные для хранения состояния
_telegram_client: Optional[TelegramClientWrapper] = None
_api_id: int = 0
_api_hash: str = ""


class SendMessageRequest(BaseModel):
    """Модель запроса на отправку сообщения."""
    channel_id: Optional[int] = None
    message: str


class SendMessageResponse(BaseModel):
    """Модель ответа на отправку сообщения."""
    success: bool
    message_id: Optional[int] = None
    channel_id: Optional[int] = None
    error: Optional[str] = None


class ChannelInfo(BaseModel):
    """Информация о канале."""
    id: int
    name: Optional[str] = None
    username: Optional[str] = None


class HealthResponse(BaseModel):
    """Ответ проверки здоровья."""
    status: str
    telegram_connected: bool
    telegram_authorized: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для FastAPI приложения."""
    global _telegram_client
    
    # Startup
    print("Запуск вебхук-сервера...")
    _telegram_client = TelegramClientWrapper(_api_id, _api_hash)
    await _telegram_client.connect()
    
    if not await _telegram_client.is_authorized():
        print("ВНИМАНИЕ: Telegram не авторизован!")
        print("Сначала запустите в интерактивном режиме для авторизации:")
        print("  python main.py --interactive")
    else:
        me = await _telegram_client.get_me()
        print(f"Telegram авторизован как: {me['first_name']} (@{me['username']})")
    
    yield
    
    # Shutdown
    print("Остановка вебхук-сервера...")
    if _telegram_client:
        await _telegram_client.disconnect()


# Создаём приложение FastAPI
app = FastAPI(
    title="Telegram Channel Manager",
    description="API для отправки сообщений в Telegram каналы",
    version="1.0.0",
    lifespan=lifespan
)


def _get_type_order_from_dialog_info(info: Optional[dict]) -> int:
    """
    Возвращает порядок типа диалога для сортировки.

    Порядок (как в интерактивном режиме):
    0 - канал (broadcast)
    1 - группа/чат/мегагруппа
    2 - личные сообщения (User)
    99 - неизвестно/нет данных
    """
    if not info:
        return 99

    entity_type = info.get("type")

    if entity_type == "Channel":
        # Канал (broadcast) выше, мегагруппы/прочее ниже
        if info.get("is_broadcast"):
            return 0
        return 1

    if entity_type == "Chat":
        return 1

    if entity_type == "User":
        return 2

    return 99


def _sort_channels_for_api(
    channels: List[ChannelInfo],
    config: Config,
    type_orders: dict[int, int],
) -> List[ChannelInfo]:
    """
    Применяет сортировку к списку каналов для API согласно настройкам.
    
    Args:
        channels: Список ChannelInfo объектов
        config: Объект конфигурации
        type_orders: Словарь channel_id -> type_order (для сортировки по типу)
        
    Returns:
        Отсортированный список каналов
    """
    sort_type = config.get_channels_sort_type()
    selected_ids = set(config.get_selected_channels())

    def type_order(ch: ChannelInfo) -> int:
        return type_orders.get(ch.id, 99)
    
    if sort_type == "none":
        return channels
    
    if sort_type == "selected":
        selected_channels = [ch for ch in channels if ch.id in selected_ids]
        other_channels = [ch for ch in channels if ch.id not in selected_ids]
        return selected_channels + other_channels
    
    if sort_type == "type":
        return sorted(channels, key=lambda ch: (type_order(ch), (ch.name or '').lower()))

    if sort_type == "type_id":
        return sorted(channels, key=lambda ch: (type_order(ch), ch.id))

    if sort_type == "type_name":
        return sorted(channels, key=lambda ch: (type_order(ch), (ch.name or '').lower()))

    if sort_type == "type_selected":
        return sorted(
            channels,
            key=lambda ch: (
                type_order(ch),
                0 if ch.id in selected_ids else 1,
                ch.id,
            ),
        )
    
    if sort_type == "id":
        return sorted(channels, key=lambda ch: ch.id)
    
    if sort_type == "name":
        return sorted(channels, key=lambda ch: (ch.name or '').lower())
    
    return channels


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Проверка работоспособности сервера."""
    connected = _telegram_client is not None and _telegram_client.client.is_connected()
    authorized = False
    
    if connected:
        try:
            authorized = await _telegram_client.is_authorized()
        except Exception:
            pass
    
    return HealthResponse(
        status="ok" if connected and authorized else "degraded",
        telegram_connected=connected,
        telegram_authorized=authorized
    )


@app.get("/channels", response_model=list[ChannelInfo])
async def get_channels():
    """Возвращает список выбранных каналов."""
    config = Config()
    channel_ids = config.get_selected_channels()
    
    channels = []
    type_orders: dict[int, int] = {}
    for channel_id in channel_ids:
        info = await _telegram_client.get_dialog_info(channel_id)
        if info:
            type_orders[channel_id] = _get_type_order_from_dialog_info(info)
            channels.append(ChannelInfo(
                id=channel_id,
                name=info.get('title', info.get('first_name')),
                username=info.get('username')
            ))
        else:
            type_orders[channel_id] = 99
            channels.append(ChannelInfo(id=channel_id))
    
    # Применяем сортировку
    channels = _sort_channels_for_api(channels, config, type_orders)
    
    return channels


@app.post("/send", response_model=SendMessageResponse)
async def send_message(request: SendMessageRequest):
    """
    Отправляет сообщение в канал.
    
    channel_id может быть указан в теле запроса или взят из конфигурации.
    """
    # Проверяем авторизацию
    if not await _telegram_client.is_authorized():
        raise HTTPException(
            status_code=503,
            detail="Telegram не авторизован. Запустите в интерактивном режиме."
        )
    
    # Определяем канал
    channel_id = request.channel_id
    if channel_id is None:
        config = Config()
        channel_id = config.get_webhook_default_channel()
        
        if channel_id is None:
            # Берём первый из выбранных
            selected = config.get_selected_channels()
            if selected:
                channel_id = selected[0]
    
    if channel_id is None:
        raise HTTPException(
            status_code=400,
            detail="channel_id не указан и нет канала по умолчанию"
        )
    
    # Отправляем сообщение
    result = await _telegram_client.send_message(channel_id, request.message)
    
    if result:
        return SendMessageResponse(
            success=True,
            message_id=result['telegram_id'],
            channel_id=channel_id
        )
    else:
        return SendMessageResponse(
            success=False,
            channel_id=channel_id,
            error="Не удалось отправить сообщение"
        )


@app.post("/send/{channel_id}", response_model=SendMessageResponse)
async def send_message_to_channel(channel_id: int, request: SendMessageRequest):
    """
    Отправляет сообщение в указанный канал.
    
    channel_id берётся из URL.
    """
    # Проверяем авторизацию
    if not await _telegram_client.is_authorized():
        raise HTTPException(
            status_code=503,
            detail="Telegram не авторизован. Запустите в интерактивном режиме."
        )
    
    # Отправляем сообщение
    result = await _telegram_client.send_message(channel_id, request.message)
    
    if result:
        return SendMessageResponse(
            success=True,
            message_id=result['telegram_id'],
            channel_id=channel_id
        )
    else:
        return SendMessageResponse(
            success=False,
            channel_id=channel_id,
            error="Не удалось отправить сообщение"
        )


def run_webhook_server(api_id: int, api_hash: str, port: int = 8080):
    """
    Запускает вебхук-сервер.
    
    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash
        port: Порт для сервера
    """
    global _api_id, _api_hash
    _api_id = api_id
    _api_hash = api_hash
    
    print(f"\n=== Telegram Channel Manager - Webhook Server ===")
    print(f"Порт: {port}")
    print(f"Документация: http://localhost:{port}/docs")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

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
    for channel_id in channel_ids:
        info = await _telegram_client.get_dialog_info(channel_id)
        if info:
            channels.append(ChannelInfo(
                id=channel_id,
                name=info.get('title', info.get('first_name')),
                username=info.get('username')
            ))
        else:
            channels.append(ChannelInfo(id=channel_id))
    
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

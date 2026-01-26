"""
Модуль-обёртка над Telethon для работы с Telegram API.

Предоставляет удобный интерфейс для:
- Авторизации
- Получения информации об аккаунте и диалогах
- Получения сообщений из каналов
- Отправки сообщений
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, AsyncIterator

from telethon import TelegramClient
from telethon.tl.types import (
    Channel, Chat, User, Message,
    PeerChannel, PeerChat, PeerUser,
    MessageReactions
)
from telethon.errors import SessionPasswordNeededError


class TelegramClientWrapper:
    """Обёртка над TelegramClient для упрощения работы."""
    
    def __init__(self, api_id: int, api_hash: str, session_path: str = None):
        """
        Инициализация клиента.
        
        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_path: Путь к файлу сессии (по умолчанию session.session)
        """
        if session_path is None:
            base_dir = Path(__file__).parent.parent
            session_path = str(base_dir / "session")
        
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path
        self._client: Optional[TelegramClient] = None
    
    @property
    def client(self) -> TelegramClient:
        """Возвращает клиент Telethon."""
        if self._client is None:
            self._client = TelegramClient(
                self.session_path,
                self.api_id,
                self.api_hash
            )
        return self._client
    
    async def connect(self) -> bool:
        """
        Подключается к Telegram.
        
        Returns:
            True если подключение успешно
        """
        await self.client.connect()
        return self.client.is_connected()
    
    async def disconnect(self) -> None:
        """Отключается от Telegram."""
        if self._client is not None:
            await self._client.disconnect()
    
    async def is_authorized(self) -> bool:
        """Проверяет, авторизован ли пользователь."""
        return await self.client.is_user_authorized()
    
    async def authorize(self) -> bool:
        """
        Выполняет интерактивную авторизацию.
        
        Returns:
            True если авторизация успешна
        """
        if await self.is_authorized():
            return True
        
        phone = input("Введите номер телефона (с кодом страны, например +79001234567): ")
        await self.client.send_code_request(phone)
        
        try:
            code = input("Введите код из Telegram: ")
            await self.client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Введите пароль двухфакторной аутентификации: ")
            await self.client.sign_in(password=password)
        
        return await self.is_authorized()
    
    async def get_me(self) -> Dict[str, Any]:
        """
        Получает информацию о текущем аккаунте.
        
        Returns:
            Словарь с информацией об аккаунте
        """
        me = await self.client.get_me()
        return {
            'id': me.id,
            'first_name': me.first_name,
            'last_name': me.last_name,
            'username': me.username,
            'phone': me.phone,
            'is_premium': getattr(me, 'premium', False)
        }
    
    async def get_dialogs(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Получает список диалогов (каналов, чатов, личных сообщений).
        
        Args:
            limit: Ограничение количества
            
        Returns:
            Список диалогов
        """
        dialogs = await self.client.get_dialogs(limit=limit)
        result = []
        
        for dialog in dialogs:
            entity = dialog.entity
            dialog_info = {
                'id': dialog.id,
                'name': dialog.name,
                'unread_count': dialog.unread_count,
                'is_channel': isinstance(entity, Channel) and entity.broadcast,
                'is_group': isinstance(entity, (Chat, Channel)) and (
                    isinstance(entity, Chat) or 
                    (isinstance(entity, Channel) and entity.megagroup)
                ),
                'is_user': isinstance(entity, User)
            }
            
            if isinstance(entity, Channel):
                dialog_info['username'] = entity.username
                dialog_info['participants_count'] = getattr(entity, 'participants_count', None)
            
            result.append(dialog_info)
        
        return result
    
    async def get_dialog_info(self, dialog_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает подробную информацию о диалоге.
        
        Args:
            dialog_id: ID диалога
            
        Returns:
            Словарь с информацией или None
        """
        try:
            entity = await self.client.get_entity(dialog_id)
        except Exception:
            return None
        
        info = {
            'id': entity.id,
            'type': type(entity).__name__
        }
        
        if isinstance(entity, Channel):
            info.update({
                'title': entity.title,
                'username': entity.username,
                'is_broadcast': entity.broadcast,
                'is_megagroup': entity.megagroup,
                'participants_count': getattr(entity, 'participants_count', None),
                'restricted': entity.restricted,
                'verified': entity.verified
            })
        elif isinstance(entity, Chat):
            info.update({
                'title': entity.title,
                'participants_count': entity.participants_count
            })
        elif isinstance(entity, User):
            info.update({
                'first_name': entity.first_name,
                'last_name': entity.last_name,
                'username': entity.username,
                'phone': entity.phone,
                'is_bot': entity.bot
            })
        
        return info
    
    async def fetch_messages(self, channel_id: int, 
                            offset_start: int = 0, 
                            offset_end: int = None,
                            limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получает сообщения из канала по смещению.
        
        Args:
            channel_id: ID канала
            offset_start: Начальное смещение (в секундах от текущего времени)
            offset_end: Конечное смещение (в секундах от текущего времени)
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений
        """
        now = datetime.utcnow()
        
        if offset_start > 0:
            date_from = now - timedelta(seconds=offset_start)
        else:
            date_from = None
        
        if offset_end is not None and offset_end > 0:
            date_to = now - timedelta(seconds=offset_end)
        else:
            date_to = now
        
        return await self.fetch_messages_by_date(
            channel_id, date_from, date_to, limit
        )
    
    async def fetch_messages_by_date(self, channel_id: int,
                                     date_from: datetime = None,
                                     date_to: datetime = None,
                                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получает сообщения из канала по датам.
        
        Args:
            channel_id: ID канала
            date_from: Начальная дата
            date_to: Конечная дата
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений
        """
        try:
            entity = await self.client.get_entity(channel_id)
        except Exception as e:
            print(f"Ошибка получения канала {channel_id}: {e}")
            return []
        
        messages = []
        
        async for message in self.client.iter_messages(
            entity,
            limit=limit,
            offset_date=date_to,
            reverse=False
        ):
            if date_from and message.date.replace(tzinfo=None) < date_from:
                continue
            if date_to and message.date.replace(tzinfo=None) > date_to:
                continue
            
            msg_dict = self._message_to_dict(message, channel_id)
            messages.append(msg_dict)
        
        return messages
    
    def _message_to_dict(self, message: Message, channel_id: int) -> Dict[str, Any]:
        """Конвертирует объект Message в словарь."""
        # Получаем информацию об отправителе
        sender_info = None
        if message.sender:
            sender = message.sender
            sender_info = {
                'id': sender.id,
                'first_name': getattr(sender, 'first_name', None),
                'last_name': getattr(sender, 'last_name', None),
                'username': getattr(sender, 'username', None)
            }
        
        # Получаем количество реакций
        reactions_count = 0
        if message.reactions:
            for reaction in message.reactions.results:
                reactions_count += reaction.count
        
        # Получаем ID сообщения, на которое ответили
        reply_to_msg_id = None
        if message.reply_to:
            reply_to_msg_id = message.reply_to.reply_to_msg_id
        
        return {
            'telegram_id': message.id,
            'channel_id': channel_id,
            'content': message.text or '',
            'date': message.date.replace(tzinfo=None) if message.date else None,
            'sender': sender_info,
            'reply_to_msg_id': reply_to_msg_id,
            'reactions_count': reactions_count,
            'has_media': message.media is not None,
            'views': message.views,
            'forwards': message.forwards,
            'raw_json': self._message_to_raw_json(message)
        }
    
    def _message_to_raw_json(self, message: Message) -> str:
        """Конвертирует сообщение в JSON строку."""
        try:
            data = {
                'id': message.id,
                'date': message.date.isoformat() if message.date else None,
                'message': message.text,
                'views': message.views,
                'forwards': message.forwards,
                'reactions': None
            }
            
            if message.reactions:
                data['reactions'] = [
                    {'emoji': str(r.reaction), 'count': r.count}
                    for r in message.reactions.results
                ]
            
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            return '{}'
    
    async def send_message(self, channel_id: int, text: str) -> Optional[Dict[str, Any]]:
        """
        Отправляет сообщение в канал.
        
        Args:
            channel_id: ID канала
            text: Текст сообщения
            
        Returns:
            Информация об отправленном сообщении или None
        """
        try:
            entity = await self.client.get_entity(channel_id)
            message = await self.client.send_message(entity, text)
            return self._message_to_dict(message, channel_id)
        except Exception as e:
            print(f"Ошибка отправки сообщения: {e}")
            return None
    
    async def __aenter__(self):
        """Контекстный менеджер - вход."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход."""
        await self.disconnect()
    
    def __repr__(self) -> str:
        return f"TelegramClientWrapper(session={self.session_path})"

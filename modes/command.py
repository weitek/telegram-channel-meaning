"""
Командный режим работы приложения.

Обрабатывает CLI аргументы для:
- Получения сообщений (--fetch)
- Очистки данных (--clear)
- Отслеживания реакций (--track-reactions)
- Отправки результатов по URL (--send-url)
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import httpx

from core.telegram_client import TelegramClientWrapper
from core.database import Database
from core.config import Config
from utils.message_chains import find_chain_roots, build_chains, separate_standalone_and_chains
from utils.formatters import format_messages, format_message_json, format_reactions_json


async def run_command_mode(api_id: int, api_hash: str, args):
    """
    Запускает командный режим.
    
    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash
        args: Аргументы командной строки
    """
    handler = CommandHandler(api_id, api_hash, args)
    await handler.run()


class CommandHandler:
    """Обработчик командного режима."""
    
    def __init__(self, api_id: int, api_hash: str, args):
        self.api_id = api_id
        self.api_hash = api_hash
        self.args = args
        self.database = Database()
        self.config = Config()
        self.telegram: Optional[TelegramClientWrapper] = None
    
    async def run(self):
        """Выполняет команду."""
        async with TelegramClientWrapper(self.api_id, self.api_hash) as tg:
            self.telegram = tg
            
            # Проверяем авторизацию
            if not await tg.is_authorized():
                print("Требуется авторизация. Запустите в интерактивном режиме:")
                print("  python main.py --interactive")
                return
            
            # Выполняем команду
            if self.args.clear:
                await self.handle_clear()
            elif self.args.fetch or self.args.fetch_channel:
                await self.handle_fetch()
    
    async def handle_fetch(self):
        """Обрабатывает команду получения сообщений."""
        # Определяем каналы
        if self.args.fetch_channel:
            channel_ids = [self.args.fetch_channel]
        else:
            channel_ids = self.config.get_selected_channels()
            if not channel_ids:
                print("Ошибка: Нет выбранных каналов.")
                print("Укажите канал через --fetch-channel ID")
                print("или выберите каналы в интерактивном режиме.")
                return
        
        # Определяем период
        date_from, date_to = self._parse_period()
        
        print(f"Получение сообщений...")
        if date_from:
            print(f"  Период: {date_from} - {date_to}")
        print(f"  Каналы: {channel_ids}")
        
        # Получаем сообщения
        all_messages = []
        
        for channel_id in channel_ids:
            messages = await self.telegram.fetch_messages_by_date(
                channel_id, date_from, date_to, limit=1000
            )
            
            # Сохраняем в базу
            for msg in messages:
                sender_id = None
                if msg['sender']:
                    sender_id = self.database.get_or_create_sender(
                        msg['sender']['id'],
                        msg['sender']['first_name'],
                        msg['sender']['last_name'],
                        msg['sender']['username']
                    )
                
                db_msg_id = self.database.save_message(
                    telegram_id=msg['telegram_id'],
                    channel_id=msg['channel_id'],
                    content=msg['content'],
                    date=msg['date'],
                    sender_id=sender_id,
                    reply_to_msg_id=msg['reply_to_msg_id'],
                    reactions_count=msg['reactions_count'],
                    raw_json=msg['raw_json']
                )
                
                # Сохраняем реакции если нужно
                if self.args.track_reactions:
                    self.database.save_reactions_snapshot(
                        db_msg_id, msg['reactions_count']
                    )
            
            all_messages.extend(messages)
            
            info = await self.telegram.get_dialog_info(channel_id)
            name = info.get('title', 'Неизвестно') if info else 'Неизвестно'
            print(f"  {name}: {len(messages)} сообщений")
        
        print(f"\nВсего: {len(all_messages)} сообщений")
        
        # Формируем вывод
        output = self._format_output(all_messages)
        
        # Выводим или отправляем
        if self.args.send_url:
            await self._send_to_url(output)
        else:
            print("\n" + output)
    
    async def handle_clear(self):
        """Обрабатывает команду очистки."""
        channel_id = self.args.clear_channel
        date_from = None
        date_to = None
        
        # Парсим период
        if self.args.clear_period:
            now = datetime.utcnow()
            offset_from, offset_to = self.args.clear_period
            date_from = now - timedelta(seconds=offset_from)
            date_to = now - timedelta(seconds=offset_to)
        
        # Получаем информацию о канале для вывода
        channel_name = None
        if channel_id:
            info = await self.telegram.get_dialog_info(channel_id)
            channel_name = info.get('title', 'Неизвестно') if info else 'Неизвестно'
        
        # Формируем описание того, что будет удалено
        desc_parts = []
        if channel_id:
            desc_parts.append(f"канал '{channel_name}' (ID: {channel_id})")
        if date_from and date_to:
            desc_parts.append(f"период {date_from.strftime('%Y-%m-%d %H:%M')} - {date_to.strftime('%Y-%m-%d %H:%M')}")
        
        if desc_parts:
            print(f"Очистка сообщений: {', '.join(desc_parts)}")
        else:
            print("Очистка ВСЕХ сообщений")
        
        # Выполняем очистку
        count = self.database.clear_messages(
            channel_id=channel_id,
            date_from=date_from,
            date_to=date_to
        )
        
        print(f"Удалено: {count} сообщений")
    
    def _parse_period(self) -> tuple:
        """Парсит период из аргументов."""
        now = datetime.utcnow()
        date_from = None
        date_to = now
        
        if self.args.period_offset:
            offset_start, offset_end = self.args.period_offset
            date_from = now - timedelta(seconds=offset_start)
            if offset_end > 0:
                date_to = now - timedelta(seconds=offset_end)
        
        elif self.args.period_dates:
            try:
                date_from_str, date_to_str = self.args.period_dates
                
                # Поддерживаем разные форматы
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        date_from = datetime.strptime(date_from_str, fmt)
                        break
                    except ValueError:
                        continue
                
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        date_to = datetime.strptime(date_to_str, fmt)
                        break
                    except ValueError:
                        continue
            except Exception as e:
                print(f"Ошибка парсинга дат: {e}")
        
        return date_from, date_to
    
    def _format_output(self, messages: List[Dict[str, Any]]) -> str:
        """Форматирует вывод в зависимости от --output."""
        output_format = self.args.output
        
        if output_format == 'text':
            return format_messages(messages, include_chains=True)
        
        elif output_format == 'json':
            # Разделяем на одиночные и цепочки
            standalone, chains = separate_standalone_and_chains(messages)
            data = {
                'standalone_messages': [format_message_json(m) for m in standalone],
                'chains': []
            }
            for chain in chains:
                chain_data = {
                    'root': format_message_json(chain[0]),
                    'replies': [format_message_json(m) for m in chain[1:]]
                }
                data['chains'].append(chain_data)
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        
        elif output_format == 'json-no-chains':
            # Все сообщения в плоском списке
            data = {
                'messages': [format_message_json(m) for m in messages]
            }
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        
        elif output_format == 'json-reactions':
            # Только сообщения с изменениями реакций
            hours = 24  # По умолчанию за 24 часа
            messages_with_changes = self.database.get_messages_with_reaction_changes(hours)
            data = {
                'period_hours': hours,
                'messages': [format_reactions_json(m) for m in messages_with_changes]
            }
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        
        return ""
    
    async def _send_to_url(self, data: str):
        """Отправляет данные по URL."""
        url = self.args.send_url
        
        print(f"\nОтправка данных на {url}...")
        
        try:
            # Пытаемся распарсить как JSON
            try:
                json_data = json.loads(data)
                content_type = 'application/json'
            except json.JSONDecodeError:
                json_data = {'text': data}
                content_type = 'application/json'
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=json_data,
                    headers={'Content-Type': content_type},
                    timeout=30.0
                )
                
                print(f"Статус: {response.status_code}")
                if response.status_code >= 400:
                    print(f"Ответ: {response.text[:500]}")
                else:
                    print("Данные успешно отправлены")
        
        except httpx.TimeoutException:
            print("Ошибка: Таймаут соединения")
        except httpx.RequestError as e:
            print(f"Ошибка запроса: {e}")
        except Exception as e:
            print(f"Ошибка: {e}")

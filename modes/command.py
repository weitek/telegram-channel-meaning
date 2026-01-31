"""
Командный режим работы приложения.

Обрабатывает CLI аргументы для:
- Получения сообщений (--fetch)
- Очистки данных (--clear)
- Отслеживания реакций (--track-reactions)
- Отправки результатов по URL (--send-url)
"""

import asyncio
import contextlib
import io
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import httpx

from core.telegram_client import TelegramClientWrapper
from core.database import Database
from core.config import Config
from utils.message_chains import find_chain_roots, build_chains, separate_standalone_and_chains
from utils.formatters import format_messages, format_message_json, format_reactions_json
from utils.message_sorting import group_and_sort_messages
from utils.timezone import get_timezone


async def run_command_mode(api_id: int, api_hash: str, args):
    """
    Запускает командный режим.
    
    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash
        args: Аргументы командной строки
    """
    stdout_only_mode = (args.fetch or args.fetch_channel) and not args.send_url

    # В stdout-only режиме подавляем весь служебный вывод/ошибки из внутренних модулей
    # и печатаем только сформированный результат (output) и только если есть сообщения.
    if stdout_only_mode:
        handler = CommandHandler(api_id, api_hash, args, stdout_only_mode=True)
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        output: str = ""
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            try:
                output = (await handler.run()) or ""
            except Exception:
                # Никаких трейсбеков/ошибок в stdout-only режиме
                output = ""
        if output:
            print(output, end="")
        return

    handler = CommandHandler(api_id, api_hash, args, stdout_only_mode=False)
    await handler.run()


class CommandHandler:
    """Обработчик командного режима."""
    
    def __init__(self, api_id: int, api_hash: str, args, stdout_only_mode: bool = False):
        self.api_id = api_id
        self.api_hash = api_hash
        self.args = args
        self.stdout_only_mode = stdout_only_mode
        self.database = Database()
        self.config = Config()
        self.telegram: Optional[TelegramClientWrapper] = None
    
    async def run(self) -> Optional[str]:
        """Выполняет команду."""
        async with TelegramClientWrapper(self.api_id, self.api_hash) as tg:
            self.telegram = tg
            
            # Проверяем авторизацию
            if not await tg.is_authorized():
                print("Требуется авторизация. Запустите в интерактивном режиме:")
                print("  python main.py --interactive")
                return None
            
            # Выполняем команду
            if self.args.clear:
                await self.handle_clear()
            elif self.args.fetch or self.args.fetch_channel:
                return await self.handle_fetch()
        return None
    
    async def handle_fetch(self) -> Optional[str]:
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
                return "" if self.stdout_only_mode else None
        
        # Определяем период
        date_from, date_to = self._parse_period()
        
        print(f"Получение сообщений...")
        if date_from:
            print(f"  Период: {date_from} - {date_to}")
        print(f"  Каналы: {channel_ids}")
        
        # Получаем сообщения
        all_messages = []
        channel_titles: Dict[int, str] = {}
        saved_message_ids: List[int] = []
        
        limit = (
            self.args.limit
            if getattr(self.args, "limit", None) is not None
            else self.config.get_fetch_messages_limit()
        )
        for channel_id in channel_ids:
            messages = await self.telegram.fetch_messages_by_date(
                channel_id,
                date_from,
                date_to,
                limit=limit,
                pause_seconds=self.config.get_fetch_messages_pause_seconds(),
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
                saved_message_ids.append(db_msg_id)
                
                # Сохраняем реакции если нужно
                if self.args.track_reactions:
                    self.database.save_reactions_snapshot(
                        db_msg_id, msg['reactions_count']
                    )
            
            all_messages.extend(messages)
            
            info = await self.telegram.get_dialog_info(channel_id)
            name = info.get('title', 'Неизвестно') if info else 'Неизвестно'
            channel_titles[int(channel_id)] = name
            print(f"  {name}: {len(messages)} сообщений")
        
        print(f"\nВсего: {len(all_messages)} сообщений")

        # В stdout-only режиме не печатаем ничего, если сообщений нет.
        if self.stdout_only_mode and not all_messages:
            return ""
        
        # Подтягиваем предков цепочек до корня (только для --output json и --chains-to-root)
        if (
            self.args.output == 'json'
            and getattr(self.args, 'chains_to_root', False)
        ):
            all_messages = await self._expand_chains_to_root(
                all_messages, saved_message_ids
            )
        
        # Формируем вывод
        output = self._format_output(all_messages, channel_titles=channel_titles)
        
        delete_after = getattr(self.args, 'delete_after', False)
        
        # Выводим или отправляем
        if self.args.send_url:
            success = await self._send_to_url(output)
            if success and delete_after and saved_message_ids:
                count = self.database.delete_message_ids(saved_message_ids)
                print(f"Удалено из БД: {count} сообщений")
            return None
        else:
            if self.stdout_only_mode:
                if delete_after and saved_message_ids:
                    self.database.delete_message_ids(saved_message_ids)
                return output
            print("\n" + output)
            if delete_after and saved_message_ids:
                count = self.database.delete_message_ids(saved_message_ids)
                print(f"Удалено из БД: {count} сообщений")
            return None
    
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
                tz = get_timezone()

                # Парсим в зоне TIMEZONE: только дата — начало/конец дня, дата+время — указанный момент
                date_from_parsed = None
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        date_from_parsed = datetime.strptime(date_from_str, fmt)
                        break
                    except ValueError:
                        continue
                if date_from_parsed is None:
                    raise ValueError(f"Не удалось распознать дату: {date_from_str}")

                date_to_parsed = None
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                    try:
                        date_to_parsed = datetime.strptime(date_to_str, fmt)
                        break
                    except ValueError:
                        continue
                if date_to_parsed is None:
                    raise ValueError(f"Не удалось распознать дату: {date_to_str}")

                if len(date_from_str.strip()) <= 10:
                    date_from_parsed = date_from_parsed.replace(hour=0, minute=0, second=0, microsecond=0)
                if len(date_to_str.strip()) <= 10:
                    date_to_parsed = date_to_parsed.replace(hour=23, minute=59, second=59, microsecond=999999)

                date_from = date_from_parsed.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
                date_to = date_to_parsed.replace(tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
            except Exception as e:
                print(f"Ошибка парсинга дат: {e}")
        
        return date_from, date_to
    
    @staticmethod
    def _db_row_to_message_dict(row: Dict[str, Any]) -> Dict[str, Any]:
        """Приводит строку БД (get_message_by_telegram_id_with_sender) к формату сообщения."""
        sender = None
        if row.get('sender_telegram_id') is not None:
            sender = {
                'id': row['sender_telegram_id'],
                'first_name': row.get('sender_first_name'),
                'last_name': row.get('sender_last_name'),
                'username': row.get('sender_username'),
            }
        return {
            'telegram_id': row['telegram_id'],
            'channel_id': row['channel_id'],
            'content': row.get('content') or '',
            'date': row.get('date'),
            'reply_to_msg_id': row.get('reply_to_msg_id'),
            'reactions_count': row.get('reactions_count') or 0,
            'raw_json': row.get('raw_json'),
            'sender': sender,
        }
    
    async def _expand_chains_to_root(
        self,
        all_messages: List[Dict[str, Any]],
        saved_message_ids: List[int],
    ) -> List[Dict[str, Any]]:
        """
        Подтягивает предков цепочек из БД и Telegram до корня.
        Модифицирует saved_message_ids, добавляя ID вновь сохранённых сообщений.
        """
        by_channel: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for m in all_messages:
            cid = m.get('channel_id')
            if cid is not None:
                by_channel[cid].append(m)
        
        for channel_id, msgs in list(by_channel.items()):
            message_ids = {m['telegram_id'] for m in msgs}
            queue: deque = deque()
            for m in msgs:
                rt = m.get('reply_to_msg_id')
                if rt and rt > 0 and rt not in message_ids:
                    queue.append(rt)
            
            while queue:
                parent_id = queue.popleft()
                if parent_id in message_ids:
                    continue
                row = self.database.get_message_by_telegram_id_with_sender(
                    parent_id, channel_id
                )
                if row:
                    msg_dict = self._db_row_to_message_dict(row)
                    msgs.append(msg_dict)
                    message_ids.add(msg_dict['telegram_id'])
                    rt = msg_dict.get('reply_to_msg_id')
                    if rt and rt > 0 and rt not in message_ids:
                        queue.append(rt)
                    continue
                msg_dict = await self.telegram.fetch_message_by_id(
                    channel_id, parent_id
                )
                if not msg_dict:
                    continue
                sender_id = None
                if msg_dict.get('sender'):
                    s = msg_dict['sender']
                    sender_id = self.database.get_or_create_sender(
                        s['id'],
                        s.get('first_name'),
                        s.get('last_name'),
                        s.get('username'),
                    )
                db_msg_id = self.database.save_message(
                    telegram_id=msg_dict['telegram_id'],
                    channel_id=msg_dict['channel_id'],
                    content=msg_dict['content'],
                    date=msg_dict['date'],
                    sender_id=sender_id,
                    reply_to_msg_id=msg_dict.get('reply_to_msg_id'),
                    reactions_count=msg_dict.get('reactions_count', 0),
                    raw_json=msg_dict.get('raw_json'),
                )
                saved_message_ids.append(db_msg_id)
                if getattr(self.args, 'track_reactions', False):
                    self.database.save_reactions_snapshot(
                        db_msg_id, msg_dict.get('reactions_count', 0)
                    )
                msgs.append(msg_dict)
                message_ids.add(msg_dict['telegram_id'])
                rt = msg_dict.get('reply_to_msg_id')
                if rt and rt > 0 and rt not in message_ids:
                    queue.append(rt)
        
        return [m for msgs in by_channel.values() for m in msgs]
    
    def _format_output(
        self,
        messages: List[Dict[str, Any]],
        channel_titles: Optional[Dict[int, str]] = None,
    ) -> str:
        """Форматирует вывод в зависимости от --output."""
        output_format = self.args.output
        sort_order = self._get_messages_sort_order()
        channel_titles = channel_titles or {}
        grouped = group_and_sort_messages(messages, sort_order=sort_order)
        is_multi_channel = len(grouped) > 1
        
        if output_format == 'text':
            if not is_multi_channel:
                # Один канал (или пусто) — без блока по каналу.
                return format_messages(
                    messages,
                    include_chains=True,
                    standalone_sort_order=sort_order,
                )

            blocks: List[str] = []
            for channel_id, ch_messages in grouped:
                title = channel_titles.get(channel_id, "Неизвестно")
                blocks.append("=" * 60)
                blocks.append(f"КАНАЛ: {title} (ID: {channel_id})")
                blocks.append("=" * 60)
                blocks.append(
                    format_messages(
                        ch_messages,
                        include_chains=True,
                        standalone_sort_order=sort_order,
                    )
                )
                blocks.append("")
            return "\n".join(blocks).rstrip()
        
        elif output_format == 'json':
            def _sort_chain_replies(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
                """Сортирует ответы в цепочке по sort_order (корень остаётся первым)."""
                if len(chain) <= 1:
                    return chain
                root, replies = chain[0], chain[1:]
                if sort_order in ("id_asc", "id_desc"):
                    reverse = sort_order == "id_desc"
                    replies = sorted(
                        replies,
                        key=lambda m: int(m.get("telegram_id", -1)),
                        reverse=reverse,
                    )
                return [root] + replies

            if not is_multi_channel:
                # Совместимость: прежняя структура при одном канале.
                standalone, chains = separate_standalone_and_chains(messages)
                if standalone and sort_order in ("id_asc", "id_desc"):
                    reverse = sort_order == "id_desc"
                    standalone.sort(key=lambda m: int(m.get("telegram_id", -1)), reverse=reverse)
                data = {
                    'standalone_messages': [format_message_json(m) for m in standalone],
                    'chains': []
                }
                for chain in chains:
                    chain_sorted = _sort_chain_replies(chain)
                    chain_data = {
                        'root': format_message_json(chain_sorted[0]),
                        'replies': [format_message_json(m) for m in chain_sorted[1:]]
                    }
                    data['chains'].append(chain_data)
                return json.dumps(data, ensure_ascii=False, indent=2, default=str)

            # Мультиканальный вывод: блоки по channel_id
            data = {"channels": []}
            for channel_id, ch_messages in grouped:
                standalone, chains = separate_standalone_and_chains(ch_messages)
                if standalone and sort_order in ("id_asc", "id_desc"):
                    reverse = sort_order == "id_desc"
                    standalone.sort(key=lambda m: int(m.get("telegram_id", -1)), reverse=reverse)

                ch_data = {
                    "channel_id": channel_id,
                    "standalone_messages": [format_message_json(m) for m in standalone],
                    "chains": [],
                }
                for chain in chains:
                    chain_sorted = _sort_chain_replies(chain)
                    ch_data["chains"].append(
                        {
                            "root": format_message_json(chain_sorted[0]),
                            "replies": [format_message_json(m) for m in chain_sorted[1:]],
                        }
                    )
                data["channels"].append(ch_data)
            return json.dumps(data, ensure_ascii=False, indent=2, default=str)
        
        elif output_format == 'json-no-chains':
            if not is_multi_channel:
                # Совместимость: прежняя структура при одном канале.
                data = {
                    'messages': [format_message_json(m) for m in grouped[0][1]] if grouped else []
                }
                return json.dumps(data, ensure_ascii=False, indent=2, default=str)

            data = {"channels": []}
            for channel_id, ch_messages in grouped:
                data["channels"].append(
                    {
                        "channel_id": channel_id,
                        "messages": [format_message_json(m) for m in ch_messages],
                    }
                )
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

    def _get_messages_sort_order(self) -> str:
        """
        Определяет порядок сортировки сообщений:
        - CLI `--messages-sort` имеет приоритет, если задан
        - иначе используется значение из конфига
        """
        order = getattr(self.args, "messages_sort", None)
        if order:
            return order
        return self.config.get_messages_sort_order()
    
    async def _send_to_url(self, data: str) -> bool:
        """Отправляет данные по URL. Возвращает True при успехе (2xx)."""
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
                    return False
                print("Данные успешно отправлены")
                return True
        
        except httpx.TimeoutException:
            print("Ошибка: Таймаут соединения")
            return False
        except httpx.RequestError as e:
            print(f"Ошибка запроса: {e}")
            return False
        except Exception as e:
            print(f"Ошибка: {e}")
            return False

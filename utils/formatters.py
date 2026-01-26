"""
Утилиты для форматирования вывода.

Поддерживает форматирование:
- Текстовый вывод для консоли
- JSON для API и файлов
- Специальный формат для реакций
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from .message_chains import separate_standalone_and_chains, get_chain_statistics


def format_messages(messages: List[Dict[str, Any]], 
                   include_chains: bool = True) -> str:
    """
    Форматирует сообщения для текстового вывода.
    
    Args:
        messages: Список сообщений
        include_chains: Группировать ли сообщения по цепочкам
        
    Returns:
        Отформатированная строка
    """
    if not messages:
        return "Нет сообщений"
    
    lines = []
    
    if include_chains:
        standalone, chains = separate_standalone_and_chains(messages)
        
        # Выводим одиночные сообщения
        if standalone:
            lines.append("=" * 60)
            lines.append("ОДИНОЧНЫЕ СООБЩЕНИЯ")
            lines.append("=" * 60)
            
            for msg in standalone:
                lines.append(_format_single_message(msg))
                lines.append("-" * 40)
        
        # Выводим цепочки
        if chains:
            lines.append("")
            lines.append("=" * 60)
            lines.append(f"ЦЕПОЧКИ СООБЩЕНИЙ ({len(chains)})")
            lines.append("=" * 60)
            
            for i, chain in enumerate(chains, 1):
                lines.append(f"\n--- Цепочка #{i} ({len(chain)} сообщений) ---")
                
                for j, msg in enumerate(chain):
                    prefix = "ROOT" if j == 0 else f"  └─ RE"
                    lines.append(f"{prefix}: {_format_single_message(msg, compact=True)}")
                
                lines.append("-" * 40)
        
        # Статистика
        stats = get_chain_statistics(chains)
        lines.append("")
        lines.append(f"Всего: {len(messages)} сообщений")
        lines.append(f"  - Одиночных: {len(standalone)}")
        lines.append(f"  - В цепочках: {stats['total_messages']} ({stats['total_chains']} цепочек)")
    
    else:
        # Простой вывод без группировки
        for msg in messages:
            lines.append(_format_single_message(msg))
            lines.append("-" * 40)
        
        lines.append(f"\nВсего: {len(messages)} сообщений")
    
    return "\n".join(lines)


def _format_single_message(msg: Dict[str, Any], compact: bool = False) -> str:
    """Форматирует одно сообщение."""
    # Дата
    date = msg.get('date')
    if isinstance(date, datetime):
        date_str = date.strftime('%Y-%m-%d %H:%M')
    elif isinstance(date, str):
        date_str = date[:16] if len(date) > 16 else date
    else:
        date_str = '-'
    
    # Отправитель
    sender = msg.get('sender')
    if sender:
        sender_name = sender.get('first_name', '')
        if sender.get('last_name'):
            sender_name += f" {sender['last_name']}"
        if sender.get('username'):
            sender_name += f" (@{sender['username']})"
    else:
        sender_name = "Неизвестно"
    
    # Контент
    content = msg.get('content', '')
    if len(content) > 200 and compact:
        content = content[:200] + "..."
    
    # Реакции
    reactions = msg.get('reactions_count', 0)
    reactions_str = f" [{reactions} ❤]" if reactions > 0 else ""
    
    if compact:
        content_preview = content[:100].replace('\n', ' ')
        if len(content) > 100:
            content_preview += "..."
        return f"[{date_str}] {sender_name}{reactions_str}: {content_preview}"
    else:
        lines = [
            f"ID: {msg.get('telegram_id', '-')} | Канал: {msg.get('channel_id', '-')}",
            f"Дата: {date_str}",
            f"От: {sender_name}",
        ]
        if reactions > 0:
            lines.append(f"Реакции: {reactions}")
        if msg.get('reply_to_msg_id'):
            lines.append(f"Ответ на: {msg['reply_to_msg_id']}")
        lines.append(f"Текст: {content}")
        
        return "\n".join(lines)


def format_message_json(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Форматирует сообщение для JSON вывода.
    
    Args:
        msg: Сообщение
        
    Returns:
        Словарь для JSON сериализации
    """
    # Обрабатываем дату
    date = msg.get('date')
    if isinstance(date, datetime):
        date_str = date.isoformat()
    else:
        date_str = str(date) if date else None
    
    result = {
        'id': msg.get('telegram_id'),
        'channel_id': msg.get('channel_id'),
        'date': date_str,
        'content': msg.get('content'),
        'reactions_count': msg.get('reactions_count', 0),
        'reply_to_msg_id': msg.get('reply_to_msg_id'),
    }
    
    # Добавляем информацию об отправителе
    sender = msg.get('sender')
    if sender:
        result['sender'] = {
            'id': sender.get('id'),
            'first_name': sender.get('first_name'),
            'last_name': sender.get('last_name'),
            'username': sender.get('username')
        }
    else:
        result['sender'] = None
    
    # Дополнительные поля если есть
    if 'views' in msg:
        result['views'] = msg['views']
    if 'forwards' in msg:
        result['forwards'] = msg['forwards']
    if 'has_media' in msg:
        result['has_media'] = msg['has_media']
    
    return result


def format_reactions_json(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Форматирует сообщение с информацией об изменении реакций.
    
    Args:
        msg: Сообщение с полями old_reactions, new_reactions, reactions_change
        
    Returns:
        Словарь для JSON сериализации
    """
    base = format_message_json(msg)
    
    base['reactions'] = {
        'old': msg.get('old_reactions', 0),
        'new': msg.get('new_reactions', 0),
        'change': msg.get('reactions_change', 0)
    }
    
    return base


def format_channels_list(channels: List[Dict[str, Any]]) -> str:
    """
    Форматирует список каналов для текстового вывода.
    
    Args:
        channels: Список каналов
        
    Returns:
        Отформатированная строка
    """
    if not channels:
        return "Нет каналов"
    
    lines = ["=" * 60, "СПИСОК КАНАЛОВ", "=" * 60, ""]
    
    for i, ch in enumerate(channels, 1):
        lines.append(f"{i}. {ch.get('name', 'Без названия')}")
        lines.append(f"   ID: {ch.get('id')}")
        if ch.get('username'):
            lines.append(f"   Username: @{ch['username']}")
        if ch.get('participants_count'):
            lines.append(f"   Участников: {ch['participants_count']}")
        lines.append("")
    
    return "\n".join(lines)


def format_statistics(stats: Dict[str, Any]) -> str:
    """
    Форматирует статистику для текстового вывода.
    
    Args:
        stats: Словарь со статистикой
        
    Returns:
        Отформатированная строка
    """
    lines = [
        "=" * 60,
        "СТАТИСТИКА",
        "=" * 60,
        "",
        f"Всего сообщений: {stats.get('total_messages', 0)}",
        f"Всего отправителей: {stats.get('total_senders', 0)}",
        f"Всего каналов: {stats.get('total_channels', 0)}",
    ]
    
    if stats.get('first_message_date'):
        lines.append(f"Первое сообщение: {stats['first_message_date']}")
    if stats.get('last_message_date'):
        lines.append(f"Последнее сообщение: {stats['last_message_date']}")
    
    return "\n".join(lines)

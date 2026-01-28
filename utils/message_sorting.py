"""
Утилиты для группировки и сортировки сообщений на уровне вывода.

Важно: сортировку делаем на этапе форматирования/выдачи, а не в Telegram-клиенте и не в SQL.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


def group_and_sort_messages(
    messages: Iterable[Dict[str, Any]],
    sort_order: str = "telegram",
) -> List[Tuple[int, List[Dict[str, Any]]]]:
    """
    Группирует сообщения по channel_id и (опционально) сортирует внутри группы по telegram_id.

    - Порядок групп каналов — стабильный (по первому появлению channel_id во входном списке).
    - sort_order="telegram" сохраняет исходный порядок сообщений внутри группы.
    - sort_order="id_asc"/"id_desc" сортирует внутри группы по telegram_id.

    Args:
        messages: входной список сообщений (словарей)
        sort_order: "telegram" | "id_asc" | "id_desc"

    Returns:
        Список пар (channel_id, messages_for_channel)
    """
    groups: List[Tuple[int, List[Dict[str, Any]]]] = []
    index_by_channel: Dict[int, int] = {}

    for msg in messages:
        channel_id = msg.get("channel_id")
        if channel_id is None:
            # На всякий случай: пропускаем сообщения без channel_id (не ожидается, но безопасно).
            continue

        # channel_id в проекте ожидается int, но не ломаемся на строках.
        try:
            channel_key = int(channel_id)
        except Exception:
            continue

        idx = index_by_channel.get(channel_key)
        if idx is None:
            index_by_channel[channel_key] = len(groups)
            groups.append((channel_key, [msg]))
        else:
            groups[idx][1].append(msg)

    if sort_order not in ("telegram", "id_asc", "id_desc"):
        sort_order = "telegram"

    if sort_order == "telegram":
        return groups

    reverse = sort_order == "id_desc"

    def id_key(m: Dict[str, Any]) -> int:
        mid = m.get("telegram_id")
        try:
            return int(mid)
        except Exception:
            # Не ожидается, но чтобы сортировка была тотальной.
            return -1

    for _, msgs in groups:
        msgs.sort(key=id_key, reverse=reverse)

    return groups


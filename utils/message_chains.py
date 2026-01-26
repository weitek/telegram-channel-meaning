"""
Утилиты для работы с цепочками сообщений.

Цепочка сообщений - это группа сообщений, связанных через reply_to_msg_id.
Первое сообщение в цепочке (корень) не имеет reply_to_msg_id.
"""

from typing import List, Dict, Any, Tuple, Set
from collections import defaultdict


def find_chain_roots(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Находит корневые сообщения цепочек.
    
    Корневое сообщение - это сообщение, на которое есть ответы,
    но само оно не является ответом на другое сообщение из списка.
    
    Args:
        messages: Список сообщений
        
    Returns:
        Список корневых сообщений
    """
    # Собираем ID всех сообщений
    message_ids = {msg['telegram_id'] for msg in messages}
    
    # Собираем ID сообщений, на которые есть ответы
    replied_to_ids: Set[int] = set()
    for msg in messages:
        if msg.get('reply_to_msg_id'):
            replied_to_ids.add(msg['reply_to_msg_id'])
    
    # Корни - сообщения, на которые есть ответы, но сами они не ответы
    # (или их родитель не в списке)
    roots = []
    for msg in messages:
        msg_id = msg['telegram_id']
        reply_to = msg.get('reply_to_msg_id')
        
        # Это корень если:
        # 1. На него есть ответы
        # 2. Оно не является ответом ИЛИ его родитель не в списке
        if msg_id in replied_to_ids:
            if not reply_to or reply_to not in message_ids:
                roots.append(msg)
    
    # Сортируем по дате
    roots.sort(key=lambda x: x.get('date') or '', reverse=True)
    
    return roots


def build_chains(messages: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Группирует сообщения в цепочки.
    
    Каждая цепочка начинается с корневого сообщения,
    за которым следуют ответы в хронологическом порядке.
    
    Args:
        messages: Список сообщений
        
    Returns:
        Список цепочек (каждая цепочка - список сообщений)
    """
    if not messages:
        return []
    
    # Создаём индекс сообщений по telegram_id
    msg_by_id: Dict[int, Dict[str, Any]] = {}
    for msg in messages:
        msg_by_id[msg['telegram_id']] = msg
    
    # Строим граф ответов: parent_id -> [children]
    children_map: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for msg in messages:
        reply_to = msg.get('reply_to_msg_id')
        if reply_to and reply_to in msg_by_id:
            children_map[reply_to].append(msg)
    
    # Сортируем детей по дате
    for children in children_map.values():
        children.sort(key=lambda x: x.get('date') or '')
    
    # Находим корни
    roots = find_chain_roots(messages)
    
    # Строим цепочки рекурсивно
    chains = []
    visited: Set[int] = set()
    
    def build_chain(root: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Строит цепочку начиная с корня."""
        chain = [root]
        visited.add(root['telegram_id'])
        
        # Добавляем всех потомков рекурсивно (BFS)
        queue = [root['telegram_id']]
        while queue:
            current_id = queue.pop(0)
            for child in children_map.get(current_id, []):
                if child['telegram_id'] not in visited:
                    chain.append(child)
                    visited.add(child['telegram_id'])
                    queue.append(child['telegram_id'])
        
        # Сортируем по дате (кроме корня)
        if len(chain) > 1:
            root_msg = chain[0]
            replies = sorted(chain[1:], key=lambda x: x.get('date') or '')
            chain = [root_msg] + replies
        
        return chain
    
    for root in roots:
        if root['telegram_id'] not in visited:
            chain = build_chain(root)
            chains.append(chain)
    
    return chains


def separate_standalone_and_chains(
    messages: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[List[Dict[str, Any]]]]:
    """
    Разделяет сообщения на одиночные и цепочки.
    
    Args:
        messages: Список сообщений
        
    Returns:
        Кортеж (одиночные_сообщения, цепочки)
    """
    if not messages:
        return [], []
    
    # Собираем ID всех сообщений
    message_ids = {msg['telegram_id'] for msg in messages}
    
    # Определяем, какие сообщения являются частью цепочек
    in_chain: Set[int] = set()
    
    # Сообщения, на которые есть ответы
    for msg in messages:
        reply_to = msg.get('reply_to_msg_id')
        if reply_to and reply_to in message_ids:
            in_chain.add(reply_to)
            in_chain.add(msg['telegram_id'])
    
    # Разделяем
    standalone = []
    chain_messages = []
    
    for msg in messages:
        if msg['telegram_id'] in in_chain:
            chain_messages.append(msg)
        else:
            standalone.append(msg)
    
    # Строим цепочки из chain_messages
    chains = build_chains(chain_messages)
    
    # Сортируем одиночные по дате
    standalone.sort(key=lambda x: x.get('date') or '', reverse=True)
    
    return standalone, chains


def get_chain_depth(chain: List[Dict[str, Any]]) -> int:
    """
    Возвращает глубину цепочки (максимальное количество уровней вложенности).
    
    Args:
        chain: Цепочка сообщений
        
    Returns:
        Глубина цепочки
    """
    if not chain:
        return 0
    
    # Создаём индекс
    msg_by_id = {msg['telegram_id']: msg for msg in chain}
    
    def get_depth(msg: Dict[str, Any], depth: int = 1) -> int:
        reply_to = msg.get('reply_to_msg_id')
        if reply_to and reply_to in msg_by_id:
            return get_depth(msg_by_id[reply_to], depth + 1)
        return depth
    
    return max(get_depth(msg) for msg in chain)


def get_chain_statistics(chains: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Возвращает статистику по цепочкам.
    
    Args:
        chains: Список цепочек
        
    Returns:
        Словарь со статистикой
    """
    if not chains:
        return {
            'total_chains': 0,
            'total_messages': 0,
            'avg_chain_length': 0,
            'max_chain_length': 0,
            'avg_chain_depth': 0,
            'max_chain_depth': 0
        }
    
    lengths = [len(chain) for chain in chains]
    depths = [get_chain_depth(chain) for chain in chains]
    
    return {
        'total_chains': len(chains),
        'total_messages': sum(lengths),
        'avg_chain_length': sum(lengths) / len(chains),
        'max_chain_length': max(lengths),
        'avg_chain_depth': sum(depths) / len(chains),
        'max_chain_depth': max(depths)
    }

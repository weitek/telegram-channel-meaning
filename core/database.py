"""
Модуль для работы с SQLite базой данных.

Схема базы данных:
- messages: сообщения из каналов
- senders: отправители сообщений
- reactions_history: история изменений реакций
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple


class Database:
    """Класс для работы с SQLite базой данных."""
    
    def __init__(self, db_path: str = None):
        """
        Инициализация базы данных.
        
        Args:
            db_path: Путь к файлу базы данных.
                    По умолчанию data/data.db в директории проекта.
        """
        if db_path is None:
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
            # Создаём папку data если не существует
            data_dir.mkdir(exist_ok=True)
            db_path = data_dir / "data.db"
        
        self.db_path = Path(db_path)
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Создаёт соединение с базой данных."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self) -> None:
        """Инициализирует структуру базы данных."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица отправителей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS senders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица сообщений
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    sender_id INTEGER,
                    content TEXT,
                    date DATETIME,
                    reply_to_msg_id INTEGER,
                    reactions_count INTEGER DEFAULT 0,
                    raw_json TEXT,
                    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES senders(id),
                    UNIQUE(telegram_id, channel_id)
                )
            """)
            
            # Таблица истории реакций
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reactions_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    reactions_count INTEGER NOT NULL,
                    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES messages(id)
                )
            """)
            
            # Индексы для оптимизации
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_channel 
                ON messages(channel_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_date 
                ON messages(date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_reply 
                ON messages(reply_to_msg_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_senders_telegram_id 
                ON senders(telegram_id)
            """)
            
            conn.commit()
    
    # ==================== Методы для отправителей ====================
    
    def get_or_create_sender(self, telegram_id: int, first_name: str = None,
                             last_name: str = None, username: str = None) -> int:
        """
        Получает или создаёт отправителя.
        
        Returns:
            ID отправителя в базе данных
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Пробуем найти существующего
            cursor.execute(
                "SELECT id FROM senders WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # Обновляем информацию
                cursor.execute("""
                    UPDATE senders 
                    SET first_name = COALESCE(?, first_name),
                        last_name = COALESCE(?, last_name),
                        username = COALESCE(?, username)
                    WHERE telegram_id = ?
                """, (first_name, last_name, username, telegram_id))
                conn.commit()
                return row['id']
            
            # Создаём нового
            cursor.execute("""
                INSERT INTO senders (telegram_id, first_name, last_name, username)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, first_name, last_name, username))
            conn.commit()
            return cursor.lastrowid
    
    def get_senders_list(self) -> List[Dict[str, Any]]:
        """Возвращает список всех отправителей."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, COUNT(m.id) as message_count
                FROM senders s
                LEFT JOIN messages m ON s.id = m.sender_id
                GROUP BY s.id
                ORDER BY message_count DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_sender_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает отправителя по Telegram ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM senders WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Методы для сообщений ====================
    
    def save_message(self, telegram_id: int, channel_id: int, 
                    content: str = None, date: datetime = None,
                    sender_id: int = None, reply_to_msg_id: int = None,
                    reactions_count: int = 0, raw_json: str = None) -> int:
        """
        Сохраняет или обновляет сообщение.
        
        Returns:
            ID сообщения в базе данных
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Используем INSERT OR REPLACE для обновления существующих
            cursor.execute("""
                INSERT INTO messages 
                    (telegram_id, channel_id, content, date, sender_id, 
                     reply_to_msg_id, reactions_count, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id, channel_id) DO UPDATE SET
                    content = excluded.content,
                    date = excluded.date,
                    sender_id = excluded.sender_id,
                    reply_to_msg_id = excluded.reply_to_msg_id,
                    reactions_count = excluded.reactions_count,
                    raw_json = excluded.raw_json,
                    fetched_at = CURRENT_TIMESTAMP
            """, (telegram_id, channel_id, content, date, sender_id,
                  reply_to_msg_id, reactions_count, raw_json))
            conn.commit()
            
            # Получаем ID сообщения
            cursor.execute("""
                SELECT id FROM messages 
                WHERE telegram_id = ? AND channel_id = ?
            """, (telegram_id, channel_id))
            return cursor.fetchone()['id']
    
    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Получает сообщение по ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_message_by_telegram_id(self, telegram_id: int, 
                                   channel_id: int) -> Optional[Dict[str, Any]]:
        """Получает сообщение по Telegram ID и каналу."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages 
                WHERE telegram_id = ? AND channel_id = ?
            """, (telegram_id, channel_id))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_messages(self, channel_id: int = None, 
                    date_from: datetime = None,
                    date_to: datetime = None,
                    limit: int = None,
                    offset: int = 0) -> List[Dict[str, Any]]:
        """
        Получает сообщения с фильтрацией.
        
        Args:
            channel_id: Фильтр по каналу
            date_from: Начальная дата
            date_to: Конечная дата
            limit: Ограничение количества
            offset: Смещение
            
        Returns:
            Список сообщений
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM messages WHERE 1=1"
            params = []
            
            if channel_id is not None:
                query += " AND channel_id = ?"
                params.append(channel_id)
            
            if date_from is not None:
                query += " AND date >= ?"
                params.append(date_from)
            
            if date_to is not None:
                query += " AND date <= ?"
                params.append(date_to)
            
            query += " ORDER BY date DESC"
            
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_messages_with_senders(self, channel_id: int = None,
                                  date_from: datetime = None,
                                  date_to: datetime = None) -> List[Dict[str, Any]]:
        """Получает сообщения с информацией об отправителях."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT m.*, 
                       s.telegram_id as sender_telegram_id,
                       s.first_name as sender_first_name,
                       s.last_name as sender_last_name,
                       s.username as sender_username
                FROM messages m
                LEFT JOIN senders s ON m.sender_id = s.id
                WHERE 1=1
            """
            params = []
            
            if channel_id is not None:
                query += " AND m.channel_id = ?"
                params.append(channel_id)
            
            if date_from is not None:
                query += " AND m.date >= ?"
                params.append(date_from)
            
            if date_to is not None:
                query += " AND m.date <= ?"
                params.append(date_to)
            
            query += " ORDER BY m.date DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def clear_messages(self, channel_id: int = None,
                      date_from: datetime = None,
                      date_to: datetime = None) -> int:
        """
        Удаляет сообщения с фильтрацией.
        
        Returns:
            Количество удалённых сообщений
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "DELETE FROM messages WHERE 1=1"
            params = []
            
            if channel_id is not None:
                query += " AND channel_id = ?"
                params.append(channel_id)
            
            if date_from is not None:
                query += " AND date >= ?"
                params.append(date_from)
            
            if date_to is not None:
                query += " AND date <= ?"
                params.append(date_to)
            
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    # ==================== Методы для реакций ====================
    
    def save_reactions_snapshot(self, message_id: int, 
                                reactions_count: int) -> int:
        """
        Сохраняет снимок реакций для сообщения.
        
        Returns:
            ID записи истории
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reactions_history (message_id, reactions_count)
                VALUES (?, ?)
            """, (message_id, reactions_count))
            conn.commit()
            return cursor.lastrowid
    
    def get_messages_with_reaction_changes(self, 
                                           hours: int = 24) -> List[Dict[str, Any]]:
        """
        Получает сообщения с изменениями реакций за период.
        
        Args:
            hours: Период в часах
            
        Returns:
            Список сообщений с информацией об изменениях
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*,
                       rh_old.reactions_count as old_reactions,
                       rh_new.reactions_count as new_reactions,
                       (rh_new.reactions_count - rh_old.reactions_count) as reactions_change
                FROM messages m
                JOIN reactions_history rh_new ON m.id = rh_new.message_id
                JOIN reactions_history rh_old ON m.id = rh_old.message_id
                WHERE rh_new.checked_at = (
                    SELECT MAX(checked_at) FROM reactions_history 
                    WHERE message_id = m.id
                )
                AND rh_old.checked_at = (
                    SELECT MIN(checked_at) FROM reactions_history 
                    WHERE message_id = m.id
                    AND checked_at >= datetime('now', ?)
                )
                AND rh_new.reactions_count != rh_old.reactions_count
                ORDER BY reactions_change DESC
            """, (f'-{hours} hours',))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_reaction_history(self, message_id: int) -> List[Dict[str, Any]]:
        """Получает историю реакций для сообщения."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM reactions_history 
                WHERE message_id = ?
                ORDER BY checked_at DESC
            """, (message_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== Статистика ====================
    
    def get_message_counts_by_channel(self) -> List[Dict[str, Any]]:
        """Возвращает количество сообщений по каналам."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT channel_id, 
                       COUNT(*) as message_count,
                       MIN(date) as first_message,
                       MAX(date) as last_message
                FROM messages
                GROUP BY channel_id
                ORDER BY message_count DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает общую статистику базы данных."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            total_messages = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM senders")
            total_senders = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(DISTINCT channel_id) as count FROM messages")
            total_channels = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT MIN(date) as first, MAX(date) as last 
                FROM messages
            """)
            date_range = cursor.fetchone()
            
            return {
                'total_messages': total_messages,
                'total_senders': total_senders,
                'total_channels': total_channels,
                'first_message_date': date_range['first'],
                'last_message_date': date_range['last']
            }
    
    def __repr__(self) -> str:
        return f"Database({self.db_path})"

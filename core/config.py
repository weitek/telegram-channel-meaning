"""
Модуль для работы с JSON конфигурацией приложения.

Конфигурация хранится в файле config.json и содержит:
- selected_channels: список ID выбранных каналов
- webhook_default_channel: ID канала по умолчанию для вебхука
- channels_sort_type: вид сортировки списка каналов
  - "none" - без сортировки
  - "type" - по типу (внутри типа по названию)
  - "id" - по ID
  - "name" - по названию
  - "selected" - выбранные в начале списка
  - "type_id" - по типу + по ID
  - "type_name" - по типу + по названию
  - "type_selected" - по типу + по выбранным (внутри подгрупп по ID)
- messages_sort_order: порядок сортировки сообщений в выводе (командный режим)
  - "telegram" - как пришли/сформировались (по умолчанию)
  - "id_asc" - по telegram_id по возрастанию
  - "id_desc" - по telegram_id по убыванию
"""

import json
import os
from pathlib import Path
from typing import List, Optional


class Config:
    """Класс для работы с конфигурацией приложения."""
    
    VALID_MESSAGES_SORT_ORDERS = ["telegram", "id_asc", "id_desc"]

    DEFAULT_CONFIG = {
        "selected_channels": [],
        "webhook_default_channel": None,
        "channels_sort_type": "none",
        "messages_sort_order": "telegram",
    }
    
    def __init__(self, config_path: str = None):
        """
        Инициализация конфигурации.
        
        Args:
            config_path: Путь к файлу конфигурации. 
                        По умолчанию data/config.json в директории проекта.
        """
        if config_path is None:
            # Определяем путь относительно main.py
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
            # Создаём папку data если не существует
            data_dir.mkdir(exist_ok=True)
            config_path = data_dir / "config.json"
        
        self.config_path = Path(config_path)
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """Загружает конфигурацию из файла."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Объединяем с дефолтными значениями
                    return {**self.DEFAULT_CONFIG, **config}
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка чтения конфигурации: {e}")
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self) -> bool:
        """Сохраняет конфигурацию в файл."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False
    
    def get_selected_channels(self) -> List[int]:
        """Возвращает список ID выбранных каналов."""
        return self._config.get("selected_channels", [])
    
    def add_channel(self, channel_id: int) -> bool:
        """
        Добавляет канал в список выбранных.
        
        Args:
            channel_id: ID канала для добавления
            
        Returns:
            True если канал добавлен, False если уже существует
        """
        channels = self._config.get("selected_channels", [])
        if channel_id not in channels:
            channels.append(channel_id)
            self._config["selected_channels"] = channels
            self._save_config()
            return True
        return False
    
    def remove_channel(self, channel_id: int) -> bool:
        """
        Удаляет канал из списка выбранных.
        
        Args:
            channel_id: ID канала для удаления
            
        Returns:
            True если канал удалён, False если не найден
        """
        channels = self._config.get("selected_channels", [])
        if channel_id in channels:
            channels.remove(channel_id)
            self._config["selected_channels"] = channels
            self._save_config()
            return True
        return False
    
    def set_selected_channels(self, channel_ids: List[int]) -> None:
        """
        Устанавливает список выбранных каналов.
        
        Args:
            channel_ids: Список ID каналов
        """
        self._config["selected_channels"] = list(channel_ids)
        self._save_config()
    
    def get_webhook_default_channel(self) -> Optional[int]:
        """Возвращает ID канала по умолчанию для вебхука."""
        return self._config.get("webhook_default_channel")
    
    def set_webhook_default_channel(self, channel_id: Optional[int]) -> None:
        """
        Устанавливает канал по умолчанию для вебхука.
        
        Args:
            channel_id: ID канала или None для сброса
        """
        self._config["webhook_default_channel"] = channel_id
        self._save_config()
    
    def get_channels_sort_type(self) -> str:
        """
        Возвращает текущий вид сортировки каналов.
        
        Returns:
            Вид сортировки:
            - "none", "type", "id", "name", "selected"
            - "type_id", "type_name", "type_selected"
        """
        return self._config.get("channels_sort_type", "none")
    
    def set_channels_sort_type(self, sort_type: str) -> None:
        """
        Устанавливает вид сортировки каналов.
        
        Args:
            sort_type: Вид сортировки.
        """
        valid_types = [
            "none",
            "type",
            "id",
            "name",
            "selected",
            "type_id",
            "type_name",
            "type_selected",
        ]
        if sort_type not in valid_types:
            raise ValueError(f"Неверный тип сортировки. Допустимые: {valid_types}")
        self._config["channels_sort_type"] = sort_type
        self._save_config()

    def get_messages_sort_order(self) -> str:
        """
        Возвращает порядок сортировки сообщений в выводе.

        Returns:
            "telegram", "id_asc" или "id_desc"
        """
        order = self._config.get("messages_sort_order", "telegram")
        if order not in self.VALID_MESSAGES_SORT_ORDERS:
            return "telegram"
        return order

    def set_messages_sort_order(self, order: str) -> None:
        """
        Устанавливает порядок сортировки сообщений в выводе.

        Args:
            order: "telegram", "id_asc" или "id_desc"
        """
        if order not in self.VALID_MESSAGES_SORT_ORDERS:
            raise ValueError(
                f"Неверный порядок сортировки сообщений. Допустимые: {self.VALID_MESSAGES_SORT_ORDERS}"
            )
        self._config["messages_sort_order"] = order
        self._save_config()
    
    def get(self, key: str, default=None):
        """
        Получает значение из конфигурации.
        
        Args:
            key: Ключ конфигурации
            default: Значение по умолчанию
            
        Returns:
            Значение из конфигурации или default
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value) -> None:
        """
        Устанавливает значение в конфигурации.
        
        Args:
            key: Ключ конфигурации
            value: Значение для установки
        """
        self._config[key] = value
        self._save_config()
    
    def reload(self) -> None:
        """Перезагружает конфигурацию из файла."""
        self._config = self._load_config()
    
    def to_dict(self) -> dict:
        """Возвращает конфигурацию как словарь."""
        return self._config.copy()
    
    def __repr__(self) -> str:
        return f"Config({self.config_path})"

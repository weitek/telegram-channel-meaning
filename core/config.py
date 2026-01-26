"""
Модуль для работы с JSON конфигурацией приложения.

Конфигурация хранится в файле config.json и содержит:
- selected_channels: список ID выбранных каналов
- webhook_default_channel: ID канала по умолчанию для вебхука
"""

import json
import os
from pathlib import Path
from typing import List, Optional


class Config:
    """Класс для работы с конфигурацией приложения."""
    
    DEFAULT_CONFIG = {
        "selected_channels": [],
        "webhook_default_channel": None
    }
    
    def __init__(self, config_path: str = None):
        """
        Инициализация конфигурации.
        
        Args:
            config_path: Путь к файлу конфигурации. 
                        По умолчанию config.json в директории скрипта.
        """
        if config_path is None:
            # Определяем путь относительно main.py
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config.json"
        
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

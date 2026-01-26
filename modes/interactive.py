"""
Интерактивный режим работы приложения.

Предоставляет многоуровневое меню для:
- Просмотра информации об аккаунте
- Управления каналами
- Просмотра отправителей
- Статистики сообщений
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from core.telegram_client import TelegramClientWrapper
from core.database import Database
from core.config import Config


def clear_screen():
    """Очищает экран консоли."""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title: str):
    """Печатает заголовок меню."""
    print()
    print("=" * 50)
    print(f"  {title}")
    print("=" * 50)


def print_menu(options: list):
    """Печатает пункты меню."""
    print()
    for i, option in enumerate(options):
        if i == len(options) - 1:
            print(f"  0. {option}")
        else:
            print(f"  {i + 1}. {option}")
    print()


def get_choice(max_choice: int) -> int:
    """Получает выбор пользователя."""
    while True:
        try:
            choice = input("Выберите пункт: ").strip()
            if choice == '':
                return -1
            num = int(choice)
            if 0 <= num <= max_choice:
                return num
            print(f"Введите число от 0 до {max_choice}")
        except ValueError:
            print("Введите число")


def wait_for_enter():
    """Ожидает нажатия Enter."""
    input("\nНажмите Enter для продолжения...")


class InteractiveMode:
    """Класс интерактивного режима."""
    
    def __init__(self, api_id: int, api_hash: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.telegram: Optional[TelegramClientWrapper] = None
        self.database = Database()
        self.config = Config()
    
    async def run(self):
        """Запускает интерактивный режим."""
        async with TelegramClientWrapper(self.api_id, self.api_hash) as tg:
            self.telegram = tg
            
            # Авторизация
            if not await tg.is_authorized():
                print("\n=== Требуется авторизация ===\n")
                if not await tg.authorize():
                    print("Ошибка авторизации!")
                    return
                print("\nАвторизация успешна!")
            
            # Главное меню
            await self.main_menu()
    
    async def main_menu(self):
        """Главное меню."""
        while True:
            clear_screen()
            print_header("Главное меню")
            print_menu([
                "Информация об аккаунте",
                "Каналы и чаты",
                "Отправители",
                "Статистика сообщений",
                "Выход"
            ])
            
            choice = get_choice(4)
            
            if choice == 0:
                print("\nДо свидания!")
                break
            elif choice == 1:
                await self.show_account_info()
            elif choice == 2:
                await self.channels_menu()
            elif choice == 3:
                await self.senders_menu()
            elif choice == 4:
                await self.statistics_menu()
    
    async def show_account_info(self):
        """Показывает информацию об аккаунте."""
        clear_screen()
        print_header("Информация об аккаунте")
        
        me = await self.telegram.get_me()
        
        print(f"\n  ID: {me['id']}")
        print(f"  Имя: {me['first_name'] or '-'}")
        print(f"  Фамилия: {me['last_name'] or '-'}")
        print(f"  Username: @{me['username']}" if me['username'] else "  Username: -")
        print(f"  Телефон: {me['phone']}")
        print(f"  Premium: {'Да' if me['is_premium'] else 'Нет'}")
        
        wait_for_enter()
    
    async def channels_menu(self):
        """Меню каналов и чатов."""
        while True:
            clear_screen()
            print_header("Каналы и чаты")
            
            selected = self.config.get_selected_channels()
            if selected:
                print(f"\n  Выбрано каналов: {len(selected)}")
            
            print_menu([
                "Показать все каналы/чаты",
                "Информация о канале/чате",
                "Управление выбранными каналами",
                "Получить сообщения",
                "Назад"
            ])
            
            choice = get_choice(4)
            
            if choice == 0:
                break
            elif choice == 1:
                await self.show_all_dialogs()
            elif choice == 2:
                await self.show_dialog_info()
            elif choice == 3:
                await self.manage_selected_channels()
            elif choice == 4:
                await self.fetch_messages_menu()
    
    async def show_all_dialogs(self):
        """Показывает все диалоги."""
        clear_screen()
        print_header("Все каналы и чаты")
        
        print("\nЗагрузка...")
        dialogs = await self.telegram.get_dialogs()
        
        clear_screen()
        print_header("Все каналы и чаты")
        
        selected = self.config.get_selected_channels()
        
        print(f"\n{'#':<4} {'Тип':<10} {'ID':<15} {'Название':<30} {'Выбран'}")
        print("-" * 70)
        
        for i, dialog in enumerate(dialogs, 1):
            if dialog['is_channel']:
                dtype = "Канал"
            elif dialog['is_group']:
                dtype = "Группа"
            else:
                dtype = "Личный"
            
            name = (dialog['name'] or '-')[:28]
            is_selected = "✓" if dialog['id'] in selected else ""
            
            print(f"{i:<4} {dtype:<10} {dialog['id']:<15} {name:<30} {is_selected}")
        
        wait_for_enter()
    
    async def show_dialog_info(self):
        """Показывает информацию о конкретном диалоге."""
        clear_screen()
        print_header("Информация о канале/чате")
        
        try:
            dialog_id = int(input("\nВведите ID канала/чата: "))
        except ValueError:
            print("Неверный ID!")
            wait_for_enter()
            return
        
        print("\nЗагрузка...")
        info = await self.telegram.get_dialog_info(dialog_id)
        
        if not info:
            print("Канал/чат не найден!")
            wait_for_enter()
            return
        
        clear_screen()
        print_header(f"Информация о {info.get('title', info.get('first_name', 'диалоге'))}")
        
        print(f"\n  ID: {info['id']}")
        print(f"  Тип: {info['type']}")
        
        if 'title' in info:
            print(f"  Название: {info['title']}")
        if 'username' in info and info['username']:
            print(f"  Username: @{info['username']}")
        if 'first_name' in info:
            print(f"  Имя: {info['first_name']}")
        if 'last_name' in info and info['last_name']:
            print(f"  Фамилия: {info['last_name']}")
        if 'participants_count' in info and info['participants_count']:
            print(f"  Участников: {info['participants_count']}")
        if 'is_broadcast' in info:
            print(f"  Канал (broadcast): {'Да' if info['is_broadcast'] else 'Нет'}")
        if 'verified' in info:
            print(f"  Верифицирован: {'Да' if info['verified'] else 'Нет'}")
        
        wait_for_enter()
    
    async def manage_selected_channels(self):
        """Управление выбранными каналами."""
        while True:
            clear_screen()
            print_header("Выбранные каналы")
            
            selected = self.config.get_selected_channels()
            
            if selected:
                print("\nТекущие выбранные каналы:")
                for i, channel_id in enumerate(selected, 1):
                    info = await self.telegram.get_dialog_info(channel_id)
                    name = info.get('title', info.get('first_name', 'Неизвестно')) if info else 'Неизвестно'
                    print(f"  {i}. {channel_id} - {name}")
            else:
                print("\n  Нет выбранных каналов")
            
            print_menu([
                "Добавить канал",
                "Удалить канал",
                "Очистить все",
                "Назад"
            ])
            
            choice = get_choice(3)
            
            if choice == 0:
                break
            elif choice == 1:
                await self.add_channel()
            elif choice == 2:
                await self.remove_channel()
            elif choice == 3:
                self.config.set_selected_channels([])
                print("\nВсе каналы удалены из выбранных")
                wait_for_enter()
    
    async def add_channel(self):
        """Добавляет канал в выбранные."""
        try:
            channel_id = int(input("\nВведите ID канала: "))
        except ValueError:
            print("Неверный ID!")
            wait_for_enter()
            return
        
        # Проверяем, что канал существует
        info = await self.telegram.get_dialog_info(channel_id)
        if not info:
            print("Канал не найден!")
            wait_for_enter()
            return
        
        if self.config.add_channel(channel_id):
            name = info.get('title', info.get('first_name', 'Неизвестно'))
            print(f"\nКанал '{name}' добавлен в выбранные")
        else:
            print("\nКанал уже в списке выбранных")
        
        wait_for_enter()
    
    async def remove_channel(self):
        """Удаляет канал из выбранных."""
        selected = self.config.get_selected_channels()
        
        if not selected:
            print("\nНет выбранных каналов")
            wait_for_enter()
            return
        
        try:
            channel_id = int(input("\nВведите ID канала для удаления: "))
        except ValueError:
            print("Неверный ID!")
            wait_for_enter()
            return
        
        if self.config.remove_channel(channel_id):
            print("\nКанал удалён из выбранных")
        else:
            print("\nКанал не найден в списке")
        
        wait_for_enter()
    
    async def fetch_messages_menu(self):
        """Меню получения сообщений."""
        clear_screen()
        print_header("Получение сообщений")
        
        selected = self.config.get_selected_channels()
        
        if not selected:
            print("\nСначала выберите каналы!")
            wait_for_enter()
            return
        
        print_menu([
            "За последний час",
            "За последние 24 часа",
            "За последнюю неделю",
            "Указать период вручную",
            "Назад"
        ])
        
        choice = get_choice(4)
        
        if choice == 0:
            return
        
        now = datetime.utcnow()
        
        if choice == 1:
            date_from = now - timedelta(hours=1)
        elif choice == 2:
            date_from = now - timedelta(days=1)
        elif choice == 3:
            date_from = now - timedelta(weeks=1)
        elif choice == 4:
            try:
                hours = int(input("\nСколько часов назад? "))
                date_from = now - timedelta(hours=hours)
            except ValueError:
                print("Неверное значение!")
                wait_for_enter()
                return
        
        print("\nПолучение сообщений...")
        
        total_messages = 0
        for channel_id in selected:
            messages = await self.telegram.fetch_messages_by_date(
                channel_id, date_from, now, limit=500
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
                
                self.database.save_message(
                    telegram_id=msg['telegram_id'],
                    channel_id=msg['channel_id'],
                    content=msg['content'],
                    date=msg['date'],
                    sender_id=sender_id,
                    reply_to_msg_id=msg['reply_to_msg_id'],
                    reactions_count=msg['reactions_count'],
                    raw_json=msg['raw_json']
                )
            
            total_messages += len(messages)
            info = await self.telegram.get_dialog_info(channel_id)
            name = info.get('title', 'Неизвестно') if info else 'Неизвестно'
            print(f"  {name}: {len(messages)} сообщений")
        
        print(f"\nВсего получено: {total_messages} сообщений")
        wait_for_enter()
    
    async def senders_menu(self):
        """Меню отправителей."""
        clear_screen()
        print_header("Отправители")
        
        senders = self.database.get_senders_list()
        
        if not senders:
            print("\n  Нет данных об отправителях.")
            print("  Сначала получите сообщения из каналов.")
            wait_for_enter()
            return
        
        print(f"\n{'#':<4} {'ID':<15} {'Имя':<20} {'Username':<20} {'Сообщений'}")
        print("-" * 70)
        
        for i, sender in enumerate(senders[:30], 1):
            name = f"{sender['first_name'] or ''} {sender['last_name'] or ''}".strip() or '-'
            username = f"@{sender['username']}" if sender['username'] else '-'
            print(f"{i:<4} {sender['telegram_id']:<15} {name[:18]:<20} {username[:18]:<20} {sender['message_count']}")
        
        if len(senders) > 30:
            print(f"\n... и ещё {len(senders) - 30} отправителей")
        
        wait_for_enter()
    
    async def statistics_menu(self):
        """Меню статистики."""
        clear_screen()
        print_header("Статистика сообщений")
        
        stats = self.database.get_statistics()
        
        print(f"\n  Всего сообщений: {stats['total_messages']}")
        print(f"  Всего отправителей: {stats['total_senders']}")
        print(f"  Всего каналов: {stats['total_channels']}")
        
        if stats['first_message_date']:
            print(f"\n  Первое сообщение: {stats['first_message_date']}")
            print(f"  Последнее сообщение: {stats['last_message_date']}")
        
        print("\n--- По каналам ---")
        
        by_channel = self.database.get_message_counts_by_channel()
        
        if by_channel:
            for item in by_channel:
                info = await self.telegram.get_dialog_info(item['channel_id'])
                name = info.get('title', 'Неизвестно') if info else 'Неизвестно'
                print(f"\n  {name} (ID: {item['channel_id']})")
                print(f"    Сообщений: {item['message_count']}")
                if item['first_message']:
                    print(f"    Период: {item['first_message'][:10]} - {item['last_message'][:10]}")
        else:
            print("\n  Нет данных")
        
        wait_for_enter()


async def run_interactive_mode(api_id: int, api_hash: str):
    """Запускает интерактивный режим."""
    mode = InteractiveMode(api_id, api_hash)
    await mode.run()

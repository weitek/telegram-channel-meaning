"""
Интерактивный режим работы приложения.

Предоставляет многоуровневое меню для:
- Просмотра информации об аккаунте
- Управления каналами
- Просмотра отправителей
- Статистики сообщений
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

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
        # Количество диалогов на странице из переменной окружения
        self.dialogs_per_page = int(os.environ.get('DIALOGS_PER_PAGE', '20'))
        # Ширина столбца "Название" в таблице диалогов/каналов
        self.dialogs_name_col_width = int(os.environ.get('DIALOGS_NAME_COL_WIDTH', '30'))
        if self.dialogs_name_col_width < 10:
            self.dialogs_name_col_width = 10

    @staticmethod
    def _get_dialog_type_label(dialog: Dict[str, Any]) -> str:
        """Возвращает человекочитаемый тип диалога."""
        if dialog.get('is_channel'):
            return "Канал"
        if dialog.get('is_group'):
            return "Группа"
        return "Личный"

    @staticmethod
    def _fit_text(text: Optional[str], width: int) -> str:
        """Обрезает строку под ширину колонки (с многоточием)."""
        if width <= 0:
            return ""
        s = (text or "-").replace("\n", " ")
        if len(s) <= width:
            return s
        if width == 1:
            return "…"
        return s[: width - 1] + "…"
    
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
                "Настройка сортировки списка",
                "Настройка сортировки вывода сообщений",
                "Получить сообщения",
                "Назад"
            ])
            
            choice = get_choice(6)
            
            if choice == 0:
                break
            elif choice == 1:
                await self.show_all_dialogs()
            elif choice == 2:
                await self.show_dialog_info()
            elif choice == 3:
                await self.manage_selected_channels()
            elif choice == 4:
                await self.channels_sort_settings_menu()
            elif choice == 5:
                await self.messages_sort_settings_menu()
            elif choice == 6:
                await self.fetch_messages_menu()

    async def messages_sort_settings_menu(self):
        """Меню настройки сортировки вывода сообщений."""
        while True:
            clear_screen()
            print_header("Сортировка вывода сообщений")

            current = self.config.get_messages_sort_order()
            names = {
                "telegram": "Как сформировались (telegram)",
                "id_asc": "По telegram_id (возрастание)",
                "id_desc": "По telegram_id (убывание)",
            }
            print(f"\n  Текущая сортировка: {names.get(current, current)}")

            print_menu([
                "Как сформировались (telegram)",
                "По telegram_id (возрастание)",
                "По telegram_id (убывание)",
                "Назад",
            ])

            choice = get_choice(3)
            if choice == 0:
                break
            elif choice == 1:
                self.config.set_messages_sort_order("telegram")
                print("\nСортировка вывода установлена: telegram")
                wait_for_enter()
            elif choice == 2:
                self.config.set_messages_sort_order("id_asc")
                print("\nСортировка вывода установлена: id_asc")
                wait_for_enter()
            elif choice == 3:
                self.config.set_messages_sort_order("id_desc")
                print("\nСортировка вывода установлена: id_desc")
                wait_for_enter()
    
    def _sort_dialogs(self, dialogs: List[Dict[str, Any]], selected: List[int]) -> List[Dict[str, Any]]:
        """
        Применяет сортировку к списку диалогов согласно настройкам.
        
        Args:
            dialogs: Список диалогов
            selected: Список ID выбранных каналов
            
        Returns:
            Отсортированный список диалогов
        """
        sort_type = self.config.get_channels_sort_type()
        selected_set = set(selected)

        def get_type_order(d: Dict[str, Any]) -> int:
            if d.get('is_channel'):
                return 0
            if d.get('is_group'):
                return 1
            return 2
        
        if sort_type == "none":
            return dialogs
        
        if sort_type == "selected":
            selected_dialogs = [d for d in dialogs if d['id'] in selected_set]
            other_dialogs = [d for d in dialogs if d['id'] not in selected_set]
            return selected_dialogs + other_dialogs
        
        if sort_type == "type":
            return sorted(dialogs, key=lambda d: (get_type_order(d), d.get('name', '').lower()))
        
        if sort_type == "type_id":
            return sorted(dialogs, key=lambda d: (get_type_order(d), d['id']))

        if sort_type == "type_name":
            return sorted(dialogs, key=lambda d: (get_type_order(d), (d.get('name') or '').lower()))

        if sort_type == "type_selected":
            return sorted(
                dialogs,
                key=lambda d: (get_type_order(d), 0 if d['id'] in selected_set else 1, d['id'])
            )

        if sort_type == "id":
            return sorted(dialogs, key=lambda d: d['id'])
        
        if sort_type == "name":
            return sorted(dialogs, key=lambda d: d.get('name', '').lower())
        
        return dialogs
    
    async def channels_sort_settings_menu(self):
        """Меню настройки сортировки списка каналов."""
        while True:
            clear_screen()
            print_header("Настройка сортировки списка")
            
            current_sort = self.config.get_channels_sort_type()
            sort_names = {
                "none": "Без сортировки",
                "type": "По Типу",
                "id": "По ID",
                "name": "По Названию",
                "selected": "По Выбранным",
                "type_id": "По Типу + По ID",
                "type_name": "По Типу + По Названию",
                "type_selected": "По Типу + По Выбранным",
            }
            current_name = sort_names.get(current_sort, "Неизвестно")
            
            print(f"\n  Текущая сортировка: {current_name}")
            
            print_menu([
                "Без сортировки",
                "По Типу",
                "По ID",
                "По Названию",
                "По Выбранным",
                "По Типу + По ID",
                "По Типу + По Названию",
                "По Типу + По Выбранным",
                "Назад"
            ])
            
            choice = get_choice(8)
            
            if choice == 0:
                break
            elif choice == 1:
                self.config.set_channels_sort_type("none")
                print("\nСортировка установлена: Без сортировки")
                wait_for_enter()
            elif choice == 2:
                self.config.set_channels_sort_type("type")
                print("\nСортировка установлена: По Типу")
                wait_for_enter()
            elif choice == 3:
                self.config.set_channels_sort_type("id")
                print("\nСортировка установлена: По ID")
                wait_for_enter()
            elif choice == 4:
                self.config.set_channels_sort_type("name")
                print("\nСортировка установлена: По Названию")
                wait_for_enter()
            elif choice == 5:
                self.config.set_channels_sort_type("selected")
                print("\nСортировка установлена: По Выбранным")
                wait_for_enter()
            elif choice == 6:
                self.config.set_channels_sort_type("type_id")
                print("\nСортировка установлена: По Типу + По ID")
                wait_for_enter()
            elif choice == 7:
                self.config.set_channels_sort_type("type_name")
                print("\nСортировка установлена: По Типу + По Названию")
                wait_for_enter()
            elif choice == 8:
                self.config.set_channels_sort_type("type_selected")
                print("\nСортировка установлена: По Типу + По Выбранным")
                wait_for_enter()
    
    async def show_all_dialogs(self):
        """Показывает все диалоги с постраничной навигацией."""
        print("\nЗагрузка...")
        dialogs = await self.telegram.get_dialogs()
        
        if not dialogs:
            clear_screen()
            print_header("Все каналы и чаты")
            print("\n  Нет доступных диалогов")
            wait_for_enter()
            return
        
        selected = self.config.get_selected_channels()
        # Применяем сортировку
        dialogs = self._sort_dialogs(dialogs, selected)
        
        total_pages = (len(dialogs) + self.dialogs_per_page - 1) // self.dialogs_per_page
        current_page = 1
        
        while True:
            clear_screen()
            print_header("Все каналы и чаты")
            
            # Вычисляем диапазон для текущей страницы
            start_idx = (current_page - 1) * self.dialogs_per_page
            end_idx = min(start_idx + self.dialogs_per_page, len(dialogs))
            page_dialogs = dialogs[start_idx:end_idx]
            
            print(f"\nСтраница {current_page} из {total_pages} (всего диалогов: {len(dialogs)})")
            header = (
                f"{'#':<4} "
                f"{'Выбран':<7} "
                f"{'Тип':<10} "
                f"{'ID':<15} "
                f"{'Название':<{self.dialogs_name_col_width}}"
            )
            print("\n" + header)
            print("-" * len(header))
            
            for i, dialog in enumerate(page_dialogs, start=start_idx + 1):
                dtype = self._get_dialog_type_label(dialog)
                name = self._fit_text(dialog.get('name') or "-", self.dialogs_name_col_width)
                is_selected = "✓" if dialog['id'] in selected else ""
                print(
                    f"{i:<4} "
                    f"{is_selected:<7} "
                    f"{dtype:<10} "
                    f"{dialog['id']:<15} "
                    f"{name:<{self.dialogs_name_col_width}}"
                )
            
            # Навигация
            print("\n" + "-" * len(header))
            if total_pages > 1:
                nav_options = []
                nav_actions = []

                if current_page < total_pages:
                    nav_options.append("Следующая страница")
                    nav_actions.append('next')
                
                if current_page > 1:
                    nav_options.append("Предыдущая страница")
                    nav_actions.append('prev')
                
                print("\nНавигация:")
                for i, option in enumerate(nav_options, 1):
                    print(f"  {i}. {option}")
                print("  0. Назад")
                
                choice = get_choice(len(nav_options))
                
                if choice == 0:
                    break
                
                if choice <= len(nav_actions):
                    action = nav_actions[choice - 1]
                    if action == 'prev':
                        current_page -= 1
                    elif action == 'next':
                        current_page += 1
                    elif action == 'back':
                        break
            else:
                print("\nНажмите Enter для возврата...")
                input()
                break
    
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
                selected_set = set(selected)
                # Получаем информацию о всех выбранных каналах
                selected_dialogs = []
                for channel_id in selected:
                    info = await self.telegram.get_dialog_info(channel_id)
                    if info:
                        dialog_type = info.get('type', '')
                        is_channel = info.get('is_broadcast', False) or dialog_type == 'Channel'
                        is_group = dialog_type == 'Chat' or info.get('is_megagroup', False)
                        is_user = dialog_type == 'User'
                        
                        dialog = {
                            'id': channel_id,
                            'name': info.get('title', info.get('first_name', 'Неизвестно')),
                            'is_channel': is_channel,
                            'is_group': is_group,
                            'is_user': is_user
                        }
                        selected_dialogs.append(dialog)
                
                # Применяем сортировку
                selected_dialogs = self._sort_dialogs(selected_dialogs, selected)
                
                print("\nТекущие выбранные каналы:")
                header = (
                    f"{'#':<4} "
                    f"{'Выбран':<7} "
                    f"{'Тип':<10} "
                    f"{'ID':<15} "
                    f"{'Название':<{self.dialogs_name_col_width}}"
                )
                print("\n" + header)
                print("-" * len(header))

                for i, dialog in enumerate(selected_dialogs, 1):
                    dtype = self._get_dialog_type_label(dialog)
                    name = self._fit_text(dialog.get('name') or "-", self.dialogs_name_col_width)
                    is_selected = "✓" if dialog.get('id') in selected_set else ""
                    print(
                        f"{i:<4} "
                        f"{is_selected:<7} "
                        f"{dtype:<10} "
                        f"{dialog['id']:<15} "
                        f"{name:<{self.dialogs_name_col_width}}"
                    )
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
                channel_id,
                date_from,
                now,
                limit=self.config.get_fetch_messages_limit(),
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

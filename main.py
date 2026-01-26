#!/usr/bin/env python3
"""
Telegram Channel Manager - CLI приложение для работы с Telegram каналами.

Поддерживает три режима работы:
- Интерактивный режим (по умолчанию)
- Командный режим (CLI аргументы)
- Вебхук режим (FastAPI сервер)
"""

import argparse
import asyncio
import os
import sys

# Загрузка переменных окружения из .env файла (опционально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv не установлен, используем только системные переменные
    pass


def check_environment():
    """Проверяет наличие необходимых переменных окружения."""
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')
    
    missing = []
    if not api_id:
        missing.append('TELEGRAM_API_ID')
    if not api_hash:
        missing.append('TELEGRAM_API_HASH')
    
    if missing:
        print("Ошибка: Отсутствуют переменные окружения:")
        for var in missing:
            print(f"  - {var}")
        print("\nУстановите их одним из способов:")
        print("\n1. Создайте файл .env (скопируйте .env.example):")
        print("   TELEGRAM_API_ID=your_api_id")
        print("   TELEGRAM_API_HASH=your_api_hash")
        print("\n2. Или установите переменные окружения:")
        print("   Windows (PowerShell):")
        print('     $env:TELEGRAM_API_ID="your_api_id"')
        print('     $env:TELEGRAM_API_HASH="your_api_hash"')
        print("   Linux/macOS:")
        print('     export TELEGRAM_API_ID="your_api_id"')
        print('     export TELEGRAM_API_HASH="your_api_hash"')
        print("\nПолучить API credentials можно на https://my.telegram.org/apps")
        sys.exit(1)
    
    return int(api_id), api_hash


def create_parser():
    """Создаёт парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description='Telegram Channel Manager - управление каналами Telegram',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s                                    # Интерактивный режим
  %(prog)s --fetch --period-offset 86400 0    # Получить сообщения за 24 часа
  %(prog)s --fetch --track-reactions          # С отслеживанием лайков
  %(prog)s --webhook --port 8080              # Запустить вебхук-сервер
  %(prog)s --clear --clear-period 999999999 604800  # Очистить старше 7 дней
        """
    )
    
    # Режим работы
    mode_group = parser.add_argument_group('Режим работы')
    mode_group.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Запустить в интерактивном режиме (по умолчанию)'
    )
    mode_group.add_argument(
        '--webhook', '-w',
        action='store_true',
        help='Запустить вебхук-сервер'
    )
    mode_group.add_argument(
        '--port', '-p',
        type=int,
        default=8080,
        help='Порт для вебхук-сервера (по умолчанию: 8080)'
    )
    
    # Получение сообщений
    fetch_group = parser.add_argument_group('Получение сообщений')
    fetch_group.add_argument(
        '--fetch', '-f',
        action='store_true',
        help='Получить сообщения из выбранных каналов'
    )
    fetch_group.add_argument(
        '--fetch-channel',
        type=int,
        metavar='ID',
        help='Получить сообщения из конкретного канала'
    )
    fetch_group.add_argument(
        '--period-offset',
        nargs=2,
        type=int,
        metavar=('START', 'END'),
        help='Период смещениями в секундах от текущего времени'
    )
    fetch_group.add_argument(
        '--period-dates',
        nargs=2,
        metavar=('FROM', 'TO'),
        help='Период датами в формате ISO (YYYY-MM-DD или YYYY-MM-DDTHH:MM:SS)'
    )
    fetch_group.add_argument(
        '--track-reactions',
        action='store_true',
        help='Отслеживать изменения лайков'
    )
    fetch_group.add_argument(
        '--fetch-chains',
        action='store_true',
        help='Получить начала цепочек сообщений'
    )
    
    # Вывод
    output_group = parser.add_argument_group('Формат вывода')
    output_group.add_argument(
        '--output', '-o',
        choices=['text', 'json', 'json-no-chains', 'json-reactions'],
        default='text',
        help='Формат вывода (по умолчанию: text)'
    )
    output_group.add_argument(
        '--send-url',
        metavar='URL',
        help='Отправить результат по указанному URL'
    )
    
    # Очистка
    clear_group = parser.add_argument_group('Очистка данных')
    clear_group.add_argument(
        '--clear',
        action='store_true',
        help='Очистить сохранённые сообщения'
    )
    clear_group.add_argument(
        '--clear-channel',
        type=int,
        metavar='ID',
        help='Очистить сообщения для конкретного канала'
    )
    clear_group.add_argument(
        '--clear-period',
        nargs=2,
        type=int,
        metavar=('FROM', 'TO'),
        help='Очистить сообщения за период (смещения в секундах)'
    )
    
    return parser


def main():
    """Главная точка входа."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Проверяем переменные окружения
    api_id, api_hash = check_environment()
    
    # Определяем режим работы
    if args.webhook:
        # Вебхук режим
        from modes.webhook import run_webhook_server
        run_webhook_server(api_id, api_hash, args.port)
    
    elif args.fetch or args.clear or args.fetch_channel:
        # Командный режим
        from modes.command import run_command_mode
        asyncio.run(run_command_mode(api_id, api_hash, args))
    
    else:
        # Интерактивный режим (по умолчанию)
        from modes.interactive import run_interactive_mode
        asyncio.run(run_interactive_mode(api_id, api_hash))


if __name__ == '__main__':
    main()

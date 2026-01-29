"""
Централизованное получение временной зоны из настройки TIMEZONE (.env).

Используется при выводе дат сообщений и при интерпретации --period-dates.
По умолчанию — UTC (GMT+0).
"""

import os
import warnings
from zoneinfo import ZoneInfo


def get_timezone() -> ZoneInfo:
    """
    Возвращает объект временной зоны из переменной окружения TIMEZONE.

    Returns:
        ZoneInfo для указанной зоны (например Europe/Moscow, UTC).
        При пустом или невалидном значении возвращается UTC.
    """
    name = (os.environ.get("TIMEZONE") or "").strip() or "UTC"
    try:
        return ZoneInfo(name)
    except Exception:
        warnings.warn(
            f"Неверное значение TIMEZONE='{name}', используется UTC.",
            UserWarning,
            stacklevel=2,
        )
        return ZoneInfo("UTC")

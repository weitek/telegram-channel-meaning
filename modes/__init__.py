"""Режимы работы приложения."""

from .interactive import run_interactive_mode
from .command import run_command_mode
from .webhook import run_webhook_server

__all__ = ['run_interactive_mode', 'run_command_mode', 'run_webhook_server']

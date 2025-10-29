"""
AI-модуль для интеллектуальной обработки запросов пользователей.
Использует OpenAI Assistants API для FAQ и консультаций.
"""

from .assistant import AssistantManager, get_or_create_thread, clear_thread
from .response_parser import (
    detect_response_type,
    extract_order_data,
    format_response_for_platform,
    clean_html_tags
)

__all__ = [
    'AssistantManager',
    'get_or_create_thread',
    'clear_thread',
    'detect_response_type',
    'extract_order_data',
    'format_response_for_platform',
    'clean_html_tags'
]

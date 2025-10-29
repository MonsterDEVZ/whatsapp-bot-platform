"""
Утилиты для обработки ответов от AI Assistant.

Обрабатывает два типа ответов:
1. Текстовые (FAQ) - очистка HTML, отправка напрямую
2. JSON (намерение заказа) - парсинг и запуск FSM-сценария
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def clean_html_tags(text: str) -> str:
    """
    Удаляет HTML-теги из текста для WhatsApp.

    WhatsApp не поддерживает HTML-форматирование, поэтому
    необходимо удалить все теги перед отправкой.

    Args:
        text: Текст с возможными HTML-тегами

    Returns:
        Очищенный текст
    """
    # Удаляем HTML-теги с помощью регулярного выражения
    cleaned = re.sub(r'<[^>]+>', '', text)

    # Заменяем HTML-сущности
    cleaned = cleaned.replace('&nbsp;', ' ')
    cleaned = cleaned.replace('&lt;', '<')
    cleaned = cleaned.replace('&gt;', '>')
    cleaned = cleaned.replace('&amp;', '&')
    cleaned = cleaned.replace('&quot;', '"')
    cleaned = cleaned.replace('&#39;', "'")

    return cleaned.strip()


def clean_text_for_whatsapp(text: str) -> str:
    """
    Конвертирует HTML-теги в Markdown-разметку для WhatsApp.

    WhatsApp поддерживает Markdown:
    - *text* для жирного текста
    - _text_ для курсива
    - ~text~ для зачеркнутого
    - ```text``` для моноширинного

    Args:
        text: Текст с возможными HTML-тегами

    Returns:
        Текст с Markdown-разметкой для WhatsApp
    """
    # Конвертируем HTML → Markdown
    # <b>, <strong> → *bold*
    text = re.sub(r'<b>(.*?)</b>', r'*\1*', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<strong>(.*?)</strong>', r'*\1*', text, flags=re.IGNORECASE | re.DOTALL)

    # <i>, <em> → _italic_
    text = re.sub(r'<i>(.*?)</i>', r'_\1_', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<em>(.*?)</em>', r'_\1_', text, flags=re.IGNORECASE | re.DOTALL)

    # <s>, <strike>, <del> → ~strikethrough~
    text = re.sub(r'<s>(.*?)</s>', r'~\1~', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<strike>(.*?)</strike>', r'~\1~', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<del>(.*?)</del>', r'~\1~', text, flags=re.IGNORECASE | re.DOTALL)

    # <code>, <pre> → ```monospace```
    text = re.sub(r'<code>(.*?)</code>', r'```\1```', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<pre>(.*?)</pre>', r'```\1```', text, flags=re.IGNORECASE | re.DOTALL)

    # Удаляем оставшиеся HTML-теги
    text = re.sub(r'<[^>]+>', '', text)

    # Заменяем HTML-сущности
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")

    return text.strip()


def detect_response_type(response: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Определяет тип ответа от Assistant: JSON или текст.

    Args:
        response: Ответ от Assistant

    Returns:
        Tuple из (тип, данные):
        - ("json", parsed_data) если обнаружен валидный JSON
        - ("text", None) если это текстовый ответ
    """
    # Пытаемся найти JSON в ответе
    # Ищем JSON-блоки, которые могут быть окружены текстом
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'

    matches = re.finditer(json_pattern, response, re.DOTALL)

    for match in matches:
        json_str = match.group()
        try:
            # Пытаемся распарсить JSON
            data = json.loads(json_str)

            # Проверяем, что это действительно JSON намерения на заказ
            # (должен содержать поля category, brand или model)
            if isinstance(data, dict) and any(key in data for key in ['category', 'brand', 'model', 'intent']):
                logger.info(f"✅ Обнаружен JSON ответ: {data}")
                return ("json", data)

        except json.JSONDecodeError:
            continue

    # Если JSON не найден - это текстовый ответ
    logger.info("📝 Обнаружен текстовый ответ")
    return ("text", None)


def extract_order_data(parsed_json: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Извлекает данные заказа из распарсенного JSON.

    Args:
        parsed_json: Распарсенный JSON от Assistant

    Returns:
        Словарь с ключами:
        - category: Категория (eva, 3d, organizer и т.д.)
        - brand: Марка автомобиля
        - model: Модель автомобиля
        - options: Опции (например, "с бортами")
    """
    return {
        "category": parsed_json.get("category"),
        "brand": parsed_json.get("brand"),
        "model": parsed_json.get("model"),
        "options": parsed_json.get("options")
    }


def format_response_for_platform(response: str, platform: str) -> str:
    """
    Форматирует ответ для конкретной платформы.

    Args:
        response: Текстовый ответ от Assistant
        platform: Платформа ("telegram" или "whatsapp")

    Returns:
        Отформатированный ответ
    """
    if platform == "whatsapp":
        # WhatsApp: конвертируем HTML в Markdown
        return clean_text_for_whatsapp(response)
    elif platform == "telegram":
        # Telegram поддерживает HTML, оставляем как есть
        return response
    else:
        # По умолчанию конвертируем в Markdown
        return clean_text_for_whatsapp(response)

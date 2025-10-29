"""
Унифицированный обработчик "умного" гибридного ввода.

Этот модуль содержит единую логику обработки текстового и цифрового ввода
для всех этапов (выбор марки, выбор модели).

Ключевые функции:
- handle_text_or_digit_input: главная функция для обработки ввода
- apply_two_level_fuzzy: двухуровневая логика fuzzy search
- extract_vehicle_from_ai: извлечение марки+модели из ответа AI
"""

import logging
import json
import re
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Config
from core.ai.assistant import AssistantManager, get_or_create_thread
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


def apply_two_level_fuzzy(
    user_input: str,
    database_list: List[str],
    threshold_auto: float = 70.0,
    threshold_min: float = 60.0
) -> Dict[str, any]:
    """
    Двухуровневая логика fuzzy search.
    
    Логика:
    - Схожесть > 70%: автоматически применяем (без переспроса)
    - Схожесть 60-70%: переспрашиваем пользователя
    - Схожесть < 60%: ничего не найдено
    
    Args:
        user_input: Текст от пользователя или AI
        database_list: Список значений из БД
        threshold_auto: Порог для автоматического применения (по умолчанию 70%)
        threshold_min: Минимальный порог для переспроса (по умолчанию 60%)
        
    Returns:
        dict: {
            "action": "apply" | "ask" | "not_found",
            "value": найденное значение (или None),
            "similarity": процент схожести
        }
    """
    if not database_list:
        return {"action": "not_found", "value": None, "similarity": 0}
    
    best_match = process.extractOne(
        user_input,
        database_list,
        scorer=fuzz.ratio
    )
    
    if not best_match:
        return {"action": "not_found", "value": None, "similarity": 0}
    
    matched_value = best_match[0]
    similarity = best_match[1]
    
    if similarity > threshold_auto:
        # >70% - автоматически применяем
        logger.info(
            f"[FUZZY_AUTO] '{user_input}' → '{matched_value}' "
            f"({similarity:.1f}% > {threshold_auto}%) → auto-apply"
        )
        return {
            "action": "apply",
            "value": matched_value,
            "similarity": similarity
        }
    elif similarity >= threshold_min:
        # 60-70% - переспрашиваем
        logger.info(
            f"[FUZZY_ASK] '{user_input}' → '{matched_value}' "
            f"({similarity:.1f}% between {threshold_min}-{threshold_auto}%) → ask confirmation"
        )
        return {
            "action": "ask",
            "value": matched_value,
            "similarity": similarity
        }
    else:
        # <60% - не найдено
        logger.info(
            f"[FUZZY_NOT_FOUND] '{user_input}' → '{matched_value}' "
            f"({similarity:.1f}% < {threshold_min}%) → not found"
        )
        return {
            "action": "not_found",
            "value": None,
            "similarity": similarity
        }


def extract_vehicle_from_ai(ai_response: str) -> Dict[str, Optional[str]]:
    """
    Извлекает марку и модель из ответа AI.
    
    AI может вернуть:
    - JSON: {"brand": "BMW", "model": "X5"}
    - Текст: "Марка: BMW, Модель: X5"
    - Только марка: {"brand": "BMW", "model": null}
    
    Args:
        ai_response: Ответ от AI Assistant
        
    Returns:
        dict: {"brand": str | None, "model": str | None}
    """
    # Попытка 1: Парсинг JSON
    try:
        data = json.loads(ai_response.strip())
        if isinstance(data, dict):
            return {
                "brand": data.get("brand"),
                "model": data.get("model")
            }
    except:
        pass
    
    # Попытка 2: JSON внутри текста
    json_match = re.search(r'\{[^{}]*"brand"[^{}]*\}', ai_response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "brand": data.get("brand"),
                "model": data.get("model")
            }
        except:
            pass
    
    # Попытка 3: Парсинг текста
    brand_match = re.search(
        r'(?:[Мм]арка|Brand)[:\s]+([A-Za-zА-Яа-я0-9\-\s]+)',
        ai_response
    )
    model_match = re.search(
        r'(?:[Мм]одель|Model)[:\s]+([A-Za-z0-9А-Яа-я\-\s]+)',
        ai_response
    )
    
    if brand_match or model_match:
        return {
            "brand": brand_match.group(1).strip() if brand_match else None,
            "model": model_match.group(1).strip() if model_match else None
        }
    
    # Попытка 4: Одна строка - считаем маркой
    clean_response = ai_response.strip().split('\n')[0].strip()
    clean_response = clean_response.replace('"', '').replace("'", "")
    
    if clean_response:
        return {"brand": clean_response, "model": None}
    
    return {"brand": None, "model": None}


async def ask_ai_to_parse_vehicle(
    user_text: str,
    chat_id: str,
    context: str,  # "brand" или "model"
    category_name: str,
    brand_name: Optional[str] = None,
    config = None  # Добавлен для отправки заглушки
) -> Dict[str, Optional[str]]:
    """
    Обращается к AI для извлечения марки и/или модели из текста пользователя.
    
    Args:
        user_text: Текст от пользователя
        chat_id: ID чата
        context: "brand" (ищем марку) или "model" (ищем модель)
        category_name: Название категории (для контекста AI)
        brand_name: Название марки (если context="model")
        config: Конфигурация для отправки заглушки
        
    Returns:
        dict: {"brand": str | None, "model": str | None}
    """
    # Заглушка уже отправлена в handle_text_or_digit_input()
    # Здесь не дублируем
    
    try:
        assistant = AssistantManager()
        thread_id = get_or_create_thread(chat_id, assistant)
        
        # Формируем prompt в зависимости от контекста
        if context == "brand":
            ai_prompt = (
                f"Пользователь хочет заказать {category_name}. "
                f"Он написал: '{user_text}'. "
                f"Определи марку автомобиля и, если возможно, модель. "
                f"Верни JSON: {{\"brand\": \"название марки\", \"model\": \"название модели\"}}. "
                f"Если модель не указана, верни {{\"brand\": \"...\", \"model\": null}}. "
                f"Если ничего не понятно, верни {{\"brand\": null, \"model\": null}}."
            )
        else:  # context == "model"
            ai_prompt = (
                f"Пользователь выбирает модель автомобиля {brand_name}. "
                f"Он написал: '{user_text}'. "
                f"Определи модель автомобиля. "
                f"Верни JSON: {{\"brand\": \"{brand_name}\", \"model\": \"название модели\"}}. "
                f"Если модель не понятна, верни {{\"brand\": \"{brand_name}\", \"model\": null}}."
            )
        
        logger.info(f"[🤖 AI_PARSE] Context: {context}, Input: '{user_text}'")
        
        response, _ = await assistant.get_response(
            thread_id=thread_id,
            user_message=ai_prompt,
            chat_id=chat_id,
            timeout=20
        )

        logger.info(f"[🤖 AI_PARSE] AI response: {response[:200]}")
        
        return extract_vehicle_from_ai(response)
        
    except Exception as e:
        logger.error(f"[🤖 AI_PARSE] Error: {e}", exc_info=True)
        return {"brand": None, "model": None}


async def handle_text_or_digit_input(
    user_input: str,
    context: str,  # "brand" или "model"
    chat_id: str,
    callback_mapping: Dict[str, str],
    database_list: List[str],
    category_name: str,
    brand_name: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    config = None  # Добавлен для передачи в ask_ai_to_parse_vehicle
) -> Dict[str, any]:
    """
    Единая унифицированная функция для обработки "умного" гибридного ввода.
    
    Логика:
    1. Если ввод - ЦИФРА (1-8, 00, 99): обрабатывается как выбор из списка
    2. Если ввод - ТЕКСТ: немедленно передается в AI для анализа
    3. После AI применяется двухуровневый fuzzy search
    
    Args:
        user_input: Введенный текст пользователя
        context: "brand" или "model" - что мы ищем
        chat_id: ID чата WhatsApp
        callback_mapping: Маппинг цифр на callback_data
        database_list: Список значений из БД (марки или модели)
        category_name: Название категории товара
        brand_name: Название марки (только для context="model")
        session: Сессия БД (опционально)
        
    Returns:
        dict: {
            "type": "digit" | "text_auto" | "text_ask" | "text_not_found" | "jump",
            "value": найденное значение,
            "brand": марка (для прыжка),
            "model": модель (для прыжка),
            "similarity": процент схожести,
            "callback_data": данные для цифрового ввода
        }
    """
    logger.info(
        f"[SMART_INPUT] Context: {context}, Input: '{user_input}', "
        f"DB list size: {len(database_list)}"
    )
    
    # ===== ПРОВЕРКА 1: Это цифровой ввод? =====
    if user_input in callback_mapping:
        logger.info(f"[SMART_INPUT] Digit input: '{user_input}' → using callback mapping")
        return {
            "type": "digit",
            "callback_data": callback_mapping[user_input],
            "value": None
        }
    
    # ===== ПРОВЕРКА 2: Текстовый ввод =====
    # === ОТПРАВКА ЗАГЛУШКИ ПЕРЕД ЛЮБОЙ ОБРАБОТКОЙ ТЕКСТА ===
    logger.info(f"[SMART_INPUT] Text input detected: '{user_input}' → sending loading message")
    
    if config:
        try:
            from loading_messages import send_loading_message_whatsapp, get_whatsapp_credentials_from_config
            creds = get_whatsapp_credentials_from_config(config)
            if creds:
                await send_loading_message_whatsapp(
                    chat_id, 
                    creds["instance_id"], 
                    creds["api_token"], 
                    creds["api_url"]
                )
                logger.info(f"[LOADING] Loading message sent for text input: '{user_input}'")
        except Exception as e:
            logger.warning(f"[LOADING] Could not send loading message: {e}")
    
    # ===== Теперь обработка текста (AI) =====
    logger.info(f"[SMART_INPUT] Processing text via AI: '{user_input}'")
    
    ai_result = await ask_ai_to_parse_vehicle(
        user_text=user_input,
        chat_id=chat_id,
        context=context,
        category_name=category_name,
        brand_name=brand_name,
        config=config  # Передаем config для отправки заглушки
    )
    
    extracted_brand = ai_result.get("brand")
    extracted_model = ai_result.get("model")
    
    logger.info(
        f"[SMART_INPUT] AI extracted: brand='{extracted_brand}', model='{extracted_model}'"
    )
    
    # ===== ПРОВЕРКА 3: "Прыжок через шаги" (марка+модель одновременно) =====
    if context == "brand" and extracted_brand and extracted_model:
        logger.info(
            f"[SMART_INPUT] 🚀 JUMP detected: both brand and model found - "
            f"'{extracted_brand}' + '{extracted_model}'"
        )
        # Проверяем обе через fuzzy
        # Пока вернем флаг - обработка будет в caller
        return {
            "type": "jump",
            "brand": extracted_brand,
            "model": extracted_model,
            "value": None
        }
    
    # ===== ПРОВЕРКА 4: Двухуровневый Fuzzy Search =====
    if context == "brand":
        search_value = extracted_brand
    else:  # context == "model"
        search_value = extracted_model
    
    if not search_value:
        logger.warning(f"[SMART_INPUT] AI did not extract {context}")
        return {
            "type": "text_not_found",
            "value": None,
            "similarity": 0
        }
    
    fuzzy_result = apply_two_level_fuzzy(
        user_input=search_value,
        database_list=database_list,
        threshold_auto=70.0,
        threshold_min=60.0
    )
    
    if fuzzy_result["action"] == "apply":
        # >70% - автоматически применяем
        return {
            "type": "text_auto",
            "value": fuzzy_result["value"],
            "similarity": fuzzy_result["similarity"]
        }
    elif fuzzy_result["action"] == "ask":
        # 60-70% - переспрашиваем
        return {
            "type": "text_ask",
            "value": fuzzy_result["value"],
            "similarity": fuzzy_result["similarity"],
            "original_input": user_input
        }
    else:
        # <60% - не найдено
        return {
            "type": "text_not_found",
            "value": None,
            "similarity": fuzzy_result.get("similarity", 0)
        }


# Вспомогательные функции для генерации сообщений

def generate_confirmation_message(
    context: str,
    original_input: str,
    suggested_value: str,
    similarity: float
) -> str:
    """
    Генерирует сообщение для подтверждения (когда схожесть 60-70%).
    
    Args:
        context: "brand" или "model"
        original_input: Что ввел пользователь
        suggested_value: Что предлагаем
        similarity: Процент схожести
        
    Returns:
        str: Сообщение для пользователя
    """
    if context == "brand":
        entity = "марку"
    else:
        entity = "модель"
    
    return (
        f"❓ Вы написали: '{original_input}'\n\n"
        f"Возможно, вы имели в виду {entity} '{suggested_value}' "
        f"(схожесть: {similarity:.0f}%)?\n\n"
        f"1 - Да, использовать '{suggested_value}'\n"
        f"2 - Нет, ввести заново"
    )


def generate_not_found_message(context: str, user_input: str) -> str:
    """
    Генерирует сообщение когда ничего не найдено (<60% схожести).
    
    Args:
        context: "brand" или "model"
        user_input: Что ввел пользователь
        
    Returns:
        str: Сообщение для пользователя
    """
    if context == "brand":
        entity = "Марка"
        examples = "Toyota, BMW, Mercedes-Benz"
    else:
        entity = "Модель"
        examples = "Camry, X5, E-Class"
    
    return (
        f"❌ {entity} '{user_input}' не найдена в базе.\n\n"
        f"Попробуйте:\n"
        f"• Выбрать из списка (введите цифру 1-8)\n"
        f"• Написать точнее (например: {examples})\n"
        f"• Связаться с менеджером"
    )

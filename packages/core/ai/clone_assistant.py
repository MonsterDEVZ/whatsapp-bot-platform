"""
Скрипт для клонирования OpenAI Assistant.

Копирует конфигурацию существующего ассистента (instructions, model, tools, files)
и создает нового ассистента для другого tenant.

Использование:
    python packages/core/ai/clone_assistant.py <source_assistant_id> <new_assistant_name>

Пример:
    python packages/core/ai/clone_assistant.py asst_2BtVGCAEd5UjG4IK3DmVqRcF "5Deluxe Consultant"
"""

import os
import sys
import openai
from typing import Optional
import argparse


def clone_assistant(source_assistant_id: str, new_name: str, api_key: Optional[str] = None) -> str:
    """
    Клонирует существующего OpenAI Assistant.

    Args:
        source_assistant_id: ID исходного ассистента для клонирования
        new_name: Имя нового ассистента
        api_key: OpenAI API ключ (если None, берется из OPENAI_API_KEY)

    Returns:
        ID нового созданного ассистента

    Raises:
        Exception: Если не удалось клонировать ассистента
    """
    # Получаем API ключ
    api_key = api_key or os.getenv('OPENAI_API_KEY')

    if not api_key:
        raise ValueError("OPENAI_API_KEY не найден в переменных окружения")

    # Создаем клиент OpenAI
    client = openai.OpenAI(api_key=api_key)

    print(f"🔍 Получаю информацию об исходном ассистенте: {source_assistant_id}")

    try:
        # 1. Получаем информацию об исходном ассистенте
        source_assistant = client.beta.assistants.retrieve(source_assistant_id)

        print(f"✅ Найден ассистент: {source_assistant.name}")
        print(f"📝 Model: {source_assistant.model}")
        print(f"🛠️  Tools: {[tool.type for tool in source_assistant.tools]}")

        # 2. Получаем список файлов ассистента (если есть)
        file_ids = []
        if hasattr(source_assistant, 'file_ids') and source_assistant.file_ids:
            file_ids = source_assistant.file_ids
            print(f"📎 Файлы: {len(file_ids)} файлов")

        # 3. Создаем нового ассистента с той же конфигурацией
        print(f"\n🚀 Создаю нового ассистента: {new_name}")

        new_assistant = client.beta.assistants.create(
            name=new_name,
            instructions=source_assistant.instructions,
            model=source_assistant.model,
            tools=source_assistant.tools,
            # Копируем file_ids если есть
            file_ids=file_ids if file_ids else None,
            # Копируем другие настройки если есть
            temperature=source_assistant.temperature if hasattr(source_assistant, 'temperature') else None,
            top_p=source_assistant.top_p if hasattr(source_assistant, 'top_p') else None,
        )

        print(f"✅ Новый ассистент успешно создан!")
        print(f"\n{'='*60}")
        print(f"🆔 НОВЫЙ ASSISTANT_ID: {new_assistant.id}")
        print(f"{'='*60}\n")
        print(f"📝 Добавьте эту строку в .env файл tenant:\n")
        print(f"OPENAI_ASSISTANT_ID={new_assistant.id}")
        print(f"или")
        print(f"<TENANT_SLUG>_OPENAI_ASSISTANT_ID={new_assistant.id}")
        print(f"\n{'='*60}\n")

        # 4. Если были файлы, показываем информацию о них
        if file_ids:
            print(f"⚠️  Внимание: Были скопированы {len(file_ids)} файлов из исходного ассистента.")
            print(f"   Если у разных tenants должны быть разные базы знаний,")
            print(f"   вам нужно будет загрузить новые файлы и обновить ассистента.\n")

        return new_assistant.id

    except Exception as e:
        print(f"❌ Ошибка при клонировании ассистента: {e}")
        raise


def main():
    """Главная функция для запуска скрипта из командной строки."""
    parser = argparse.ArgumentParser(
        description='Клонирует OpenAI Assistant для нового tenant'
    )

    parser.add_argument(
        'source_id',
        type=str,
        help='ID исходного ассистента (например: asst_2BtVGCAEd5UjG4IK3DmVqRcF)'
    )

    parser.add_argument(
        'new_name',
        type=str,
        help='Имя нового ассистента (например: "5Deluxe Consultant")'
    )

    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='OpenAI API ключ (если не указан, берется из OPENAI_API_KEY)'
    )

    args = parser.parse_args()

    try:
        new_assistant_id = clone_assistant(args.source_id, args.new_name, args.api_key)
        print(f"✅ Клонирование завершено успешно!")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Клонирование не удалось: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

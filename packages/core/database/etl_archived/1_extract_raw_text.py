#!/usr/bin/env python3
"""
ETL Pipeline - Step 1: EXTRACT
================================
Извлекает сырой текст из PDF файла БД_машины.pdf
и сохраняет его в output/raw_text.txt

Использование:
    python 1_extract_raw_text.py

Результат:
    Создается файл ../output/raw_text.txt со всем текстом из PDF
"""

import sys
from pathlib import Path

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import pdfplumber
except ImportError:
    print("❌ Ошибка: библиотека pdfplumber не установлена")
    print("Установите: pip install pdfplumber")
    sys.exit(1)


def extract_text_from_pdf(pdf_path: Path, output_path: Path):
    """
    Извлекает весь текст из PDF файла.

    Args:
        pdf_path: Путь к PDF файлу
        output_path: Путь к выходному текстовому файлу
    """
    print("=" * 70)
    print("📄 ИЗВЛЕЧЕНИЕ ТЕКСТА ИЗ PDF")
    print("=" * 70)
    print(f"Источник: {pdf_path}")
    print(f"Назначение: {output_path}\n")

    if not pdf_path.exists():
        print(f"❌ Файл не найден: {pdf_path}")
        sys.exit(1)

    # Создаем директорию для output если её нет
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_text = []
    page_count = 0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"📖 Всего страниц в PDF: {total_pages}\n")

            for page_num, page in enumerate(pdf.pages, start=1):
                print(f"   Обрабатываю страницу {page_num}/{total_pages}...", end="\r")

                # Извлекаем текст со страницы
                text = page.extract_text()

                if text:
                    all_text.append(f"=== СТРАНИЦА {page_num} ===\n")
                    all_text.append(text)
                    all_text.append("\n\n")
                    page_count += 1

            print(f"\n✅ Обработано страниц: {page_count}/{total_pages}")

        # Сохраняем весь текст в файл
        full_text = "".join(all_text)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(full_text)

        # Статистика
        lines_count = len(full_text.split('\n'))
        chars_count = len(full_text)

        print(f"\n📊 СТАТИСТИКА:")
        print(f"   Строк: {lines_count:,}")
        print(f"   Символов: {chars_count:,}")
        print(f"   Размер файла: {chars_count / 1024:.1f} KB")

        print("\n" + "=" * 70)
        print(f"✅ УСПЕШНО: Текст сохранен в {output_path}")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ОШИБКА при обработке PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Главная функция."""
    # Определяем пути
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    pdf_path = project_root / "БД_машины.pdf"
    output_path = project_root / "output" / "raw_text.txt"

    extract_text_from_pdf(pdf_path, output_path)


if __name__ == "__main__":
    main()

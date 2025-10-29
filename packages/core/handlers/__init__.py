"""
Обработчики команд и callback'ов бота.
"""

from aiogram import Router

from .start import router as start_router
from .menu import router as menu_router
from .navigation import router as navigation_router
from .categories import router as categories_router
from .requests import router as requests_router
from .eva_mats import router as eva_mats_router
from .seat_covers import router as seat_covers_router
from .mats_5d import router as mats_5d_router
from .dash_mats import router as dash_mats_router
from .info_sections import router as info_sections_router
from .debug import router as debug_router
from .reset import router as reset_router
from .ai_debug import router as ai_debug_router
from .ai_parser import router as ai_parser_router

# Главный роутер, объединяющий все обработчики
main_router = Router()

# Подключаем все роутеры
# ВАЖНО: порядок имеет значение!
# 1. start_router - команды /start
# 2. reset_router - команда /reset (только для админов)
# 3. ai_debug_router - секретная команда /ask_ai (только для админов)
# 4. debug_router - команды отладки (/debug_on, /debug_off)
# 5. info_sections_router - информационные разделы (Индивидуальный замер, О нас, FAQ, Наши работы)
# 6. navigation_router - кнопки навигационной панели (высокий приоритет)
# 7. menu_router - выбор языка и возврат в меню
# 8. eva_mats_router - специфичный обработчик для EVA-ковриков
# 9. seat_covers_router - специфичный обработчик для Автомобильных чехлов
# 10. mats_5d_router - специфичный обработчик для 5D-ковриков
# 11. dash_mats_router - специфичный обработчик для Накидок на панель
# 12. categories_router - общий обработчик категорий
# 13. requests_router - обработка заявок
# 14. ai_parser_router - AI-парсер для текстовых сообщений (ДОЛЖЕН БЫТЬ ПОСЛЕДНИМ!)
main_router.include_router(start_router)
main_router.include_router(reset_router)
main_router.include_router(ai_debug_router)
main_router.include_router(debug_router)
main_router.include_router(info_sections_router)
main_router.include_router(navigation_router)
main_router.include_router(menu_router)
main_router.include_router(eva_mats_router)
main_router.include_router(seat_covers_router)
main_router.include_router(mats_5d_router)
main_router.include_router(dash_mats_router)
main_router.include_router(categories_router)
main_router.include_router(requests_router)
main_router.include_router(ai_parser_router)  # ПОСЛЕДНИЙ - ловит все текстовые сообщения без FSM-состояния

__all__ = ["main_router"]

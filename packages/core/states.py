"""
FSM состояния для управления диалогами бота.
"""

from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    """
    Состояния для процесса оформления заказа.
    """
    # Ожидание ввода марки автомобиля
    waiting_for_brand = State()

    # Ожидание ввода модели автомобиля
    waiting_for_model = State()

    # Ожидание выбора года выпуска
    waiting_for_year = State()

    # Ожидание выбора типа кузова
    waiting_for_body_type = State()

    # Выбор опций продукта
    selecting_options = State()

    # Подтверждение заказа
    confirming_order = State()

    # Ожидание ввода имени клиента
    waiting_for_name = State()

    # Ожидание отправки телефона клиента
    waiting_for_phone = State()

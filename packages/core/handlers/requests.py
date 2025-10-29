"""
Обработчики для создания и отправки заявок в группу.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, User, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from core.keyboards import get_back_to_menu_keyboard
from core.config import Config

router = Router()


async def send_request_to_group(bot: Bot, callback: CallbackQuery, config: Config, category: str = None):
    """
    Отправляет заявку от пользователя в группу менеджеров.

    Args:
        bot: Экземпляр бота
        callback: Callback query от пользователя
        config: Экземпляр конфигурации
        category: Категория товара (если указана)
    """
    i18n = config.bot.i18n

    if not config.bot.group_chat_id:
        # Если group_chat_id не настроен, просто уведомляем пользователя
        await callback.message.answer(
            i18n.get("errors.request_unavailable")
        )
        return

    user = callback.from_user

    # Формируем информацию о категории
    category_names = {
        "eva_mats": i18n.get("buttons.categories.eva_mats"),
        "seat_covers": i18n.get("categories.seat_covers.name"),
        "5d_mats": i18n.get("categories.5d_mats.name"),
        "dashboard_covers": i18n.get("categories.dashboard_covers.name")
    }

    category_text = f"{i18n.get('request.notification.category')} {category_names.get(category, i18n.get('values.not_specified'))}\n" if category else ""

    # Формируем сообщение для группы
    message_text = (
        f"{i18n.get('request.notification.new_request_simple')}\n\n"
        f"{i18n.get('request.notification.client')} {user.full_name}\n"
        f"{i18n.get('request.notification.id')} <code>{user.id}</code>\n"
        f"{i18n.get('request.notification.username')} @{user.username if user.username else i18n.get('values.not_set')}\n"
        f"{category_text}"
        f"{i18n.get('request.notification.date')} {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    # Создаем клавиатуру с кнопками для менеджеров
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.write_to_client"),
            url=f"tg://user?id={user.id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=i18n.get("buttons.actions.take_in_work"),
            callback_data=f"take_order:{user.id}"
        )
    )

    try:
        # Отправляем сообщение в группу
        await bot.send_message(
            chat_id=config.bot.group_chat_id,
            text=message_text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

        return True

    except Exception as e:
        print(f"❌ Ошибка отправки заявки в группу: {e}")
        return False


async def send_callback_request_to_airtable(
    bot: Bot,
    user: User,
    config: Config,
    client_name: str,
    client_phone: str,
    callback_details: str
) -> bool:
    """
    Сохраняет запрос на обратный звонок в Airtable.

    Args:
        bot: Экземпляр бота (не используется, оставлен для совместимости)
        user: Объект пользователя Telegram
        config: Экземпляр конфигурации
        client_name: Имя клиента
        client_phone: Телефон клиента
        callback_details: Детали запроса клиента

    Returns:
        bool: True если сохранение успешно, False иначе
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"🔍 [CALLBACK_AIRTABLE] === НАЧАЛО СОХРАНЕНИЯ CALLBACK REQUEST ===")
    logger.info(f"🔍 [CALLBACK_AIRTABLE] Tenant: {config.bot.tenant_slug}")
    logger.info(f"🔍 [CALLBACK_AIRTABLE] Клиент: {client_name} (User ID: {user.id})")
    logger.info(f"🔍 [CALLBACK_AIRTABLE] Детали: {callback_details}")

    # Проверяем конфигурацию Airtable
    if not config.airtable:
        logger.error(f"❌ [CALLBACK_AIRTABLE] Airtable не настроен для tenant={config.bot.tenant_slug}")
        return False

    try:
        from core.services import AirtableService

        # Инициализируем сервис Airtable
        airtable_service = AirtableService(
            api_key=config.airtable.api_key,
            base_id=config.airtable.base_id,
            table_name=config.airtable.table_name
        )

        # Формируем данные для Airtable
        product_full_name = "Запрос на обратный звонок"
        details_text = callback_details

        airtable_data = {
            "client_name": client_name,
            "client_phone": client_phone,
            "source": "Telegram",
            "project": config.bot.tenant_slug.upper(),
            "product": product_full_name,
            "details": details_text,
            "user_id": user.id,
            "username": user.username if user.username else None
        }

        logger.info("🔄 [CALLBACK_AIRTABLE] Попытка сохранить callback request в Airtable...")

        # Сохраняем в Airtable
        record_id = await airtable_service.create_application(airtable_data)

        if record_id:
            logger.info(f"✅ [CALLBACK_AIRTABLE] Callback request успешно сохранён. Record ID: {record_id}")
            logger.info(f"   Клиент: {client_name} (@{user.username})")
            logger.info(f"   Детали: {details_text}")
            logger.info(f"🔍 [CALLBACK_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (SUCCESS) ===")
            return True
        else:
            logger.error(f"❌ [CALLBACK_AIRTABLE] Не удалось сохранить callback request")
            logger.error(f"🔍 [CALLBACK_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
            return False

    except Exception as e:
        logger.exception("!!! КРИТИЧЕСКАЯ ОШИБКА СОХРАНЕНИЯ CALLBACK REQUEST В AIRTABLE !!!")
        logger.error(f"❌ [CALLBACK_AIRTABLE] Tenant: {config.bot.tenant_slug}")
        logger.error(f"❌ [CALLBACK_AIRTABLE] User ID: {user.id}")
        logger.error(f"❌ [CALLBACK_AIRTABLE] Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ [CALLBACK_AIRTABLE] Сообщение: {str(e)}")
        logger.error(f"🔍 [CALLBACK_AIRTABLE] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
        return False


async def send_detailed_request_card(
    bot: Bot,
    user: User,
    config: Config,
    client_name: str,
    client_phone: str,
    brand_name: str,
    model_name: str,
    category_name: str,
    option_details: str,
    total_price: int
) -> bool:
    """
    Сохраняет детальную карточку заявки в Airtable.
    Также сохраняет заявку в локальной БД для истории.

    Args:
        bot: Экземпляр бота (не используется, оставлен для совместимости)
        user: Объект пользователя Telegram
        config: Экземпляр конфигурации
        client_name: Имя клиента
        client_phone: Телефон клиента
        brand_name: Марка автомобиля
        model_name: Модель автомобиля
        category_name: Название категории товара
        option_details: Детали опций (например, "С бортами")
        total_price: Итоговая цена

    Returns:
        bool: True если сохранение успешно, False иначе
    """
    import logging
    logger = logging.getLogger(__name__)

    # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
    logger.info(f"🔍 [SEND_REQUEST] === НАЧАЛО СОХРАНЕНИЯ ЗАЯВКИ ===")
    logger.info(f"🔍 [SEND_REQUEST] Tenant: {config.bot.tenant_slug}")
    logger.info(f"🔍 [SEND_REQUEST] Клиент: {client_name} (User ID: {user.id})")
    logger.info(f"🔍 [SEND_REQUEST] Заказ: {category_name} для {brand_name} {model_name}")

    # Проверяем конфигурацию Airtable
    if not config.airtable:
        logger.error(f"❌ [SEND_REQUEST] Airtable не настроен в конфигурации для tenant={config.bot.tenant_slug}")
        return False

    # Сохраняем заявку в БД
    from core.db.connection import get_session
    from core.db.queries import get_tenant_by_slug
    from core.database.models import Application

    application_id = None
    async for session in get_session():
        try:
            # Получаем tenant
            tenant = await get_tenant_by_slug(session, config.bot.tenant_slug)

            # Создаем заявку
            application = Application(
                tenant_id=tenant.id,
                customer_id=user.id,
                customer_name=client_name,
                customer_phone=client_phone,
                customer_username=user.username,
                application_details={
                    "brand_name": brand_name,
                    "model_name": model_name,
                    "category_name": category_name,
                    "option_details": option_details,
                    "total_price": total_price,
                    "is_individual_measure": option_details == "Индивидуальный замер"
                },
                status="new"
            )

            session.add(application)
            await session.commit()
            await session.refresh(application)

            application_id = application.id
            print(f"✅ Заявка #{application_id} сохранена в БД")

        except Exception as e:
            print(f"❌ Ошибка сохранения заявки в БД: {e}")
            await session.rollback()
            # Продолжаем без application_id

    # ========================================================================
    # СОХРАНЕНИЕ В AIRTABLE
    # ========================================================================
    try:
        from core.services import AirtableService

        # Инициализируем сервис Airtable
        airtable_service = AirtableService(
            api_key=config.airtable.api_key,
            base_id=config.airtable.base_id,
            table_name=config.airtable.table_name
        )

        # Формируем данные для Airtable
        product_full_name = f"{category_name} для {brand_name} {model_name}"
        details_text = f"{option_details}, {total_price} сом"

        airtable_data = {
            "client_name": client_name,
            "client_phone": client_phone,
            "source": "Telegram",
            "project": config.bot.tenant_slug.upper(),
            "product": product_full_name,
            "details": details_text,
            "price": total_price,
            "user_id": user.id,
            "username": user.username if user.username else None
        }

        logger.info("🔄 [AIRTABLE] Попытка сохранить заявку в Airtable...")

        # Сохраняем в Airtable
        record_id = await airtable_service.create_application(airtable_data)

        if record_id:
            logger.info(f"✅ [SEND_REQUEST] Заявка #{application_id} успешно сохранена в Airtable. Record ID: {record_id}")
            logger.info(f"   Клиент: {client_name} (@{user.username})")
            logger.info(f"   Заказ: {product_full_name}")
            logger.info(f"   Детали: {details_text}")
            logger.info(f"🔍 [SEND_REQUEST] === КОНЕЦ СОХРАНЕНИЯ (SUCCESS) ===")
            return True
        else:
            logger.error(f"❌ [SEND_REQUEST] Не удалось сохранить заявку в Airtable")
            logger.error(f"🔍 [SEND_REQUEST] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
            return False

    except Exception as e:
        logger.exception("!!! КРИТИЧЕСКАЯ ОШИБКА СОХРАНЕНИЯ В AIRTABLE !!!")
        logger.error(f"❌ [SEND_REQUEST] Tenant: {config.bot.tenant_slug}")
        logger.error(f"❌ [SEND_REQUEST] User ID: {user.id}")
        logger.error(f"❌ [SEND_REQUEST] Тип ошибки: {type(e).__name__}")
        logger.error(f"❌ [SEND_REQUEST] Сообщение: {str(e)}")
        logger.error(f"🔍 [SEND_REQUEST] === КОНЕЦ СОХРАНЕНИЯ (FAILED) ===")
        return False


@router.callback_query(F.data.startswith("request:"))
async def handle_request(callback: CallbackQuery, bot: Bot, config: Config):
    """
    Обработчик кнопки "Оставить заявку".

    Формат callback_data: "request:category_code" или "request:contact"
    """
    # Извлекаем тип заявки из callback_data
    request_type = callback.data.split(":")[1]

    # Определяем категорию если это заявка на товар
    category = request_type if request_type != "contact" else None

    # Отправляем заявку в группу
    success = await send_request_to_group(bot, callback, config, category)

    i18n = config.bot.i18n

    if success:
        # Уведомляем пользователя об успехе
        await callback.message.edit_text(
            text=i18n.get("request.sent"),
            reply_markup=get_back_to_menu_keyboard(i18n),
            parse_mode="HTML"
        )

        # Отвечаем на callback
        await callback.answer(i18n.get("notifications.request_sent"), show_alert=False)
    else:
        # Уведомляем об ошибке
        await callback.message.edit_text(
            text=i18n.get("request.error"),
            reply_markup=get_back_to_menu_keyboard(i18n),
            parse_mode="HTML"
        )

        await callback.answer(i18n.get("errors.try_again"), show_alert=True)


@router.callback_query(F.data.startswith("take_application:"))
async def handle_take_application(callback: CallbackQuery, config: Config):
    """
    Обработчик кнопки "Взять в работу".
    Обновляет статус заявки в БД и уведомляет менеджера.
    """
    i18n = config.bot.i18n

    # Извлекаем application_id из callback_data
    application_id = int(callback.data.split(":")[1])

    # Получаем информацию о менеджере
    manager = callback.from_user
    manager_name = manager.full_name
    manager_username = manager.username

    # Обновляем заявку в БД
    from core.db.connection import get_session
    from core.database.models import Application
    from sqlalchemy import select

    async for session in get_session():
        try:
            # Получаем заявку
            stmt = select(Application).where(Application.id == application_id)
            result = await session.execute(stmt)
            application = result.scalar_one_or_none()

            if not application:
                await callback.answer(i18n.get("errors.application_not_found"), show_alert=True)
                return

            # Проверяем статус
            if application.status != "new":
                # Заявку уже взял другой менеджер
                other_manager = application.manager_username or f"ID {application.manager_id}"
                await callback.answer(
                    i18n.get("errors.application_taken").replace("{manager}", other_manager),
                    show_alert=True
                )
                return

            # Обновляем заявку
            application.status = "in_progress"
            application.manager_id = manager.id
            application.manager_username = manager_username

            await session.commit()
            print(f"✅ Заявка #{application_id} взята в работу менеджером @{manager_username}")

        except Exception as e:
            print(f"❌ Ошибка обновления заявки в БД: {e}")
            await session.rollback()
            await callback.answer(i18n.get("errors.application_update_error"), show_alert=True)
            return

    # Уведомляем менеджера
    await callback.answer(
        i18n.get("notifications.application_taken").replace("{id}", str(application_id)),
        show_alert=False
    )

    # Обновляем текст сообщения
    try:
        original_text = callback.message.text
        updated_text = (
            f"{original_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{i18n.get('request.notification.in_progress')}\n"
            f"{i18n.get('request.notification.manager')} @{manager_username or manager_name}\n"
            f"{i18n.get('request.notification.taken_at')} {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # Убираем кнопку "Взять в работу", оставляем только "Написать клиенту"
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        # Получаем User ID из оригинального сообщения
        import re
        user_id_match = re.search(r'User ID:</b> <code>(\d+)</code>', original_text)
        user_id = int(user_id_match.group(1)) if user_id_match else None

        if user_id:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="💬 Написать клиенту",
                    url=f"tg://user?id={user_id}"
                )
            )

            await callback.message.edit_text(
                text=updated_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=updated_text,
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"❌ Ошибка обновления сообщения: {e}")


# Старый обработчик для совместимости (если какие-то заявки были созданы без БД)
@router.callback_query(F.data.startswith("take_order:"))
async def handle_take_order(callback: CallbackQuery):
    """Старый обработчик для совместимости."""
    user_id = callback.data.split(":")[1]
    manager = callback.from_user
    manager_name = manager.full_name

    await callback.answer(
        f"✅ Заявка взята в работу!\nМенеджер: {manager_name}",
        show_alert=True
    )

    try:
        original_text = callback.message.text
        updated_text = (
            f"{original_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Взято в работу</b>\n"
            f"👨‍💼 Менеджер: {manager_name}\n"
            f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        await callback.message.edit_text(
            text=updated_text,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Ошибка обновления сообщения: {e}")

"""Seller-бот: /start покупателя. Сама запись в базу происходит в
CustomerTrackerMiddleware — сюда апдейт приходит уже с сохранённым customer."""

import html

from aiogram import Bot, Router, types
from aiogram.filters import CommandObject, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_settings
from app.models import Customer, SellerBot
from app.services.notify_texts import buyer_text

router = Router()

# Капча для заявок в канал: reply-кнопка внизу чата (её шлёт
# handlers/seller/channels.py). Нажатие приходит обычным сообщением с текстом
# кнопки — дефолтным на любом из языков или тем, что задал продавец в канале.
ROBOT_CONFIRM_TEXTS = {
    "Я не робот",
    "Я не робот 🤖",
    "I'm not a robot",
    "I'm not a robot 🤖",
}


def is_robot_confirm(text: str | None) -> bool:
    return (text or "").strip() in ROBOT_CONFIRM_TEXTS


async def is_captcha_press(message: types.Message, bot_record: SellerBot) -> bool:
    if message.chat.type != "private" or not message.text:
        return False
    if is_robot_confirm(message.text):
        return True
    from app.services.channels import captcha_channels

    text = message.text.strip()
    return any(ch.captcha_button == text for ch in await captcha_channels(bot_record.id))


async def approve_pending_requests(bot: Bot, bot_record: SellerBot, user_id: int) -> list[str]:
    """Одобряет заявки человека во всех каналах бота с капчей; возвращает
    названия каналов, куда пустили. Где заявки нет (уже вступил, отозвал,
    канал без неё) — Telegram отвечает ошибкой, её и пропускаем: хранить
    очередь заявок у себя не нужно."""
    from app.services.channels import captcha_channels

    approved = []
    for channel in await captcha_channels(bot_record.id):
        try:
            await bot.approve_chat_join_request(
                chat_id=channel.telegram_chat_id, user_id=user_id
            )
        except Exception:
            continue
        approved.append(channel.title)
    return approved


async def _has_orders(bot_id: int, customer_id: int) -> bool:
    from sqlalchemy import select

    from app.db import get_session
    from app.models import Order

    async with get_session() as session:
        return (
            await session.scalar(
                select(Order.id)
                .where(Order.bot_id == bot_id, Order.customer_id == customer_id)
                .limit(1)
            )
        ) is not None


async def catalog_keyboard(
    bot_record: SellerBot, customer: Customer | None = None
) -> types.InlineKeyboardMarkup | None:
    """Кнопка витрины — на языке покупателя (если текст не написал продавец).

    Mini App — единственный вход и в каталог, и в историю заказов, и в чат с
    продавцом. Выключенная кнопка каталога оставляла уже заплатившего человека
    вообще без входа: ни заказа посмотреть, ни написать. Теперь без заказов
    тоже отдаём витрину — иначе покупатель оставался без входа вовсе.
    """
    webapp_url = get_settings().effective_webapp_url
    if not webapp_url:
        return None

    url = f"{webapp_url}?bot_id={bot_record.id}"
    if bot_record.show_catalog_button:
        # текст продавца — его слова, не переводим; дефолт — на языке покупателя
        label = bot_record.catalog_button_text or buyer_text(customer, "start.button")
    elif customer is not None and await _has_orders(bot_record.id, customer.id):
        label = buyer_text(customer, "start.my_orders")
        url = f"{webapp_url}?bot_id={bot_record.id}#/my-orders"
    else:
        # тупик: кнопка выключена, заказов нет — раньше приветствие уходило
        # вообще без кнопки; витрина нужна в любом случае
        label = buyer_text(customer, "start.button")

    kb = InlineKeyboardBuilder()
    # Mini App получает контекст продавца через query-параметр;
    # витрина фильтрует каталог по этому bot_id (проверка — на бэкенде по initData)
    kb.button(text=label, web_app=types.WebAppInfo(url=url))
    return kb.as_markup()


def welcome_text_for(bot_record: SellerBot, customer: Customer | None = None) -> str:
    return bot_record.welcome_text or buyer_text(
        customer, "start.welcome", username=bot_record.bot_username
    )


async def send_welcome(
    message: types.Message, bot_record: SellerBot, customer: Customer | None = None
) -> None:
    """Приветствие из настроек бота + кнопка витрины. Единственная точка
    ответа «как на /start» — её же использует подтверждение «Я не робот»."""
    kb = await catalog_keyboard(bot_record, customer)
    try:
        await message.answer(welcome_text_for(bot_record, customer), reply_markup=kb)
    except Exception:
        # продавец мог сохранить текст с битым HTML — витрина не должна ломаться
        await message.answer(
            html.escape(welcome_text_for(bot_record, customer)), reply_markup=kb
        )


@router.message(CommandStart())
async def cmd_start(
    message: types.Message,
    command: CommandObject,
    bot_record: SellerBot,
    customer: Customer | None = None,
) -> None:
    # «⚙️ Настройки бота» в хаб-боте ведёт диплинком t.me/<bot>?start=settings —
    # владельцу открываем меню настроек вместо приветствия покупателя
    if command.args == "settings":
        from app.handlers.seller.settings import is_owner, show_settings_menu

        if await is_owner(bot_record, message.from_user):
            await show_settings_menu(message, bot_record)
            return

    await send_welcome(message, bot_record, customer)


@router.message(is_captcha_press)
async def robot_confirm(
    message: types.Message,
    bot: Bot,
    bot_record: SellerBot,
    customer: Customer | None = None,
) -> None:
    """Нажатие кнопки капчи: одобряем висящие заявки в каналы и отвечаем
    тем же, что и на /start — приветствие и кнопка витрины из настроек бота.
    Reply-клавиатура после нажатия убирается; отдельным сообщением потому,
    что ReplyKeyboardRemove не живёт рядом с inline-кнопкой."""
    approved = []
    if message.from_user is not None:
        approved = await approve_pending_requests(bot, bot_record, message.from_user.id)
    if approved:
        confirm = buyer_text(
            customer, "channel.joined", channel=html.escape(", ".join(approved))
        )
    else:
        confirm = buyer_text(customer, "start.robot_confirmed")
    await message.answer(confirm, reply_markup=types.ReplyKeyboardRemove())
    await send_welcome(message, bot_record, customer)

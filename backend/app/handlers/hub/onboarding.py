"""Онбординг продавца в hub-боте.

Шаг 1 — подключение выплат: продавец нажимает /start у @CryptoBot, чтобы transfer
мог класть его долю на баланс внутри @CryptoBot. Прямого API-метода «проверить,
что юзер стартовал @CryptoBot» нет, поэтому подтверждение здесь со слов продавца;
реальная проверка происходит при первой выплате (ошибка transfer -> просим
продавца нажать /start и повторяем).

Шаг 2 — подключение своего бота через @BotFather (см. services/bot_connect).
"""

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.db import get_session
from app.models import Seller
from app.services.bot_connect import connect_seller_bot

router = Router()


class ConnectBot(StatesGroup):
    waiting_token = State()


CRYPTOBOT_STEP = (
    "<b>Шаг 1 из 2 — куда будут приходить деньги</b>\n\n"
    "Выплаты с продаж приходят на твой баланс внутри @CryptoBot — дальше ты сам "
    "выводишь их на любой удобный кошелёк.\n\n"
    "1️⃣ Открой @CryptoBot по кнопке ниже\n"
    "2️⃣ Нажми <b>/start</b> (этого достаточно)\n"
    "3️⃣ Вернись сюда и нажми «Готово»"
)

BOTFATHER_STEP = (
    "<b>Шаг 2 из 2 — подключи своего бота</b>\n\n"
    "Через этого бота твои покупатели будут видеть каталог и оформлять заказы.\n\n"
    "1️⃣ Открой @BotFather по кнопке ниже\n"
    "2️⃣ Отправь команду <b>/newbot</b>\n"
    "3️⃣ Придумай имя, затем username бота (должен оканчиваться на <i>bot</i>)\n"
    "4️⃣ Скопируй токен из ответа @BotFather — строка вида "
    "<code>1234567890:AA...</code>\n"
    "5️⃣ Нажми «Ввести токен» и пришли его сюда"
)

TOKEN_ERRORS = {
    "bad_format": (
        "Это не похоже на токен бота. Токен выглядит так: "
        "<code>1234567890:AAEhBOweik6ad9r_QXMENQknvqfy9HdKWvs</code>\n"
        "Скопируй его целиком из сообщения @BotFather и пришли ещё раз "
        "(или /cancel для отмены)."
    ),
    "get_me_failed": (
        "Telegram не принял этот токен — возможно, он отозван или скопирован "
        "с ошибкой. Проверь в @BotFather (/mybots → API Token) и пришли ещё раз "
        "(или /cancel для отмены)."
    ),
    "taken_by_other": (
        "Этот бот уже подключён к платформе другим продавцом. "
        "Создай нового бота в @BotFather и пришли его токен."
    ),
}


def cryptobot_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Открыть @CryptoBot", url="https://t.me/CryptoBot")
    kb.button(text="✅ Готово, я нажал /start", callback_data="onboarding:cryptobot_done")
    kb.adjust(1)
    return kb.as_markup()


def botfather_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🤖 Открыть @BotFather", url="https://t.me/BotFather")
    kb.button(text="🔑 Ввести токен", callback_data="onboarding:enter_token")
    kb.adjust(1)
    return kb.as_markup()


async def _get_seller(telegram_id: int) -> Seller | None:
    async with get_session() as session:
        result = await session.execute(select(Seller).where(Seller.telegram_id == telegram_id))
        return result.scalar_one_or_none()


@router.callback_query(F.data == "onboarding:begin")
async def onboarding_begin(callback: types.CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return
    seller = await _get_seller(callback.from_user.id)
    if seller is None:
        await callback.message.answer("Нажми /start, чтобы зарегистрироваться.")
        return

    if not seller.cryptobot_connected:
        await callback.message.answer(CRYPTOBOT_STEP, reply_markup=cryptobot_keyboard())
    else:
        await callback.message.answer(BOTFATHER_STEP, reply_markup=botfather_keyboard())


@router.callback_query(F.data == "onboarding:cryptobot_done")
async def cryptobot_done(callback: types.CallbackQuery) -> None:
    await callback.answer("Отлично!")
    if callback.message is None or callback.from_user is None:
        return
    async with get_session() as session:
        result = await session.execute(
            select(Seller).where(Seller.telegram_id == callback.from_user.id)
        )
        seller = result.scalar_one_or_none()
        if seller is None:
            return
        seller.cryptobot_connected = True
        if seller.onboarding_step in ("none", "cryptobot"):
            seller.onboarding_step = "bot_connect"
        await session.commit()

    await callback.message.answer(BOTFATHER_STEP, reply_markup=botfather_keyboard())


@router.callback_query(F.data == "onboarding:enter_token")
async def enter_token(callback: types.CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if callback.message is None:
        return
    await state.set_state(ConnectBot.waiting_token)
    await callback.message.answer(
        "Пришли токен бота одним сообщением.\n"
        "Сообщение с токеном будет удалено сразу после проверки — "
        "токен хранится только в зашифрованном виде.\n\n"
        "Отмена — /cancel"
    )


@router.message(Command("cancel"), ConnectBot.waiting_token)
async def cancel_token(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ок, подключение бота отменено. Вернуться: /start")


@router.message(ConnectBot.waiting_token, F.text)
async def process_token(message: types.Message, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return

    raw_token = message.text
    # Сообщение с токеном не должно оставаться в чате
    try:
        await message.delete()
    except Exception:
        pass

    seller = await _get_seller(message.from_user.id)
    if seller is None:
        await state.clear()
        await message.answer("Нажми /start, чтобы зарегистрироваться.")
        return

    result = await connect_seller_bot(seller.id, raw_token)

    if result.ok and result.bot_record is not None:
        await state.clear()
        webhook_note = (
            ""
            if result.bot_record.webhook_status == "active"
            else "\n\n⚠️ Вебхук будет активирован после запуска платформы на сервере."
        )
        await message.answer(
            f"🎉 Бот <b>@{result.bot_username}</b> подключён!\n\n"
            "Что дальше:\n"
            "• добавь первый товар или услугу в кабинете продавца\n"
            "• поделись ссылкой на бота с покупателями — каждый, кто напишет ему, "
            "попадёт в твою базу"
            f"{webhook_note}"
        )
        return

    if result.error == "already_yours":
        await state.clear()
        await message.answer(
            f"Бот <b>@{result.bot_username}</b> уже подключён к твоему аккаунту. "
            "Всё в порядке!"
        )
        return

    await message.answer(TOKEN_ERRORS.get(result.error or "", TOKEN_ERRORS["get_me_failed"]))


@router.message(Command("mybots"))
async def my_bots(message: types.Message) -> None:
    if message.from_user is None:
        return
    async with get_session() as session:
        seller = (
            await session.execute(
                select(Seller).where(Seller.telegram_id == message.from_user.id)
            )
        ).scalar_one_or_none()
        if seller is None:
            await message.answer("Нажми /start, чтобы зарегистрироваться.")
            return
        await session.refresh(seller, ["bots"])
        bots = seller.bots

    if not bots:
        await message.answer("У тебя пока нет подключённых ботов. Настройка: /start")
        return

    status_icons = {"active": "🟢", "pending": "🟡", "failed": "🔴"}
    lines = [
        f"{status_icons.get(b.webhook_status, '⚪')} @{b.bot_username}"
        + ("" if b.is_active else " (выключен)")
        for b in bots
    ]
    await message.answer("<b>Твои боты:</b>\n" + "\n".join(lines))

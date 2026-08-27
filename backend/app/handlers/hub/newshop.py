"""Онбординг магазина без BotFather: название → кнопка → бот создан.

Экспериментальный сценарий (ветка managed-bot-case). Живёт целиком в hub-боте,
чтобы его можно было прогнать в Telegram, не трогая Mini App: проверяем именно
механику managed-ботов, а не вёрстку.

Как это работает:

1. `/newshop` спрашивает название магазина и заводит черновик — строку
   `seller_bots` с пустым токеном (app/services/shop_draft.py).
2. В ответ уходит reply-кнопка `KeyboardButtonRequestManagedBot` с
   `suggested_name` и `suggested_username`, собранными из названия.
3. Продавец жмёт её, Telegram сам показывает диалог создания бота и сам же
   проверяет занятость ссылки — BotFather в этом пути не участвует вовсе.
4. Нам приходит сообщение с `managed_bot_created`; по id нового бота берём
   токен через `getManagedBotToken`, дописываем черновик и ставим вебхук.

Владелец созданного бота — продавец: в `ManagedBotUpdated.user` Telegram
присылает «User that created the bot», а у владельца доступ неотнимаемый
(`BotAccessSettings`: «The bot's owner can always access it»). Мы — только
управляющий бот, как и раньше при ручном вводе токена.

Ручной путь (`POST /api/seller/bots` с токеном от BotFather) остаётся: у
существующих продавцов боты уже созданы, да и managed-боты могут оказаться
доступны не всем.
"""

import html
import logging

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.db import get_session
from app.models import Seller
from app.services.shop_draft import (
    MANAGEMENT_OFF,
    DraftPromotionError,
    can_create_managed_bots,
    create_draft,
    promote_draft,
    suggest_username,
)

logger = logging.getLogger(__name__)

router = Router()

MAX_TITLE = 128
REQUEST_ID = 1


class NewShop(StatesGroup):
    waiting_title = State()


async def _seller_for(message: types.Message) -> Seller | None:
    """Продавец по автору сообщения. Middleware у hub-бота нет — остальные
    хендлеры делают ровно так же."""
    from sqlalchemy import select

    if message.from_user is None:
        return None
    async with get_session() as session:
        return (
            await session.execute(
                select(Seller).where(Seller.telegram_id == message.from_user.id)
            )
        ).scalar_one_or_none()


NO_SELLER = "Сначала нажми /start — я заведу тебя в системе."


@router.message(Command("newshop"))
async def cmd_newshop(message: types.Message, state: FSMContext) -> None:
    # спрашиваем до вопроса про название: иначе человек введёт его, получит
    # кнопку и упрётся в «this bot doesn't support managing bots»
    if not await can_create_managed_bots():
        await message.answer(MANAGEMENT_OFF, reply_markup=types.ReplyKeyboardRemove())
        return

    await state.set_state(NewShop.waiting_title)
    await message.answer(
        "Как назовём магазин?\n\n"
        "Название увидят покупатели в шапке витрины — из него же я предложу "
        "адрес для бота.\n\n"
        "Например: <b>Кофейня у дома</b>",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(StateFilter(NewShop.waiting_title), F.text)
async def got_title(message: types.Message, state: FSMContext) -> None:
    seller = await _seller_for(message)
    if seller is None:
        await state.clear()
        await message.answer(NO_SELLER)
        return

    title = (message.text or "").strip()
    if not title or title.startswith("/"):
        await message.answer("Нужно название магазина — просто напиши его текстом.")
        return
    if len(title) > MAX_TITLE:
        await message.answer(f"Слишком длинное название — до {MAX_TITLE} символов.")
        return

    await state.clear()
    shop = await create_draft(seller.id, title)
    username = suggest_username(title)
    logger.info("Черновик магазина %s создан продавцом %s", shop.id, seller.id)

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text=f"🤖 Создать бота «{title[:40]}»",
                    request_managed_bot=types.KeyboardButtonRequestManagedBot(
                        request_id=REQUEST_ID,
                        suggested_name=title[:64],
                        suggested_username=username,
                    ),
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        f"Магазин <b>{html.escape(title)}</b> готов.\n\n"
        "Остался бот — через него покупатели попадут в витрину. "
        "Создам его сам, тебе только подтвердить.\n\n"
        f"Предложу адрес: <code>@{username}</code> — Telegram даст поправить, "
        "если он занят.",
        reply_markup=kb,
    )


@router.message(F.managed_bot_created)
async def bot_created(message: types.Message) -> None:
    """Telegram создал бота по нашей кнопке — забираем токен и включаем магазин."""
    from app.bots.hub import hub_bot
    from app.bots.runner import setup_seller_webhook
    from app.services.shop_draft import latest_draft

    seller = await _seller_for(message)
    if seller is None:
        await message.answer(NO_SELLER, reply_markup=types.ReplyKeyboardRemove())
        return

    created = message.managed_bot_created.bot_user
    logger.info("Создан managed-бот %s (@%s)", created.id, created.username)

    shop = await latest_draft(seller.id)
    if shop is None:
        # кнопку нажали, не заводя магазин: без черновика прицепить бота некуда
        await message.answer(
            "Бот создан, но магазина для него нет. Начни с /newshop — "
            "и я подключу его к новому магазину.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    try:
        token = await hub_bot.get_managed_bot_token(user_id=created.id)
    except Exception:
        logger.exception("Не удалось получить токен managed-бота %s", created.id)
        await message.answer(
            "Бот создан, но забрать его токен не вышло. "
            "Напиши мне — разберёмся вручную.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    try:
        shop = await promote_draft(shop.id, token, created.username or "", created.id)
    except DraftPromotionError as exc:
        await message.answer(
            f"Бот создан, но подключить его не вышло: {html.escape(str(exc))}.",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    webhook_ok = await setup_seller_webhook(shop)
    if not webhook_ok:
        logger.warning("Вебхук для магазина %s не встал", shop.id)

    await message.answer(
        f"✅ Магазин <b>{html.escape(shop.title or '')}</b> подключён к "
        f"@{html.escape(shop.bot_username or '')}.\n\n"
        + (
            "Открой приложение и добавь первый товар."
            if webhook_ok
            else "Бот создан, но вебхук пока не встал — сообщения покупателей "
            "могут не доходить. Загляни в /mybots через минуту."
        ),
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.managed_bot()
async def managed_bot_changed(event: types.ManagedBotUpdated) -> None:
    """Смена токена или владельца бота, которым мы управляем.

    Пока только пишем в лог: реакция зависит от того, что именно Telegram
    присылает в этих случаях — а это проверяется живьём.
    """
    logger.info(
        "managed_bot: бот %s (@%s), пользователь %s",
        event.bot_user.id,
        event.bot_user.username,
        event.user.id,
    )

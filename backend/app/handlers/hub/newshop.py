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
from time import time

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.db import get_session
from app.models import Seller
from app.services.seller_texts import seller_locale, text
from app.services.shop_draft import (
    DraftPromotionError,
    can_create_managed_bots,
    create_draft,
    promote_draft,
    set_webhook_status,
    suggest_username,
)

logger = logging.getLogger(__name__)

router = Router()

MAX_TITLE = 128
REQUEST_ID = 1
# Состояние «жду название» живёт в памяти до перезапуска, и никакой другой
# хендлер его не снимает: /newshop, потом /mybots, потом через час обычное
# «привет» — и заводился магазин с таким названием. Ограничиваем по времени.
TITLE_TIMEOUT_SEC = 15 * 60


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


@router.message(Command("newshop"))
async def cmd_newshop(message: types.Message, state: FSMContext) -> None:
    # спрашиваем до вопроса про название: иначе человек введёт его, получит
    # кнопку и упрётся в «this bot doesn't support managing bots»
    if not await can_create_managed_bots():
        await message.answer(
            text("ru", "newshop.management_off"), reply_markup=types.ReplyKeyboardRemove()
        )
        return

    await state.set_state(NewShop.waiting_title)
    await state.update_data(asked_at=time())
    # локаль берём у продавца: он мог переключить язык до запуска онбординга
    seller = await _seller_for(message)
    locale = seller_locale(seller) if seller is not None else "ru"
    await message.answer(
        text(locale, "newshop.ask_title"),
        reply_markup=types.ReplyKeyboardRemove(),
    )


@router.message(StateFilter(NewShop.waiting_title), F.text)
async def got_title(message: types.Message, state: FSMContext) -> None:
    seller = await _seller_for(message)
    if seller is None:
        await state.clear()
        await message.answer(text("ru", "hub.no_seller"))
        return
    locale = seller_locale(seller)

    asked_at = (await state.get_data()).get("asked_at", 0)
    if time() - asked_at > TITLE_TIMEOUT_SEC:
        # разговор давно прервали: считать следующую реплику названием нельзя
        await state.clear()
        return

    title = (message.text or "").strip()
    if title.startswith("/"):
        # команда вместо названия — человек передумал, а не назвал магазин так
        await state.clear()
        await message.answer(text(locale, "newshop.cancel"))
        return
    if not title:
        await message.answer(text(locale, "newshop.need_title"))
        return
    if len(title) > MAX_TITLE:
        await message.answer(text(locale, "newshop.title_too_long", n=MAX_TITLE))
        return

    await state.clear()
    shop = await create_draft(seller.id, title)
    username = suggest_username(title)
    logger.info("Черновик магазина %s создан продавцом %s", shop.id, seller.id)

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text=text(locale, "newshop.btn_create", title=title[:40]),
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
        text(
            locale,
            "newshop.ready",
            title=html.escape(title),
            username=username,
        ),
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
        await message.answer(
            text("ru", "hub.no_seller"), reply_markup=types.ReplyKeyboardRemove()
        )
        return
    locale = seller_locale(seller)

    created = message.managed_bot_created.bot_user
    logger.info("Создан managed-бот %s (@%s)", created.id, created.username)

    shop = await latest_draft(seller.id)
    if shop is None:
        # кнопку нажали, не заводя магазин: без черновика прицепить бота некуда
        await message.answer(
            text(locale, "newshop.no_draft"),
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    try:
        token = await hub_bot.get_managed_bot_token(user_id=created.id)
    except Exception:
        logger.exception("Не удалось получить токен managed-бота %s", created.id)
        await message.answer(
            text(locale, "newshop.token_failed"),
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    try:
        shop = await promote_draft(
            shop.id,
            token,
            created.username or "",
            created.id,
            bot_name=getattr(created, "first_name", None),
        )
    except DraftPromotionError as exc:
        await message.answer(
            text(locale, "newshop.promote_failed", error=html.escape(str(exc))),
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    webhook_ok = await setup_seller_webhook(shop)
    if not webhook_ok:
        logger.warning("Вебхук для магазина %s не встал", shop.id)
    # статус пишем здесь же, как bot_connect и bot_recovery: иначе магазин
    # до перезапуска процесса значится «pending» и светится в /mybots жёлтым
    await set_webhook_status(shop.id, "active" if webhook_ok else "pending")

    await message.answer(
        text(
            locale,
            "newshop.done",
            title=html.escape(shop.title or ""),
            username=html.escape(shop.bot_username or ""),
            next=(
                text(locale, "newshop.done_next")
                if webhook_ok
                else text(locale, "newshop.done_webhook")
            ),
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

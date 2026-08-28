"""Мультибот-раннер: держит N seller-ботов на вебхуках /webhook/seller/{bot_id}.

Архитектура перенесена из reference/botconnect (main.py + handlers_for_added_bots),
с двумя отличиями:
- в путях вебхуков суррогатный bot_id, а не токен;
- токены достаются из БД только в зашифрованном виде и расшифровываются в памяти.
"""

import logging

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select

from app.bots.middleware import CustomerTrackerMiddleware
from app.config import get_settings
from app.db import get_session
from app.handlers.seller import channels as seller_channels
from app.handlers.seller import chat as seller_chat
from app.handlers.seller import settings as seller_settings
from app.handlers.seller import start as seller_start
from app.models import SellerBot
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

# Общий Dispatcher для всех seller-ботов (как dp_for_added_bots в botconnect)
seller_dp = Dispatcher()
seller_dp.message.outer_middleware(CustomerTrackerMiddleware())
seller_dp.include_router(seller_channels.router)
# настройки раньше start: их /settings перехватывает команду до приветствия
seller_dp.include_router(seller_settings.router)
seller_dp.include_router(seller_start.router)
# relay-чат — последним: это catch-all по тексту, он не должен перехватить
# ни /start, ни «Я не робот», ни тексты FSM настроек; без чатов молчит
seller_dp.include_router(seller_chat.router)

SELLER_ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "chat_join_request",
    "my_chat_member",
    "chat_member",
]


def seller_webhook_path(bot_id: int) -> str:
    return f"/webhook/seller/{bot_id}"


def make_seller_bot(token: str) -> Bot:
    return Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def menu_button_for(record: SellerBot) -> types.MenuButtonWebApp:
    """Кнопка меню бота (слева от поля ввода) — постоянный вход в витрину.

    Она не зависит от show_catalog_button (та глобальная на чат): меню должно
    работать всегда, иначе покупатель без инлайн-кнопки оставался без входа.
    Текст статичный для всех языков — на этом пути продаёт продавец; Telegram
    ограничивает длину, обрезаем защитно (точный лимит проверен живьём не был).
    """
    label = (record.catalog_button_text or seller_settings.DEFAULT_BUTTON_TEXT)[:64]
    url = f"{get_settings().effective_webapp_url}?bot_id={record.id}"
    return types.MenuButtonWebApp(text=label, web_app=types.WebAppInfo(url=url))


async def apply_seller_menu_button(record: SellerBot) -> bool:
    """Ставит кнопку меню витрины отдельным вызовом — для смены текста кнопки
    из настроек. Возвращает успех."""
    if not get_settings().effective_webapp_url or record.bot_token_encrypted is None:
        return False
    token = decrypt_bot_token(record.bot_token_encrypted)
    bot = make_seller_bot(token)
    try:
        await bot.set_chat_menu_button(menu_button=menu_button_for(record))
        return True
    except Exception:
        logger.exception("Не удалось поставить кнопку меню seller-бота id=%s", record.id)
        return False
    finally:
        await bot.session.close()


async def setup_seller_webhook(record: SellerBot) -> bool:
    """Ставит вебхук для одного seller-бота. Возвращает успех."""
    settings = get_settings()
    if not settings.webhook_base_url:
        return False
    if record.bot_token_encrypted is None:
        # черновик магазина: бота ещё нет, вешать вебхук не на что
        return False
    token = decrypt_bot_token(record.bot_token_encrypted)
    bot = make_seller_bot(token)
    try:
        url = f"{settings.webhook_base_url}{seller_webhook_path(record.id)}"
        info = await bot.get_webhook_info()
        if info.url != url:
            await bot.set_webhook(
                url=url,
                secret_token=settings.telegram_webhook_secret,
                drop_pending_updates=True,
                allowed_updates=SELLER_ALLOWED_UPDATES,
            )
        try:
            # кнопка меню ставится там же, где вебхук: при рестарте и при
            # переподключении бота она восстанавливается сама
            await bot.set_chat_menu_button(menu_button=menu_button_for(record))
        except Exception:
            logger.exception("Не удалось поставить кнопку меню seller-бота id=%s", record.id)
        return True
    except Exception:
        logger.exception("Не удалось поставить вебхук для seller-бота id=%s", record.id)
        return False
    finally:
        await bot.session.close()


async def remove_seller_webhook(record: SellerBot) -> None:
    """Снимает вебхук выключаемого бота — Telegram перестаёт слать апдейты."""
    if record.bot_token_encrypted is None:
        return  # черновик: снимать нечего
    token = decrypt_bot_token(record.bot_token_encrypted)
    bot = make_seller_bot(token)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            # гигиена: бот выключен — витрина убирается и из меню
            await bot.set_chat_menu_button(menu_button=types.MenuButtonDefault())
        except Exception:
            logger.exception("Не удалось сбросить кнопку меню seller-бота id=%s", record.id)
    except Exception:
        logger.exception("Не удалось снять вебхук seller-бота id=%s", record.id)
    finally:
        await bot.session.close()


async def setup_all_seller_webhooks() -> None:
    async with get_session() as session:
        result = await session.execute(
            select(SellerBot).where(SellerBot.is_active.is_(True))
        )
        records = result.scalars().all()
        for record in records:
            if record.webhook_status == "revoked":
                # токен отозван (401, см. bot_health) — рестарт это не лечит.
                # Не понижаем до failed: иначе после каждого деплоя статус
                # терял бы точность, а продавца снова звали переподключать
                continue
            ok = await setup_seller_webhook(record)
            record.webhook_status = "active" if ok else "failed"
        await session.commit()


async def feed_seller_update(bot_id: int, update_data: dict) -> None:
    """Роутит апдейт seller-бота в общий Dispatcher с контекстом bot_id/seller_id."""
    async with get_session() as session:
        record = await session.get(SellerBot, bot_id)
    if record is None or not record.is_active or record.bot_token_encrypted is None:
        logger.warning("Апдейт для неизвестного/выключенного seller-бота id=%s", bot_id)
        return

    token = decrypt_bot_token(record.bot_token_encrypted)
    bot = make_seller_bot(token)
    try:
        update = types.Update(**update_data)
        # bot_record попадает в хендлеры как аргумент (aiogram workflow data)
        await seller_dp.feed_update(bot, update, bot_record=record)
    finally:
        await bot.session.close()

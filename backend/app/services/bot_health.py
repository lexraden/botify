"""Проверка живости seller-ботов: не отозван ли токен у @BotFather.

Зачем: вебхук ставится один раз при подключении бота. Если продавец удалит
или перевыпустит токен в @BotFather, Telegram снимет вебхук со своей стороны
молча — апдейты просто перестанут приходить. У нас `webhook_status` при этом
остаётся «active», в кабинете всё выглядит рабочим, а сообщения покупателей
уходят в никуда. Узнать об этом продавец может только по жалобам покупателей.

Проверка простая: `get_me` по каждому активному боту. 401 (Unauthorized) —
токен больше не действует. Всё остальное (сеть легла, Telegram пятисотит)
статус не трогает: разовая ошибка связи не повод пугать продавца.

Уведомление уходит один раз — на переходе в `revoked`. Пока статус не
починили переподключением, повторных пушей нет.
"""

import asyncio
import logging

from aiogram.exceptions import TelegramUnauthorizedError
from sqlalchemy import select

from app.db import get_session
from app.models import Seller, SellerBot
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

REVOKED = "revoked"

# Пауза между ботами: проверка фоновая и никуда не спешит, а Telegram не любит
# пачки запросов подряд с одного IP.
CHECK_DELAY_SEC = 0.2


async def _token_is_alive(token: str) -> bool | None:
    """True — токен рабочий, False — отозван, None — проверить не удалось."""
    from app.bots.runner import make_seller_bot

    bot = make_seller_bot(token)
    try:
        await bot.get_me()
        return True
    except TelegramUnauthorizedError:
        return False
    except Exception:
        # сеть/Telegram недоступны — это не про токен, статус не трогаем
        return None
    finally:
        await bot.session.close()


async def check_revoked_tokens() -> int:
    """Помечает боты с отозванным токеном и уведомляет продавцов.

    Возвращает число ботов, у которых токен оказался отозван на этом проходе.
    """
    async with get_session() as session:
        bots = list(
            (
                await session.execute(
                    select(SellerBot).where(
                        SellerBot.is_active.is_(True),
                        SellerBot.webhook_status != REVOKED,
                        # у черновика токена нет — проверять нечего
                        SellerBot.bot_token_encrypted.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        # токены расшифровываем сразу и наружу не выносим
        targets = [(b.id, b.bot_username, decrypt_bot_token(b.bot_token_encrypted)) for b in bots]

    revoked: list[tuple[int, str]] = []
    for bot_id, username, token in targets:
        alive = await _token_is_alive(token)
        if alive is False:
            revoked.append((bot_id, username))
        await asyncio.sleep(CHECK_DELAY_SEC)

    if not revoked:
        return 0

    async with get_session() as session:
        notify: list[tuple[int, int, str, bool]] = []
        for bot_id, username in revoked:
            record = await session.get(SellerBot, bot_id)
            # статус мог измениться, пока мы ходили в Telegram
            if record is None or record.webhook_status == REVOKED:
                continue
            record.webhook_status = REVOKED
            seller = await session.get(Seller, record.seller_id)
            if seller is not None:
                notify.append((seller.telegram_id, bot_id, username, record.is_managed))
        await session.commit()

    for seller_tg, bot_id, username, is_managed in notify:
        await _notify_revoked(seller_tg, bot_id, username, is_managed)
    logger.warning("Ботов с отозванным токеном: %d", len(revoked))
    return len(revoked)


def revoked_text(bot_username: str, is_managed: bool) -> str:
    """Что написать продавцу. Разный текст: у управляемого бота починка — одно
    нажатие, у подключённого вручную придётся идти за токеном."""
    import html

    head = (
        f"🔴 Магазин @{html.escape(bot_username)} перестал получать сообщения.\n\n"
        "Похоже, токен бота отозван или перевыпущен в @BotFather — покупатели "
        "сейчас не могут ни написать, ни оформить заказ.\n\n"
    )
    if is_managed:
        return head + (
            "Этого бота создавал я, поэтому починить могу сам: нажми кнопку, и я "
            "выпущу новый токен.\n\n"
            "⚠️ Тот токен, который ты получил в @BotFather, после этого работать "
            "перестанет. Если он нужен тебе для своих скриптов — не восстанавливай, "
            "напиши мне."
        )
    return head + (
        "Чтобы починить: возьми в @BotFather свежий токен этого бота и подключи "
        "магазин заново — каталог, заказы и касса останутся на месте."
    )


async def _notify_revoked(
    seller_tg: int, bot_id: int, bot_username: str, is_managed: bool
) -> None:
    from app.bots.hub import hub_bot
    from app.handlers.hub.mybots import restore_keyboard

    try:
        await hub_bot.send_message(
            seller_tg,
            revoked_text(bot_username, is_managed),
            reply_markup=restore_keyboard(bot_id) if is_managed else None,
        )
    except Exception:
        logger.exception("Не удалось уведомить продавца об отозванном токене")

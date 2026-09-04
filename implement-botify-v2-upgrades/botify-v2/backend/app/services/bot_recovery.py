"""Восстановление магазина, у которого отвалился токен.

Откуда берётся проблема: созданный нашей кнопкой бот виден у продавца в
@BotFather (проверено живьём), и там же он может перевыпустить токен. Наш
экземпляр токена после этого мёртв — Telegram отвечает 401, апдейты не
приходят, магазин молча перестаёт работать. Ловит это `bot_health`.

Почему это чинится без продавца: бот управляемый, а `replaceManagedBotToken`
выдаёт платформе новый токен по одному вызову. Ни BotFather, ни копипаст не
нужны — нужна только кнопка «восстановить».

Почему всё-таки с кнопкой, а не молча: перевыпуск обнуляет тот токен, который
продавец только что получил в @BotFather. Если он сделал это нарочно (хотел
дёргать бота своим скриптом), молчаливый перевыпуск сломает ему работу и он
не поймёт почему. Поэтому решение остаётся за человеком, а наше дело —
объяснить и дать одно нажатие.

Боту, подключённому вручную токеном, так нельзя: им управляет только продавец,
и остаётся прежний путь — принести свежий токен.
"""

import asyncio
import logging
from collections import defaultdict

from app.db import get_session
from app.models import SellerBot
from app.security import encrypt_bot_token
from app.services.bot_health import REVOKED

logger = logging.getLogger(__name__)

# Результаты — ключами, тексты живут в хендлере рядом с остальными
RESTORED = "restored"
NOT_MANAGED = "not_managed"
FAILED = "failed"
NOT_FOUND = "not_found"
ALREADY_OK = "already_ok"
WEBHOOK_PENDING = "webhook_pending"

# Кнопка «Восстановить» живёт в двух местах (пуш от bot_health и карточка
# магазина) и остаётся нажимаемой. Два нажатия — два replaceManagedBotToken,
# каждый убивает токен предыдущего; кто закоммитится последним, того токен и
# останется в базе, а он уже мёртв. Деплой однопроцессный (как и rate limit
# чата), поэтому замок в памяти — достаточная защита.
_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


async def restore_managed_token(bot_id: int, seller_id: int) -> str:
    """Перевыпустить токен управляемого бота и поднять магазин обратно.

    Возвращает 'restored' | 'already_ok' | 'webhook_pending' | 'not_managed'
    | 'failed' | 'not_found'.
    """
    from app.bots.hub import hub_bot
    from app.bots.runner import setup_seller_webhook

    async with _locks[bot_id]:
        async with get_session() as session:
            bot = await session.get(SellerBot, bot_id)
            if bot is None or bot.seller_id != seller_id:
                return NOT_FOUND
            if not bot.is_managed or bot.telegram_bot_id is None:
                return NOT_MANAGED
            if bot.webhook_status != REVOKED:
                # первое нажатие уже всё починило: второе не должно выпускать
                # ещё один токен и тем самым убивать только что выданный
                return ALREADY_OK
            telegram_bot_id = bot.telegram_bot_id

        try:
            token = await hub_bot.replace_managed_bot_token(user_id=telegram_bot_id)
        except Exception:
            # доступ к боту могли отобрать (setManagedBotAccessSettings), либо
            # Telegram недоступен — в обоих случаях остаётся ручной путь
            logger.exception("Не удалось перевыпустить токен бота %s", bot_id)
            return FAILED

        async with get_session() as session:
            bot = await session.get(SellerBot, bot_id)
            if bot is None:
                return NOT_FOUND
            bot.bot_token_encrypted = encrypt_bot_token(token)
            # is_active не трогаем: магазин мог быть отключён продавцом
            # намеренно, и починка токена — не повод открывать его снова
            webhook_ok = await setup_seller_webhook(bot)
            bot.webhook_status = "active" if webhook_ok else "pending"
            await session.commit()

    if not webhook_ok:
        # Токен заменён и закоммичен — старый из @BotFather уже мёртв. Назвать
        # это «не вышло восстановить» нельзя: продавец решит, что ничего не
        # произошло, и пойдёт искать старый токен, которого больше нет.
        logger.warning("Токен бота %s перевыпущен, вебхук не встал", bot_id)
        return WEBHOOK_PENDING
    logger.info("Токен бота %s перевыпущен, магазин восстановлен", bot_id)
    return RESTORED

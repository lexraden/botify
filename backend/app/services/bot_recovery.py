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

import logging

from app.db import get_session
from app.models import SellerBot
from app.security import encrypt_bot_token

logger = logging.getLogger(__name__)

# Результаты — ключами, тексты живут в хендлере рядом с остальными
RESTORED = "restored"
NOT_MANAGED = "not_managed"
FAILED = "failed"
NOT_FOUND = "not_found"


async def restore_managed_token(bot_id: int, seller_id: int) -> str:
    """Перевыпустить токен управляемого бота и поднять магазин обратно.

    Возвращает 'restored' | 'not_managed' | 'failed' | 'not_found'.
    """
    from app.bots.hub import hub_bot
    from app.bots.runner import setup_seller_webhook

    async with get_session() as session:
        bot = await session.get(SellerBot, bot_id)
        if bot is None or bot.seller_id != seller_id:
            return NOT_FOUND
        if not bot.is_managed or bot.telegram_bot_id is None:
            return NOT_MANAGED
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
        bot.is_active = True
        webhook_ok = await setup_seller_webhook(bot)
        bot.webhook_status = "active" if webhook_ok else "pending"
        await session.commit()

    if not webhook_ok:
        # токен новый и рабочий, но вебхук не встал — магазин ещё не ожил
        logger.warning("Токен бота %s перевыпущен, вебхук не встал", bot_id)
        return FAILED
    logger.info("Токен бота %s перевыпущен, магазин восстановлен", bot_id)
    return RESTORED

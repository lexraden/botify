"""Магазин, заведённый до бота, и превращение его в настоящий.

Черновик заводится в момент, когда продавцу показывают кнопку создания бота,
и пока что без названия: его человек даёт боту в окне Telegram, и при
promote_draft оно становится названием магазина.

Черновик — обычная строка `seller_bots` с пустым токеном и `is_active=False`.
Покупателям он недоступен (`get_buyer` требует активный магазин), вебхуков у
него нет, а `bot_id` уже существует — поэтому ни одна строка каталога,
витрины или изоляции не меняется.
"""

import logging

from sqlalchemy import select

from app.db import get_session
from app.models import SellerBot
from app.security import encrypt_bot_token

logger = logging.getLogger(__name__)

async def create_draft(seller_id: int, title: str | None = None) -> SellerBot:
    """Завести магазин без бота. Возвращает строку с готовым bot_id.

    Незаконченный черновик у продавца ровно один: повторный /newshop
    переиспользует его, а не плодит новый. Иначе каждая брошенная попытка
    оставляла мусорную строку в кабинете навсегда, а кнопка из первого
    сообщения привязывала созданного бота к магазину из второго.

    Название необязательно: в основном сценарии его даёт окно Telegram, где
    человек называет бота, и в магазин оно попадает при promote_draft.
    """
    async with get_session() as session:
        shop = (
            await session.execute(
                select(SellerBot)
                .where(
                    SellerBot.seller_id == seller_id,
                    SellerBot.bot_token_encrypted.is_(None),
                )
                .order_by(SellerBot.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if shop is None:
            shop = SellerBot(
                seller_id=seller_id,
                is_active=False,  # покупателям черновик не показываем
                webhook_status="pending",
            )
            session.add(shop)
        if title and title.strip():
            shop.title = title.strip()[:128]
        await session.commit()
        await session.refresh(shop)
        return shop


async def latest_draft(seller_id: int) -> SellerBot | None:
    """Незавершённый магазин продавца, если он есть."""
    async with get_session() as session:
        return (
            await session.execute(
                select(SellerBot)
                .where(
                    SellerBot.seller_id == seller_id,
                    SellerBot.bot_token_encrypted.is_(None),
                )
                .order_by(SellerBot.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()


# getMe у Telegram ради одного флага на каждый вход в приложение — лишний
# рейс на самом частом запросе. Флаг меняется руками в @BotFather и раз в
# несколько минут перечитать его достаточно.
_MANAGED_TTL_SEC = 300.0
# payload диплинка: /start с ним сразу открывает создание магазина
NEWSHOP_PAYLOAD = "newshop"
_managed_cache: tuple[float, bool] | None = None


async def create_shop_deeplink() -> str | None:
    """Ссылка, которая открывает в hub-боте создание магазина.

    None — Telegram не разрешает нам создавать ботов: тогда единственный
    рабочий путь ручной, и звать человека в диалог, где его встретит отказ,
    нельзя.
    """
    from app.bots.hub import hub_bot

    if not await can_create_managed_bots():
        return None
    try:
        me = await hub_bot.get_me()
    except Exception:
        logger.exception("Не удалось узнать юзернейм hub-бота")
        return None
    return f"https://t.me/{me.username}?start={NEWSHOP_PAYLOAD}" if me.username else None


def reset_managed_cache() -> None:
    """Забыть закэшированный флаг. Нужен тестам: кэш живёт в модуле, и без
    сброса один тест наследовал бы ответ Telegram, подменённый в другом."""
    global _managed_cache
    _managed_cache = None


async def can_create_managed_bots() -> bool:
    """Разрешено ли нашему боту создавать боты для пользователей.

    Флаг `can_manage_bots` поднимается вручную в мини-аппе @BotFather
    («Bot Management Mode») и приходит только в ответе `getMe`. Пока он снят,
    Telegram отвечает на кнопку «this bot doesn't support managing bots» —
    поэтому кнопку лучше не показывать вовсе, чем показывать сломанной.

    Ошибку связи трактуем как «нельзя»: лучше предложить ручной путь, чем
    отправить человека в тупик.
    """
    from time import monotonic

    from app.bots.hub import hub_bot

    global _managed_cache
    now = monotonic()
    if _managed_cache is not None and now - _managed_cache[0] < _MANAGED_TTL_SEC:
        return _managed_cache[1]

    try:
        me = await hub_bot.get_me()
    except Exception:
        logger.exception("Не удалось спросить getMe у hub-бота")
        return False  # сбой связи не кэшируем: следующая попытка спросит заново
    # getattr, а не атрибут: поля может не быть вовсе (старая библиотека,
    # изменившийся ответ Telegram). Обращение к нему живёт за пределами try
    # выше, и AttributeError здесь ронял бы /api/seller/me — то есть весь
    # вход в приложение из-за необязательного флага.
    allowed = bool(getattr(me, "can_manage_bots", False))
    _managed_cache = (now, allowed)
    return allowed


async def set_webhook_status(shop_id: int, status: str) -> None:
    """Записать исход установки вебхука.

    Отдельной функцией, потому что вебхук ставится уже после promote_draft:
    ему нужен bot_id, а тот появляется только вместе с записанным токеном.
    """
    async with get_session() as session:
        shop = await session.get(SellerBot, shop_id)
        if shop is not None:
            shop.webhook_status = status
            await session.commit()


class DraftPromotionError(Exception):
    """Черновик не удалось превратить в магазин."""


async def promote_draft(
    shop_id: int,
    token: str,
    bot_username: str,
    telegram_bot_id: int,
    bot_name: str | None = None,
) -> SellerBot:
    """Дописать боту черновик и включить магазин.

    Токен шифруется тем же путём, что и при ручном подключении — способ
    появления бота на хранение не влияет.
    """
    async with get_session() as session:
        shop = await session.get(SellerBot, shop_id)
        if shop is None:
            raise DraftPromotionError("магазин не найден")
        if shop.bot_token_encrypted is not None:
            raise DraftPromotionError("к этому магазину бот уже подключён")

        taken = (
            await session.execute(
                select(SellerBot.id).where(
                    SellerBot.telegram_bot_id == telegram_bot_id,
                    SellerBot.id != shop_id,
                )
            )
        ).scalar_one_or_none()
        if taken is not None:
            raise DraftPromotionError("этот бот уже подключён к другому магазину")

        shop.bot_token_encrypted = encrypt_bot_token(token)
        shop.bot_username = bot_username
        shop.telegram_bot_id = telegram_bot_id
        shop.is_active = True
        # бот наш управляемый: если продавец сменит токен в @BotFather,
        # мы сможем перевыпустить его сами (app/services/bot_recovery.py)
        shop.is_managed = True
        # Название не спрашивали отдельно — им становится имя, которое
        # человек дал боту в окне Telegram. Это и есть название магазина:
        # вопрос до кнопки был тем же вопросом, заданным дважды
        if not shop.title and bot_name and bot_name.strip():
            shop.title = bot_name.strip()[:128]
        # Шапка витрины читает shop_name, а не title (api/store.py). Без этой
        # строки магазин, заведённый как «Кофейня у дома», показывал покупателю
        # @kofeynya_u_doma_bot — ровно то, ради чего онбординг и начинали с
        # названия. Своё имя, если продавец успел его задать, не трогаем.
        if not shop.shop_name and shop.title:
            shop.shop_name = shop.title[:64]
        # исходное Telegram-имя для возврата при сбросе shop_name
        # (services/bot_profile.py): у managed-бота это имя, с которым его
        # создал @BotFather, — оно приходит в managed_bot_created; если по
        # какой-то причине не пришло, берём название магазина, из которого
        # оно и собиралось
        if not shop.default_bot_name:
            shop.default_bot_name = ((bot_name or shop.title or "").strip()[:64]) or None
        await session.commit()
        await session.refresh(shop)
        return shop

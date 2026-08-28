"""Магазин, заведённый до бота, и превращение его в настоящий.

Онбординг идёт от названия магазина к боту, а не наоборот: «как называется
магазин» — вопрос, на который у человека есть ответ, а «вставь токен» — нет.
Из названия же собирается предложение юзернейма для кнопки создания бота, так
что первый шаг кормит последний.

Черновик — обычная строка `seller_bots` с пустым токеном и `is_active=False`.
Покупателям он недоступен (`get_buyer` требует активный магазин), вебхуков у
него нет, а `bot_id` уже существует — поэтому товары можно заводить в него
сразу, и ни одна строка каталога, витрины или изоляции не меняется.
"""

import logging
import re
import secrets

from sqlalchemy import select

from app.db import get_session
from app.models import SellerBot
from app.security import encrypt_bot_token

logger = logging.getLogger(__name__)

# Телеграм требует латиницу, цифры и подчёркивания, 5–32 символа, окончание bot
_SUFFIX = "_bot"
MAX_USERNAME = 32

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def suggest_username(title: str) -> str:
    """Юзернейм-кандидат из названия магазина.

    Это именно предложение: занятость проверяет Telegram в своём же диалоге
    создания, и он же даст человеку поправить. Наша задача — чтобы в поле уже
    лежало что-то осмысленное, а не пустота.

    Хвост из случайных символов не добавляем: осмысленное имя человек оставит
    охотнее, а если оно занято — Telegram попросит другое, и это нормально.
    """
    lowered = "".join(_TRANSLIT.get(ch, ch) for ch in title.lower())
    cleaned = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    if not cleaned:
        # название целиком из символов, которые мы не переводим (иероглифы,
        # эмодзи) — предложить осмысленное нечего, даём нейтральное
        cleaned = f"shop_{secrets.token_hex(3)}"
    if cleaned[0].isdigit():
        # Telegram требует, чтобы юзернейм начинался с буквы: «7 небо» дало бы
        # 7_nebo_bot, и диалог создания отверг бы наше же предложение
        cleaned = f"shop_{cleaned}"
    return cleaned[: MAX_USERNAME - len(_SUFFIX)].strip("_") + _SUFFIX


async def create_draft(seller_id: int, title: str) -> SellerBot:
    """Завести магазин без бота. Возвращает строку с готовым bot_id.

    Незаконченный черновик у продавца ровно один: повторный /newshop
    переименовывает его, а не плодит новый. Иначе каждая брошенная попытка
    оставляла мусорную строку в кабинете навсегда, а кнопка из первого
    сообщения привязывала созданного бота к магазину из второго —
    подтверждение называло один магазин, а бот нёс адрес другого.
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


async def can_create_managed_bots() -> bool:
    """Разрешено ли нашему боту создавать боты для пользователей.

    Флаг `can_manage_bots` поднимается вручную в мини-аппе @BotFather
    («Bot Management Mode») и приходит только в ответе `getMe`. Пока он снят,
    Telegram отвечает на кнопку «this bot doesn't support managing bots» —
    поэтому кнопку лучше не показывать вовсе, чем показывать сломанной.

    Ошибку связи трактуем как «нельзя»: лучше предложить ручной путь, чем
    отправить человека в тупик.
    """
    from app.bots.hub import hub_bot

    try:
        me = await hub_bot.get_me()
    except Exception:
        logger.exception("Не удалось спросить getMe у hub-бота")
        return False
    return bool(me.can_manage_bots)


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
    shop_id: int, token: str, bot_username: str, telegram_bot_id: int
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
        # Шапка витрины читает shop_name, а не title (api/store.py). Без этой
        # строки магазин, заведённый как «Кофейня у дома», показывал покупателю
        # @kofeynya_u_doma_bot — ровно то, ради чего онбординг и начинали с
        # названия. Своё имя, если продавец успел его задать, не трогаем.
        if not shop.shop_name and shop.title:
            shop.shop_name = shop.title[:64]
        await session.commit()
        await session.refresh(shop)
        return shop

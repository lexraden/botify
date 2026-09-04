from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_api_session
from app.models import Customer, Seller, SellerBot
from app.security import decrypt_bot_token
from app.services.channels import TgUserInfo, upsert_customer
from app.services.webapp_auth import validate_init_data


@dataclass
class BuyerContext:
    customer: Customer
    bot: SellerBot
    session: AsyncSession


async def _buyer_context(
    bot_id: int,
    x_init_data: str,
    session: AsyncSession,
    *,
    require_active: bool,
    x_locale: str = "",
) -> BuyerContext:
    """Покупатель: initData подписана токеном seller-бота, из которого открыта витрина.

    `require_active` разделяет две разные вещи. Витрина и оформление заказа у
    отключённого магазина закрыты — покупать там нечего. А свои уже оплаченные
    заказы, переписка с продавцом и отзывы остаются доступными: продавец нажал
    «Отключить», а деньги покупателя уже у него, и отбирать вместе с витриной
    историю покупок нельзя.
    """
    bot = await session.get(SellerBot, bot_id)
    # Черновик отсеиваем вместе с несуществующим магазином: бота у него нет,
    # значит и подписать initData нечем. Без этой проверки require_active=False
    # пропускал черновик дальше, и расшифровка пустого токена давала 500
    # на угадываемом id вместо честного 404.
    if bot is None or bot.bot_token_encrypted is None or (require_active and not bot.is_active):
        raise HTTPException(status_code=404, detail="shop not found")

    token = decrypt_bot_token(bot.bot_token_encrypted)
    data = validate_init_data(x_init_data, token)
    if data is None or "user" not in data:
        raise HTTPException(status_code=401, detail="invalid init data")

    user = data["user"]
    customer, _ = await upsert_customer(
        bot,
        TgUserInfo(
            telegram_id=user["id"],
            username=user.get("username"),
            first_name=user.get("first_name"),
            language_code=user.get("language_code"),
        ),
        source="webapp",
        locale=x_locale or None,
    )
    if customer.is_banned:
        raise HTTPException(status_code=403, detail="banned")
    return BuyerContext(customer=customer, bot=bot, session=session)


async def get_buyer(
    bot_id: int = Path(),
    x_init_data: str = Header(default=""),
    x_locale: str = Header(default=""),
    session: AsyncSession = Depends(get_api_session),
) -> BuyerContext:
    """Витрина и покупка: только у работающего магазина."""
    return await _buyer_context(bot_id, x_init_data, session, require_active=True, x_locale=x_locale)


async def get_buyer_any_shop(
    bot_id: int = Path(),
    x_init_data: str = Header(default=""),
    x_locale: str = Header(default=""),
    session: AsyncSession = Depends(get_api_session),
) -> BuyerContext:
    """Свои заказы, чат и отзывы — доступны и у отключённого магазина."""
    return await _buyer_context(
        bot_id, x_init_data, session, require_active=False, x_locale=x_locale
    )


async def get_seller(
    x_init_data: str = Header(default=""),
    session: AsyncSession = Depends(get_api_session),
) -> Seller:
    """Продавец: initData подписана токеном hub-бота (кабинет открыт из него)."""
    data = validate_init_data(x_init_data, get_settings().hub_bot_token)
    if data is None or "user" not in data:
        raise HTTPException(status_code=401, detail="invalid init data")

    result = await session.execute(
        select(Seller).where(Seller.telegram_id == data["user"]["id"])
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise HTTPException(status_code=403, detail="not registered; press /start in the bot")
    if seller.is_banned:
        raise HTTPException(status_code=403, detail="banned")
    return seller

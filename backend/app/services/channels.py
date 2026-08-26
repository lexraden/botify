"""Каналы продавца и сбор базы покупателей (изоляция по seller_id/bot_id).

Логика перенесена из reference/botconnect/handlers/channels, но без привязки
к токену бота: всё ключуется по суррогатным id.
"""

from dataclasses import dataclass

from sqlalchemy import select

from app.db import get_session
from app.models import Channel, Customer, SellerBot


async def register_channel(bot_record: SellerBot, chat_id: int, title: str) -> tuple[Channel, bool]:
    """Регистрирует канал, куда добавили seller-бота. Возвращает (канал, новый ли)."""
    async with get_session() as session:
        existing = (
            await session.execute(select(Channel).where(Channel.telegram_chat_id == chat_id))
        ).scalar_one_or_none()
        if existing is not None:
            existing.title = title
            existing.bot_id = bot_record.id
            existing.seller_id = bot_record.seller_id
            existing.is_active = True
            await session.commit()
            return existing, False

        channel = Channel(
            seller_id=bot_record.seller_id,
            bot_id=bot_record.id,
            telegram_chat_id=chat_id,
            title=title,
        )
        session.add(channel)
        await session.commit()
        return channel, True


async def deactivate_channel(chat_id: int) -> None:
    async with get_session() as session:
        channel = (
            await session.execute(select(Channel).where(Channel.telegram_chat_id == chat_id))
        ).scalar_one_or_none()
        if channel is not None:
            channel.is_active = False
            await session.commit()


async def list_channels(bot_id: int) -> list[Channel]:
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(Channel.bot_id == bot_id).order_by(Channel.id)
        )
        return list(result.scalars().all())


async def get_bot_channel(bot_id: int, channel_id: int) -> Channel | None:
    """Канал достаётся только парой (bot_id, channel_id): чужой канал другого
    магазина из этого контекста недостижим."""
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
    if channel is None or channel.bot_id != bot_id:
        return None
    return channel


async def get_channel_for_bot(bot_id: int, chat_id: int) -> Channel | None:
    """Канал этого бота по telegram_chat_id; чужой магазин недостижим."""
    async with get_session() as session:
        result = await session.execute(
            select(Channel).where(
                Channel.telegram_chat_id == chat_id, Channel.bot_id == bot_id
            )
        )
        return result.scalar_one_or_none()


async def deactivate_channel_by_id(bot_id: int, channel_id: int) -> bool:
    """Отключает канал продавца по id; чужой канал не трогаем."""
    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel is None or channel.bot_id != bot_id:
            return False
        channel.is_active = False
        await session.commit()
        return True


async def get_channel(chat_id: int) -> Channel | None:
    async with get_session() as session:
        return (
            await session.execute(select(Channel).where(Channel.telegram_chat_id == chat_id))
        ).scalar_one_or_none()


@dataclass
class TgUserInfo:
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    language_code: str | None = None


async def upsert_customer(
    bot_record: SellerBot, user: TgUserInfo, source: str | None = None
) -> tuple[Customer, bool]:
    """Добавляет покупателя в базу конкретного seller-бота (или обновляет).
    source записывается только при первом контакте — фиксируем происхождение лида."""
    async with get_session() as session:
        customer = (
            await session.execute(
                select(Customer).where(
                    Customer.telegram_id == user.telegram_id,
                    Customer.bot_id == bot_record.id,
                )
            )
        ).scalar_one_or_none()

        if customer is not None:
            customer.username = user.username
            customer.first_name = user.first_name
            # Раз он снова здесь — бот разблокирован, рассылки опять доходят.
            # Иначе отметка «не доставляется» осталась бы навсегда.
            customer.mailing_blocked = False
            await session.commit()
            return customer, False

        customer = Customer(
            telegram_id=user.telegram_id,
            seller_id=bot_record.seller_id,
            bot_id=bot_record.id,
            username=user.username,
            first_name=user.first_name,
            language_code=user.language_code,
            source=source,
        )
        session.add(customer)
        await session.commit()
        return customer, True

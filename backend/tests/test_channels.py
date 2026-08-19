import pytest
from sqlalchemy import select

from app.models import Channel, Customer, Seller, SellerBot
from app.services.channels import (
    TgUserInfo,
    deactivate_channel,
    get_channel,
    register_channel,
    upsert_customer,
)


async def make_seller_with_bot(db, telegram_id=111, tg_bot_id=555) -> SellerBot:
    async with db() as session:
        seller = Seller(telegram_id=telegram_id)
        session.add(seller)
        await session.flush()
        bot = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=b"encrypted",
            bot_username=f"shop{tg_bot_id}_bot",
            telegram_bot_id=tg_bot_id,
        )
        session.add(bot)
        await session.commit()
        return bot


@pytest.mark.asyncio
async def test_register_and_deactivate_channel(db):
    bot = await make_seller_with_bot(db)

    channel, is_new = await register_channel(bot, -100123, "Мой канал")
    assert is_new
    assert channel.auto_accept  # авто-приём включён по умолчанию

    # повторное добавление — не новый, название обновляется
    channel2, is_new2 = await register_channel(bot, -100123, "Мой канал (new)")
    assert not is_new2
    assert channel2.id == channel.id
    assert channel2.title == "Мой канал (new)"

    await deactivate_channel(-100123)
    stored = await get_channel(-100123)
    assert stored is not None and not stored.is_active

    # возвращение бота в канал реактивирует его
    _, is_new3 = await register_channel(bot, -100123, "Мой канал")
    stored = await get_channel(-100123)
    assert not is_new3 and stored.is_active


@pytest.mark.asyncio
async def test_upsert_customer_isolated_per_bot(db):
    bot_a = await make_seller_with_bot(db, telegram_id=111, tg_bot_id=555)
    bot_b = await make_seller_with_bot(db, telegram_id=222, tg_bot_id=556)
    user = TgUserInfo(telegram_id=999, username="buyer", first_name="Иван")

    c1, created1 = await upsert_customer(bot_a, user, source="channel:-100123")
    assert created1
    assert c1.source == "channel:-100123"
    assert c1.seller_id == bot_a.seller_id

    # тот же юзер у другого продавца — отдельная запись (изоляция баз)
    c2, created2 = await upsert_customer(bot_b, user)
    assert created2
    assert c2.id != c1.id
    assert c2.seller_id == bot_b.seller_id

    # повторный контакт с первым ботом — не дубль, source первого контакта сохранён
    c3, created3 = await upsert_customer(bot_a, TgUserInfo(telegram_id=999, username="buyer2"))
    assert not created3
    assert c3.id == c1.id

    async with db() as session:
        stored = await session.get(Customer, c1.id)
        assert stored.username == "buyer2"  # обновился
        assert stored.source == "channel:-100123"  # источник не перезаписан
        total = (await session.execute(select(Customer))).scalars().all()
        assert len(total) == 2

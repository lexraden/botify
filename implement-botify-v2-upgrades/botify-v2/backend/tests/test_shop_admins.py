"""Роли в магазине: админ ведёт магазин наравне с владельцем, кроме денег.

Матрица прав в API (get_shop пропускает владельца и приглашённого админа,
_require_owner отсекает админа от денег), выдача и снятие роли в hub-боте,
меню «Магазины, где я администратор».
"""

import os
from time import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.bots.hub import hub_bot
from app.handlers.hub import mybots, shop_admins, start
from app.models import Seller, SellerBot, StoreAdmin
from tests.test_api import SELLER_TG, client, init_data_for, seller_headers, setup_shop
from tests.test_bot_connect import make_seller
from tests.test_hub_menus import (
    button_texts,
    fake_callback,
    fake_message,
    fake_state,
    make_bot,
    patch_settings,
)


def admin_headers() -> dict:
    user = {"id": 222, "first_name": "Хелпер", "username": "helper"}
    return {"X-Init-Data": init_data_for(user, os.environ["HUB_BOT_TOKEN"])}


async def grant_admin(db, bot_id: int, seller_id: int) -> None:
    async with db() as session:
        session.add(StoreAdmin(bot_id=bot_id, seller_id=seller_id))
        await session.commit()


async def make_seller_with_username(db, telegram_id: int, username: str) -> int:
    async with db() as session:
        seller = Seller(telegram_id=telegram_id, username=username)
        session.add(seller)
        await session.commit()
        return seller.id


# --------------------------------------------------------------------------
# API: доступ и матрица прав
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_viewer_role_owner_and_admin(db):
    bot_id = await setup_shop(db)
    helper_id = await make_seller(db, telegram_id=222)
    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        assert r.status_code == 200
        assert r.json()["viewer_role"] == "owner"

        await grant_admin(db, bot_id, helper_id)
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=admin_headers())
        assert r.status_code == 200
        assert r.json()["viewer_role"] == "admin"


@pytest.mark.asyncio
async def test_admin_full_access_except_money(db):
    bot_id = await setup_shop(db)
    helper_id = await make_seller(db, telegram_id=222)
    await grant_admin(db, bot_id, helper_id)
    async with client() as c:
        # рабочие операции: каталог под полным управлением админа
        r = await c.post(
            f"/api/seller/bots/{bot_id}/products",
            json={"type": "physical", "title": "Кружка", "price": "10", "stock": 5},
            headers=admin_headers(),
        )
        assert r.status_code == 200
        r = await c.get(f"/api/seller/bots/{bot_id}/products", headers=admin_headers())
        assert [p["title"] for p in r.json()] == ["Кружка"]
        # заказы, отзывы, рассылки, статистика — читаются
        for path in ("orders", "reviews", "mailings", "stats"):
            r = await c.get(f"/api/seller/bots/{bot_id}/{path}", headers=admin_headers())
            assert r.status_code == 200

        # деньги и жизнь магазина — только владелец
        r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=admin_headers())
        assert r.status_code == 403
        r = await c.delete(f"/api/seller/bots/{bot_id}", headers=admin_headers())
        assert r.status_code == 403
        # магазин цел, владелец по-прежнему всё видит
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=seller_headers())
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_disable_and_owner_is_notified(db):
    bot_id = await setup_shop(db)
    helper_id = await make_seller(db, telegram_id=222)
    await grant_admin(db, bot_id, helper_id)
    with patch.object(hub_bot, "send_message", new=AsyncMock()) as notify:
        async with client() as c:
            r = await c.post(f"/api/seller/bots/{bot_id}/disable", headers=admin_headers())
        assert r.status_code == 200
        assert r.json()["is_active"] is False
    # пуш уходит владельцу магазина, а не тому, кто нажал кнопку
    notify.assert_awaited_once()
    assert notify.await_args.args[0] == SELLER_TG["id"]


@pytest.mark.asyncio
async def test_stranger_without_role_sees_404(db):
    bot_id = await setup_shop(db)
    await make_seller(db, telegram_id=222)
    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/summary", headers=admin_headers())
        assert r.status_code == 404
        r = await c.post(f"/api/seller/bots/{bot_id}/payouts/withdraw", headers=admin_headers())
        assert r.status_code == 404


# --------------------------------------------------------------------------
# Хаб: кнопка в карточке, меню «Магазины, где я администратор»
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_card_keyboard_has_admins_button(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="manned_shop")
    async with db() as session:
        bot = await session.get(SellerBot, bot_id)
        texts = button_texts(mybots.bot_card_keyboard(bot))
    assert "👥 Администраторы" in texts


@pytest.mark.asyncio
async def test_start_shows_admin_shops_button_only_with_role(db):
    owner_id = await make_seller(db, telegram_id=111)
    await make_bot(db, owner_id, username="own_shop")
    stranger_id = await make_seller(db, telegram_id=222)
    other_bot_id = await make_bot(db, stranger_id, username="other_shop")

    msg = fake_message()
    with patch_settings("start"):
        await start.cmd_start(msg, fake_state())
    assert "🛠 Магазины, где я администратор" not in button_texts(
        msg.answer.call_args.kwargs["reply_markup"]
    )

    # 111 выдали админа в чужом магазине — кнопка появляется
    await grant_admin(db, other_bot_id, owner_id)
    msg = fake_message()
    with patch_settings("start"):
        await start.cmd_start(msg, fake_state())
    assert "🛠 Магазины, где я администратор" in button_texts(
        msg.answer.call_args.kwargs["reply_markup"]
    )


@pytest.mark.asyncio
async def test_adminshops_menu_lists_shop_with_cabinet_button(db):
    owner_id = await make_seller(db, telegram_id=222)
    bot_id = await make_bot(db, owner_id, username="trusted_shop")
    helper_id = await make_seller(db, telegram_id=111)
    await grant_admin(db, bot_id, helper_id)

    msg = fake_message(telegram_id=111)
    with patch_settings("shop_admins"):
        await shop_admins.cmd_adminshops(msg)
    text = msg.answer.call_args.args[0]
    assert "Магазины, где ты администратор" in text and "@trusted_shop" in text
    markup = msg.answer.call_args.kwargs["reply_markup"]
    button = markup.inline_keyboard[0][0]
    assert button.web_app.url == f"https://app.example.com/shop/{bot_id}"


@pytest.mark.asyncio
async def test_adminshops_menu_without_role(db):
    await make_seller(db, telegram_id=111)
    msg = fake_message(telegram_id=111)
    with patch_settings("shop_admins"):
        await shop_admins.cmd_adminshops(msg)
    assert "ни одного магазина" in msg.answer.call_args.args[0]


# --------------------------------------------------------------------------
# Хаб: приглашение и removal
# --------------------------------------------------------------------------


def waiting_state(bot_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        clear=AsyncMock(),
        get_data=AsyncMock(return_value={"bot_id": bot_id, "asked_at": time()}),
    )


@pytest.mark.asyncio
async def test_add_admin_by_username(db):
    bot_id = await setup_shop(db)
    helper_id = await make_seller_with_username(db, 333, "Helper")

    msg = fake_message(telegram_id=111)
    msg.text = "@HELPER"  # юзернеймы нечувствительны к регистру
    with patch.object(hub_bot, "send_message", new=AsyncMock()) as notify:
        await shop_admins.got_admin_contact(msg, waiting_state(bot_id))

    answer = msg.answer.call_args.args[0]
    assert "✅" in answer and "@Helper" in answer
    async with db() as session:
        row = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot_id, StoreAdmin.seller_id == helper_id
                )
            )
        ).scalar_one_or_none()
        assert row is not None
    # новый админ получил пуш с кнопкой меню
    notify.assert_awaited_once()
    assert notify.await_args.args[0] == 333


@pytest.mark.asyncio
async def test_add_admin_by_telegram_id(db):
    bot_id = await setup_shop(db)
    helper_id = await make_seller(db, telegram_id=333)

    msg = fake_message(telegram_id=111)
    msg.text = "333"
    with patch.object(hub_bot, "send_message", new=AsyncMock()):
        await shop_admins.got_admin_contact(msg, waiting_state(bot_id))
    assert "✅" in msg.answer.call_args.args[0]
    async with db() as session:
        seller = await session.get(Seller, helper_id)
        assert seller.telegram_id == 333
        row = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot_id, StoreAdmin.seller_id == helper_id
                )
            )
        ).scalar_one_or_none()
        assert row is not None


@pytest.mark.asyncio
async def test_add_admin_unknown_candidate(db):
    bot_id = await setup_shop(db)
    msg = fake_message(telegram_id=111)
    msg.text = "@ghost"
    await shop_admins.got_admin_contact(msg, waiting_state(bot_id))
    assert "Никого такого" in msg.answer.call_args.args[0]
    async with db() as session:
        rows = (await session.execute(select(StoreAdmin))).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_add_admin_rejects_owner_and_duplicate(db):
    bot_id = await setup_shop(db)
    async with db() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == SELLER_TG["id"]))
        ).scalar_one()
        seller.username = "seller1"
        await session.commit()

    msg = fake_message(telegram_id=111)
    msg.text = "@seller1"
    await shop_admins.got_admin_contact(msg, waiting_state(bot_id))
    assert "владелец" in msg.answer.call_args.args[0]

    helper_id = await make_seller_with_username(db, 333, "helper")
    await grant_admin(db, bot_id, helper_id)
    msg = fake_message(telegram_id=111)
    msg.text = "@helper"
    await shop_admins.got_admin_contact(msg, waiting_state(bot_id))
    assert "уже администратор" in msg.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_remove_admin_flow(db):
    bot_id = await setup_shop(db)
    helper_id = await make_seller(db, telegram_id=333)
    await grant_admin(db, bot_id, helper_id)

    card_msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    confirm = fake_callback(card_msg, f"mybots:adm_del:{bot_id}:{helper_id}", user_id=111)
    with patch.object(hub_bot, "send_message", new=AsyncMock()):
        await shop_admins.confirm_remove_admin(confirm)
    confirm_text = card_msg.edit_text.call_args.args[0]
    assert "Убрать" in confirm_text

    removal = fake_callback(card_msg, f"mybots:adm_del_yes:{bot_id}:{helper_id}", user_id=111)
    with patch.object(hub_bot, "send_message", new=AsyncMock()) as notify:
        await shop_admins.do_remove_admin(removal)
    removal.answer.assert_awaited_with("Убран")
    # убранному уходит пуш
    notify.assert_awaited_once()
    assert notify.await_args.args[0] == 333
    async with db() as session:
        row = (
            await session.execute(
                select(StoreAdmin).where(
                    StoreAdmin.bot_id == bot_id, StoreAdmin.seller_id == helper_id
                )
            )
        ).scalar_one_or_none()
        assert row is None

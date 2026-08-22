"""Интеграция Telegram-каналов: подключение и уведомления в оба бота продавца,
верификация вступившего («Я не робот»), изоляция каналов по bot_id,
API кабинета и дедуп повторных апдейтов."""

from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram import types
from sqlalchemy import select

from app.bots.dedupe import duplicate_update
from app.bots.hub import hub_bot
from app.handlers.seller import channels as ch
from app.handlers.seller import settings as st
from app.handlers.seller import start as seller_start
from app.models import Channel, Customer, SellerBot
from app.services.channels import deactivate_channel_by_id, list_channels
from tests.test_api import client, seller_headers, setup_shop
from tests.test_bot_connect import make_seller
from tests.test_bot_settings import fake_fsm_state, load_bot
from tests.test_hub_menus import FAKE_SETTINGS, fake_callback, make_bot

_chats = count(-100_900_500_001)


def fake_tg_bot():
    return AsyncMock()


def added_event(chat_id, title="Тестовый канал", can_invite=True):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type="channel", title=title),
        new_chat_member=SimpleNamespace(can_invite_users=can_invite),
    )


def join_event(chat_id, user_id=555):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(
            id=user_id, username="lead", first_name="Лид", language_code="ru"
        ),
    )


def verify_callback(channel_id, user_id=555, message=None):
    return SimpleNamespace(
        answer=AsyncMock(),
        message=message if message is not None else SimpleNamespace(edit_text=AsyncMock()),
        data=f"verify:{channel_id}",
        from_user=SimpleNamespace(
            id=user_id, username="lead", first_name="Лид", language_code="ru"
        ),
    )


async def seed_channel(db, seller_id, bot_id, *, auto_accept=True, greeting_text=None):
    async with db() as session:
        channel = Channel(
            seller_id=seller_id,
            bot_id=bot_id,
            telegram_chat_id=next(_chats),
            title="Мой канал",
            auto_accept=auto_accept,
            greeting_text=greeting_text,
        )
        session.add(channel)
        await session.commit()
        return channel.id, channel.telegram_chat_id


# --------------------------------------------------------------------------
# Подключение канала: уведомления в hub-бот И в собственный бот продавца
# --------------------------------------------------------------------------


async def test_added_to_chat_notifies_both_bots(db):
    seller_id = await make_seller(db)  # telegram_id=111
    bot_id = await make_bot(db, seller_id, username="chan_bot")
    bot_record = await load_bot(db, bot_id)

    seller_tg = fake_tg_bot()
    with patch.object(hub_bot, "send_message", new=AsyncMock()) as hub_send:
        await ch.on_bot_added_to_chat(added_event(-100111), seller_tg, bot_record)

    hub_send.assert_awaited_once()
    assert "добавлен в «Тестовый канал»" in hub_send.await_args.args[1]
    seller_tg.send_message.assert_awaited_once()
    own_text = seller_tg.send_message.await_args.args[1]
    assert "подключён к магазину @chan_bot" in own_text

    assert len(await list_channels(bot_id)) == 1


async def test_missing_invite_right_warns_seller(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="no_right_bot")
    bot_record = await load_bot(db, bot_id)

    seller_tg = fake_tg_bot()
    with patch.object(hub_bot, "send_message", new=AsyncMock()):
        await ch.on_bot_added_to_chat(
            added_event(-100222, can_invite=False), seller_tg, bot_record
        )

    own_text = seller_tg.send_message.await_args.args[1]
    assert "Приглашать пользователей" in own_text  # подсказка, что право не отмечено


async def test_reconnect_same_channel_notifies_once(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="once_bot")
    bot_record = await load_bot(db, bot_id)

    seller_tg = fake_tg_bot()
    with patch.object(hub_bot, "send_message", new=AsyncMock()):
        await ch.on_bot_added_to_chat(added_event(-100333), seller_tg, bot_record)
        await ch.on_bot_added_to_chat(added_event(-100333), seller_tg, bot_record)

    seller_tg.send_message.assert_awaited_once()  # второй my_chat_member — без спама


# --------------------------------------------------------------------------
# Заявка на вступление: одобрение + reply-кнопка «Я не робот 🤖» вместо inline
# --------------------------------------------------------------------------


async def test_join_request_sends_reply_keyboard_not_inline(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="funnel_bot")
    _channel_id, chat_id = await seed_channel(db, seller_id, bot_id)
    bot_record = await load_bot(db, bot_id)

    tg = fake_tg_bot()
    await ch.on_join_request(join_event(chat_id), tg, bot_record)

    tg.approve_chat_join_request.assert_awaited_once_with(chat_id=chat_id, user_id=555)
    kb = tg.send_message.await_args.kwargs["reply_markup"]
    assert isinstance(kb, types.ReplyKeyboardMarkup)
    btn = kb.keyboard[0][0]
    assert isinstance(btn, types.KeyboardButton)
    assert not isinstance(btn, types.InlineKeyboardButton)
    assert btn.text == "Я не робот 🤖"

    # лид уже сохранён в базу этого магазина с источником-каналом
    async with db() as session:
        customer = (
            (await session.execute(select(Customer).where(Customer.bot_id == bot_id)))
            .scalars()
            .one()
        )
    assert customer.telegram_id == 555
    assert customer.source == f"channel:{chat_id}"


def test_robot_text_matcher():
    """Нажатие reply-кнопки присылает текст кнопки; принимаем оба варианта."""
    assert seller_start.is_robot_confirm("Я не робот")
    assert seller_start.is_robot_confirm("Я не робот 🤖")
    assert seller_start.is_robot_confirm("  Я не робот  ")
    assert not seller_start.is_robot_confirm("не робот")
    assert not seller_start.is_robot_confirm("/start")
    assert not seller_start.is_robot_confirm(None)


async def test_robot_confirm_answers_like_start(db):
    """«Я не робот» отвечает тем же приветствием из настроек, что и /start."""
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="verify_bot")
    await st._update_bot(
        bot_id, welcome_text="<b>Привет!</b>", catalog_button_text="🛒 В магазин"
    )

    msg = SimpleNamespace(answer=AsyncMock(), text="Я не робот")
    with patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS):
        await seller_start.robot_confirm(msg, await load_bot(db, bot_id))

    assert msg.answer.await_args.args[0] == "<b>Привет!</b>"
    kb = msg.answer.await_args.kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].text == "🛒 В магазин"


async def test_robot_confirm_isolated_per_bot(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="bot_a")
    bot_b = await make_bot(db, seller_id, username="bot_b")
    await st._update_bot(bot_a, welcome_text="Магазин А")

    with patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS):
        msg = SimpleNamespace(answer=AsyncMock(), text="Я не робот 🤖")
        await seller_start.robot_confirm(msg, await load_bot(db, bot_a))
        assert msg.answer.await_args.args[0] == "Магазин А"

        msg = SimpleNamespace(answer=AsyncMock(), text="Я не робот 🤖")
        await seller_start.robot_confirm(msg, await load_bot(db, bot_b))
        assert msg.answer.await_args.args[0] == "Добро пожаловать в магазин <b>@bot_b</b>!"


async def test_join_request_without_auto_accept_stays_pending(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="manual_bot")
    _, chat_id = await seed_channel(db, seller_id, bot_id, auto_accept=False)
    bot_record = await load_bot(db, bot_id)

    tg = fake_tg_bot()
    await ch.on_join_request(join_event(chat_id), tg, bot_record)

    tg.approve_chat_join_request.assert_not_awaited()
    tg.send_message.assert_not_awaited()


async def test_join_request_for_other_bots_channel_ignored(db):
    """Заявка в чужой канал приходит на вебхук другого бота — не его забота."""
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="bot_a")
    bot_b = await make_bot(db, seller_id, username="bot_b")
    _, chat_id = await seed_channel(db, seller_id, bot_a)
    record_b = await load_bot(db, bot_b)

    tg = fake_tg_bot()
    await ch.on_join_request(join_event(chat_id), tg, record_b)

    tg.approve_chat_join_request.assert_not_awaited()
    tg.send_message.assert_not_awaited()
    async with db() as session:
        customers = (
            (await session.execute(select(Customer).where(Customer.bot_id == bot_b)))
            .scalars()
            .all()
        )
    assert customers == []


# --------------------------------------------------------------------------
# Отключение канала продавцом через /settings
# --------------------------------------------------------------------------


async def test_settings_remove_channel_flow(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="drop_bot")
    channel_id, _ = await seed_channel(db, seller_id, bot_id)
    bot_record = await load_bot(db, bot_id)

    msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())

    await st.confirm_remove_channel(
        fake_callback(msg, f"set:ch_del:{channel_id}"), fake_fsm_state(), bot_record
    )
    assert "Отключить канал" in msg.edit_text.await_args.args[0]  # подтверждение

    await st.do_remove_channel(
        fake_callback(msg, f"set:ch_del_yes:{channel_id}"), fake_fsm_state(), bot_record
    )
    assert await st._bot_channels(bot_id) == []  # исчез из списка активных

    # запись осталась (история), но неактивная
    async with db() as session:
        channel = await session.get(Channel, channel_id)
        assert channel.is_active is False


async def test_service_remove_isolated_between_bots(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="bot_a")
    bot_b = await make_bot(db, seller_id, username="bot_b")
    channel_id, _ = await seed_channel(db, seller_id, bot_a)

    assert await deactivate_channel_by_id(bot_b, channel_id) is False
    async with db() as session:
        channel = await session.get(Channel, channel_id)
        assert channel.is_active is True

    assert await deactivate_channel_by_id(bot_a, channel_id) is True


# --------------------------------------------------------------------------
# API кабинета: список и отключение каналов
# --------------------------------------------------------------------------


async def test_channels_api_list_and_remove(db):
    bot_id = await setup_shop(db)
    async with db() as session:
        shop = await session.get(SellerBot, bot_id)
        seller_id = shop.seller_id
    _, _chat = await seed_channel(db, seller_id, bot_id)

    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/channels", headers=seller_headers())
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["title"] == "Мой канал"
        assert body[0]["auto_accept"] is True
        channel_id = body[0]["id"]

        r = await c.delete(
            f"/api/seller/bots/{bot_id}/channels/{channel_id}", headers=seller_headers()
        )
        assert r.status_code == 200
        assert r.json() == {"status": "removed"}

        r = await c.get(f"/api/seller/bots/{bot_id}/channels", headers=seller_headers())
        # отключённый канал остаётся в списке — но с пометкой is_active=False
        assert len(r.json()) == 1
        assert r.json()[0]["is_active"] is False

        # повторное отключение своего же канала идемпотентно (двойной тап без ошибок)
        r = await c.delete(
            f"/api/seller/bots/{bot_id}/channels/{channel_id}", headers=seller_headers()
        )
        assert r.status_code == 200


async def test_channels_api_stranger_gets_404(db):
    import os

    from tests.test_api import init_data_for

    bot_id = await setup_shop(db)
    await make_seller(db, telegram_id=222)  # зарегистрированный чужой продавец
    stranger_headers = {
        "X-Init-Data": init_data_for({"id": 222}, os.environ["HUB_BOT_TOKEN"])
    }
    async with client() as c:
        r = await c.get(f"/api/seller/bots/{bot_id}/channels", headers=stranger_headers)
        assert r.status_code == 404
        r = await c.delete(f"/api/seller/bots/{bot_id}/channels/1", headers=stranger_headers)
        assert r.status_code == 404


# --------------------------------------------------------------------------
# Дедуп повторных апдейтов Telegram
# --------------------------------------------------------------------------


def test_duplicate_updates_are_dropped():
    assert duplicate_update("seller:900001", 100) is False
    assert duplicate_update("seller:900001", 100) is True  # ретрай того же апдейта
    assert duplicate_update("seller:900002", 100) is False  # другой магазин — свой скоуп
    assert duplicate_update("seller:900001", 101) is False
    assert duplicate_update("seller:900001", None) is False

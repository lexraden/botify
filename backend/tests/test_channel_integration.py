"""Интеграция Telegram-каналов: подключение и уведомления в оба бота продавца,
капча для заявок в канал («Я не робот» или свой текст), изоляция каналов по bot_id,
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


def join_event(chat_id, user_id=555, language_code="ru"):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id),
        from_user=SimpleNamespace(
            id=user_id, username="lead", first_name="Лид", language_code=language_code
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
# Заявка на вступление: капча reply-кнопкой, одобрение — только после нажатия
# --------------------------------------------------------------------------


async def test_join_request_waits_for_captcha(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="funnel_bot")
    _channel_id, chat_id = await seed_channel(db, seller_id, bot_id)
    bot_record = await load_bot(db, bot_id)

    tg = fake_tg_bot()
    await ch.on_join_request(join_event(chat_id), tg, bot_record)

    # заявка не одобрена, пока человек не нажал кнопку
    tg.approve_chat_join_request.assert_not_awaited()
    kb = tg.send_message.await_args.kwargs["reply_markup"]
    assert isinstance(kb, types.ReplyKeyboardMarkup)
    btn = kb.keyboard[0][0]
    assert isinstance(btn, types.KeyboardButton)
    assert not isinstance(btn, types.InlineKeyboardButton)
    assert btn.text == "Я не робот 🤖"
    assert "Чтобы вступить в «Мой канал»" in tg.send_message.await_args.args[1]

    # лид уже сохранён в базу этого магазина с источником-каналом
    async with db() as session:
        customer = (
            (await session.execute(select(Customer).where(Customer.bot_id == bot_id)))
            .scalars()
            .one()
        )
    assert customer.telegram_id == 555
    assert customer.source == f"channel:{chat_id}"


async def test_join_request_texts_follow_buyer_language(db):
    """Иностранец получает английскую кнопку и английское сообщение."""
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="en_funnel_bot")
    _channel_id, chat_id = await seed_channel(db, seller_id, bot_id)
    bot_record = await load_bot(db, bot_id)

    tg = fake_tg_bot()
    await ch.on_join_request(join_event(chat_id, language_code="en"), tg, bot_record)

    kb = tg.send_message.await_args.kwargs["reply_markup"]
    assert kb.keyboard[0][0].text == "I'm not a robot 🤖"
    message = tg.send_message.await_args.args[1]
    assert "To join “Мой канал”" in message
    assert "I'm not a robot 🤖" in message


async def test_join_request_uses_seller_texts_and_user_chat_id(db):
    """Свой текст кнопки и сообщения продавца; пишем в user_chat_id —
    так Telegram пускает в ЛС того, кто бота ещё не стартовал."""
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="custom_captcha_bot")
    channel_id, chat_id = await seed_channel(
        db, seller_id, bot_id, greeting_text="Жми кнопку и заходи!"
    )
    await st._update_channel(bot_id, channel_id, captcha_button="Хочу в канал 🔥")
    bot_record = await load_bot(db, bot_id)

    event = join_event(chat_id, language_code="en")
    event.user_chat_id = 9_555
    tg = fake_tg_bot()
    await ch.on_join_request(event, tg, bot_record)

    assert tg.send_message.await_args.args[0] == 9_555
    assert tg.send_message.await_args.args[1] == "Жми кнопку и заходи!"
    kb = tg.send_message.await_args.kwargs["reply_markup"]
    assert kb.keyboard[0][0].text == "Хочу в канал 🔥"
    tg.approve_chat_join_request.assert_not_awaited()


async def test_join_request_approved_when_dm_impossible(db):
    """Показать кнопку некуда — пускаем без капчи, а не держим вечно в заявках."""
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="no_dm_bot")
    _, chat_id = await seed_channel(db, seller_id, bot_id)
    bot_record = await load_bot(db, bot_id)

    tg = fake_tg_bot()
    tg.send_message.side_effect = RuntimeError("Forbidden: bot can't initiate conversation")
    await ch.on_join_request(join_event(chat_id), tg, bot_record)

    tg.approve_chat_join_request.assert_awaited_once_with(chat_id=chat_id, user_id=555)


def test_robot_text_matcher():
    """Нажатие reply-кнопки присылает текст кнопки; принимаем оба варианта."""
    assert seller_start.is_robot_confirm("Я не робот")
    assert seller_start.is_robot_confirm("Я не робот 🤖")
    assert seller_start.is_robot_confirm("  Я не робот  ")
    assert not seller_start.is_robot_confirm("не робот")
    assert not seller_start.is_robot_confirm("/start")
    assert not seller_start.is_robot_confirm(None)


def press(text, user_id=555, chat_type="private"):
    return SimpleNamespace(
        answer=AsyncMock(),
        text=text,
        chat=SimpleNamespace(type=chat_type),
        from_user=SimpleNamespace(id=user_id),
    )


async def test_custom_captcha_button_is_recognised_only_in_its_bot(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="press_a")
    bot_b = await make_bot(db, seller_id, username="press_b")
    channel_id, _ = await seed_channel(db, seller_id, bot_a)
    await st._update_channel(bot_a, channel_id, captcha_button="Хочу в канал 🔥")
    record_a = await load_bot(db, bot_a)
    record_b = await load_bot(db, bot_b)

    assert await seller_start.is_captcha_press(press("Хочу в канал 🔥"), record_a)
    assert await seller_start.is_captcha_press(press(" Хочу в канал 🔥 "), record_a)
    assert not await seller_start.is_captcha_press(press("Хочу в канал 🔥"), record_b)
    assert not await seller_start.is_captcha_press(press("привет"), record_a)
    # дефолтная кнопка (в т.ч. уже разосланная раньше) работает в любом боте
    assert await seller_start.is_captcha_press(press("Я не робот 🤖"), record_b)
    assert not await seller_start.is_captcha_press(
        press("Я не робот 🤖", chat_type="group"), record_b
    )


async def test_captcha_press_approves_pending_requests(db):
    """Нажатие одобряет заявки в каналы ЭТОГО бота с включённым приёмом;
    где заявки нет, Telegram отвечает ошибкой — её пропускаем."""
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="approve_bot")
    other_bot = await make_bot(db, seller_id, username="approve_other")
    _, chat_main = await seed_channel(db, seller_id, bot_id)
    _, chat_empty = await seed_channel(db, seller_id, bot_id)
    _, chat_manual = await seed_channel(db, seller_id, bot_id, auto_accept=False)
    _, chat_foreign = await seed_channel(db, seller_id, other_bot)

    tg = fake_tg_bot()

    async def approve(chat_id, user_id):
        if chat_id == chat_empty:
            raise RuntimeError("HIDE_REQUESTER_MISSING")

    tg.approve_chat_join_request.side_effect = approve
    msg = press("Я не робот 🤖")
    with patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS):
        await seller_start.robot_confirm(msg, tg, await load_bot(db, bot_id))

    tried = {c.kwargs["chat_id"] for c in tg.approve_chat_join_request.await_args_list}
    assert tried == {chat_main, chat_empty}
    assert chat_manual not in tried and chat_foreign not in tried
    confirm = msg.answer.await_args_list[0]
    # язык неизвестен (customer=None) — дефолт платформы EN
    assert confirm.args[0] == "✅ Done — you're in “Мой канал”"
    assert isinstance(confirm.kwargs["reply_markup"], types.ReplyKeyboardRemove)


async def test_robot_confirm_answers_like_start(db):
    """Нажатие без висящих заявок отвечает тем же приветствием, что и /start."""
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="verify_bot")
    await st._update_bot(
        bot_id, welcome_text="<b>Привет!</b>", catalog_button_text="🛒 В магазин"
    )

    msg = press("Я не робот")
    with patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS):
        await seller_start.robot_confirm(msg, fake_tg_bot(), await load_bot(db, bot_id))

    # первым сообщением убирается reply-клавиатура капчи…
    first = msg.answer.await_args_list[0]
    assert first.args[0] == "✅ Verification passed"
    assert isinstance(first.kwargs["reply_markup"], types.ReplyKeyboardRemove)
    # …затем то же приветствие, что и на /start
    assert msg.answer.await_args_list[1].args[0] == "<b>Привет!</b>"
    kb = msg.answer.await_args_list[1].kwargs["reply_markup"]
    assert kb.inline_keyboard[0][0].text == "🛒 В магазин"


async def test_robot_confirm_isolated_per_bot(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="bot_a")
    bot_b = await make_bot(db, seller_id, username="bot_b")
    await st._update_bot(bot_a, welcome_text="Магазин А")

    with patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS):
        msg = press("Я не робот 🤖")
        await seller_start.robot_confirm(msg, fake_tg_bot(), await load_bot(db, bot_a))
        assert msg.answer.await_args.args[0] == "Магазин А"

        msg = press("Я не робот 🤖")
        await seller_start.robot_confirm(msg, fake_tg_bot(), await load_bot(db, bot_b))
        # язык неизвестен (customer=None) — дефолт платформы EN
        assert msg.answer.await_args.args[0] == "Welcome to the <b>@bot_b</b> shop!"


# --------------------------------------------------------------------------
# Текст кнопки капчи в /settings
# --------------------------------------------------------------------------


async def _saved_button(db, channel_id):
    async with db() as session:
        return (await session.get(Channel, channel_id)).captcha_button


async def test_settings_save_captcha_button(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="btn_bot")
    channel_id, _ = await seed_channel(db, seller_id, bot_id)
    bot_record = await load_bot(db, bot_id)

    msg = SimpleNamespace(answer=AsyncMock(), text="  Хочу в канал 🔥 ")
    await st.save_captcha_button(msg, fake_fsm_state({"channel_id": channel_id}), bot_record)
    assert await _saved_button(db, channel_id) == "Хочу в канал 🔥"
    # карточка канала показывает новую кнопку
    assert "Хочу в канал 🔥" in msg.answer.await_args_list[-1].args[0]

    msg = SimpleNamespace(answer=AsyncMock(), text="/reset")
    await st.save_captcha_button(msg, fake_fsm_state({"channel_id": channel_id}), bot_record)
    assert await _saved_button(db, channel_id) is None


async def test_settings_captcha_button_rejects_bad_text(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="bad_btn_bot")
    channel_id, _ = await seed_channel(db, seller_id, bot_id)
    await st._update_channel(bot_id, channel_id, captcha_button="Было")
    bot_record = await load_bot(db, bot_id)

    for text in ("x" * 65, "/settings"):
        state = fake_fsm_state({"channel_id": channel_id})
        msg = SimpleNamespace(answer=AsyncMock(), text=text)
        await st.save_captcha_button(msg, state, bot_record)
        state.clear.assert_not_awaited()  # ждём исправленный текст
        assert await _saved_button(db, channel_id) == "Было"


async def test_settings_captcha_button_of_other_bot_untouched(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="own_btn_a")
    bot_b = await make_bot(db, seller_id, username="own_btn_b")
    channel_id, _ = await seed_channel(db, seller_id, bot_a)

    msg = SimpleNamespace(answer=AsyncMock(), text="Чужая кнопка")
    with patch.object(st, "show_settings_menu", new=AsyncMock()):
        await st.save_captcha_button(
            msg, fake_fsm_state({"channel_id": channel_id}), await load_bot(db, bot_b)
        )
    assert await _saved_button(db, channel_id) is None


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

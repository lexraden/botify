"""Seller-бот: /settings — приветствие, кнопка каталога, каналы.

Ключевое требование — изоляция по bot_id: настройки и каналы одного бота
недоступны из контекста другого, даже у одного продавца.
"""

from itertools import count
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.handlers.hub import mybots
from app.handlers.seller import settings as st
from app.handlers.seller import start as seller_start
from app.models import Channel, SellerBot
from tests.test_bot_connect import make_seller
from tests.test_hub_menus import FAKE_SETTINGS, fake_callback, fake_message, make_bot, button_texts

_chat_ids = count(-100_900_000_001)


def patch_start_settings():
    return patch("app.handlers.seller.start.get_settings", return_value=FAKE_SETTINGS)


def fake_fsm_state(data=None):
    return SimpleNamespace(
        clear=AsyncMock(),
        set_state=AsyncMock(),
        get_data=AsyncMock(return_value=data or {}),
        update_data=AsyncMock(),
    )


async def load_bot(db, bot_id) -> SellerBot:
    async with db() as session:
        return await session.get(SellerBot, bot_id)


async def make_channel(db, seller_id, bot_id, *, auto_accept=True) -> int:
    async with db() as session:
        channel = Channel(
            seller_id=seller_id,
            bot_id=bot_id,
            telegram_chat_id=next(_chat_ids),
            title="Мой канал",
            auto_accept=auto_accept,
        )
        session.add(channel)
        await session.commit()
        return channel.id


# --------------------------------------------------------------------------
# /start: кастомное приветствие и кнопка витрины
# --------------------------------------------------------------------------


async def test_custom_welcome_and_button_text(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="styled_shop")
    await st._update_bot(
        bot_id, welcome_text="<b>Привет!</b>", catalog_button_text="🛒 В магазин"
    )

    msg = fake_message()
    with patch_start_settings():
        await seller_start.cmd_start(
            msg, SimpleNamespace(args=None), await load_bot(db, bot_id)
        )

    assert msg.answer.call_args.args[0] == "<b>Привет!</b>"
    btn = msg.answer.call_args.kwargs["reply_markup"].inline_keyboard[0][0]
    assert btn.text == "🛒 В магазин"
    assert f"bot_id={bot_id}" in btn.web_app.url


async def test_catalog_button_can_be_hidden(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="quiet_shop")
    await st._update_bot(bot_id, show_catalog_button=False)

    msg = fake_message()
    with patch_start_settings():
        await seller_start.cmd_start(
            msg, SimpleNamespace(args=None), await load_bot(db, bot_id)
        )

    assert msg.answer.call_args.kwargs["reply_markup"] is None


# --------------------------------------------------------------------------
# Диплинк t.me/<bot>?start=settings и гард владельца
# --------------------------------------------------------------------------


async def test_deeplink_settings_opens_menu_for_owner(db):
    seller_id = await make_seller(db)  # telegram_id=111, как у fake_message
    bot_id = await make_bot(db, seller_id, username="own_shop")

    msg = fake_message()
    with patch_start_settings():
        await seller_start.cmd_start(
            msg, SimpleNamespace(args="settings"), await load_bot(db, bot_id)
        )

    text = msg.answer.call_args.args[0]
    assert "Настройки бота @own_shop" in text
    texts = button_texts(msg.answer.call_args.kwargs["reply_markup"])
    assert "✍️ Приветствие" in texts
    assert "📢 Каналы (0)" in texts


async def test_deeplink_settings_is_private_for_stranger(db):
    seller_id = await make_seller(db, telegram_id=999)
    bot_id = await make_bot(db, seller_id, username="strange_shop")

    msg = fake_message()  # from_user.id = 111 — не владелец
    with patch_start_settings():
        await seller_start.cmd_start(
            msg, SimpleNamespace(args="settings"), await load_bot(db, bot_id)
        )

    # чужаку — обычное приветствие покупателя, меню не раскрывается
    assert "Добро пожаловать в магазин" in msg.answer.call_args.args[0]


async def test_settings_callbacks_gated_by_owner(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="gate_shop")
    bot = await load_bot(db, bot_id)

    msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    callback = fake_callback(msg, "set:welcome", user_id=222)
    await st.ask_welcome(callback, fake_fsm_state(), bot)

    callback.answer.assert_awaited_once_with(st.OWNER_ONLY, show_alert=True)
    msg.edit_text.assert_not_awaited()


# --------------------------------------------------------------------------
# Кнопка каталога: переключение и сохранение текста
# --------------------------------------------------------------------------


async def _button_flag(db, bot_id) -> bool:
    async with db() as session:
        bot = await session.get(SellerBot, bot_id)
        return bot.show_catalog_button


async def test_catalog_button_toggle_roundtrip(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="toggle_shop")

    msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    state = fake_fsm_state()
    await st.toggle_catalog_button(
        fake_callback(msg, "set:btn_toggle"), state, await load_bot(db, bot_id)
    )
    assert await _button_flag(db, bot_id) is False

    await st.toggle_catalog_button(
        fake_callback(msg, "set:btn_toggle"), state, await load_bot(db, bot_id)
    )
    assert await _button_flag(db, bot_id) is True

    # меню перерисовано после каждого переключения с актуальным состоянием
    assert "выключена" in msg.edit_text.await_args_list[0].args[0]
    assert "включена" in msg.edit_text.await_args_list[-1].args[0]


async def test_save_welcome_persists(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="text_shop")

    msg = SimpleNamespace(answer=AsyncMock(), text="Новое приветствие")
    await st.save_welcome(msg, fake_fsm_state(), await load_bot(db, bot_id))

    async with db() as session:
        saved = await session.get(SellerBot, bot_id)
        assert saved.welcome_text == "Новое приветствие"
    # первый ответ — подтверждение, вторым приходит обновлённое меню
    answers = [call.args[0] for call in msg.answer.await_args_list]
    assert any("✅ Приветствие сохранено" in a for a in answers)


async def test_save_welcome_cancel_keeps_old(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="keep_shop")
    await st._update_bot(bot_id, welcome_text="Старое")

    msg = SimpleNamespace(answer=AsyncMock(), text="/cancel")
    await st.save_welcome(msg, fake_fsm_state(), await load_bot(db, bot_id))

    async with db() as session:
        saved = await session.get(SellerBot, bot_id)
        assert saved.welcome_text == "Старое"


# --------------------------------------------------------------------------
# Каналы: изоляция по bot_id и переключение авто-приёма
# --------------------------------------------------------------------------


async def test_channel_settings_isolated_between_bots(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="bot_a")
    bot_b = await make_bot(db, seller_id, username="bot_b")
    channel_id = await make_channel(db, seller_id, bot_a)

    # у второго бота того же продавца каналов не видно
    assert await st._bot_channels(bot_b) == []

    # чужой канал через контекст другого бота изменить нельзя
    assert await st._update_channel(bot_b, channel_id, auto_accept=False) is None

    async with db() as session:
        channel = await session.get(Channel, channel_id)
        assert channel.auto_accept is True  # не тронут


async def test_channel_submenu_rejects_foreign_channel(db):
    seller_id = await make_seller(db)
    bot_a = await make_bot(db, seller_id, username="bot_a")
    bot_b = await make_bot(db, seller_id, username="bot_b")
    channel_id = await make_channel(db, seller_id, bot_a)

    msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    callback = fake_callback(msg, f"set:ch:{channel_id}")
    await st.channel_menu(callback, fake_fsm_state(), await load_bot(db, bot_b))

    callback.answer.assert_awaited_once_with("Канал не найден", show_alert=True)
    msg.edit_text.assert_not_awaited()


async def test_auto_accept_toggle_via_menu(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="chan_shop")
    channel_id = await make_channel(db, seller_id, bot_id, auto_accept=True)

    msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    await st.toggle_auto_accept(
        fake_callback(msg, f"set:ch_auto:{channel_id}"),
        fake_fsm_state(),
        await load_bot(db, bot_id),
    )

    async with db() as session:
        channel = await session.get(Channel, channel_id)
        assert channel.auto_accept is False
    assert "выключен" in msg.edit_text.await_args.args[0]


async def test_save_channel_greeting(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="greet_shop")
    channel_id = await make_channel(db, seller_id, bot_id)

    msg = SimpleNamespace(answer=AsyncMock(), text="Добро пожаловать, друг!")
    await st.save_greeting(
        msg,
        fake_fsm_state({"channel_id": channel_id}),
        await load_bot(db, bot_id),
    )

    async with db() as session:
        channel = await session.get(Channel, channel_id)
        assert channel.greeting_text == "Добро пожаловать, друг!"


# --------------------------------------------------------------------------
# Хаб-бот: карточка магазина ведёт в настройки самого бота
# --------------------------------------------------------------------------


def test_card_keyboard_links_to_bot_settings():
    # настоящая модель, а не SimpleNamespace: клавиатура читает всё больше
    # полей (is_draft, is_managed, webhook_status), и стаб их молча не имел
    bot = SellerBot(
        id=7,
        bot_username="deep_shop",
        bot_token_encrypted=b"x",  # не черновик
        is_active=True,
        webhook_status="active",
        is_managed=False,
    )
    kb = mybots.bot_card_keyboard(bot)
    assert "⚙️ Настройки бота" in button_texts(kb)
    url_buttons = [btn for row in kb.inline_keyboard for btn in row if btn.url]
    assert any(b.url == "https://t.me/deep_shop?start=settings" for b in url_buttons)

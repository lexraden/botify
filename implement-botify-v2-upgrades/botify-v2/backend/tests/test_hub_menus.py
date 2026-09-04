"""Хаб-бот: меню «Мои магазины», карточка магазина и ветвление /start."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.handlers.hub import mybots, start
from app.models import SellerBot
from tests.test_bot_connect import make_seller

FAKE_SETTINGS = SimpleNamespace(
    effective_webapp_url="https://app.example.com",
    admin_ids=set(),
)


def patch_settings(module: str):
    return patch(f"app.handlers.hub.{module}.get_settings", return_value=FAKE_SETTINGS)


def fake_message(telegram_id=111):
    return SimpleNamespace(
        answer=AsyncMock(),
        from_user=SimpleNamespace(
            id=telegram_id, username="alex", first_name="Alex", language_code="ru"
        ),
    )


def fake_state():
    return SimpleNamespace(clear=AsyncMock())


def fake_callback(message, data, user_id=111):
    return SimpleNamespace(
        answer=AsyncMock(), message=message, data=data, from_user=SimpleNamespace(id=user_id)
    )


_bot_ids = iter(range(10_000_000, 10_001_000))


async def make_bot(
    db,
    seller_id,
    *,
    username="shop_one",
    is_active=True,
    webhook_status="active",
) -> int:
    async with db() as session:
        bot = SellerBot(
            seller_id=seller_id,
            bot_token_encrypted=b"encrypted",
            bot_username=username,
            telegram_bot_id=next(_bot_ids),
            webhook_status=webhook_status,
            is_active=is_active,
        )
        session.add(bot)
        await session.commit()
        return bot.id


def button_texts(markup) -> list[str]:
    return [btn.text for row in markup.inline_keyboard for btn in row]


async def test_shops_menu_is_one_message(db):
    seller_id = await make_seller(db)
    await make_bot(db, seller_id, username="one_shop")
    await make_bot(db, seller_id, username="two_shop", is_active=False)

    msg = fake_message()
    with patch_settings("mybots"):
        await mybots.send_shops_menu(msg, SimpleNamespace(id=seller_id))

    assert msg.answer.await_count == 1
    text = msg.answer.call_args.args[0]
    assert "@one_shop" in text and "включён" in text
    assert "@two_shop" in text and "отключён" in text
    assert "свой каталог" in text  # питч про изолированность магазинов на месте
    texts = button_texts(msg.answer.call_args.kwargs["reply_markup"])
    assert texts == ["@one_shop", "@two_shop", "➕ Подключить ещё магазин"]


async def test_start_single_disabled_shop_opens_shops_menu(db):
    seller_id = await make_seller(db)
    await make_bot(db, seller_id, username="lonely_shop", is_active=False)

    msg = fake_message()
    with patch_settings("start"), patch_settings("mybots"):
        await start.cmd_start(msg, fake_state())

    msg.answer.assert_awaited_once()
    text = msg.answer.call_args.args[0]
    assert "@lonely_shop" in text and "отключён" in text
    texts = button_texts(msg.answer.call_args.kwargs["reply_markup"])
    # сразу окно «Мои магазины»: магазин кнопкой и добавление нового —
    # без «Открыть приложение», витрина всё равно выключена
    assert texts == ["@lonely_shop", "➕ Подключить ещё магазин"]


async def test_start_active_shop_shows_welcome_and_myshops_button(db):
    seller_id = await make_seller(db)
    await make_bot(db, seller_id, username="live_shop")

    msg = fake_message()
    with patch_settings("start"):
        await start.cmd_start(msg, fake_state())

    text = msg.answer.call_args.args[0]
    assert "С возвращением" in text and "@live_shop</b> работает" in text
    texts = button_texts(msg.answer.call_args.kwargs["reply_markup"])
    assert texts == ["🚀 Открыть приложение", "🏪 Мои магазины"]


async def test_start_mixed_shops_keeps_welcome(db):
    """Есть хоть один включённый магазин — обычный приветственный экран."""
    seller_id = await make_seller(db)
    await make_bot(db, seller_id, username="live_shop")
    await make_bot(db, seller_id, username="sleepy_shop", is_active=False)

    msg = fake_message()
    with patch_settings("start"):
        await start.cmd_start(msg, fake_state())

    assert "С возвращением" in msg.answer.call_args.args[0]


async def test_card_open_and_back_navigation(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="nav_shop", is_active=False)

    card_msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    callback = fake_callback(card_msg, f"mybots:card:{bot_id}")
    await mybots.open_bot_card(callback)

    callback.answer.assert_awaited_once()
    card_msg.edit_text.assert_awaited_once()
    text = card_msg.edit_text.call_args.args[0]
    assert "@nav_shop" in text and "отключён" in text
    texts = button_texts(card_msg.edit_text.call_args.kwargs["reply_markup"])
    assert "🔁 Включить" in texts and "⬅️ Все магазины" in texts

    back = fake_callback(card_msg, "mybots:menu")
    await mybots.back_to_shops_menu(back)
    list_text = card_msg.edit_text.await_args_list[1].args[0]
    assert "Твои магазины" in list_text


async def test_delete_last_shop_leads_to_empty_state(db):
    seller_id = await make_seller(db)
    bot_id = await make_bot(db, seller_id, username="gone_shop", is_active=False)

    card_msg = SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock())
    callback = fake_callback(card_msg, f"mybots:del_yes:{bot_id}")
    with patch("app.services.bot_connect.remove_seller_webhook", new=AsyncMock()):
        await mybots.do_delete(callback)

    callback.answer.assert_awaited_with("Удалён")
    final = card_msg.edit_text.await_args_list[-1].args[0]
    assert "нет подключённых магазинов" in final

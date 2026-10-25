"""Онбординг без BotFather: название магазина → кнопка → бот создан.

Живое поведение Telegram отсюда не проверить — из среды разработки он
недоступен. Что проверяется здесь: что мы правильно собираем кнопку, правильно
разбираем ответ и что черновик магазина не ломает уже существующий код.
"""

from time import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import Seller, SellerBot
from app.security import decrypt_bot_token, encrypt_bot_token
from app.services.shop_draft import (
    DraftPromotionError,
    create_draft,
    latest_draft,
    promote_draft,
)

NEW_TOKEN = "7891234567:AAHmanaged-bot-token-for-tests-aaaa"


@pytest.fixture(autouse=True)
def _no_creator_welcome():
    """bot_created шлёт приветствие от нового бота в фоне — в тестах это
    был бы настоящий запрос в Telegram. Само приветствие проверено в
    tests/test_shop_dashboard_button.py."""
    with patch(
        "app.handlers.hub.newshop.welcome_creator_from_bot", new=AsyncMock()
    ) as welcome:
        yield welcome


async def _seller(db, telegram_id: int = 4242, *, terms: bool = False) -> Seller:
    from datetime import datetime, timezone

    async with db() as session:
        seller = Seller(
            telegram_id=telegram_id,
            terms_accepted_at=datetime.now(timezone.utc) if terms else None,
        )
        session.add(seller)
        await session.commit()
        await session.refresh(seller)
        return seller


# --------------------------------------------------------------------------
# Черновик магазина
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_shop_exists_before_any_bot(db):
    """Смысл всей затеи: магазин заводится раньше бота."""
    seller = await _seller(db)
    shop = await create_draft(seller.id, "Кофейня у дома")

    assert shop.id is not None  # bot_id есть сразу — товары уже можно заводить
    assert shop.is_draft is True
    assert shop.bot_token_encrypted is None
    assert shop.is_active is False  # покупателям черновик не показываем
    assert shop.title == "Кофейня у дома"


@pytest.mark.asyncio
async def test_draft_is_invisible_to_buyers(db):
    """Витрина черновика не открывается: покупать там нечего."""
    from tests.test_api import buyer_headers, client

    seller = await _seller(db)
    shop = await create_draft(seller.id, "Кофейня у дома")

    async with client() as c:
        r = await c.get(f"/api/store/{shop.id}", headers=buyer_headers())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_promote_fills_the_draft_and_opens_the_shop(db):
    """Пришёл токен — черновик становится настоящим магазином."""
    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня у дома")

    shop = await promote_draft(draft.id, NEW_TOKEN, "kofeynya_u_doma_bot", 7891234567)

    assert shop.id == draft.id  # тот же bot_id: товары никуда не переезжают
    assert shop.is_draft is False
    assert shop.is_active is True
    assert shop.bot_username == "kofeynya_u_doma_bot"
    assert shop.telegram_bot_id == 7891234567
    # токен хранится так же, как при ручном подключении
    assert decrypt_bot_token(shop.bot_token_encrypted) == NEW_TOKEN


@pytest.mark.asyncio
async def test_promote_refuses_shop_that_already_has_a_bot(db):
    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")
    await promote_draft(draft.id, NEW_TOKEN, "kofeynya_bot", 7891234567)

    with pytest.raises(DraftPromotionError):
        await promote_draft(draft.id, NEW_TOKEN, "kofeynya_bot", 7891234567)


@pytest.mark.asyncio
async def test_promote_refuses_bot_taken_by_another_shop(db):
    """telegram_bot_id уникален: один бот — один магазин."""
    seller = await _seller(db)
    async with db() as session:
        session.add(
            SellerBot(
                seller_id=seller.id,
                title="Старый",
                bot_token_encrypted=encrypt_bot_token(NEW_TOKEN),
                bot_username="old_bot",
                telegram_bot_id=7891234567,
            )
        )
        await session.commit()

    draft = await create_draft(seller.id, "Новый")
    with pytest.raises(DraftPromotionError):
        await promote_draft(draft.id, NEW_TOKEN, "new_bot", 7891234567)


@pytest.mark.asyncio
async def test_latest_draft_ignores_finished_shops(db):
    seller = await _seller(db)
    done = await create_draft(seller.id, "Готовый")
    await promote_draft(done.id, NEW_TOKEN, "done_bot", 111)
    pending = await create_draft(seller.id, "Незаконченный")

    found = await latest_draft(seller.id)
    assert found is not None and found.id == pending.id


# --------------------------------------------------------------------------
# Право создавать боты
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_newshop_explains_instead_of_offering_broken_button(db):
    """Пока `can_manage_bots` снят, Telegram отвечает на кнопку ошибкой.

    Значит спрашивать название бессмысленно: человек его введёт, получит
    кнопку и упрётся в «this bot doesn't support managing bots».
    """
    from app.handlers.hub.newshop import cmd_newshop

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=4242), answer=AsyncMock()
    )
    state = SimpleNamespace(set_state=AsyncMock(), clear=AsyncMock())

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=False)),
    ):
        await cmd_newshop(message, state)

    state.set_state.assert_not_awaited()  # до вопроса про название не дошли
    assert "BotFather" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_newshop_offers_the_button_right_away(db):
    """Кнопка — сразу, без вопроса про название: имя и адрес человек вводит
    в окне Telegram, а отдельный вопрос был тем же вопросом, заданным дважды."""
    from app.handlers.hub.newshop import cmd_newshop

    seller = await _seller(db, terms=True)
    message = SimpleNamespace(from_user=SimpleNamespace(id=seller.telegram_id), answer=AsyncMock())
    state = SimpleNamespace(set_state=AsyncMock(), clear=AsyncMock())

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True)),
    ):
        await cmd_newshop(message, state)

    state.set_state.assert_not_awaited()  # ничего не ждём — ни названия, ни ответа
    button = message.answer.await_args.kwargs["reply_markup"].keyboard[0][0]
    assert button.request_managed_bot is not None
    # не подсказываем: имя и адрес — в окне Telegram
    assert button.request_managed_bot.suggested_name is None
    assert button.request_managed_bot.suggested_username is None
    # черновик под кнопку уже заведён, пока без названия
    draft = await latest_draft(seller.id)
    assert draft is not None and draft.title is None

@pytest.mark.asyncio
async def test_unreachable_telegram_does_not_offer_the_button(db):
    """Связь легла — предлагаем ручной путь, а не кнопку наугад."""
    from app.services.shop_draft import can_create_managed_bots

    with patch(
        "app.bots.hub.hub_bot.get_me", new=AsyncMock(side_effect=Exception("timeout"))
    ):
        assert await can_create_managed_bots() is False


# --------------------------------------------------------------------------
# Кнопка и разбор ответа Telegram
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_created_bot_becomes_the_shop(db):
    """Ответ Telegram разобран, токен забран, магазин включён."""
    from app.handlers.hub.newshop import bot_created

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня у дома")

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        managed_bot_created=SimpleNamespace(
            bot_user=SimpleNamespace(id=7891234567, username="kofeynya_u_doma_bot")
        ),
        answer=AsyncMock(),
    )

    with (
        patch("app.bots.hub.hub_bot.get_managed_bot_token", new=AsyncMock(return_value=NEW_TOKEN)),
        patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=True)),
    ):
        await bot_created(message)

    async with db() as session:
        shop = await session.get(SellerBot, draft.id)
        assert shop.is_draft is False
        assert shop.is_active is True
        assert decrypt_bot_token(shop.bot_token_encrypted) == NEW_TOKEN
    assert "подключён" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_created_bot_removes_reply_keyboard_then_offers_the_shop(db, _no_creator_welcome):
    """«Создать бота» снимается первым сообщением (one_time её только
    сворачивает), кнопка в магазин — вторым; создателю шлём приветствие
    от нового бота."""
    import asyncio

    from aiogram import types

    from app.handlers.hub.newshop import bot_created
    from tests.test_hub_menus import FAKE_SETTINGS

    seller = await _seller(db)
    draft = await create_draft(seller.id)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        managed_bot_created=SimpleNamespace(
            bot_user=SimpleNamespace(id=7891234567, username="two_msg_bot", first_name="Two")
        ),
        answer=AsyncMock(),
    )
    with (
        patch("app.bots.hub.hub_bot.get_managed_bot_token", new=AsyncMock(return_value=NEW_TOKEN)),
        patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=True)),
        patch("app.handlers.hub.newshop.get_settings", return_value=FAKE_SETTINGS),
    ):
        await bot_created(message)
        await asyncio.sleep(0)  # дать фоновой задаче стартовать

    first, second = message.answer.await_args_list
    assert "подключён" in first.args[0]
    assert isinstance(first.kwargs["reply_markup"], types.ReplyKeyboardRemove)
    button = second.kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == f"https://app.example.com/shop/{draft.id}"
    _no_creator_welcome.assert_awaited_once()
    assert _no_creator_welcome.await_args.args[0].id == draft.id


@pytest.mark.asyncio
async def test_token_failure_leaves_draft_alone(db):
    """Токен не отдали — магазин остаётся черновиком, а не полуживым."""
    from app.handlers.hub.newshop import bot_created

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        managed_bot_created=SimpleNamespace(
            bot_user=SimpleNamespace(id=7891234567, username="kofeynya_bot")
        ),
        answer=AsyncMock(),
    )
    with patch(
        "app.bots.hub.hub_bot.get_managed_bot_token",
        new=AsyncMock(side_effect=Exception("403")),
    ):
        await bot_created(message)

    async with db() as session:
        shop = await session.get(SellerBot, draft.id)
        assert shop.is_draft is True
        assert shop.is_active is False


@pytest.mark.asyncio
async def test_bot_created_without_draft_still_becomes_a_shop(db):
    """Кнопку нажали из старого сообщения, черновика уже нет — а бот создан
    по-настоящему. Отправить человека «начать заново» значило бы бросить
    живого бота без магазина."""
    from app.handlers.hub.newshop import bot_created

    seller = await _seller(db)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        managed_bot_created=SimpleNamespace(
            bot_user=SimpleNamespace(id=999, username="lonely_bot", first_name="Lonely Shop")
        ),
        answer=AsyncMock(),
    )
    with patch(
        "app.bots.hub.hub_bot.get_managed_bot_token", new=AsyncMock(return_value=NEW_TOKEN)
    ), patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=True)):
        await bot_created(message)

    async with db() as session:
        shop = (await session.execute(select(SellerBot))).scalar_one()
    assert shop.bot_username == "lonely_bot"
    assert shop.shop_name == "Lonely Shop"
    assert shop.is_active is True

# --------------------------------------------------------------------------
# Продавец сменил токен в @BotFather
# --------------------------------------------------------------------------


REPLACEMENT_TOKEN = "7891234567:AAHreplaced-token-aaaaaaaaaaaaaaaa"


async def _connected_shop(db, *, is_managed: bool) -> tuple[Seller, SellerBot]:
    """Работающий магазин с отозванным токеном — состояние после того, как
    продавец перевыпустил токен в @BotFather."""
    seller = await _seller(db)
    async with db() as session:
        shop = SellerBot(
            seller_id=seller.id,
            title="Кофейня",
            bot_token_encrypted=encrypt_bot_token(NEW_TOKEN),
            bot_username="kofeynya_bot",
            telegram_bot_id=7891234567,
            is_managed=is_managed,
            is_active=True,
            webhook_status="revoked",
        )
        session.add(shop)
        await session.commit()
        await session.refresh(shop)
        return seller, shop


@pytest.mark.asyncio
async def test_managed_shop_is_restored_without_the_seller(db):
    """Смысл кнопки: ни BotFather, ни копипаста токена."""
    from app.services.bot_recovery import RESTORED, restore_managed_token

    seller, shop = await _connected_shop(db, is_managed=True)

    with (
        patch(
            "app.bots.hub.hub_bot.replace_managed_bot_token",
            new=AsyncMock(return_value=REPLACEMENT_TOKEN),
        ),
        patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=True)),
    ):
        assert await restore_managed_token(shop.id, seller.id) == RESTORED

    async with db() as session:
        fresh = await session.get(SellerBot, shop.id)
        assert decrypt_bot_token(fresh.bot_token_encrypted) == REPLACEMENT_TOKEN
        assert fresh.webhook_status == "active"  # магазин снова живой
        assert fresh.is_active is True


@pytest.mark.asyncio
async def test_manually_connected_shop_cannot_be_restored(db):
    """Чужим ботом мы не управляем — перевыпускать нечего."""
    from app.services.bot_recovery import NOT_MANAGED, restore_managed_token

    seller, shop = await _connected_shop(db, is_managed=False)
    replace = AsyncMock()
    with patch("app.bots.hub.hub_bot.replace_managed_bot_token", new=replace):
        assert await restore_managed_token(shop.id, seller.id) == NOT_MANAGED
    replace.assert_not_awaited()  # и не ходим в Telegram зря


@pytest.mark.asyncio
async def test_failed_replace_leaves_the_old_token_alone(db):
    """Доступ к боту забрали — магазин остаётся как был, а не без токена."""
    from app.services.bot_recovery import FAILED, restore_managed_token

    seller, shop = await _connected_shop(db, is_managed=True)
    with patch(
        "app.bots.hub.hub_bot.replace_managed_bot_token",
        new=AsyncMock(side_effect=Exception("access revoked")),
    ):
        assert await restore_managed_token(shop.id, seller.id) == FAILED

    async with db() as session:
        fresh = await session.get(SellerBot, shop.id)
        assert decrypt_bot_token(fresh.bot_token_encrypted) == NEW_TOKEN


@pytest.mark.asyncio
async def test_restore_refuses_someone_elses_shop(db):
    """Chat id в callback_data подделать несложно — владельца проверяем."""
    from app.services.bot_recovery import NOT_FOUND, restore_managed_token

    _, shop = await _connected_shop(db, is_managed=True)
    stranger = await _seller(db, telegram_id=999)

    replace = AsyncMock()
    with patch("app.bots.hub.hub_bot.replace_managed_bot_token", new=replace):
        assert await restore_managed_token(shop.id, stranger.id) == NOT_FOUND
    replace.assert_not_awaited()


@pytest.mark.asyncio
async def test_promoted_shop_is_marked_managed(db):
    """Без этого флага починить бота кнопкой будет нечем."""
    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")
    shop = await promote_draft(draft.id, NEW_TOKEN, "kofeynya_bot", 7891234567)
    assert shop.is_managed is True


@pytest.mark.asyncio
async def test_revoked_push_offers_the_button_only_to_managed_bots(db):
    """Кнопка, которая ничего не чинит, хуже честного текста про BotFather."""
    from app.services.bot_health import revoked_text

    managed = revoked_text("kofeynya_bot", is_managed=True)
    manual = revoked_text("kofeynya_bot", is_managed=False)

    assert "новый токен" in managed
    assert "перестанет" in managed  # предупреждаем: старый токен умрёт
    assert "BotFather" in manual and "новый токен" not in manual


# --------------------------------------------------------------------------
# Черновик не ломает существующий код
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_gets_no_webhook(db):
    """Вебхук вешать не на что — раньше это была бы расшифровка None."""
    from app.bots.runner import setup_seller_webhook

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")

    async with db() as session:
        shop = await session.get(SellerBot, draft.id)
        assert await setup_seller_webhook(shop) is False


@pytest.mark.asyncio
async def test_draft_cannot_be_switched_on(db):
    """Кнопка «Включить» у черновика не должна поднимать магазин без бота."""
    from app.services.bot_connect import enable_bot

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")
    assert await enable_bot(draft.id, seller.id) is None

    async with db() as session:
        assert (await session.get(SellerBot, draft.id)).is_active is False


@pytest.mark.asyncio
async def test_token_check_skips_drafts(db):
    """Проверка отозванных токенов не должна спотыкаться о пустой токен."""
    from app.services.bot_health import check_revoked_tokens

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")
    async with db() as session:
        shop = await session.get(SellerBot, draft.id)
        shop.is_active = True  # даже если черновик кто-то включил руками в БД
        await session.commit()

    assert await check_revoked_tokens() == 0


@pytest.mark.asyncio
async def test_draft_shop_answers_404_not_500(db):
    """Черновик пускали до расшифровки токена — на угадываемом id это 500.

    `get_buyer_any_shop` не требует активного магазина (свои заказы у
    отключённого магазина остаются доступны), поэтому черновик проходил
    проверку на 404 и падал на `decrypt(None)`.
    """
    from tests.test_api import buyer_headers, client

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")

    async with client() as c:
        # витрина (get_buyer) и «свои заказы» (get_buyer_any_shop, который
        # намеренно пускает отключённые магазины — там и был пробой)
        for path in (f"/api/store/{draft.id}", f"/api/store/{draft.id}/orders/my"):
            r = await c.get(path, headers=buyer_headers())
            assert r.status_code == 404, f"{path} -> {r.status_code}"


@pytest.mark.asyncio
async def test_mailing_for_shop_without_bot_fails_once(db):
    """Рассылка без бота падала каждый раз и вечно оживала из sending."""
    from app.models import Mailing
    from app.services.mailing import send_mailing

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")
    async with db() as session:
        mailing = Mailing(
            seller_id=seller.id, bot_id=draft.id, text="Привет", status="sending"
        )
        session.add(mailing)
        await session.commit()
        await session.refresh(mailing)
        mailing_id = mailing.id

    await send_mailing(mailing_id)  # раньше — ValidationError на decrypt(None)

    async with db() as session:
        assert (await session.get(Mailing, mailing_id)).status == "failed"


# --------------------------------------------------------------------------
# Как черновик и отозванный токен выглядят в /mybots
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mybots_never_renders_at_none(db):
    """Кнопка «@None» и ссылка t.me/None — это сбой, а не название магазина."""
    from app.handlers.hub.mybots import (
        bot_card_keyboard,
        bot_card_text,
        shops_menu_keyboard,
        shops_menu_text,
    )

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня у дома")

    menu = shops_menu_text([draft])
    buttons = [b.text for row in shops_menu_keyboard([draft]).inline_keyboard for b in row]
    card = bot_card_text(draft)
    card_kb = bot_card_keyboard(draft)
    urls = [b.url for row in card_kb.inline_keyboard for b in row if b.url]

    assert "None" not in menu and "None" not in card
    assert not any("None" in text for text in buttons)
    assert not any("None" in url for url in urls)
    assert "Кофейня у дома" in card
    # включать черновик нечего — кнопку не предлагаем
    labels = [b.text for row in card_kb.inline_keyboard for b in row]
    assert not any("Включить" in label for label in labels)


@pytest.mark.asyncio
async def test_enable_on_draft_does_not_claim_success(db):
    """Тост «Включён» врал: enable_bot черновик не включает."""
    from app.handlers.hub.mybots import do_enable

    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня")
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        data=f"mybots:on:{draft.id}",
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )

    await do_enable(callback)

    assert "Включён" not in callback.answer.await_args.args[0]
    callback.message.edit_text.assert_not_awaited()


# --------------------------------------------------------------------------
# Восстановление: двойное нажатие и половинчатый успех
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_press_does_not_kill_the_fresh_token(db):
    """Каждый replaceManagedBotToken убивает токен предыдущего вызова.

    Два нажатия подряд оставляли в базе токен того вызова, чья транзакция
    закоммитилась последней, — и он мог быть уже мёртвым.
    """
    from app.services.bot_recovery import ALREADY_OK, RESTORED, restore_managed_token

    seller, shop = await _connected_shop(db, is_managed=True)
    replace = AsyncMock(return_value=REPLACEMENT_TOKEN)
    with (
        patch("app.bots.hub.hub_bot.replace_managed_bot_token", new=replace),
        patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=True)),
    ):
        assert await restore_managed_token(shop.id, seller.id) == RESTORED
        assert await restore_managed_token(shop.id, seller.id) == ALREADY_OK

    assert replace.await_count == 1  # второй токен не выпускали
    async with db() as session:
        fresh = await session.get(SellerBot, shop.id)
        assert decrypt_bot_token(fresh.bot_token_encrypted) == REPLACEMENT_TOKEN


@pytest.mark.asyncio
async def test_webhook_failure_is_not_reported_as_nothing_happened(db):
    """Токен уже заменён — «не вышло восстановить» отправило бы продавца
    искать старый токен, которого больше нет."""
    from app.services.bot_recovery import WEBHOOK_PENDING, restore_managed_token

    seller, shop = await _connected_shop(db, is_managed=True)
    with (
        patch(
            "app.bots.hub.hub_bot.replace_managed_bot_token",
            new=AsyncMock(return_value=REPLACEMENT_TOKEN),
        ),
        patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=False)),
    ):
        assert await restore_managed_token(shop.id, seller.id) == WEBHOOK_PENDING

    async with db() as session:
        fresh = await session.get(SellerBot, shop.id)
        # новый токен сохранён: делать вид, что ничего не было, нельзя
        assert decrypt_bot_token(fresh.bot_token_encrypted) == REPLACEMENT_TOKEN


@pytest.mark.asyncio
async def test_restore_does_not_reopen_a_shop_turned_off_on_purpose(db):
    """Продавец отключил магазин сам — починка токена не повод открывать его."""
    from app.services.bot_recovery import restore_managed_token

    seller, shop = await _connected_shop(db, is_managed=True)
    async with db() as session:
        record = await session.get(SellerBot, shop.id)
        record.is_active = False
        await session.commit()

    with (
        patch(
            "app.bots.hub.hub_bot.replace_managed_bot_token",
            new=AsyncMock(return_value=REPLACEMENT_TOKEN),
        ),
        patch("app.bots.runner.setup_seller_webhook", new=AsyncMock(return_value=True)),
    ):
        await restore_managed_token(shop.id, seller.id)

    async with db() as session:
        assert (await session.get(SellerBot, shop.id)).is_active is False


@pytest.mark.asyncio
async def test_promoted_shop_shows_its_name_on_the_storefront(db):
    """Витрина читает shop_name, а не title — иначе «Кофейня у дома»
    показывалась покупателю как @kofeynya_u_doma_bot."""
    seller = await _seller(db)
    draft = await create_draft(seller.id, "Кофейня у дома")
    shop = await promote_draft(draft.id, NEW_TOKEN, "kofeynya_u_doma_bot", 7891234567)
    assert shop.shop_name == "Кофейня у дома"


# --------------------------------------------------------------------------
# Брошенный /newshop
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repeated_newshop_reuses_the_draft(db):
    """Каждая брошенная попытка оставляла мусорный магазин навсегда."""
    seller = await _seller(db)
    first = await create_draft(seller.id)
    second = await create_draft(seller.id)

    assert second.id == first.id
    async with db() as session:
        shops = (await session.execute(select(SellerBot))).scalars().all()
        assert len(shops) == 1


@pytest.mark.asyncio
async def test_untitled_draft_takes_the_name_given_in_telegram(db):
    """Название не спрашиваем — им становится имя, которое человек дал боту
    в окне Telegram. И попадает оно туда, где его видит покупатель."""
    seller = await _seller(db)
    draft = await create_draft(seller.id)
    shop = await promote_draft(draft.id, NEW_TOKEN, "zee_store_bot", 555, bot_name="Zee Store")

    assert shop.title == "Zee Store"
    assert shop.shop_name == "Zee Store"

# --------------------------------------------------------------------------
# Вход из Mini App: диплинк вместо ручного ввода токена
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deeplink_offers_the_button_after_terms(db):
    """Запасной путь из Mini App: человек принял условия, диплинк ведёт в чат —
    там его сразу должна ждать кнопка, без вопросов."""
    from app.handlers.hub.start import cmd_start_newshop

    seller = await _seller(db, telegram_id=5150, terms=True)
    message = SimpleNamespace(
        from_user=SimpleNamespace(
            id=seller.telegram_id, username="newbie", first_name="Новичок", language_code="ru"
        ),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(set_state=AsyncMock(), clear=AsyncMock())

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub_bot")),
    ):
        await cmd_start_newshop(message, state)

    button = message.answer.await_args.kwargs["reply_markup"].keyboard[0][0]
    assert button.request_managed_bot is not None


@pytest.mark.asyncio
async def test_first_shop_needs_terms_even_from_the_chat(db):
    """Галочка условий живёт в приложении, а /newshop в чате раньше заводил
    первый магазин в обход неё. Теперь без условий — только просьба их принять."""
    from app.handlers.hub.start import cmd_start_newshop

    message = SimpleNamespace(
        from_user=SimpleNamespace(
            id=5151, username="newbie2", first_name="Новичок", language_code="ru"
        ),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(set_state=AsyncMock(), clear=AsyncMock())

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub_bot")),
    ):
        await cmd_start_newshop(message, state)

    async with db() as session:
        seller = (await session.execute(select(Seller).where(Seller.telegram_id == 5151))).scalar_one()
    assert seller is not None  # диплинк по-прежнему регистрирует продавца
    assert "условия" in message.answer.await_args.args[0]
    assert await latest_draft(seller.id) is None  # магазина без условий нет


@pytest.mark.asyncio
async def test_old_sellers_without_terms_are_not_locked_out(db):
    """Продавцы, подключившиеся до появления галочки, имеют пустой
    terms_accepted_at, а экран условий приложение показывает только тем,
    у кого магазинов нет. Требовать условия на каждый /newshop — значит
    навсегда закрыть им второй магазин."""
    from app.handlers.hub.newshop import needs_terms

    seller = await _seller(db)  # условий нет
    assert await needs_terms(seller) is True
    async with db() as session:
        session.add(
            SellerBot(
                seller_id=seller.id,
                bot_token_encrypted=encrypt_bot_token(NEW_TOKEN),
                bot_username="old_bot",
                is_active=True,
            )
        )
        await session.commit()
    assert await needs_terms(seller) is False

@pytest.mark.asyncio
async def test_deeplink_is_absent_when_creation_is_off(db):
    """Флаг снят — звать человека в диалог, где его встретит отказ, нельзя."""
    from app.services.shop_draft import create_shop_deeplink

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=False, username="hub_bot")),
    ):
        assert await create_shop_deeplink() is None


@pytest.mark.asyncio
async def test_deeplink_points_at_the_hub_bot(db):
    from app.services.shop_draft import NEWSHOP_PAYLOAD, create_shop_deeplink

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub_bot")),
    ):
        link = await create_shop_deeplink()
    assert link == f"https://t.me/hub_bot?start={NEWSHOP_PAYLOAD}"


@pytest.mark.asyncio
async def test_managed_flag_is_cached_not_asked_every_time(db):
    """getMe на каждом открытии приложения — лишний рейс на самом частом
    запросе."""
    from app.services.shop_draft import can_create_managed_bots

    get_me = AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub_bot"))
    with patch("app.bots.hub.hub_bot.get_me", new=get_me):
        assert await can_create_managed_bots() is True
        assert await can_create_managed_bots() is True
    assert get_me.await_count == 1


@pytest.mark.asyncio
async def test_connection_failure_is_not_cached(db):
    """Сбой связи — не ответ «нельзя»: следующая попытка должна спросить снова,
    иначе одна сетевая ошибка запирает онбординг на пять минут."""
    from app.services.shop_draft import can_create_managed_bots

    with patch("app.bots.hub.hub_bot.get_me", new=AsyncMock(side_effect=Exception("boom"))):
        assert await can_create_managed_bots() is False

    ok = AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub_bot"))
    with patch("app.bots.hub.hub_bot.get_me", new=ok):
        assert await can_create_managed_bots() is True
    assert ok.await_count == 1


# --------------------------------------------------------------------------
# После галочки в приложении: сервер сам присылает кнопку в чат
# --------------------------------------------------------------------------


async def _post_prompt(get_me_flag=True, send=None):
    from tests.test_api import client, seller_headers

    send = send or AsyncMock()
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=get_me_flag, username="hub")),
    ), patch("app.bots.hub.hub_bot.send_message", new=send):
        async with client() as c:
            r = await c.post("/api/seller/onboarding/bot-prompt", headers=seller_headers())
    return r, send


@pytest.mark.asyncio
async def test_prompt_lands_in_the_chat_with_the_button(db):
    """Mini App не умеет показать кнопку создания бота — её показывает чат.
    Сервер присылает её туда сам, и приложению остаётся закрыться."""
    from tests.test_api import SELLER_TG

    seller = await _seller(db, telegram_id=SELLER_TG["id"], terms=True)
    r, send = await _post_prompt()

    assert r.status_code == 200, r.text
    assert r.json() == {"sent": True}
    assert send.await_args.args[0] == SELLER_TG["id"]
    button = send.await_args.kwargs["reply_markup"].keyboard[0][0]
    assert button.request_managed_bot is not None
    assert await latest_draft(seller.id) is not None


@pytest.mark.asyncio
async def test_prompt_needs_terms_for_the_first_shop(db):
    from tests.test_api import SELLER_TG

    await _seller(db, telegram_id=SELLER_TG["id"])  # условия не приняты
    r, send = await _post_prompt()

    assert r.status_code == 403
    assert r.json()["detail"] == "terms_required"
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_prompt_is_not_sent_when_management_is_off(db):
    """Кнопка с выключенным Bot Management Mode упала бы у человека в руках —
    не шлём её, фронт уйдёт на ручной путь."""
    from tests.test_api import SELLER_TG

    await _seller(db, telegram_id=SELLER_TG["id"], terms=True)
    r, send = await _post_prompt(get_me_flag=False)

    assert r.json() == {"sent": False}
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_prompt_failure_falls_back_instead_of_breaking(db):
    """Telegram не принял сообщение — это не повод ронять онбординг:
    у фронта есть запасной путь."""
    from tests.test_api import SELLER_TG

    await _seller(db, telegram_id=SELLER_TG["id"], terms=True)
    r, _ = await _post_prompt(send=AsyncMock(side_effect=RuntimeError("blocked")))

    assert r.status_code == 200
    assert r.json() == {"sent": False}

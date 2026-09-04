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
    suggest_username,
)

NEW_TOKEN = "7891234567:AAHmanaged-bot-token-for-tests-aaaa"


async def _seller(db, telegram_id: int = 4242) -> Seller:
    async with db() as session:
        seller = Seller(telegram_id=telegram_id)
        session.add(seller)
        await session.commit()
        await session.refresh(seller)
        return seller


# --------------------------------------------------------------------------
# Предложение юзернейма
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Кофейня у дома", "kofeynya_u_doma_bot"),
        ("Coffee House", "coffee_house_bot"),
        ("Пекарня  «Хлеб»!", "pekarnya_hleb_bot"),
        ("Ёлки-Палки", "elki_palki_bot"),
    ],
)
def test_username_is_suggested_from_title(title, expected):
    """Продавцу должно хватать нажать «ок»: адрес собирается из названия."""
    assert suggest_username(title) == expected


def test_username_fits_telegram_limits():
    """32 символа с обязательным окончанием bot — длинное название режется."""
    name = suggest_username("Очень длинное название магазина про всё на свете")
    assert len(name) <= 32
    assert name.endswith("_bot")
    assert not name.startswith("_") and "__" not in name


def test_username_never_starts_with_a_digit():
    """Telegram требует букву в начале — «7 небо» давало 7_nebo_bot,
    и его же диалог создания отверг бы наше предложение."""
    for title in ("7 небо", "24 часа", "1С Магазин"):
        name = suggest_username(title)
        assert name[0].isalpha(), f"{title} -> {name}"
        assert name.endswith("_bot") and len(name) <= 32


def test_unsuggestable_title_still_gives_valid_username():
    """Название из одних эмодзи перевести не во что — но адрес нужен всё равно."""
    name = suggest_username("🌸🌸🌸")
    assert name.endswith("_bot") and len(name) > len("_bot")


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
async def test_newshop_asks_for_title_when_management_is_on(db):
    from app.handlers.hub.newshop import cmd_newshop

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=4242), answer=AsyncMock()
    )
    state = SimpleNamespace(
        set_state=AsyncMock(), clear=AsyncMock(), update_data=AsyncMock()
    )

    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True)),
    ):
        await cmd_newshop(message, state)

    state.set_state.assert_awaited()
    assert "назовём магазин" in message.answer.await_args.args[0]


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
async def test_button_carries_name_and_username(db):
    """Кнопка должна прийти к продавцу уже заполненной — в этом весь смысл."""
    from app.handlers.hub.newshop import got_title

    seller = await _seller(db)
    answers = []
    message = SimpleNamespace(
        text="Кофейня у дома",
        from_user=SimpleNamespace(id=seller.telegram_id),
        answer=AsyncMock(side_effect=lambda text, **kw: answers.append((text, kw))),
    )
    state = SimpleNamespace(
        clear=AsyncMock(),
        set_state=AsyncMock(),
        get_data=AsyncMock(return_value={"asked_at": time()}),
    )

    await got_title(message, state)

    kb = answers[-1][1]["reply_markup"]
    button = kb.keyboard[0][0]
    assert button.request_managed_bot.suggested_name == "Кофейня у дома"
    assert button.request_managed_bot.suggested_username == "kofeynya_u_doma_bot"

    # и черновик под неё уже заведён
    assert (await latest_draft(seller.id)) is not None


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
async def test_bot_created_without_draft_does_not_crash(db):
    """Кнопку нажали, магазина нет: прицепить бота некуда, но падать нельзя."""
    from app.handlers.hub.newshop import bot_created

    seller = await _seller(db)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        managed_bot_created=SimpleNamespace(
            bot_user=SimpleNamespace(id=999, username="lonely_bot")
        ),
        answer=AsyncMock(),
    )
    await bot_created(message)

    async with db() as session:
        assert (await session.execute(select(SellerBot))).scalars().all() == []
    assert "нет" in message.answer.await_args.args[0]


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
async def test_repeated_newshop_renames_the_draft(db):
    """Каждая брошенная попытка оставляла мусорный магазин навсегда."""
    seller = await _seller(db)
    first = await create_draft(seller.id, "Кофейня")
    second = await create_draft(seller.id, "Пекарня")

    assert second.id == first.id  # тот же магазин, новое название
    assert second.title == "Пекарня"
    async with db() as session:
        shops = (await session.execute(select(SellerBot))).scalars().all()
        assert len(shops) == 1


@pytest.mark.asyncio
async def test_stale_state_does_not_turn_a_greeting_into_a_shop(db):
    """/newshop, потом /mybots, потом через час «привет» — заводился магазин.

    Состояние FSM живёт в памяти до перезапуска, и снять его было некому.
    """
    from app.handlers.hub.newshop import TITLE_TIMEOUT_SEC, got_title

    seller = await _seller(db)
    message = SimpleNamespace(
        text="привет",
        from_user=SimpleNamespace(id=seller.telegram_id),
        answer=AsyncMock(),
    )
    stale = {"asked_at": time() - TITLE_TIMEOUT_SEC - 1}
    state = SimpleNamespace(
        clear=AsyncMock(), set_state=AsyncMock(), get_data=AsyncMock(return_value=stale)
    )

    await got_title(message, state)

    state.clear.assert_awaited()
    assert await latest_draft(seller.id) is None
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_command_instead_of_title_cancels_instead_of_nagging(db):
    from app.handlers.hub.newshop import got_title

    seller = await _seller(db)
    message = SimpleNamespace(
        text="/mybots",
        from_user=SimpleNamespace(id=seller.telegram_id),
        answer=AsyncMock(),
    )
    state = SimpleNamespace(
        clear=AsyncMock(),
        set_state=AsyncMock(),
        get_data=AsyncMock(return_value={"asked_at": time()}),
    )

    await got_title(message, state)

    state.clear.assert_awaited()
    assert await latest_draft(seller.id) is None

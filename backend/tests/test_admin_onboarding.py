"""/onboarding — каким путём пойдёт следующий продавец.

Команда отвечает на вопрос, который иначе проверяется только вручную и чужим
аккаунтом: включён ли в @BotFather Bot Management Mode. Поэтому здесь важны
две вещи — что мы не путаем «выключено» со «связь оборвалась», и что цифры
«как заводили магазины» считаются по реальным строкам.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.handlers.hub.admin import onboarding
from app.models import Seller, SellerBot
from app.security import encrypt_bot_token
from app.services.shop_draft import reset_managed_cache

ADMIN_TG = 777001


async def make_admin(db) -> None:
    async with db() as session:
        session.add(Seller(telegram_id=ADMIN_TG, is_admin=True))
        await session.commit()


async def add_shop(db, *, managed: bool | None) -> None:
    """managed=None — черновик: магазин заведён, бота ещё нет."""
    async with db() as session:
        seller = Seller(telegram_id=ADMIN_TG + 1 + id(object()) % 10_000)
        session.add(seller)
        await session.flush()
        session.add(
            SellerBot(
                seller_id=seller.id,
                title="Магазин",
                bot_token_encrypted=(
                    None if managed is None else encrypt_bot_token("123:token")
                ),
                is_managed=bool(managed),
            )
        )
        await session.commit()


def fake_message() -> SimpleNamespace:
    return SimpleNamespace(from_user=SimpleNamespace(id=ADMIN_TG), answer=AsyncMock())


def said(message) -> str:
    return message.answer.await_args.args[0]


@pytest.fixture(autouse=True)
def _reset_cache():
    reset_managed_cache()
    yield
    reset_managed_cache()


@pytest.mark.asyncio
async def test_not_for_regular_sellers(db):
    """Для обычного продавца команды как будто не существует."""
    async with db() as session:
        session.add(Seller(telegram_id=999123))
        await session.commit()

    message = SimpleNamespace(from_user=SimpleNamespace(id=999123), answer=AsyncMock())
    await onboarding(message)
    assert message.answer.await_count == 0


@pytest.mark.asyncio
async def test_flag_on_reports_short_path(db):
    await make_admin(db)
    message = fake_message()
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub")),
    ):
        await onboarding(message)

    text = said(message)
    assert "включён" in text
    assert "Создай магазин" in text
    # диплинк собирается тем же путём, что и в приложении
    assert "t.me/hub?start=newshop" in text


@pytest.mark.asyncio
async def test_flag_off_explains_what_seller_sees(db):
    await make_admin(db)
    message = fake_message()
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=False, username="hub")),
    ):
        await onboarding(message)

    text = said(message)
    assert "выключен" in text
    assert "@BotFather" in text  # ровно то, через что идёт продавец сейчас
    assert "Ссылка на создание: недоступна" in text


@pytest.mark.asyncio
async def test_connection_failure_is_not_reported_as_disabled(db):
    """Молчание Telegram — не «выключено»: иначе владелец пошёл бы крутить
    тумблер, который и так включён."""
    await make_admin(db)
    message = fake_message()
    with patch("app.bots.hub.hub_bot.get_me", new=AsyncMock(side_effect=RuntimeError("boom"))):
        await onboarding(message)

    text = said(message)
    assert "не ответил на getMe" in text
    assert "выключен" not in text


@pytest.mark.asyncio
async def test_missing_flag_in_api_is_not_disabled_either(db):
    """Старая библиотека не присылает поле вовсе — это тоже не «выключено»."""
    await make_admin(db)
    message = fake_message()
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(username="hub")),
    ):
        await onboarding(message)

    text = said(message)
    assert "can_manage_bots" in text
    assert "Bot Management Mode <b>выключен</b>" not in text


@pytest.mark.asyncio
async def test_counts_split_managed_manual_and_drafts(db):
    await make_admin(db)
    await add_shop(db, managed=True)
    await add_shop(db, managed=True)
    await add_shop(db, managed=False)
    await add_shop(db, managed=None)

    message = fake_message()
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub")),
    ):
        await onboarding(message)

    text = said(message)
    assert "Через Telegram: <b>2</b>" in text
    assert "Токеном вручную: <b>1</b>" in text
    assert "Черновиков без бота: 1" in text


@pytest.mark.asyncio
async def test_command_resets_the_cached_flag(db):
    """Тумблер включили — приложение обязано подхватить сразу, а не через
    пять минут, иначе это читается как «не сработало»."""
    from app.services import shop_draft

    await make_admin(db)
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=False, username="hub")),
    ):
        assert await shop_draft.can_create_managed_bots() is False
    assert shop_draft._managed_cache is not None  # ответ закэширован

    message = fake_message()
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub")),
    ):
        await onboarding(message)
        # кэш сброшен командой, поэтому следующий же вопрос видит новый флаг
        assert await shop_draft.can_create_managed_bots() is True

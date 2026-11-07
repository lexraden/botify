"""Копия магазина: содержимое переезжает в черновик, история остаётся.

Сервис (app/services/shop_copy.py) проверяется прямыми вызовами, хендлер
карточки — фейковым callback-ом, как в test_managed_bot_onboarding.py.
"""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models import (
    Category,
    Product,
    ProductImage,
    ProductVariant,
    Seller,
    SellerBot,
    ShopLogo,
    ShopPaymentMethod,
)
from app.security import encrypt_bot_token
from app.services.shop_copy import copy_shop_data
from app.services.shop_draft import create_draft, promote_draft


async def _seller(db, *, plan: str = "free", telegram_id: int = 4242) -> Seller:
    async with db() as session:
        seller = Seller(
            telegram_id=telegram_id,
            plan=plan,
            terms_accepted_at=datetime.now(timezone.utc),
        )
        session.add(seller)
        await session.commit()
        await session.refresh(seller)
        return seller


async def _source_shop(db, seller: Seller) -> SellerBot:
    async with db() as session:
        shop = SellerBot(
            seller_id=seller.id,
            bot_token_encrypted=encrypt_bot_token("123:source-token"),
            bot_username="old_shop_bot",
            telegram_bot_id=111,
            is_active=True,
            title="Старый магазин",
            shop_name="Старый",
            welcome_text="Привет, покупатель",
            show_catalog_button=True,
            catalog_button_text="В каталог",
        )
        session.add(shop)
        await session.commit()
        await session.refresh(shop)
        return shop


def _img_url(token: str) -> str:
    return f"/api/images/{token}"


# --------------------------------------------------------------------------
# Полный перенос
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_moves_catalog_settings_media_and_requisites(db):
    seller = await _seller(db, plan="pro")
    source = await _source_shop(db, seller)

    async with db() as session:
        cat = Category(seller_id=seller.id, bot_id=source.id, name="Кофе", sort_order=3)
        session.add(cat)
        await session.flush()
        with_photo = Product(
            seller_id=seller.id,
            bot_id=source.id,
            category_id=cat.id,
            type="physical",
            title="Латте",
            price=Decimal("150"),
            compare_at_price=Decimal("200"),
            stock=5,
            image_url=_img_url("tok-latte"),
        )
        session.add(with_photo)
        digital = Product(
            seller_id=seller.id,
            bot_id=source.id,
            type="digital",
            title="Гайд",
            price=Decimal("50"),
            digital_content={"url": "https://example.com/guide"},
        )
        session.add(digital)
        await session.flush()
        session.add(
            ProductVariant(
                product_id=digital.id,
                bot_id=source.id,
                sku="GUIDE-1",
                attributes={"Формат": "PDF"},
                title="PDF",
                price=Decimal("40"),
                compare_at_price=Decimal("60"),
                stock=3,
                images=[_img_url("tok-guide"), "https://cdn.example.com/ext.png"],
                position=0,
            )
        )
        session.add(
            ProductImage(
                token="tok-latte", bot_id=source.id, mime="image/png", size=10, data=b"latte"
            )
        )
        session.add(
            ProductImage(
                token="tok-guide", bot_id=source.id, mime="image/jpeg", size=12, data=b"guide"
            )
        )
        session.add(
            ShopLogo(
                bot_id=source.id, token="tok-logo", mime="image/png", size=8, data=b"logo"
            )
        )
        session.add(
            ShopPaymentMethod(
                bot_id=source.id,
                kind="card",
                label="Сбербанк",
                account="4111111111111111",
                holder="IVAN IVANOV",
                note="В назначении — номер заказа",
            )
        )
        await session.commit()

    target, result = await copy_shop_data(source.id, seller.id)

    assert target.is_draft is True
    assert (result.categories, result.products, result.variants) == (1, 2, 1)
    assert result.images == 2
    assert result.logo is True
    assert result.payment_methods == 1
    assert result.skipped_products == 0

    async with db() as session:
        fresh = await session.get(SellerBot, target.id)
        # настройки витрины переехали
        assert fresh.title == "Старый магазин"
        assert fresh.shop_name == "Старый"
        assert fresh.welcome_text == "Привет, покупатель"
        assert fresh.show_catalog_button is True
        assert fresh.catalog_button_text == "В каталог"

        new_cat = (
            await session.execute(select(Category).where(Category.bot_id == target.id))
        ).scalar_one()
        assert new_cat.name == "Кофе"
        assert new_cat.sort_order == 3

        products = (
            (await session.execute(select(Product).where(Product.bot_id == target.id)))
            .scalars()
            .all()
        )
        by_title = {p.title: p for p in products}
        latte, guide = by_title["Латте"], by_title["Гайд"]
        assert latte.category_id == new_cat.id  # remap категории
        assert latte.image_url.startswith("/api/images/")
        assert latte.image_url != _img_url("tok-latte")  # свой токен, не чужой
        assert guide.category_id is None
        assert guide.digital_content == {"url": "https://example.com/guide"}

        variant = (
            (
                await session.execute(
                    select(ProductVariant).where(ProductVariant.bot_id == target.id)
                )
            )
            .scalars()
            .one()
        )
        assert variant.sku == "GUIDE-1"
        assert variant.attributes == {"Формат": "PDF"}
        # внутренняя ссылка переписана, внешняя — как была
        assert variant.images[0].startswith("/api/images/")
        assert variant.images[0] not in (_img_url("tok-guide"),)
        assert variant.images[1] == "https://cdn.example.com/ext.png"
        # recompute_product_totals: витринные цена/остаток — из вариаций
        assert guide.price == Decimal("40")
        assert guide.stock == 3
        assert guide.compare_at_price is None

        # у копии свои строки картинок; исходные живы
        target_tokens = set(
            (
                await session.execute(
                    select(ProductImage.token).where(ProductImage.bot_id == target.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(target_tokens) == 2
        assert "tok-latte" not in target_tokens and "tok-guide" not in target_tokens
        for old in ("tok-latte", "tok-guide"):
            row = (
                await session.execute(
                    select(ProductImage).where(ProductImage.token == old)
                )
            ).scalar_one()
            assert row.bot_id == source.id

        new_logo = (
            await session.execute(select(ShopLogo).where(ShopLogo.bot_id == target.id))
        ).scalar_one()
        assert new_logo.token != "tok-logo"
        assert new_logo.data == b"logo"

        method = (
            (
                await session.execute(
                    select(ShopPaymentMethod).where(
                        ShopPaymentMethod.bot_id == target.id
                    )
                )
            )
            .scalars()
            .one()
        )
        assert method.kind == "card"
        assert method.label == "Сбербанк"
        assert method.account == "4111111111111111"  # перешифрован тем же ключом
        assert method.holder == "IVAN IVANOV"
        assert method.note == "В назначении — номер заказа"


@pytest.mark.asyncio
async def test_copy_without_pro_plan_skips_requisites(db):
    """Реквизиты — функция Pro: продавец free создал бы их через API нельзя,
    значит и в копию они не переезжают."""
    seller = await _seller(db, plan="free")
    source = await _source_shop(db, seller)
    async with db() as session:
        session.add(
            ShopPaymentMethod(
                bot_id=source.id, kind="card", label="Карта", account="4111"
            )
        )
        await session.commit()

    target, result = await copy_shop_data(source.id, seller.id)
    assert result.payment_methods == 0
    async with db() as session:
        left = (
            (
                await session.execute(
                    select(ShopPaymentMethod).where(ShopPaymentMethod.bot_id == target.id)
                )
            )
            .scalars()
            .all()
        )
        assert left == []


# --------------------------------------------------------------------------
# Переиспользованный черновик и promote
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_wipes_reused_draft_and_takes_source_product(db):
    seller = await _seller(db)
    source = await _source_shop(db, seller)
    stale = await create_draft(seller.id, "Брошенная попытка")
    async with db() as session:
        session.add(
            Product(
                seller_id=seller.id,
                bot_id=stale.id,
                type="physical",
                title="Мусор из прошлого раза",
                price=Decimal("1"),
            )
        )
        session.add(
            Product(
                seller_id=seller.id,
                bot_id=source.id,
                type="physical",
                title="Настоящий товар",
                price=Decimal("9"),
            )
        )
        await session.commit()

    target, result = await copy_shop_data(source.id, seller.id)

    assert target.id == stale.id
    assert result.products == 1
    async with db() as session:
        titles = (
            (
                await session.execute(select(Product.title).where(Product.bot_id == target.id))
            )
            .scalars()
            .all()
        )
        assert titles == ["Настоящий товар"]


@pytest.mark.asyncio
async def test_promote_keeps_copied_name_and_settings(db):
    """Главный трюк копии: promote_draft заполняет только пустое, так что
    название из старого магазина переживает подключение бота."""
    seller = await _seller(db)
    source = await _source_shop(db, seller)
    target, _ = await copy_shop_data(source.id, seller.id)

    promoted = await promote_draft(
        target.id, "789:token", "new_shop_bot", 222, bot_name="ИмяИзTelegram"
    )

    assert promoted.title == "Старый магазин"  # не «ИмяИзTelegram»
    assert promoted.shop_name == "Старый"
    assert promoted.welcome_text == "Привет, покупатель"
    # исходное Telegram-имя нового бота — от него, не от копии
    assert promoted.default_bot_name == "ИмяИзTelegram"


# --------------------------------------------------------------------------
# Лимиты тарифа
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plan_limit_caps_products(db, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "enforce_plan_limits", True)

    seller = await _seller(db)  # free: 10 товаров / 10 услуг
    source = await _source_shop(db, seller)
    async with db() as session:
        for i in range(12):
            session.add(
                Product(
                    seller_id=seller.id,
                    bot_id=source.id,
                    type="physical",
                    title=f"Т{i}",
                    price=Decimal("1"),
                )
            )
        session.add(
            Product(
                seller_id=seller.id, bot_id=source.id, type="digital", title="D1",
                price=Decimal("1"),
            )
        )
        await session.commit()

    target, result = await copy_shop_data(source.id, seller.id)

    assert result.products == 11  # 10 физических + 1 digital
    assert result.skipped_products == 2
    async with db() as session:
        count = len(
            (
                await session.execute(select(Product.id).where(Product.bot_id == target.id))
            )
            .all()
        )
        assert count == 11


# --------------------------------------------------------------------------
# Гард источника
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_refuses_foreign_and_draft_sources(db):
    seller = await _seller(db)
    draft = await create_draft(seller.id)

    with pytest.raises(LookupError):
        await copy_shop_data(999999, seller.id)
    with pytest.raises(LookupError):
        await copy_shop_data(draft.id, seller.id)  # черновик копировать нечего


# --------------------------------------------------------------------------
# Хендлер карточки
# --------------------------------------------------------------------------


def _callback(seller: Seller, bot_id: int):
    message = SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock())
    return SimpleNamespace(
        from_user=SimpleNamespace(id=seller.telegram_id),
        data=f"mybots:copy_yes:{bot_id}",
        answer=AsyncMock(),
        message=message,
    )


@pytest.mark.asyncio
async def test_copy_yes_handler_copies_and_offers_bot_creation(db):
    from app.handlers.hub.mybots import do_copy

    seller = await _seller(db)
    source = await _source_shop(db, seller)
    async with db() as session:
        session.add(
            Product(
                seller_id=seller.id,
                bot_id=source.id,
                type="physical",
                title="Товар",
                price=Decimal("5"),
            )
        )
        await session.commit()

    callback = _callback(seller, source.id)
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=True, username="hub")),
    ):
        await do_copy(callback)

    summary = callback.message.edit_text.call_args[0][0]
    assert "Копия магазина готова" in summary
    # кнопка создания бота уехала отдельным сообщением
    callback.message.answer.assert_called_once()

    async with db() as session:
        count = len(
            (
                await session.execute(
                    select(Product.id).where(
                        Product.bot_id != source.id,
                        Product.seller_id == seller.id,
                    )
                )
            ).all()
        )
        assert count == 1  # копия товара появилась в новом черновике


@pytest.mark.asyncio
async def test_copy_yes_handler_survives_telegram_failure(db):
    """Сбой Telegram-флага не должен терять результат копии: черновик уже
    создан, продавцу предлагают ручной путь."""
    from app.handlers.hub.mybots import do_copy

    seller = await _seller(db)
    source = await _source_shop(db, seller)

    callback = _callback(seller, source.id)
    with patch(
        "app.bots.hub.hub_bot.get_me",
        new=AsyncMock(return_value=SimpleNamespace(can_manage_bots=False, username="hub")),
    ):
        await do_copy(callback)

    summary = callback.message.edit_text.call_args[0][0]
    assert "Копия магазина готова" in summary
    callback.message.answer.assert_not_called()


# --------------------------------------------------------------------------
# Копия отзывов
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_copy_copies_reviews_as_inherited(db):
    """Отзывы переносятся как наследуемые: order_id=NULL, customer_id=NULL, source='inherited'."""
    from app.models import ProductReview, Product, SellerBot

    seller = await _seller(db)
    source = await _source_shop(db, seller)
    async with db() as session:
        product = Product(
            seller_id=seller.id,
            bot_id=source.id,
            type="physical",
            title="Товар с отзывом",
            price=Decimal("100"),
        )
        session.add(product)
        await session.flush()
        session.add(ProductReview(
            bot_id=source.id,
            product_id=product.id,
            order_id=123,  # обычный отзыв с заказом
            customer_id=456,
            rating=5,
            body="Отличный товар!",
            author_name="Иван И.",
            status="published",
            source="normal",
        ))
        session.add(ProductReview(
            bot_id=source.id,
            product_id=product.id,
            order_id=None,  # уже наследуемый
            customer_id=None,
            rating=4,
            body="Хорошо",
            author_name="Петр П.",
            status="pending",
            source="inherited",
        ))
        await session.commit()

    target, result = await copy_shop_data(source.id, seller.id)

    assert result.reviews_copied == 2
    async with db() as session:
        reviews = (
            await session.execute(
                select(ProductReview).where(ProductReview.bot_id == target.id)
            )
        ).scalars().all()
        assert len(reviews) == 2
        for r in reviews:
            assert r.order_id is None
            assert r.customer_id is None
            assert r.source == "inherited"
            assert r.rating in (5, 4)
            assert r.body in ("Отличный товар!", "Хорошо")
            # статус переносится как есть
            assert r.status in ("published", "pending")


@pytest.mark.asyncio
async def test_copy_reviews_affect_storefront_rating(db):
    """Рейтинг витрины нового магазина учитывает скопированные отзывы."""
    from app.models import ProductReview, Product, SellerBot

    seller = await _seller(db)
    source = await _source_shop(db, seller)
    async with db() as session:
        product = Product(
            seller_id=seller.id,
            bot_id=source.id,
            type="physical",
            title="Товар",
            price=Decimal("10"),
        )
        session.add(product)
        await session.flush()
        # 2 отзыва: 5 и 3 → среднее 4.0
        session.add(ProductReview(
            bot_id=source.id, product_id=product.id,
            order_id=1, customer_id=1, rating=5, source="normal",
        ))
        session.add(ProductReview(
            bot_id=source.id, product_id=product.id,
            order_id=2, customer_id=2, rating=3, source="normal",
        ))
        await session.commit()

    target, result = await copy_shop_data(source.id, seller.id)

    async with db() as session:
        # проверяем, что отзывы перенеслись
        reviews = (
            await session.execute(
                select(ProductReview).where(ProductReview.bot_id == target.id)
            )
        ).scalars().all()
        assert len(reviews) == 2
        ratings = [r.rating for r in reviews]
        assert sorted(ratings) == [3, 5]
        # все перенесённые отзывы — наследуемые
        for r in reviews:
            assert r.source == "inherited"
            assert r.order_id is None
            assert r.customer_id is None

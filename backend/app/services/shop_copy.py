"""Копия магазина: перенести содержимое старого бота в новый.

Запускается из карточки магазина в /mybots («Создать копию»). Цель — черновик
(create_draft): он уже имеет bot_id, к нему потом подключается обычный бот,
и promote_draft не трогает заполненные название и шапку витрины (гарды
«if not shop.title»), так что скопированные настройки переживают promote.

Переносится содержимое: настройки витрины, категории, товары с вариациями,
фото, логотип и способы оплаты. Не переносится то, что принадлежит людям и
истории (покупатели, заказы, отзывы, рассылки) и Telegram-объектам (каналы —
telegram_chat_id глобально уникален, нового бота в канал добавляет продавец).

Фото лежат в БД и адресуются строкой «/api/images/{token}» без внешнего
ключа. Копия получает СВОИ строки ProductImage с новыми токенами
(new_image_token): после удаления исходного магазина каскад унёс бы его
картинки, а вечный immutable-кэш браузера запрещает переиспользовать адреса.
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import get_session
from app.models import (
    Category,
    Product,
    ProductImage,
    ProductReview,
    ProductVariant,
    Seller,
    SellerBot,
    ShopLogo,
    ShopPaymentMethod,
)
from app.models.catalog import new_image_token
from app.plans import SERVICE_TYPES, limits_for
from app.services.shop_draft import create_draft
from app.services.variants import recompute_product_totals

logger = logging.getLogger(__name__)

# Тот же префикс, что и в остальных местах витрины (services/variants.py)
_IMAGE_PREFIX = "/api/images/"


@dataclass
class CopyResult:
    """Сколько чего переехало; skipped_products — урезано лимитом тарифа."""

    categories: int = 0
    products: int = 0
    variants: int = 0
    images: int = 0
    payment_methods: int = 0
    reviews_copied: int = 0
    skipped_products: int = 0
    logo: bool = False


def _image_token(url: str | None) -> str | None:
    """Токен из ссылки витрины. Чужое (внешний URL) — не наше, не трогаем."""
    if url and url.startswith(_IMAGE_PREFIX):
        tail = url[len(_IMAGE_PREFIX) :]
        if tail and "/" not in tail:
            return tail
    return None


@dataclass
class _ImageCloner:
    """Копирует строки ProductImage под новыми токенами, один экземпляр на
    операцию копирования: карта «старый токен → новый» не даёт размножить
    одну и ту же картинку, на которую ссылается несколько товаров."""

    session: object
    target_bot_id: int
    result: CopyResult
    _map: dict[str, str] = field(default_factory=dict)

    async def clone(self, old_token: str) -> str:
        if old_token in self._map:
            return self._map[old_token]
        source = (
            await self.session.execute(
                select(ProductImage).where(ProductImage.token == old_token)
            )
        ).scalar_one_or_none()
        if source is None:
            # ссылка без строки (битая) — адрес переносим как есть
            return old_token
        token = new_image_token()
        self.session.add(
            ProductImage(
                token=token,
                bot_id=self.target_bot_id,
                mime=source.mime,
                size=source.size,
                data=source.data,
            )
        )
        self._map[old_token] = token
        self.result.images += 1
        return token

    async def rewrite_url(self, url: str | None) -> str | None:
        old_token = _image_token(url)
        if old_token is None:
            return url
        return f"{_IMAGE_PREFIX}{await self.clone(old_token)}"

    async def rewrite_images(self, images: list | None) -> list | None:
        if not images:
            return images
        return [await self.rewrite_url(url) for url in images]


def _plan_caps(seller: Seller) -> tuple[int | None, int | None]:
    """Лимиты каталога тарифа; None — без ограничения. Пока флаг снят
    (enforce_plan_limits), лимиты не действуют — копия переносит всё."""
    if not get_settings().enforce_plan_limits:
        return None, None
    limits = limits_for(seller)
    return limits.max_products, limits.max_services


def _cap_products(
    products: list[Product], max_products: int | None, max_services: int | None
) -> tuple[list[Product], int]:
    """Первые N товаров/услуг по тарифу. Порядок по id: переносится то, что
    было заведено раньше — то же правило, по которому бесплатный тариф не
    даёт добавлять сверх лимита, ничего не удаляя."""
    if max_products is None and max_services is None:
        return products, 0
    physical = [p for p in products if p.type not in SERVICE_TYPES]
    services = [p for p in products if p.type in SERVICE_TYPES]
    if max_products is not None:
        physical = physical[:max_products]
    if max_services is not None:
        services = services[:max_services]
    kept = physical + services
    kept_ids = {p.id for p in kept}
    skipped = sum(1 for p in products if p.id not in kept_ids)
    return kept, skipped


async def copy_shop_data(source_bot_id: int, seller_id: int) -> tuple[SellerBot, CopyResult]:
    """Скопировать содержимое магазина продавца в его новый черновик.

    Возвращает черновик-цель и счётчики. Весь перенос — одна транзакция:
    обрыв посреди не должен оставлять магазин-недокопию.
    """
    result = CopyResult()

    async with get_session() as session:
        source = await session.get(SellerBot, source_bot_id)
        # копировать можно только свой настоящий магазин, а не чужой или черновик
        if (
            source is None
            or source.seller_id != seller_id
            or source.bot_token_encrypted is None
        ):
            raise LookupError("магазин не найден")
        seller = await session.get(Seller, seller_id)
        if seller is None:
            raise LookupError("продавец не найден")

        # черновик заводится своей сессией (он переиспользует незаконченный),
        # дальше цель работает внутри транзакции копирования
        target_id = (await create_draft(seller_id)).id
        target = await session.get(SellerBot, target_id)
        if target is None:
            raise LookupError("черновик-цель не найден")

        # переиспользованный черновик мог успеть набрать контент в брошенной
        # попытке — смешивать его с копией нельзя
        for table in (ProductVariant, Product, Category, ProductImage, ShopLogo, ShopPaymentMethod):
            await session.execute(delete(table).where(table.bot_id == target_id))
        await session.flush()

        # настройки витрины: promote_draft заполнит только пустое, так что
        # имя магазина и шапка переедут из источника без пост-обработки
        target.title = source.title
        target.shop_name = source.shop_name
        target.welcome_text = source.welcome_text
        target.show_catalog_button = source.show_catalog_button
        target.catalog_button_text = source.catalog_button_text

        images = _ImageCloner(session, target_id, result)

        # категории: порядок сохраняем, старый id → новый пригодится товарам
        category_map: dict[int, int] = {}
        categories = (
            (
                await session.execute(
                    select(Category)
                    .where(Category.bot_id == source_bot_id)
                    .order_by(Category.sort_order, Category.id)
                )
            )
            .scalars()
            .all()
        )
        for cat in categories:
            new_cat = Category(
                seller_id=seller_id,
                bot_id=target_id,
                name=cat.name,
                sort_order=cat.sort_order,
            )
            session.add(new_cat)
            await session.flush()
            category_map[cat.id] = new_cat.id
        result.categories = len(category_map)

        products = (
            (
                await session.execute(
                    select(Product)
                    .where(Product.bot_id == source_bot_id)
                    # вариации нужны сразу: ленивая загрузка в async-сессии
                    # падает MissingGreenlet'ом
                    .options(selectinload(Product.variants))
                    .order_by(Product.id)
                )
            )
            .scalars()
            .all()
        )
        products, result.skipped_products = _cap_products(
            products, *_plan_caps(seller)
        )

        # product_map: старый product_id -> новый product_id (для отзывов)
        product_map: dict[int, int] = {}

        for product in products:
            new_product = Product(
                seller_id=seller_id,
                bot_id=target_id,
                category_id=category_map.get(product.category_id),
                type=product.type,
                title=product.title,
                description=product.description,
                image_url=await images.rewrite_url(product.image_url),
                price=product.price,
                compare_at_price=product.compare_at_price,
                currency=product.currency,
                stock=product.stock,
                # JSONB-словарь копируем: разделять мутабельное между
                # магазинами не нужно
                digital_content=dict(product.digital_content)
                if product.digital_content
                else None,
                is_active=product.is_active,
            )
            new_variants = []
            for variant in product.variants:
                new_variants.append(
                    ProductVariant(
                        bot_id=target_id,
                        sku=variant.sku,
                        attributes=dict(variant.attributes) if variant.attributes else None,
                        title=variant.title,
                        description=variant.description,
                        price=variant.price,
                        compare_at_price=variant.compare_at_price,
                        stock=variant.stock,
                        images=await images.rewrite_images(variant.images),
                        position=variant.position,
                        is_active=variant.is_active,
                    )
                )
                result.variants += 1
            if new_variants:
                # присваиваем коллекцию, пока товар pending: похода в БД нет,
                # product_id расставится при flush по связи. Обращение к
                # .variants у уже зафиксированного объекта было бы ленивой
                # загрузкой — в async-сессии она падает MissingGreenlet'ом
                new_product.variants = new_variants
                recompute_product_totals(new_product)
            session.add(new_product)
            await session.flush()  # нужен new_product.id для product_map
            product_map[product.id] = new_product.id
            result.products += 1

        source_logo = (
            await session.execute(
                select(ShopLogo).where(ShopLogo.bot_id == source_bot_id)
            )
        ).scalar_one_or_none()
        if source_logo is not None:
            session.add(
                ShopLogo(
                    bot_id=target_id,
                    token=new_image_token(),
                    mime=source_logo.mime,
                    size=source_logo.size,
                    data=source_logo.data,
                )
            )
            result.logo = True

        # реквизиты — функция тарифа Pro: продавец без него методы создать
        # не мог бы, значит и в копию они не переезжают (та же проверка, что
        # в api/seller.py при создании)
        if limits_for(seller).p2p_payments:
            methods = (
                (
                    await session.execute(
                        select(ShopPaymentMethod).where(
                            ShopPaymentMethod.bot_id == source_bot_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            for method in methods:
                session.add(
                    ShopPaymentMethod(
                        bot_id=target_id,
                        kind=method.kind,
                        label=method.label,
                        # перешифровка через свойства, а не копия байтов:
                        # путь появления шифротекста не должен влиять
                        account=method.account,
                        holder=method.holder,
                        note=method.note,
                        is_active=method.is_active,
                    )
                )
                result.payment_methods += 1

        # отзывы — переносим без заказов/покупателей, как наследуемые
        # (source='inherited', order_id=NULL, customer_id=NULL)
        # товар должен существовать в копии (product_map)
        reviews = (
            await session.execute(
                select(ProductReview).where(ProductReview.bot_id == source_bot_id)
            )
        ).scalars()
        for review in reviews:
            if review.product_id in product_map:
                session.add(
                    ProductReview(
                        bot_id=target_id,
                        product_id=product_map[review.product_id],
                        order_id=None,
                        customer_id=None,
                        rating=review.rating,
                        body=review.body,
                        author_name=review.author_name,
                        status=review.status,
                        moderated_at=review.moderated_at,
                        reply_body=review.reply_body,
                        reply_at=review.reply_at,
                        source="inherited",
                    )
                )
                result.reviews_copied += 1

        await session.commit()
        await session.refresh(target)
        return target, result

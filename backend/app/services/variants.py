"""Вариации товара: сохранение набора и пересчёт витринных цены и остатка.

Товар либо без вариаций (цена и остаток на нём самом — так было всегда), либо
с одной и больше, и тогда правда живёт в вариации. Чтобы не переписывать
витрину, карточки, статистику и сверку платежей, `products.price` и
`products.stock` не выключаются, а пересчитываются здесь при каждом сохранении:
цена — минимальная по активным вариациям («от 500»), остаток — сумма.

Удалить вариацию, которую уже купили, нельзя: на неё ссылается order_items с
ON DELETE RESTRICT, и из старого заказа пропало бы то, за что человек заплатил.
Такая вариация деактивируется — ровно как товар в delete_product.
"""

import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy import inspect as sa_inspect

from app.models import OrderItem, Product, ProductVariant

logger = logging.getLogger(__name__)

# Свойства вариации — словарь произвольной формы, поэтому границы задаём мы
MAX_ATTRIBUTES = 10
MAX_ATTR_LEN = 64
MAX_IMAGES = 8
# Картинки принимаем только свои: адрес выдаёт наш же загрузчик. Чужая ссылка
# отсюда попала бы в <img src> на витрине у каждого покупателя
IMAGE_PREFIX = "/api/images/"


def variant_label(attributes: dict | None) -> str:
    """«Красный · M» — как вариация называется в заказе и в чеке."""
    if not attributes:
        return ""
    return " · ".join(str(v) for v in attributes.values() if str(v).strip())[:128]


def clean_attributes(attributes: dict | None) -> dict | None:
    if not attributes:
        return None
    cleaned = {}
    for key, value in list(attributes.items())[:MAX_ATTRIBUTES]:
        name = str(key).strip()[:MAX_ATTR_LEN]
        val = str(value).strip()[:MAX_ATTR_LEN]
        if name and val:
            cleaned[name] = val
    return cleaned or None


def clean_images(images: list | None) -> list | None:
    if not images:
        return None
    kept = [
        str(url)[:512]
        for url in images[:MAX_IMAGES]
        if isinstance(url, str) and url.startswith(IMAGE_PREFIX)
    ]
    return kept or None


def recompute_product_totals(product: Product) -> None:
    """Витринные цена и остаток товара — из активных вариаций.

    Без вариаций не трогаем ничего: у такого товара цена и остаток свои.
    """
    active = [v for v in product.variants if v.is_active]
    if not active:
        return
    product.price = min(Decimal(str(v.price)) for v in active)
    # Скидка у товара с вариациями — на вариации. Оставить своё старое число
    # значило бы зачеркнуть его рядом с «от 500», собранным из других цен.
    product.compare_at_price = None
    # Хоть одна вариация без ограничения — значит и товар без ограничения
    product.stock = (
        None
        if any(v.stock is None for v in active)
        else sum(v.stock for v in active)
    )


async def apply_variants(session, product: Product, incoming: list | None) -> None:
    """Привести набор вариаций товара к присланному.

    `incoming is None` — вариации в запросе не участвуют, оставляем как есть
    (так старый клиент, который про них не знает, не сотрёт их молча).
    Пустой список — вариаций у товара больше нет.
    """
    if incoming is None:
        return

    # После flush новый товар становится persistent, и обращение к коллекции
    # уходит в ленивую загрузку — в асинхронной сессии это MissingGreenlet.
    # Грузим явно, чтобы функция не зависела от того, что сделал вызывающий.
    if "variants" in sa_inspect(product).unloaded:
        await session.refresh(product, ["variants"])

    existing = {v.id: v for v in product.variants}
    seen: set[int] = set()

    for position, item in enumerate(incoming):
        data = {
            "sku": (item.sku or None),
            "attributes": clean_attributes(item.attributes),
            "price": item.price,
            "compare_at_price": item.compare_at_price,
            "stock": item.stock,
            "images": clean_images(item.images),
            "position": position,
            "is_active": item.is_active,
        }
        variant = existing.get(item.id) if item.id else None
        if variant is None:
            variant = ProductVariant(product_id=product.id, bot_id=product.bot_id, **data)
            session.add(variant)
            product.variants.append(variant)
        else:
            for key, value in data.items():
                setattr(variant, key, value)
            seen.add(variant.id)

    # Пропавшие из запроса: удаляем, а купленные — деактивируем
    for variant_id, variant in existing.items():
        if variant_id in seen:
            continue
        sold = (
            await session.execute(
                select(func.count())
                .select_from(OrderItem)
                .where(OrderItem.variant_id == variant_id)
            )
        ).scalar_one()
        if sold:
            variant.is_active = False
            logger.info("Вариация %s куплена — деактивирована вместо удаления", variant_id)
        else:
            product.variants.remove(variant)
            await session.delete(variant)

    await session.flush()
    recompute_product_totals(product)

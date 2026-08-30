import secrets

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, LargeBinary, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin

JsonB = JSON().with_variant(JSONB(), "postgresql")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    # Каждый бот — отдельный магазин: каталог не шарится между ботами продавца
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Product(Base, CreatedAtMixin):
    """Товары и услуги в одной таблице; различаются полем type.
    Для digital/service контент выдачи (ссылка/файл/инвайт/главы) лежит в digital_content."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id", ondelete="CASCADE"), index=True)
    # Магазин, которому принадлежит товар (см. Category.bot_id)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))

    type: Mapped[str] = mapped_column(String(16))  # physical | digital | service
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(512))

    # MVP: единая валюта каталога — USDT (решение владельца от 2026-08-18)
    price: Mapped[float] = mapped_column(Numeric(18, 6))
    # Зачёркнутая «старая» цена товара без вариаций. У товара с вариациями
    # скидка живёт на вариации (ProductVariant.compare_at_price), а здесь
    # обнуляется при пересчёте: витринная цена там — минимум по вариациям,
    # и зачёркивать рядом с ней чужое число было бы враньём.
    compare_at_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str] = mapped_column(String(8), default="USDT")

    # Остаток на складе; None — не ограничен (услуги/digital без учёта штук).
    # Списывается при оплате заказа (см. app/payments/service.py), не при чекауте
    stock: Mapped[int | None] = mapped_column(Integer)

    digital_content: Mapped[dict | None] = mapped_column(JsonB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    seller = relationship("Seller", back_populates="products")
    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.position",
    )


class ProductVariant(Base, CreatedAtMixin):
    """Вариация товара: цвет, размер, комплектация.

    Товар либо не имеет вариаций вовсе (тогда цена и остаток живут на нём
    самом — так работали все товары до этой таблицы), либо имеет их одну и
    больше, и тогда источник правды по цене, остатку и фотографиям — вариация.

    `products.price` и `products.stock` при этом не выключаются, а
    пересчитываются при сохранении: цена — минимальная из вариаций («от 500»),
    остаток — сумма. Благодаря этому витрина, карточки товара, статистика и
    сверка платежей читают товар ровно как раньше и ничего про вариации не
    знают — знать о них обязаны только корзина, оформление заказа и списание
    остатка.
    """

    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    # Дублируем магазин, как и в остальном каталоге: изоляция по bot_id — это
    # то, что проверяется в каждом запросе, и джойн ради неё был бы лишним
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )

    # Артикул продавца. Не уникален на уровне базы намеренно: у продавцов
    # своя нумерация, и падать при сохранении из-за совпадения — не наше дело
    sku: Mapped[str | None] = mapped_column(String(64))

    # Свойства вариации: {"Цвет": "Красный", "Размер": "M"}. Словарём, а не
    # колонками, потому что набор свойств у каждого товара свой
    attributes: Mapped[dict | None] = mapped_column(JsonB)

    # Своё название и описание. Вариации одного товара — не всегда «то же
    # самое, но красное»: у комплектаций и тарифов расходятся и название, и
    # текст. NULL — берётся товарное (так выглядят вариации до этих колонок).
    # На витрине карточка в сетке показывает товарное, а страница товара —
    # название выбранной вариации.
    title: Mapped[str | None] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)

    price: Mapped[float] = mapped_column(Numeric(18, 6))
    # Зачёркнутая «старая» цена. None — скидки нет
    compare_at_price: Mapped[float | None] = mapped_column(Numeric(18, 6))

    # Остаток этой вариации; None — не ограничен (как и у товара)
    stock: Mapped[int | None] = mapped_column(Integer)

    # Адреса картинок вариации — тот же формат, что и products.image_url
    # («/api/images/{token}»), только списком. Отдельной таблицы не заводим:
    # хранилище байтов уже есть (ProductImage), и оно одно на весь каталог
    images: Mapped[list | None] = mapped_column(JsonB)

    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product = relationship("Product", back_populates="variants")


def new_image_token() -> str:
    """Случайный адрес картинки (см. ProductImage.token)."""
    return secrets.token_urlsafe(16)


class ProductImage(Base, CreatedAtMixin):
    """Загруженные фото товаров лежат в БД: файловая система контейнера
    эфемерна (Railway), отдельного S3 у проекта нет. Байты не больше
    MAX_IMAGE_BYTES (app/services/images.py), тип — только из белого списка."""

    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Адрес картинки — случайный токен, а не порядковый id. Ответ отдаётся
    # с Cache-Control: immutable на год, поэтому адрес не должен переиспользоваться
    # никогда: после сброса базы нумерация начиналась заново, и браузер отдавал
    # из кэша чужую старую картинку по совпавшему адресу.
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=new_image_token
    )
    # фото принадлежит конкретному магазину — как и весь его каталог
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), index=True
    )
    # определяется по содержимому при загрузке (сниффер магических байтов),
    # присланному клиентом content-type доверия нет
    mime: Mapped[str] = mapped_column(String(32))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class ShopLogo(Base, CreatedAtMixin):
    """Логотип магазина, загруженный продавцом из кабинета: аватар-кружок
    в шапке витрины. Хранится в БД по образцу ProductImage; без лого витрина
    показывает первую букву имени.

    Один лого на магазин. Обновление целиком удаляет старую строку и вставляет
    новую, поэтому адрес (токен) всегда меняется — immutable-кэш браузера
    не отдаст старую картинку по адресу новой."""

    __tablename__ = "shop_logos"

    id: Mapped[int] = mapped_column(primary_key=True)
    bot_id: Mapped[int] = mapped_column(
        ForeignKey("seller_bots.id", ondelete="CASCADE"), unique=True, index=True
    )
    token: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default=new_image_token
    )
    mime: Mapped[str] = mapped_column(String(32))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)

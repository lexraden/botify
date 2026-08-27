"""Язык и тексты покупательских уведомлений (пуши бота магазина покупателю).

Решение владельца — «как в Mini App»: ручной выбор языка в профиле главнее
всего; без него русский идёт тем, у кого Telegram настроен на русский, всем
остальным — английский (дефолт платформы EN).

Продавецские пуши в hub и интерактивные тексты бота сюда не входят — они
остаются русскими. Динамика (названия товаров, треки, ссылки, тексты
продавца) не переводится; html.escape остаётся на местах вызова.
"""

from app.models import Customer
from app.services.channels import CUSTOMER_LOCALES


def buyer_locale(customer: Customer | None) -> str:
    """RU/EN для уведомлений конкретному покупателю."""
    if customer is not None and customer.locale in CUSTOMER_LOCALES:
        return customer.locale
    code = str(customer.language_code or "").lower() if customer is not None else ""
    return "ru" if code.startswith("ru") else "en"


TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "paid.header": "✅ Order #{id} paid!",
        "paid.materials": "📬 Your files:",
        "paid.preparing": "The seller is preparing your order — shipping details will arrive here.",
        "paid.review": "⭐ How did it go? Rate your purchase in “My orders”.",
        "paid.sold_out": (
            "⚠️ While the payment was going through, these sold out: {items}.\n"
            "The seller will reach out in the order chat — write to them right here."
        ),
        "fulfill.header": "📦 The seller shipped order #{id}!",
        "fulfill.photo_one": "The parcel is in the photo below.",
        "fulfill.photo_many": "Parcel photos below ({n}).",
        "fulfill.hint": "📬 Once it arrives, mark it received in “My orders” — you can rate it there too.",
        "chat.header": "💬 Order #{id}",
        "note.sent": "📦 Order #{id} shipped.",
    },
    "ru": {
        "paid.header": "✅ Заказ #{id} оплачен!",
        "paid.materials": "📬 Твои материалы:",
        "paid.preparing": "Продавец готовит заказ — детали доставки придут сюда.",
        "paid.review": "⭐ Как всё прошло? Оцени покупки в разделе «Мои покупки».",
        "paid.sold_out": (
            "⚠️ Пока шла оплата, закончилось: {items}.\n"
            "Продавец свяжется с тобой в чате заказа — напиши ему прямо здесь."
        ),
        "fulfill.header": "📦 Продавец отправил заказ #{id}!",
        "fulfill.photo_one": "Посылка на фото ниже.",
        "fulfill.photo_many": "Фото посылки ниже ({n} шт.).",
        "fulfill.hint": "📬 Получишь — отметь в «Моих покупках», там же можно оценить.",
        "chat.header": "💬 Заказ #{id}",
        "note.sent": "📦 Заказ #{id} отправлен.",
    },
}


def text(locale: str, key: str, **kw) -> str:
    """Шаблон по языку. Неизвестный язык -> EN (дефолт платформы)."""
    return TEXTS.get(locale, TEXTS["en"])[key].format(**kw)


def buyer_text(customer: Customer | None, key: str, **kw) -> str:
    return text(buyer_locale(customer), key, **kw)

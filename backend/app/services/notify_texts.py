"""Язык и тексты покупательских сообщений бота магазина.

Решение владельца — «как в Mini App»: ручной выбор языка в профиле главнее
всего; без него русский идёт тем, у кого Telegram настроен на русский, всем
остальным — английский (дефолт платформы EN).

Здесь живут и пуши (paid.*, fulfill.*), и строки самого бота, которые видит
покупатель: приветствие-дефолт, кнопка витрины, «Я не робот», ошибки чата
заказа. Чего здесь нет: экраны настроек и всё, что написал сам продавец
(welcome_text, catalog_button_text, приветствие канала) — это его слова,
а не наши строки, переводить их не нужно. Продавецские пуши в hub тоже
остаются русскими. Динамика (названия товаров, треки, ссылки) не
переводится; html.escape остаётся на местах вызова.
"""

from app.models import Customer
from app.services.channels import CUSTOMER_LOCALES


def buyer_locale(customer: Customer | None) -> str:
    """RU/EN для уведомлений конкретному покупателю.

    Правило то же, что во фронте (`webapp/src/services/locale.js`), и входы те
    же: явный выбор и `language_code`. Расходятся они, когда `customers.locale`
    у нас есть, а localStorage на устройстве уже нет (чистка кэша, переустановка,
    другое устройство): приложение снова определяет язык само, а пуши идут на
    прежнем выбранном. Отсюда и начинается разбор жалобы «бот пишет не на том
    языке» — лечится повторным переключением в профиле.
    """
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
        # строки самого бота магазина покупателю (кроме написанных продавцом)
        "start.welcome": "Welcome to the <b>@{username}</b> shop!",
        "start.button": "🛍 Open the shop",
        "start.my_orders": "🧾 My orders",
        "robot.button": "I'm not a robot 🤖",
        "start.robot_confirmed": "✅ Verification passed",
        "channel.approved": (
            "Your request to “{channel}” was approved ✅\n\n"
            "Tap the “{button}” button at the bottom of the screen 👇"
        ),
        "chat.locked": "This chat is closed for new messages — the window for discussing the order has expired.",
        "chat.rate_limited": "Too many messages in a row — wait a moment.",
        "chat.too_long": "The message is too long — 1000 characters max.",
        "chat.photo_too_big": "The photo is too large — 5 MB max.",
        "chat.bad_image": "Please send an actual photo — JPEG, PNG, WebP or GIF.",
        "chat.photo_failed": "Couldn't accept the photo — please try sending it again.",
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
        # строки самого бота магазина покупателю (кроме написанных продавцом)
        "start.welcome": "Добро пожаловать в магазин <b>@{username}</b>!",
        "start.button": "🛍 Открыть каталог",
        "start.my_orders": "🧾 Мои покупки",
        "robot.button": "Я не робот 🤖",
        "start.robot_confirmed": "✅ Проверка пройдена",
        "channel.approved": (
            "Заявка в «{channel}» принята ✅\n\n"
            "Нажми кнопку «{button}» внизу экрана 👇"
        ),
        "chat.locked": "Этот чат закрыт для новых сообщений — окно для обсуждения заказа истекло.",
        "chat.rate_limited": "Слишком много сообщений подряд — подожди немного.",
        "chat.too_long": "Сообщение слишком длинное — максимум 1000 символов.",
        "chat.photo_too_big": "Фото слишком большое — максимум 5 МБ.",
        "chat.bad_image": "Пришли, пожалуйста, именно фото — JPEG, PNG, WebP или GIF.",
        "chat.photo_failed": "Не получилось принять фото — попробуй отправить ещё раз.",
    },
}


def text(locale: str, key: str, **kw) -> str:
    """Шаблон по языку. Неизвестный язык -> EN (дефолт платформы)."""
    return TEXTS.get(locale, TEXTS["en"])[key].format(**kw)


def buyer_text(customer: Customer | None, key: str, **kw) -> str:
    return text(buyer_locale(customer), key, **kw)

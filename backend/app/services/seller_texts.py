"""Язык и тексты продавецских сообщений hub-бота.

Команда /lang даёт продавцу ручной выбор RU/EN (sellers.locale), и все
сообщения hub-бота — интерактивные экраны и фоновые пуши — уходят на
выбранном языке. Правило языка:

1. Ручной выбор в /lang главнее всего (sellers.locale).
2. Без него: ru* по language_code — RU, любой другой непустой — EN.
3. language_code неизвестен (None) — RU: hub всегда был русскоязычным, и
   молча переводить существующих продавцов на EN нельзя. У покупателей
   правило обратное (там EN — платформенный дефолт), это осознанное
   различие, а не рассинхрон.

Здесь живут все продавецские строки: меню магазинов, карточка, онбординг
/newshop, администраторы, пуши о заказах/выплатах/отзывах/токенах. Чего
здесь нет: команды супер-админа платформы (handlers/hub/admin.py —
внутренний инструмент), экраны настроек внутри seller-бота и всё, что
написал сам продавец (названия товаров, тексты каналов). html.escape
остаётся на местах вызова; RU-строки держатся байт-в-байт прежними, чтобы
не трогать сложившиеся тесты.
"""

from app.models import Seller

SELLER_LOCALES = ("ru", "en")


def seller_locale(seller: Seller | None) -> str:
    """RU/EN для сообщений конкретному продавцу (см. докстринг модуля)."""
    if seller is None:
        return "ru"
    # getattr: продавец может прийти упрощённым фейком (тесты), а не строкой БД
    locale = getattr(seller, "locale", None)
    if locale in SELLER_LOCALES:
        return locale
    code = str(getattr(seller, "language_code", None) or "ru").lower()
    return "ru" if code.startswith("ru") else "en"


def seller_text(seller: Seller | None, key: str, **kw) -> str:
    return text(seller_locale(seller), key, **kw)


TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        # --- /start ---
        "start.welcome": (
            "👋 Привет! Это <b>Botify</b> — платформа для продажи товаров и услуг "
            "через собственного Telegram бота.\n\n"
            "Здесь ты можешь:\n"
            "• принимать оплату в <b>USDT</b>\n"
            "• подключить <b>своего бота</b>\n"
            "• добавить <b>товары и услуги</b> в каталог\n"
            "• собирать <b>базу покупателей</b> и делать рассылки\n\n"
            "Начни продавать — жми кнопку 👇"
        ),
        "start.welcome_back": "👋 С возвращением!\n\n{status}",
        "start.back_one": "Твой магазин <b>@{username}</b> работает 🟢",
        "start.back_many": "Работает магазинов: <b>{n}</b> 🟢",
        "start.no_webapp": (
            "⚠️ Приложение пока не настроено: у платформы не задан публичный адрес. "
            "Загляни позже."
        ),
        "btn.open_app": "🚀 Открыть приложение",
        "btn.my_shops": "🏪 Мои магазины",
        "btn.admin_shops": "🛠 Магазины, где я администратор",
        "hub.no_seller": "Сначала нажми /start — я заведу тебя в системе.",
        "msg.register": "Нажми /start, чтобы зарегистрироваться.",
        # --- /lang ---
        "lang.prompt": (
            "🌍 Язык сообщений этого бота. Сейчас: <b>{current}</b>.\n\n"
            "Выбери — и весь интерфейс перейдёт на него."
        ),
        "lang.name.ru": "русский",
        "lang.name.en": "английский",
        "lang.btn.ru": "🇷🇺 Русский",
        "lang.btn.en": "🇬🇧 English",
        "lang.done.ru": "✅ Язык переключён на русский.",
        "lang.done.en": "✅ Language switched to English.",
        # --- /mybots: меню и карточка ---
        "shops.header": "🏪 <b>Твои магазины</b>",
        "shops.pitch": "Каждый бот живёт своей жизнью: свой каталог, свои покупатели, своя касса.",
        "shops.none": "У тебя пока нет подключённых магазинов.",
        "shops.word": "магазин",
        "status.draft": "⚪ <b>{name}</b> — бот не создан, /newshop",
        "status.disabled": "⚪ <b>@{username}</b> — отключён",
        "status.revoked": "{icon} <b>@{username}</b> — токен отозван, {fix}",
        "status.fix.managed": "нажми «Восстановить»",
        "status.fix.unmanaged": "подключи заново",
        "status.active": "{icon} <b>@{username}</b> — включён",
        "btn.add_shop": "➕ Подключить ещё магазин",
        "card.draft": (
            "⚪ <b>{name}</b> — бот не создан\n\n"
            "Магазин заведён, осталось создать бота: /newshop"
        ),
        "card.revoked": (
            "🔴 <b>@{username}</b> — токен отозван\n\n"
            "Магазин не получает сообщения от покупателей."
        ),
        "card.active": "{icon} <b>{label}</b> — работает",
        "card.disabled": "⚪ <b>{label}</b> — отключён",
        "btn.restore": "🔄 Восстановить магазин",
        "btn.off": "🔌 Отключить",
        "btn.on": "🔁 Включить",
        "btn.delete": "🗑 Удалить",
        "btn.admins": "👥 Администраторы",
        "btn.settings": "⚙️ Настройки бота",
        "btn.back_all": "⬅️ Все магазины",
        "alert.start_first": "Сначала /start",
        "alert.bot_not_found": "Бот не найден",
        "off.confirm": (
            "Отключить <b>@{username}</b>?\n\n"
            "Бот перестанет отвечать покупателям и принимать заявки в каналы. "
            "База покупателей, товары и заказы сохранятся — включить можно в любой момент."
        ),
        "btn.yes_off": "Да, отключить",
        "btn.cancel": "Отмена",
        "toast.off": "Отключён",
        "alert.draft_no_bot": "Сначала создай бота: /newshop",
        "toast.on": "Включён",
        "del.confirm": (
            "Удалить <b>{label}</b> навсегда?\n\n"
            "⚠️ Вместе с ботом удалится его база покупателей и история рассылок. "
            "Это необратимо."
        ),
        "btn.yes_delete": "🗑 Да, удалить навсегда",
        "toast.deleted": "Удалён",
        "del.has_orders": (
            "У покупателей <b>@{username}</b> есть заказы — историю продаж "
            "удалять нельзя, поэтому бот просто отключён. Подключить обратно: /mybots."
        ),
        "restore.doing": "Восстанавливаю…",
        "restore.restored": (
            "✅ Магазин <b>@{username}</b> снова работает.\n\n"
            "Токен перевыпущен, покупатели опять доходят. Старый токен из "
            "@BotFather больше не действует."
        ),
        "restore.already_ok": "Магазин <b>@{username}</b> уже работает — восстанавливать нечего.",
        "restore.webhook_pending": (
            "Токен для <b>@{username}</b> выпущен, но магазин ещё не принимает "
            "сообщения — вебхук не встал с первого раза.\n\n"
            "Загляни в /mybots через минуту. Старый токен из @BotFather уже "
            "не действует, брать его оттуда заново не нужно."
        ),
        "restore.not_managed": (
            "Бота <b>@{username}</b> создавал не я, поэтому выпустить ему токен "
            "не могу. Возьми свежий токен в @BotFather и подключи магазин заново."
        ),
        "restore.failed": (
            "Не вышло восстановить <b>@{username}</b>. Возможно, у платформы "
            "забрали доступ к боту в @BotFather. Подключить можно и вручную — "
            "свежим токеном оттуда же."
        ),
        # --- /newshop ---
        "newshop.management_off": (
            "Создание бота одной кнопкой пока не включено у платформы.\n\n"
            "Это чинится в @BotFather: открой его мини-апп (синяя кнопка «Open» слева "
            "от поля ввода) → выбери бота платформы → включи <b>Bot Management Mode</b>. "
            "Флаг приходит только в getMe, в обычном меню настроек его нет.\n\n"
            "Пока не включено — подключай бота как раньше, токеном через приложение."
        ),
        "newshop.ask_title": (
            "Как назовём магазин?\n\n"
            "Название увидят покупатели в шапке витрины — из него же я предложу "
            "адрес для бота.\n\n"
            "Например: <b>Кофейня у дома</b>"
        ),
        "newshop.cancel": "Ок, отложим. Захочешь вернуться — /newshop.",
        "newshop.need_title": "Нужно название магазина — просто напиши его текстом.",
        "newshop.title_too_long": "Слишком длинное название — до {n} символов.",
        "newshop.ready": (
            "Магазин <b>{title}</b> готов.\n\n"
            "Остался бот — через него покупатели попадут в витрину. "
            "Создам его сам, тебе только подтвердить.\n\n"
            "Предложу адрес: <code>@{username}</code> — Telegram даст поправить, "
            "если он занят."
        ),
        "newshop.btn_create": "🤖 Создать бота «{title}»",
        "newshop.no_draft": (
            "Бот создан, но магазина для него нет. Начни с /newshop — "
            "и я подключу его к новому магазину."
        ),
        "newshop.token_failed": (
            "Бот создан, но забрать его токен не вышло. "
            "Напиши мне — разберёмся вручную."
        ),
        "newshop.promote_failed": "Бот создан, но подключить его не вышло: {error}.",
        "newshop.done": "✅ Магазин <b>{title}</b> подключён к @{username}.\n\n{next}",
        "newshop.done_next": "Открой приложение и добавь первый товар.",
        "newshop.done_webhook": (
            "Бот создан, но вебхук пока не встал — сообщения покупателей "
            "могут не доходить. Загляни в /mybots через минуту."
        ),
        # --- администраторы магазина ---
        "admins.note": (
            "Админ ведёт товары, заказы, отзывы и рассылки наравне с владельцем. "
            "Деньги выводит только владелец."
        ),
        "admins.none_shops": (
            "Ты пока не администратор ни одного магазина.\n\n"
            "Владелец магазина выдаёт доступ в карточке своего магазина — по твоему "
            "@username в Botify."
        ),
        "admins.header": "🛠 <b>Магазины, где ты администратор</b>",
        "admins.nameless": "без имени",
        "admins.menu_title": "👥 <b>Администраторы {label}</b>",
        "admins.menu_empty": "Пока никого — магазин ведёшь только ты.",
        "btn.add_admin": "➕ Добавить админа",
        "btn.back_to_shop": "⬅️ К магазину",
        "admins.ask_contact": (
            "Кого сделать администратором <b>{label}</b>?\n\n"
            "Пришли @username или числовой ID.\n\n"
            "Человек должен быть зарегистрирован в Botify — хоть раз нажать /start "
            "в этом боте. Иначе я его не знаю и добавить не смогу.\n\n"
            "{note}."
        ),
        "admins.cancel": "Ок, отложим. Захочешь — кнопка «Администраторы» в карточке магазина.",
        "admins.shop_not_found": "Магазин не найден.",
        "admins.bad_contact": (
            "Не похоже на @username или ID. Юзернейм — от 5 символов: "
            "буквы, цифры и подчёркивания."
        ),
        "admins.unknown": (
            "Никого такого в Botify нет.\n\n"
            "Человек должен был хоть раз нажать /start в этом боте — проверь "
            "написание. Если он заходил без юзернейма, попроси у него числовой ID."
        ),
        "admins.is_owner": "Это ты и есть — владелец магазина 🙂",
        "admins.already": "Он уже администратор этого магазина.",
        "admins.added": (
            "✅ {name} теперь администратор {label}.\n\n"
            "Я написал ему — магазин появится в его /start."
        ),
        "admins.btn_push": "🛠 Магазины, где я админ",
        "push.admin_assigned": (
            "🛠 Тебе выдали права администратора магазина "
            "<b>{label}</b>.\n\n{note}.\n\n"
            "Кнопка «Магазины, где я администратор» появится у тебя в /start."
        ),
        "admins.remove_confirm": (
            "Убрать <b>{name}</b> "
            "из администраторов {label}? Он потеряет доступ к кабинету магазина."
        ),
        "admins.name_fallback": "этого человека",
        "btn.remove": "Убрать",
        "toast.removed": "Убран",
        "toast.already_removed": "Уже убран",
        "push.admin_removed": (
            "Тебя убрали из администраторов магазина "
            "<b>{label}</b> — доступ к его кабинету закрыт."
        ),
        # --- пуши из фоновых сервисов и API ---
        "push.paid": "💰 Твой товар купили! Заказ #{id} на {total} USDT оплачен.\n{next}",
        "push.paid_digital": "Digital-контент выдан автоматически.",
        "push.paid_fulfill": "Открой кабинет, чтобы отправить заказ и прикрепить трек/ссылку.",
        "push.paid_sold_out": (
            "\n\n⚠️ Не хватило остатка: {items}.\n"
            "Деньги за заказ уже приняты — свяжись с покупателем в чате заказа."
        ),
        "push.payout_sent": (
            "💸 Выплата <b>{amount} USDT</b> по магазину @{shop} "
            "отправлена в @CryptoBot."
        ),
        "push.payout_fail": "⚠️ Выплата {amount} USDT пока не ушла.\n{hint}",
        "payout.hint.not_started": "Открой @CryptoBot и нажми Start — деньги придут туда.",
        "payout.hint.disabled": "Переводы отключены в настройках платформы — я уже разбираюсь.",
        "payout.hint.not_enough": "На стороне платформы не хватило баланса — попробуй вывести позже.",
        "payout.hint.default": "Деньги на месте: нажми «Вывести» ещё раз, когда проблема уйдёт.",
        "push.revoked.head": (
            "🔴 Магазин @{username} перестал получать сообщения.\n\n"
            "Похоже, токен бота отозван или перевыпущен в @BotFather — покупатели "
            "сейчас не могут ни написать, ни оформить заказ.\n\n"
        ),
        "push.revoked.managed": (
            "Этого бота создавал я, поэтому починить могу сам: нажми кнопку, и я "
            "выпущу новый токен.\n\n"
            "⚠️ Тот токен, который ты получил в @BotFather, после этого работать "
            "перестанет. Если он нужен тебе для своих скриптов — не восстанавливай, "
            "напиши мне."
        ),
        "push.revoked.unmanaged": (
            "Чтобы починить: возьми в @BotFather свежий токен этого бота и подключи "
            "магазин заново — каталог, заказы и касса останутся на месте."
        ),
        "push.stuck.one": "📦 Заказ оплачен больше {hours} ч назад, но ещё не отправлен:",
        "push.stuck.many": "📦 Заказы оплачены больше {hours} ч назад, но ещё не отправлены:",
        "push.stuck.item": "• Заказ #{id} на {amount} {currency} (@{shop})",
        "push.stuck.more": "• …и ещё {n}",
        "push.stuck.tail": (
            "\n\nПокупатель уже заплатил и ждёт. Открой кабинет и отправь — "
            "или напиши ему в чат заказа, если нужна пауза."
        ),
        "push.review.head": "⭐ Новый отзыв о «{title}»: {stars}\n",
        "push.review.body": "«{body}»\n",
        "push.review.tail": "Ответить можно в кабинете, вкладка «Отзывы».",
        "push.chat_message": "💬 Новое сообщение по заказу #{id}{photo} — открой кабинет.",
        "push.channel_added": (
            "✅ Бот @{username} добавлен в «{title}».\n"
            "Заявки на вступление будут приниматься автоматически, а каждый "
            "вступивший — попадать в твою базу."
        ),
        # --- дубли из API (connect/disable/enable/delete/name) ---
        "api.connected": (
            "🎉 Бот <b>@{username}</b> подключён!\n\n"
            "Что дальше:\n"
            "• добавь первый товар или услугу в приложении\n"
            "• поделись ссылкой на бота с покупателями — каждый, кто напишет ему, "
            "попадёт в твою базу"
        ),
        "btn.open_shop": "🏪 Открыть магазин",
        "api.disabled": (
            "⚪ Магазин <b>@{username}</b> отключён через приложение.\n"
            "Бот не отвечает покупателям, база, товары и заказы сохранены."
        ),
        "api.enabled": "🟢 Магазин <b>@{username}</b> включён — бот снова работает.",
        "api.deleted": "🗑 Магазин <b>@{username}</b> удалён вместе с базой покупателей.",
        "api.has_orders": (
            "У покупателей <b>@{username}</b> есть заказы — историю продаж "
            "удалять нельзя, поэтому магазин просто отключён."
        ),
        "api.name_set": "🏪 Название магазина теперь <b>{name}</b>.",
        "api.name_reset": "🏪 Название магазина сброшено к <b>@{username}</b>.",
    },
    "en": {
        # --- /start ---
        "start.welcome": (
            "👋 Hi! This is <b>Botify</b> — a platform for selling goods and services "
            "through your own Telegram bot.\n\n"
            "Here you can:\n"
            "• accept payments in <b>USDT</b>\n"
            "• connect <b>your own bot</b>\n"
            "• add <b>products and services</b> to a catalog\n"
            "• build a <b>customer base</b> and send broadcasts\n\n"
            "Start selling — tap the button 👇"
        ),
        "start.welcome_back": "👋 Welcome back!\n\n{status}",
        "start.back_one": "Your shop <b>@{username}</b> is up 🟢",
        "start.back_many": "Shops up and running: <b>{n}</b> 🟢",
        "start.no_webapp": (
            "⚠️ The app isn't set up yet: the platform has no public address. "
            "Check back later."
        ),
        "btn.open_app": "🚀 Open the app",
        "btn.my_shops": "🏪 My shops",
        "btn.admin_shops": "🛠 Shops I administer",
        "hub.no_seller": "Tap /start first — that's how I register you.",
        "msg.register": "Tap /start to register.",
        # --- /lang ---
        "lang.prompt": (
            "🌍 The language of this bot's messages. Current: <b>{current}</b>.\n\n"
            "Pick one — the whole interface switches to it."
        ),
        "lang.name.ru": "Russian",
        "lang.name.en": "English",
        "lang.btn.ru": "🇷🇺 Русский",
        "lang.btn.en": "🇬🇧 English",
        "lang.done.ru": "✅ Язык переключён на русский.",
        "lang.done.en": "✅ Language switched to English.",
        # --- /mybots: menu and card ---
        "shops.header": "🏪 <b>Your shops</b>",
        "shops.pitch": (
            "Every bot lives its own life: its own catalog, its own customers, its own till."
        ),
        "shops.none": "You have no shops connected yet.",
        "shops.word": "shop",
        "status.draft": "⚪ <b>{name}</b> — bot not created, use /newshop",
        "status.disabled": "⚪ <b>@{username}</b> — disabled",
        "status.revoked": "{icon} <b>@{username}</b> — token revoked, {fix}",
        "status.fix.managed": "tap “Restore”",
        "status.fix.unmanaged": "reconnect it",
        "status.active": "{icon} <b>@{username}</b> — enabled",
        "btn.add_shop": "➕ Connect another shop",
        "card.draft": (
            "⚪ <b>{name}</b> — bot not created\n\n"
            "The shop is set up, all that's left is the bot: /newshop"
        ),
        "card.revoked": (
            "🔴 <b>@{username}</b> — token revoked\n\n"
            "The shop isn't receiving messages from customers."
        ),
        "card.active": "{icon} <b>{label}</b> — running",
        "card.disabled": "⚪ <b>{label}</b> — disabled",
        "btn.restore": "🔄 Restore the shop",
        "btn.off": "🔌 Disable",
        "btn.on": "🔁 Enable",
        "btn.delete": "🗑 Delete",
        "btn.admins": "👥 Admins",
        "btn.settings": "⚙️ Bot settings",
        "btn.back_all": "⬅️ All shops",
        "alert.start_first": "Tap /start first",
        "alert.bot_not_found": "Bot not found",
        "off.confirm": (
            "Disable <b>@{username}</b>?\n\n"
            "The bot will stop answering customers and accepting channel join requests. "
            "Your customer base, products and orders are kept — you can re-enable it any time."
        ),
        "btn.yes_off": "Yes, disable",
        "btn.cancel": "Cancel",
        "toast.off": "Disabled",
        "alert.draft_no_bot": "Create the bot first: /newshop",
        "toast.on": "Enabled",
        "del.confirm": (
            "Delete <b>{label}</b> for good?\n\n"
            "⚠️ The bot's customer base and broadcast history will be deleted with it. "
            "This can't be undone."
        ),
        "btn.yes_delete": "🗑 Yes, delete forever",
        "toast.deleted": "Deleted",
        "del.has_orders": (
            "Customers of <b>@{username}</b> have orders — sales history "
            "can't be deleted, so the shop is just disabled. Reconnect: /mybots."
        ),
        "restore.doing": "Restoring…",
        "restore.restored": (
            "✅ Shop <b>@{username}</b> is back up.\n\n"
            "The token was reissued and customers get through again. The old token "
            "from @BotFather no longer works."
        ),
        "restore.already_ok": "Shop <b>@{username}</b> is already running — nothing to restore.",
        "restore.webhook_pending": (
            "A token for <b>@{username}</b> was issued, but the shop isn't receiving "
            "messages yet — the webhook didn't stick on the first try.\n\n"
            "Check /mybots in a minute. The old token from @BotFather is dead already; "
            "don't grab it again."
        ),
        "restore.not_managed": (
            "I didn't create <b>@{username}</b>, so I can't reissue its token. "
            "Grab a fresh token in @BotFather and reconnect the shop."
        ),
        "restore.failed": (
            "Couldn't restore <b>@{username}</b>. The platform may have lost access "
            "to the bot in @BotFather. You can still reconnect manually — with a "
            "fresh token from there."
        ),
        # --- /newshop ---
        "newshop.management_off": (
            "One-tap bot creation isn't enabled for the platform yet.\n\n"
            "It's fixed in @BotFather: open its mini app (the blue “Open” button to "
            "the left of the input field) → pick the platform bot → enable "
            "<b>Bot Management Mode</b>. The flag only arrives via getMe; it's not in "
            "the regular settings menu.\n\n"
            "Until then — connect the bot the old way, with a token from the app."
        ),
        "newshop.ask_title": (
            "What should the shop be called?\n\n"
            "Customers will see this name in the storefront header — I'll also "
            "suggest a bot address from it.\n\n"
            "For example: <b>Corner Coffee</b>"
        ),
        "newshop.cancel": "Alright, we'll leave it for now. To come back — /newshop.",
        "newshop.need_title": "I need a shop name — just type it as a message.",
        "newshop.title_too_long": "That name is too long — up to {n} characters.",
        "newshop.ready": (
            "Shop <b>{title}</b> is set up.\n\n"
            "All that's left is the bot — customers reach the storefront through it. "
            "I'll create it myself, you just confirm.\n\n"
            "I'll suggest the address: <code>@{username}</code> — Telegram will let "
            "you change it if it's taken."
        ),
        "newshop.btn_create": "🤖 Create the bot “{title}”",
        "newshop.no_draft": (
            "The bot is created, but there's no shop for it. Start with /newshop — "
            "I'll connect it to the new shop."
        ),
        "newshop.token_failed": (
            "The bot is created, but I couldn't fetch its token. "
            "Write to me — we'll sort it out manually."
        ),
        "newshop.promote_failed": "The bot is created, but connecting it failed: {error}.",
        "newshop.done": "✅ Shop <b>{title}</b> is connected to @{username}.\n\n{next}",
        "newshop.done_next": "Open the app and add your first product.",
        "newshop.done_webhook": (
            "The bot is created, but the webhook hasn't stuck yet — customer messages "
            "may not get through. Check /mybots in a minute."
        ),
        # --- shop admins ---
        "admins.note": (
            "An admin runs products, orders, reviews and broadcasts on equal footing "
            "with the owner. Only the owner withdraws money."
        ),
        "admins.none_shops": (
            "You're not an admin of any shop yet.\n\n"
            "A shop owner grants access in their shop card — by your @username in Botify."
        ),
        "admins.header": "🛠 <b>Shops you administer</b>",
        "admins.nameless": "no name",
        "admins.menu_title": "👥 <b>Admins of {label}</b>",
        "admins.menu_empty": "Nobody yet — you're the only one running the shop.",
        "btn.add_admin": "➕ Add an admin",
        "btn.back_to_shop": "⬅️ Back to shop",
        "admins.ask_contact": (
            "Who should become an admin of <b>{label}</b>?\n\n"
            "Send their @username or numeric ID.\n\n"
            "The person must be registered with Botify — having tapped /start in this "
            "bot at least once. Otherwise I don't know them and can't add them.\n\n"
            "{note}."
        ),
        "admins.cancel": "Alright, we'll leave it for now. When you want it — the “Admins” button in the shop card.",
        "admins.shop_not_found": "Shop not found.",
        "admins.bad_contact": (
            "Doesn't look like a @username or an ID. A username is 5+ characters: "
            "letters, digits and underscores."
        ),
        "admins.unknown": (
            "Nobody like that in Botify.\n\n"
            "The person must have tapped /start in this bot at least once — check the "
            "spelling. If they joined without a username, ask for their numeric ID."
        ),
        "admins.is_owner": "That's you — the owner of the shop 🙂",
        "admins.already": "They're already an admin of this shop.",
        "admins.added": (
            "✅ {name} is now an admin of {label}.\n\n"
            "I've written to them — the shop will appear in their /start."
        ),
        "admins.btn_push": "🛠 Shops I administer",
        "push.admin_assigned": (
            "🛠 You've been granted admin rights for the shop "
            "<b>{label}</b>.\n\n{note}.\n\n"
            "The “Shops I administer” button will appear in your /start."
        ),
        "admins.remove_confirm": (
            "Remove <b>{name}</b> "
            "from the admins of {label}? They'll lose access to the shop's dashboard."
        ),
        "admins.name_fallback": "this person",
        "btn.remove": "Remove",
        "toast.removed": "Removed",
        "toast.already_removed": "Already removed",
        "push.admin_removed": (
            "You've been removed from the admins of "
            "<b>{label}</b> — access to its dashboard is closed."
        ),
        # --- pushes from background services and API ---
        "push.paid": "💰 Your product sold! Order #{id} for {total} USDT has been paid.\n{next}",
        "push.paid_digital": "Digital content was delivered automatically.",
        "push.paid_fulfill": "Open the dashboard to ship the order and attach a tracking number/link.",
        "push.paid_sold_out": (
            "\n\n⚠️ Ran out of stock: {items}.\n"
            "The payment for the order has been taken — reach the customer in the order chat."
        ),
        "push.payout_sent": (
            "💸 Payout <b>{amount} USDT</b> for shop @{shop} "
            "has been sent to @CryptoBot."
        ),
        "push.payout_fail": "⚠️ The {amount} USDT payout hasn't gone through yet.\n{hint}",
        "payout.hint.not_started": "Open @CryptoBot and tap Start — the money will arrive there.",
        "payout.hint.disabled": "Transfers are disabled in the platform's settings — I'm already on it.",
        "payout.hint.not_enough": "The platform ran short on balance — try withdrawing later.",
        "payout.hint.default": "Your money is safe: tap “Withdraw” again once the problem goes away.",
        "push.revoked.head": (
            "🔴 Shop @{username} stopped receiving messages.\n\n"
            "The bot's token looks revoked or reissued in @BotFather — customers "
            "can't message the shop or place orders right now.\n\n"
        ),
        "push.revoked.managed": (
            "I created this bot, so I can fix it myself: tap the button and I'll "
            "issue a new token.\n\n"
            "⚠️ The token you got in @BotFather will stop working after that. "
            "If you need it for your own scripts — don't restore, write to me."
        ),
        "push.revoked.unmanaged": (
            "To fix it: grab a fresh token for this bot in @BotFather and reconnect "
            "the shop — the catalog, orders and till stay in place."
        ),
        "push.stuck.one": "📦 An order was paid more than {hours} h ago but hasn't been shipped:",
        "push.stuck.many": "📦 Orders were paid more than {hours} h ago but haven't been shipped:",
        "push.stuck.item": "• Order #{id} for {amount} {currency} (@{shop})",
        "push.stuck.more": "• …and {n} more",
        "push.stuck.tail": (
            "\n\nThe customer has already paid and is waiting. Open the dashboard "
            "and ship — or write to them in the order chat if you need time."
        ),
        "push.review.head": "⭐ New review of “{title}”: {stars}\n",
        "push.review.body": "“{body}”\n",
        "push.review.tail": "You can reply in the dashboard, “Reviews” tab.",
        "push.chat_message": "💬 New message about order #{id}{photo} — open the dashboard.",
        "push.channel_added": (
            "✅ Bot @{username} was added to “{title}”.\n"
            "Join requests will be accepted automatically, and everyone who joins "
            "lands in your customer base."
        ),
        # --- duplicates from API (connect/disable/enable/delete/name) ---
        "api.connected": (
            "🎉 Bot <b>@{username}</b> is connected!\n\n"
            "What's next:\n"
            "• add your first product or service in the app\n"
            "• share the bot's link with customers — anyone who messages it "
            "lands in your base"
        ),
        "btn.open_shop": "🏪 Open the shop",
        "api.disabled": (
            "⚪ Shop <b>@{username}</b> was disabled from the app.\n"
            "The bot isn't answering customers; the base, products and orders are kept."
        ),
        "api.enabled": "🟢 Shop <b>@{username}</b> is enabled — the bot is up again.",
        "api.deleted": "🗑 Shop <b>@{username}</b> was deleted along with its customer base.",
        "api.has_orders": (
            "Customers of <b>@{username}</b> have orders — sales history "
            "can't be deleted, so the shop is just disabled."
        ),
        "api.name_set": "🏪 The shop name is now <b>{name}</b>.",
        "api.name_reset": "🏪 The shop name was reset to <b>@{username}</b>.",
    },
}


def text(locale: str, key: str, **kw) -> str:
    """Шаблон по языку. Неизвестный язык -> RU (исторический язык hub-бота)."""
    return TEXTS.get(locale, TEXTS["ru"])[key].format(**kw)

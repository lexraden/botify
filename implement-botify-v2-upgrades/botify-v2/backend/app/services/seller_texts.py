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
/newshop, администраторы, пуши о заказах/выплатах/отзывах/токенах, а с v2 —
и экраны /settings внутри seller-бота (ключи settings.*). Чего
здесь нет: команды супер-админа платформы (handlers/hub/admin.py —
внутренний инструмент) и всё, что написал сам продавец (названия товаров, тексты каналов). html.escape
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
        "pro.paid": (
            "⭐ Оплачено! Botify {plan} активен ещё {days} дней.\n"
            "Лимиты на товары, услуги и рассылки сняты."
        ),
        "pro.expiring": (
            "⏳ Botify {plan} заканчивается через {days} дн.\n"
            "Без продления останутся лимиты бесплатного тарифа — "
            "каталог и покупатели сохранятся, но добавлять новое будет нельзя."
        ),
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
        "api.profile_sync_failed": (
            "⚠️ Профиль бота в Telegram обновить не удалось — проверь, что токен "
            "действителен. Витрина уже обновлена; в Telegram изменения доедут при "
            "следующем сохранении или кнопкой «Профиль в Telegram» в /settings бота."
        ),
        "api.profile_rate_limited": (
            "⏳ Telegram ограничивает частоту смены имени бота: попробуй ещё раз "
            "через {minutes} мин. Витрина уже показывает новое имя."
        ),
        # --- /settings внутри seller-бота ---
        # Язык — тот же выбор /lang продавца: меню открывает только владелец,
        # а он у обоих ботов один и тот же человек. Алерт чужаку остаётся
        # русским (константа OWNER_ONLY в handlers/seller/settings.py): его
        # язык неизвестен, а менять исторический текст незачем.
        "settings.default_button": "Open",
        "settings.state.on": "включена",
        "settings.state.off": "выключена",
        "settings.state.short_on": "вкл",
        "settings.state.short_off": "выкл",
        "settings.default_welcome": "стандартное приветствие",
        "settings.menu": (
            "⚙️ <b>Настройки бота @{username}</b>\n\n"
            "👋 Приветствие на /start:\n<i>{welcome}</i>\n\n"
            "🔘 Кнопка «{button}»: {state}\n"
            "📢 Каналы для приёма заявок: {channels}"
        ),
        "settings.btn.welcome": "✍️ Приветствие",
        "settings.btn.catalog_toggle": "🔘 Кнопка каталога: {state}",
        "settings.btn.button_text": "✏️ Текст кнопки",
        "settings.btn.channels": "📢 Каналы ({n})",
        "settings.btn.profile": "🪪 Профиль в Telegram",
        "settings.btn.close": "✖️ Закрыть",
        "settings.btn.back": "⬅️ Назад",
        "settings.btn.reset_default": "Сбросить на стандартное",
        "settings.btn.reset_default_m": "Сбросить на стандартный",
        "settings.btn.cancel": "Отмена",
        "settings.toast.reset": "Сброшено",
        "settings.no_changes": "Хорошо, без изменений.",
        "settings.welcome.current_default": "— стандартное приветствие —",
        "settings.welcome.prompt": (
            "Пришли новый текст приветствия — его увидит покупатель на /start.\n"
            'Можно использовать HTML: <b>&lt;b&gt;</b>, <b>&lt;i&gt;</b>, <b>&lt;a href="…"&gt;</b>\n\n'
            "Сейчас:\n{current}"
        ),
        "settings.welcome.saved": "✅ Приветствие сохранено",
        "settings.button.prompt": (
            "Пришли новый текст кнопки открытия магазина (до 64 символов).\n\n"
            "Сейчас: {current}"
        ),
        "settings.button.saved": "✅ Текст кнопки сохранён",
        "settings.channels.empty": (
            "📢 <b>Каналы</b>\n\nКаналов пока нет. Добавь бота администратором "
            "в канал — он появится здесь автоматически."
        ),
        "settings.channels.list": (
            "📢 <b>Каналы</b>\n\nЗелёный — заявки принимаются автоматически. "
            "Нажми на канал, чтобы поменять настройки и приветствие вступившим."
        ),
        "settings.btn.channel_help": "➕ Как подключить канал",
        "settings.channels.help": (
            "➕ <b>Как подключить канал</b>\n\n"
            "1. Добавь бота @{username} администратором в свой канал.\n"
            "2. Отметь право «Приглашать пользователей» — без него бот не видит заявки.\n"
            "3. Канал появится в списке автоматически.\n\n"
            "Каждый, кто нажмёт «Подать заявку» в приватном канале, будет "
            "автоматически принят и попадёт в твою базу покупателей."
        ),
        "settings.channel.auto_on": "включён 🟢",
        "settings.channel.auto_off": "выключен ⚪",
        "settings.channel.default_greeting": "— стандартное приветствие канала —",
        "settings.channel.card": (
            "📢 <b>{title}</b>\n\n"
            "Авто-приём заявок: {auto}\n"
            "Приветствие вступившим:\n<i>{greeting}</i>"
        ),
        "settings.alert.channel_not_found": "Канал не найден",
        "settings.btn.auto_off": "Выключить авто-приём",
        "settings.btn.auto_on": "Включить авто-приём",
        "settings.btn.channel_greeting": "✍️ Приветствие вступившим",
        "settings.btn.channel_remove": "🗑 Отключить канал",
        "settings.toast.enabled": "Включено",
        "settings.toast.disabled": "Выключено",
        "settings.btn.yes_remove": "Да, отключить",
        "settings.channel.remove_confirm": (
            "Отключить канал «{title}»?\n\n"
            "Бот перестанет принимать заявки из него и приветствовать вступивших. "
            "Канал вернётся в список, только если заново добавить бота в канал."
        ),
        "settings.toast.channel_removed": "Канал отключён",
        "settings.greeting.prompt": (
            "Пришли приветствие, которое бот отправит вступившему в ЛС.\n"
            "/reset — вернуть стандартное.\n\n"
            "Сейчас:\n{current}"
        ),
        "settings.channel.gone": "Канал не найден — возможно, он уже отключён.",
        "settings.greeting.saved": "✅ Приветствие сохранено",
        # профиль бота в Telegram (имя/аватар из кабинета, см. services/bot_profile.py)
        "settings.profile": (
            "🪪 <b>Профиль бота в Telegram</b>\n\n"
            "Имя: <b>{name}</b>\n"
            "Исходное имя: {default}\n"
            "Логотип: {logo}\n\n"
            "Имя и логотип меняются в кабинете и сами уезжают в профиль бота. "
            "Кнопка ниже отправляет их в Telegram заново — для магазинов, "
            "подключённых раньше, или если прошлая синхронизация не прошла."
        ),
        "settings.profile.logo_yes": "загружен",
        "settings.profile.logo_no": "не загружен",
        "settings.profile.unknown": "неизвестно (бот подключён до обновления)",
        "settings.btn.profile_sync": "🔄 Отправить в Telegram",
        "settings.toast.syncing": "Синхронизирую…",
        "settings.profile.sync_ok": "✅ Профиль бота обновлён.",
        "settings.profile.sync_partial": "✅ Профиль обновлён частично: {details}",
        "settings.profile.sync_rate_limited": (
            "⏳ Telegram просит подождать {seconds} сек. перед сменой имени."
        ),
        "settings.profile.sync_failed": (
            "⚠️ Не удалось обновить профиль — проверь, что токен бота действителен."
        ),
        "settings.profile.sync_skipped": "Отправлять нечего: имя и лого ещё не заданы.",
        "settings.profile.part.name": "имя",
        "settings.profile.part.photo": "аватар",
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
        "pro.paid": (
            "⭐ Paid! Botify {plan} is active for another {days} days.\n"
            "Limits on products, services and mailings are lifted."
        ),
        "pro.expiring": (
            "⏳ Botify {plan} ends in {days} days.\n"
            "Without renewal the free plan limits come back — your catalog and "
            "customers stay, but you won't be able to add new ones."
        ),
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
        "api.profile_sync_failed": (
            "⚠️ Couldn't update the bot's Telegram profile — check that the token "
            "is still valid. The storefront is already updated; Telegram will catch "
            "up on the next save or via “Telegram profile” in the bot's /settings."
        ),
        "api.profile_rate_limited": (
            "⏳ Telegram limits how often a bot can be renamed: try again in "
            "{minutes} min. The storefront already shows the new name."
        ),
        # --- /settings inside the seller bot ---
        "settings.default_button": "Open",
        "settings.state.on": "enabled",
        "settings.state.off": "disabled",
        "settings.state.short_on": "on",
        "settings.state.short_off": "off",
        "settings.default_welcome": "default greeting",
        "settings.menu": (
            "⚙️ <b>Settings of @{username}</b>\n\n"
            "👋 Greeting on /start:\n<i>{welcome}</i>\n\n"
            "🔘 “{button}” button: {state}\n"
            "📢 Channels accepting join requests: {channels}"
        ),
        "settings.btn.welcome": "✍️ Greeting",
        "settings.btn.catalog_toggle": "🔘 Catalog button: {state}",
        "settings.btn.button_text": "✏️ Button text",
        "settings.btn.channels": "📢 Channels ({n})",
        "settings.btn.profile": "🪪 Telegram profile",
        "settings.btn.close": "✖️ Close",
        "settings.btn.back": "⬅️ Back",
        "settings.btn.reset_default": "Reset to default",
        "settings.btn.reset_default_m": "Reset to default",
        "settings.btn.cancel": "Cancel",
        "settings.toast.reset": "Reset",
        "settings.no_changes": "Okay, nothing changed.",
        "settings.welcome.current_default": "— default greeting —",
        "settings.welcome.prompt": (
            "Send the new greeting text — customers will see it on /start.\n"
            'HTML is allowed: <b>&lt;b&gt;</b>, <b>&lt;i&gt;</b>, <b>&lt;a href="…"&gt;</b>\n\n'
            "Current:\n{current}"
        ),
        "settings.welcome.saved": "✅ Greeting saved",
        "settings.button.prompt": (
            "Send the new text for the shop button (up to 64 characters).\n\n"
            "Current: {current}"
        ),
        "settings.button.saved": "✅ Button text saved",
        "settings.channels.empty": (
            "📢 <b>Channels</b>\n\nNo channels yet. Add the bot as an administrator "
            "to a channel — it will show up here automatically."
        ),
        "settings.channels.list": (
            "📢 <b>Channels</b>\n\nGreen — join requests are accepted automatically. "
            "Tap a channel to change its settings and the greeting for new members."
        ),
        "settings.btn.channel_help": "➕ How to connect a channel",
        "settings.channels.help": (
            "➕ <b>How to connect a channel</b>\n\n"
            "1. Add @{username} as an administrator to your channel.\n"
            "2. Grant the “Invite users” right — without it the bot can't see join requests.\n"
            "3. The channel appears in the list automatically.\n\n"
            "Everyone who taps “Request to join” in a private channel is accepted "
            "automatically and lands in your customer base."
        ),
        "settings.channel.auto_on": "on 🟢",
        "settings.channel.auto_off": "off ⚪",
        "settings.channel.default_greeting": "— default channel greeting —",
        "settings.channel.card": (
            "📢 <b>{title}</b>\n\n"
            "Auto-accept join requests: {auto}\n"
            "Greeting for new members:\n<i>{greeting}</i>"
        ),
        "settings.alert.channel_not_found": "Channel not found",
        "settings.btn.auto_off": "Turn auto-accept off",
        "settings.btn.auto_on": "Turn auto-accept on",
        "settings.btn.channel_greeting": "✍️ Greeting for new members",
        "settings.btn.channel_remove": "🗑 Disconnect channel",
        "settings.toast.enabled": "Enabled",
        "settings.toast.disabled": "Disabled",
        "settings.btn.yes_remove": "Yes, disconnect",
        "settings.channel.remove_confirm": (
            "Disconnect “{title}”?\n\n"
            "The bot will stop accepting join requests from it and greeting new members. "
            "The channel comes back to the list only if you add the bot to it again."
        ),
        "settings.toast.channel_removed": "Channel disconnected",
        "settings.greeting.prompt": (
            "Send the greeting the bot will DM to everyone who joins.\n"
            "/reset — back to the default one.\n\n"
            "Current:\n{current}"
        ),
        "settings.channel.gone": "Channel not found — it may already be disconnected.",
        "settings.greeting.saved": "✅ Greeting saved",
        # bot profile in Telegram (name/avatar from the dashboard, see services/bot_profile.py)
        "settings.profile": (
            "🪪 <b>Bot profile in Telegram</b>\n\n"
            "Name: <b>{name}</b>\n"
            "Original name: {default}\n"
            "Logo: {logo}\n\n"
            "The name and logo are edited in the dashboard and are pushed to the "
            "bot's profile automatically. The button below sends them to Telegram "
            "again — for shops connected earlier, or if the last sync failed."
        ),
        "settings.profile.logo_yes": "uploaded",
        "settings.profile.logo_no": "not uploaded",
        "settings.profile.unknown": "unknown (bot connected before the update)",
        "settings.btn.profile_sync": "🔄 Send to Telegram",
        "settings.toast.syncing": "Syncing…",
        "settings.profile.sync_ok": "✅ Bot profile updated.",
        "settings.profile.sync_partial": "✅ Profile partially updated: {details}",
        "settings.profile.sync_rate_limited": (
            "⏳ Telegram asks to wait {seconds} s before renaming the bot."
        ),
        "settings.profile.sync_failed": (
            "⚠️ Couldn't update the profile — check that the bot token is still valid."
        ),
        "settings.profile.sync_skipped": "Nothing to send: no name or logo set yet.",
        "settings.profile.part.name": "name",
        "settings.profile.part.photo": "avatar",
    },
}


def text(locale: str, key: str, **kw) -> str:
    """Шаблон по языку. Неизвестный язык -> RU (исторический язык hub-бота)."""
    return TEXTS.get(locale, TEXTS["ru"])[key].format(**kw)

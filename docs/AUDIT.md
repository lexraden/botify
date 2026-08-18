# Аудит существующих наработок и план проекта Botify

Дата: 2026-08-18. Аудит выполнен по коду из `reference/` (распакован из Botify.zip),
бриф — в `docs/project-brief.md`, UI-референсы — в `docs/ui-references/`.

---

## 1. Что лежит в reference/ и на чём это написано

### 1.1 `reference/botconnect` — конструктор ботов (главный актив)

**Стек:** Python 3, aiogram 3.13 + FastAPI + SQLAlchemy (async) + asyncpg + PostgreSQL,
Crypto Pay через библиотеку `aiocryptopay`. Деплой — Railway (webhook-режим, uvicorn).

**Что уже реализовано и работает:**

| Функция | Где | Качество |
|---|---|---|
| **Мультибот-раннер**: пользователь вставляет токен от BotFather, платформа валидирует, ставит webhook `/bot/{token}`, все апдейты летят в общий Dispatcher | `main.py`, `handlers_for_added_bots.py` (1040 строк) | Рабочее, архитектурно это ровно то, что нужно брифу (раздел 3.5) |
| Сбор базы юзеров по каждому боту с изоляцией (`users` уникальны по паре `user_id + bot_token`) | `db.py` | Готовая модель изоляции «каждый бот собирает своих» |
| Рассылки: планировщик (проверка раз в 60 сек), кнопки, файлы, счётчики доставки | `menu_handlers/mailing.py` (1084 строки) | Переиспользуем as-is |
| Каналы: авто-приём заявок (join request), капча, приветствие/прощание по языкам | `handlers/channels/*` (~2100 строк) | Ровно функция «приём заявок в закрытый канал» из брифа |
| Конструктор меню бота: кнопки, вложенные инлайн-кнопки, команды | `adding_button.py`, `editing_buttons.py` | Переиспользуем |
| Оплата подписки через Crypto Pay: `create_invoice` → polling `get_invoices` раз в 60 сек → активация | `subscription.py` | Логика есть, но **polling, а не webhook** — для маркетплейса заменим на webhook `invoice_paid` |
| Статистика: отправленные/отвеченные сообщения, блокировки | `db.py` счётчики | Базовая, достаточно для MVP |
| Мультиязычность RU/EN | `dict.py` (687 строк словарей) | Переиспользуем подход |

**Слабые места (исправим при переносе, не переписывая всё):**
- **Токены ботов хранятся в БД открытым текстом** и используются как FK/часть URL вебхука.
  Бриф прямо требует encryption at rest. Меняем: суррогатный `bot_id` в путях вебхуков
  (`/webhook/seller/{seller_id}`), токен — зашифрован (Fernet/AES-GCM, ключ в env).
- Webhook основного бота — `/bot/{TOKEN}` (токен в URL). Заменим на секретный путь + `secret_token` Telegram.
- FSM-состояния в `MemoryStorage` — теряются при рестарте. Для MVP терпимо, позже Redis.
- `PendingPayment` — polling вместо вебхука Crypto Pay; нет идемпотентности по `invoice_id` при гонках.
- Нет миграций (только `create_all` + ручной `ALTER TABLE`). Введём Alembic.
- Обработчик вебхука возвращает 200 при любой ошибке (это норм для Telegram), но ошибки только в лог.

### 1.2 `reference/tg-guides-backend` — бэкенд продажи гайдов

**Стек:** Java 17, Spring Boot 2.6, Spring Security + JWT, JPA/Hibernate, PostgreSQL, Docker.

**Что есть:** модели Person/Guide/Chapter/PurchasedGuides/Referral, JWT-авторизация,
загрузка медиа (изображения/видео глав), реферальная система, баланс продавца,
`TelegramPaymentService`. Swagger.

**Вердикт: НЕ переносим Java-код в новый проект.** Причины:
- Второй рантайм (JVM) рядом с Python-ботом умножает стоимость MVP без выгоды —
  вся логика («каталог цифровых товаров, покупки, главы») тривиально переносится в FastAPI.
- Spring Boot 2.6 — EOL, `jjwt 0.9.1` устаревший, `jwt.secret=guides` захардкожен.

**Что берём как идеи:** структура данных `guide → chapters (text/img/video)` — станет
digital-товаром с контентом; `purchased_guides` — прототип таблицы выдачи доступа;
реферальная модель — отложена (не MVP), но схему держим в уме.

### 1.3 `reference/tg-guides-frontend` — Mini App витрина гайдов

**Стек:** Vue 3 + Pinia + vue-router + vue-i18n + SCSS, `vue-tg` (Telegram WebApp SDK),
TON Connect (`@tonconnect/ui`), сборка Vue CLI.

**Что есть:** готовые компоненты витрины: `GuidesList/GuidesListItem` (сетка каталога),
`TopGuides`, `MineGuides`/`MyGuideItem` («мои покупки»), `SearchResult`, футер-навигация,
интеграция с Telegram WebApp (`services/telegram.js`), тёмная/светлая тема.

**Вердикт: переиспользуем как базу Mini App.** Бриф предлагал React, но существующая
витрина — Vue 3 и она хорошая; переписывать на React — потеря готового UX без выгоды.
TON Connect выкидываем (оплата идёт через Crypto Pay инвойсы, кошелёк в приложении не нужен).
Vue CLI со временем заменим на Vite (Vue CLI в maintenance), компоненты переносятся без изменений.

### 1.4 UI-референсы (`docs/ui-references/`)

Durger King-флоу для раздела «Товары»: сетка карточек (emoji/фото + имя + цена + ADD),
ADD превращается в степпер −/+, снизу sticky-кнопка «VIEW ORDER» → экран заказа со
списком позиций, полем комментария и кнопкой «PAY $X». Это и делаем.

---

## 2. Решение по стеку (предложение)

| Слой | Выбор | Почему |
|---|---|---|
| Бот + Backend API | **Python: aiogram 3 + FastAPI + SQLAlchemy async + PostgreSQL** | Это стек BotConnect — самая большая и самая ценная кодовая база из имеющихся; мультибот-раннер уже написан |
| Mini App | **Vue 3 + Pinia (перенос компонентов tg-guides), сборка Vite** | Готовая витрина, готовая интеграция с Telegram WebApp |
| Оплата | **Crypto Pay API (pay.crypt.bot)**: `createInvoice` → webhook `invoice_paid` → `transfer` на Telegram user_id продавца | Как в брифе; в BotConnect уже есть aiocryptopay, доработаем webhook и transfer |
| Миграции | Alembic | Сейчас миграций нет вообще |
| Деплой | Railway (как сейчас у BotConnect) — один сервис FastAPI отдаёт и API, и вебхуки; Mini App — статика (Railway/Vercel) | Минимум движущихся частей |

Java-бэкенд гайдов не переносится (см. 1.2).

---

## 3. Предлагаемая схема БД

Принцип из брифа: изоляция по продавцам, hub-бот только для продавцов.

```
sellers                      -- продавцы (юзеры hub-бота)
  id PK
  telegram_id BIGINT UNIQUE
  username, first_name, language_code
  cryptobot_connected BOOLEAN DEFAULT FALSE   -- прошёл ли /start у @CryptoBot (проверка transfer'ом/чек-листом)
  onboarding_step VARCHAR                     -- пошаговый чек-лист онбординга
  commission_pct NUMERIC DEFAULT 5            -- комиссия платформы (перекрывается админом)
  is_admin BOOLEAN DEFAULT FALSE
  created_at

seller_bots                  -- подключённые боты продавцов
  id PK
  seller_id FK -> sellers
  bot_token_encrypted BYTEA                   -- AES-GCM/Fernet, ключ в env; НИКОГДА plaintext
  bot_username VARCHAR
  telegram_bot_id BIGINT UNIQUE               -- id бота из getMe
  webhook_status VARCHAR (pending/active/failed)
  is_active BOOLEAN
  created_at

customers                    -- покупатели (юзеры seller-ботов); изоляция по seller_id
  id PK
  telegram_id BIGINT
  seller_id FK -> sellers                     -- чей это покупатель
  bot_id FK -> seller_bots
  username, first_name, language_code
  source VARCHAR                              -- UTM/deep-link параметр из /start
  is_banned BOOLEAN
  created_at
  UNIQUE (telegram_id, bot_id)

products                     -- товары И услуги (одна таблица, поле type)
  id PK
  seller_id FK -> sellers
  type VARCHAR: physical | digital | service
  title, description, image_url
  price NUMERIC, currency VARCHAR DEFAULT 'USDT'
  digital_content JSONB                       -- для digital/service: ссылка/файл/инвайт, главы (как chapters в guides)
  is_active BOOLEAN
  category_id FK -> categories NULL
  created_at

categories
  id PK, seller_id FK, name, sort_order

orders
  id PK
  seller_id FK -> sellers
  customer_id FK -> customers
  status VARCHAR: pending_payment | paid | fulfilled | delivered | cancelled
  total NUMERIC, currency
  comment TEXT                                -- «Add Comment...» с экрана заказа
  invoice_id BIGINT UNIQUE NULL               -- Crypto Pay invoice
  paid_at, created_at
  fulfillment JSONB                           -- трек-номер / ссылка / файл, введённые продавцом

order_items
  id PK, order_id FK, product_id FK, qty INT, price NUMERIC  -- цена на момент покупки

payouts                      -- выплаты продавцам через Crypto Pay transfer
  id PK
  order_id FK UNIQUE
  seller_id FK
  amount NUMERIC, commission NUMERIC
  transfer_id BIGINT NULL                     -- id из Crypto Pay
  status VARCHAR: pending | sent | failed
  created_at, sent_at

mailings, channels, channel_messages          -- переносятся из BotConnect почти as-is,
                                              -- bot_token в FK заменяется на bot_id
```

Ключевые отличия от BotConnect: FK по суррогатному `bot_id`, а не по токену;
токен шифруется; юзеры разделены на `sellers` (hub) и `customers` (seller-боты) —
физически разные таблицы, пересечение невозможно по построению.

---

## 4. Структура монорепо (предложение)

```
/backend            # FastAPI + aiogram: API для Mini App, вебхуки hub-бота,
                    # вебхуки seller-ботов (/webhook/seller/{bot_id}), webhook Crypto Pay
  /app
    /bots           # мультибот-раннер (перенос из botconnect)
    /handlers       # hub-бот: онбординг продавца; seller-бот: /start, каталог, заявки в каналы
    /api            # REST для Mini App (auth по initData, каталог, корзина, заказы, админка)
    /payments       # Crypto Pay: инвойсы, webhook invoice_paid, transfer, комиссия
    /models         # SQLAlchemy
    /services       # рассылки, каналы, доставка заказов
  /alembic
/webapp             # Vue 3 Mini App (перенос компонентов из tg-guides-frontend)
  /src
    /views          # Каталог (Products grid), Товар, Корзина/Checkout, Услуги,
                    # Мои покупки, Кабинет продавца, Онбординг, Админка
    /components     # OnboardingStep, ProductCard, CartBar, ...
/reference          # существующие наработки (read-only, источник переноса)
/docs               # бриф, аудит, ui-references
```

Отдельного `/bot` не нужно: в aiogram webhook-режиме бот живёт внутри того же
FastAPI-процесса (так уже сделано в BotConnect).

---

## 5. MVP-scope и порядок сборки (предложение)

Этапы (каждый — рабочий инкремент):

1. **Каркас**: монорепо, FastAPI + Alembic + модели БД, hub-бот на webhook, деплой на Railway.
2. **Онбординг продавца в hub-боте + Mini App**: регистрация, шаг «подключи @CryptoBot»
   (deep-link + «Проверить»), шаг «подключи своего бота» (инструкция BotFather → токен →
   getMe-валидация → шифрование → webhook). Компонент `OnboardingStep`.
3. **Мультибот-раннер** (перенос из BotConnect): приём апдейтов seller-ботов, сбор
   `customers` с изоляцией, /start с кнопкой Mini App, приём заявок в каналы (перенос channels).
4. **Каталог в Mini App**: продавец добавляет товары/услуги; покупатель видит витрину
   своего продавца (фильтр по seller_id из initData/startapp-параметра), Durger King-флоу,
   корзина, checkout.
5. **Crypto Pay**: createInvoice на checkout → webhook invoice_paid → уведомления
   покупателю и продавцу → digital-товары выдаются сразу.
6. **Постпродажа**: продавец прикрепляет трек/ссылку/файл → бот шлёт покупателю →
   `transfer` доли продавцу (сначала вручную-по-кнопке админа, потом автоматом).
7. **Рассылки и статистика** для продавца по своей базе (перенос mailing из BotConnect).

Вне MVP (по брифу): карты/Apple Pay, внутренний баланс, возвраты/споры, расширенная аналитика.

---

## 6. Открытые вопросы к владельцу проекта

> **Решено владельцем 2026-08-18:** 1 — стек подтверждён; 2 — только комиссия,
> с заделом под месячную Pro-подписку (включается при базе покупателей > 1000);
> 3 — USDT; 4 — новый hub-бот с чистой БД.

1. **Стек подтверждаем?** Python (aiogram+FastAPI) + Vue 3 Mini App; Java-бэкенд не переносим.
2. **Подписка продавцов** (в BotConnect продавцы платят за бота помесячно) — оставляем
   монетизацию только комиссией с продаж в MVP, или подписку тоже переносим?
3. **Валюта каталога**: цены в USDT везде, или продавец выбирает актив (USDT/TON/BTC)?
   Для MVP проще одна (USDT).
4. **Hub-бот**: используем существующего бота BotConnect (и его прод-БД?) или это
   полностью новый бот и чистая БД? (Предполагаю: новый бот, чистая БД.)

# Botify

Telegram Bot + Mini App маркетплейс: hub-бот для продавцов, seller-боты для их
покупателей, витрина-Mini App, оплата в USDT через Crypto Pay (@CryptoBot).

Бриф: `docs/project-brief.md` · Аудит и план: `docs/AUDIT.md` · Правила работы
с Claude Code и команды проекта: `CLAUDE.md`

## Структура

- `backend/` — FastAPI + aiogram 3: API для Mini App, вебхуки hub-бота и seller-ботов
  (мультибот-раннер), модели БД, Alembic-миграции
- `webapp/` — Vue 3 Mini App (витрина; компоненты переносятся из `reference/tg-guides-frontend`)
- `reference/` — существующие наработки (read-only источник переноса)
- `docs/` — бриф, аудит, UI-референсы

## Зафиксированные решения (2026-08-18)

1. Стек: Python (aiogram 3 + FastAPI + PostgreSQL) + Vue 3; Java-бэкенд из reference не переносится.
2. Монетизация MVP — только комиссия с продаж. В `sellers` заложены поля `plan`/`pro_expires_at`
   под будущую месячную Pro-подписку (включается, когда база покупателей продавца превышает 1000).
3. Валюта каталога — USDT.
4. Hub-бот — новый бот с чистой БД (существующий BotConnect не трогаем).
5. Один подключённый бот = один изолированный магазин: каталог, покупатели,
   заказы и рассылки привязаны к `bot_id`, а не к продавцу целиком
   (docs/project-brief.md, п. 8.3).

## Деплой (Railway, один сервис)

Бэкенд сам раздаёт собранную витрину (`webapp/dist` закоммичен) — отдельный
хостинг фронта не нужен. Railway читает корневой `railway.toml`:
миграции применяются на старте, сервис слушает `$PORT`.

Переменные окружения — как в `backend/.env.example`; `WEBAPP_URL` можно не
задавать (возьмётся домен из `WEBHOOK_BASE_URL`). Для тестов без реальных
денег: `CRYPTO_PAY_NETWORK=testnet` + токен приложения из @CryptoTestnetBot.

После правок фронта пересобрать и закоммитить: `cd webapp && npm run build`.

## Запуск backend локально

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # заполнить значения
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8088
```

Без `WEBHOOK_BASE_URL` вебхуки в Telegram не регистрируются — удобно для локальной
разработки. Health-чек: `GET /api/health`.

## Запуск webapp локально

```bash
cd webapp
npm install
npm run dev   # /api проксируется на localhost:8088
```

## Статус (этапы из docs/AUDIT.md, раздел 5)

- [x] Этап 1 — каркас: монорепо, модели БД + миграции, hub-бот на вебхуке, мультибот-раннер (каркас), smoke-тесты
- [x] Этап 2 — онбординг продавца: два шага (@CryptoBot, подключение бота с
      getMe-валидацией и шифрованием токена). Живёт в Mini App, прогресс хранится
      в БД (`sellers.onboarding_step`) и переживает пересоздание webview
- [x] Этап 3 — мультибот: сбор покупателей (middleware на все сообщения seller-ботам),
      каналы с авто-приёмом заявок и приветствием, уведомление продавца в hub-боте
- [x] Этап 4 — Mini App: витрина с корзиной, «Мои покупки», выбор магазина и
      кабинет в контексте бота (товары/заказы/рассылки/статистика); API с
      initData-авторизацией
- [x] Этап 5 — Crypto Pay: инвойс на checkout, webhook invoice_paid с проверкой подписи,
      уведомления покупателю/продавцу, мгновенная выдача digital, запись Payout
- [x] Этап 6 — постпродажа: продавец прикрепляет трек/ссылку → бот пересылает покупателю;
      выплаты через Crypto Pay transfer только по кнопке «Вывести»
      (идемпотентность — случайный токен пачки в payout_batches.spend_id)
- [x] Этап 7 — рассылки по базе бота (rate-limit, учёт заблокировавших, отложенная отправка)
      и базовая статистика в кабинете

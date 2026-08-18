# Botify

Telegram Bot + Mini App маркетплейс: hub-бот для продавцов, seller-боты для их
покупателей, витрина-Mini App, оплата в USDT через Crypto Pay (@CryptoBot).

Бриф: `docs/project-brief.md` · Аудит и план: `docs/AUDIT.md`

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
- [x] Этап 2 — онбординг продавца в hub-боте: шаг @CryptoBot, подключение своего бота
      (getMe-валидация, шифрование токена, вебхук, /mybots); UI-версия в Mini App — этап 4
- [x] Этап 3 — мультибот: сбор покупателей (middleware на все сообщения seller-ботам),
      каналы с авто-приёмом заявок и приветствием, уведомление продавца в hub-боте
- [ ] Этап 4 — каталог и корзина в Mini App (Durger King-флоу)
- [ ] Этап 5 — Crypto Pay: инвойсы + webhook invoice_paid
- [ ] Этап 6 — постпродажный флоу + transfer выплат
- [ ] Этап 7 — рассылки и статистика

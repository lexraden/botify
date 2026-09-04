import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

from aiogram import types
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, health, images, seller, store
from app.bots.dedupe import duplicate_update
from app.bots.hub import HUB_WEBHOOK_PATH, hub_bot, hub_dp, setup_hub_webhook
from app.bots.runner import feed_seller_update, setup_all_seller_webhooks
from app.config import get_settings
from app.db import engine
from app.payments.client import verify_webhook_signature
from app.payments.service import handle_invoice_paid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def mailing_loop() -> None:
    """Проверка созревших рассылок раз в 30 секунд."""
    from app.services.mailing import process_due_mailings

    while True:
        await asyncio.sleep(30)
        try:
            await process_due_mailings()
        except Exception:
            logger.exception("Ошибка в цикле рассылок")


async def chat_maintenance_loop() -> None:
    """Обслуживание чатов заказов раз в минуту: закрытие истёкших окон (72ч)
    и архивация переписки заблокированных больше месяца назад чатов."""
    from app.services.chat import archive_old_chats, lock_expired_chats

    while True:
        await asyncio.sleep(60)
        try:
            locked = await lock_expired_chats()
            if locked:
                logger.info("Закрыто истёкших чатов: %d", locked)
            await archive_old_chats()
        except Exception:
            logger.exception("Ошибка в цикле обслуживания чатов")


async def maintenance_loop() -> None:
    """Обслуживание раз в 10 минут: недоехавшие оплаты, застрявшие рассылки,
    зависшие заказы, истёкшие неоплаченные, отзывы, не отмодерированные
    продавцом за review_moderation_days, отозванные токены ботов и
    осиротевшие фото товаров.

    Всё это — про то, что ломается молча: вебхук об оплате не дошёл, рассылка
    вечно «идёт», оплаченный заказ никто не отправляет, бот перестал получать
    апдейты, брошенная форма оставила фото в БД навсегда. Каждая задача ловит
    свои ошибки сама, чтобы падение одной не уносило остальные вместе с циклом.
    Проверка токенов ходит в Telegram по каждому боту, поэтому у неё свой,
    более редкий, интервал.
    """
    from app.payments.reconcile import reconcile_paid_invoices
    from app.payments.service import resend_undelivered
    from app.services.bot_health import check_revoked_tokens
    from app.services.images import purge_orphan_images
    from app.services.mailing import revive_stuck_mailings
    from app.services.order_health import (
        auto_confirm_delivery,
        expire_unpaid_orders,
        remind_stuck_orders,
    )
    from app.payments.subscription import remind_expiring
    from app.services.reviews import auto_publish_stale_reviews

    settings = get_settings()
    tick = 600
    last_token_check = 0.0

    while True:
        await asyncio.sleep(tick)
        for name, job in (
            ("сверка оплат", reconcile_paid_invoices),
            ("досылка недоставленного", resend_undelivered),
            ("оживление рассылок", revive_stuck_mailings),
            ("напоминания по заказам", remind_stuck_orders),
            ("авто-подтверждение получения", auto_confirm_delivery),
            ("истечение неоплаченных заказов", expire_unpaid_orders),
            ("автопубликация отзывов", auto_publish_stale_reviews),
            ("напоминания о подписке", remind_expiring),
            ("чистка осиротевших фото", purge_orphan_images),
        ):
            try:
                await job()
            except Exception:
                logger.exception("Ошибка обслуживания: %s", name)

        now = asyncio.get_running_loop().time()
        if now - last_token_check >= settings.token_check_hours * 3600:
            last_token_check = now
            try:
                await check_revoked_tokens()
            except Exception:
                logger.exception("Ошибка обслуживания: проверка токенов ботов")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup_hub_webhook()
    await setup_all_seller_webhooks()
    # Выплаты автоматикой не трогаем вовсе: только продавец жмёт «Вывести»
    background_tasks = [
        asyncio.create_task(mailing_loop()),
        asyncio.create_task(chat_maintenance_loop()),
        asyncio.create_task(maintenance_loop()),
    ]
    yield
    for task in background_tasks:
        task.cancel()
    await hub_bot.session.close()
    await engine.dispose()


app = FastAPI(title="Botify", lifespan=lifespan)
app.include_router(health.router, prefix="/api")
app.include_router(store.router, prefix="/api")
app.include_router(seller.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


def check_telegram_secret(secret: str | None) -> None:
    # compare_digest, а не «!=»: сравнение секрета обычной строкой выходит из
    # цикла на первом несовпавшем символе. Рядом (webapp_auth, payments/client)
    # константное сравнение уже используется — пусть будет везде одинаково.
    expected = get_settings().telegram_webhook_secret
    if secret is None or not hmac.compare_digest(secret, expected):
        raise HTTPException(status_code=403, detail="bad secret token")


@app.post(HUB_WEBHOOK_PATH)
async def hub_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    check_telegram_secret(x_telegram_bot_api_secret_token)
    try:
        data = await request.json()
        if duplicate_update("hub", data.get("update_id")):
            return {"status": "ok"}  # ретрай уже обработанного — молча пропускаем
        update = types.Update(**data)
        await hub_dp.feed_update(hub_bot, update)
    except Exception:
        # Telegram ретраит не-200; ошибки обрабатываем сами, наружу всегда 200
        logger.exception("Ошибка обработки апдейта hub-бота")
    return {"status": "ok"}


@app.post("/webhook/cryptopay")
async def cryptopay_webhook(request: Request) -> dict:
    """Вебхук Crypto Pay. URL указывается в настройках приложения:
    @CryptoBot -> Crypto Pay -> My Apps -> Webhooks."""
    raw_body = await request.body()
    signature = request.headers.get("crypto-pay-api-signature")
    if not verify_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=403, detail="bad signature")

    try:
        update = await request.json()
        if update.get("update_type") == "invoice_paid":
            invoice = update.get("payload", {})
            # Подписка и заказ приходят одним вебхуком и различаются payload.
            # Развилка до handle_invoice_paid: тот ищет заказ по invoice_id и
            # на подписочном счёте просто ничего бы не нашёл.
            from app.payments.subscription import grant_plan, parse_payload

            parsed = parse_payload(invoice.get("payload"))
            if parsed is not None:
                seller_id, plan = parsed
                await grant_plan(
                    seller_id,
                    plan,
                    method="crypto",
                    invoice_id=invoice.get("invoice_id"),
                    amount_usdt=Decimal(str(invoice.get("amount") or 0)),
                )
                return {"status": "ok"}
            # Crypto Pay сообщает удержанную им комиссию — она вычитается из
            # доли продавца, поэтому берём фактическое значение, а не оценку
            fee = invoice.get("fee_amount")
            if fee is not None and invoice.get("fee_asset") not in (None, "USDT"):
                fee = None  # комиссия в другой валюте — считаем по ставке
            await handle_invoice_paid(
                invoice_id=invoice.get("invoice_id"),
                payload=invoice.get("payload"),
                fee_amount=Decimal(str(fee)) if fee is not None else None,
            )
    except Exception:
        # 5xx, а не 200: Crypto Pay повторит доставку. Раньше любой сбой до
        # коммита (недоступна БД, дедлок на FOR UPDATE) выглядел для него
        # успехом — деньги приняты, заказ навсегда в pending_payment, и
        # восстановить это было нечем. Повторная доставка безопасна: обработка
        # идемпотентна (FOR UPDATE + гард статуса в handle_invoice_paid).
        logger.exception("Ошибка обработки вебхука Crypto Pay — просим повторить")
        raise HTTPException(status_code=500, detail="retry later") from None
    return {"status": "ok"}


@app.post("/webhook/seller/{bot_id}")
async def seller_webhook(
    bot_id: int,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    check_telegram_secret(x_telegram_bot_api_secret_token)
    try:
        data = await request.json()
        if duplicate_update(f"seller:{bot_id}", data.get("update_id")):
            return {"status": "ok"}  # ретрай уже обработанного — молча пропускаем
        await feed_seller_update(bot_id, data)
    except Exception:
        logger.exception("Ошибка обработки апдейта seller-бота id=%s", bot_id)
    return {"status": "ok"}


# Собранная витрина (webapp/dist) раздаётся этим же сервисом — Mini App
# живёт на том же домене, что и API/вебхуки. Catch-all стоит последним,
# поэтому /api и /webhook обрабатываются раньше.
WEBAPP_DIST = Path(__file__).resolve().parents[2] / "webapp" / "dist"

if WEBAPP_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=WEBAPP_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_webapp(full_path: str) -> FileResponse:
        candidate = WEBAPP_DIST / full_path
        if full_path and ".." not in full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEBAPP_DIST / "index.html")

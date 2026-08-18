import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram import types
from fastapi import FastAPI, Header, HTTPException, Request

from app.api import health, seller, store
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


async def payout_retry_loop() -> None:
    """Ежечасный ретрай незавершённых выплат (пачкой, как в брифе)."""
    from app.payments.payouts import process_unsent_payouts

    while True:
        await asyncio.sleep(3600)
        try:
            await process_unsent_payouts()
        except Exception:
            logger.exception("Ошибка в цикле ретрая выплат")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup_hub_webhook()
    await setup_all_seller_webhooks()
    background_tasks = [
        asyncio.create_task(payout_retry_loop()),
        asyncio.create_task(mailing_loop()),
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


def check_telegram_secret(secret: str | None) -> None:
    if secret != get_settings().telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="bad secret token")


@app.post(HUB_WEBHOOK_PATH)
async def hub_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    check_telegram_secret(x_telegram_bot_api_secret_token)
    try:
        update = types.Update(**await request.json())
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
            await handle_invoice_paid(
                invoice_id=invoice.get("invoice_id"),
                payload=invoice.get("payload"),
            )
    except Exception:
        logger.exception("Ошибка обработки вебхука Crypto Pay")
    return {"status": "ok"}


@app.post("/webhook/seller/{bot_id}")
async def seller_webhook(
    bot_id: int,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    check_telegram_secret(x_telegram_bot_api_secret_token)
    try:
        await feed_seller_update(bot_id, await request.json())
    except Exception:
        logger.exception("Ошибка обработки апдейта seller-бота id=%s", bot_id)
    return {"status": "ok"}

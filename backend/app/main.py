import logging
from contextlib import asynccontextmanager

from aiogram import types
from fastapi import FastAPI, Header, HTTPException, Request

from app.api import health, seller, store
from app.bots.hub import HUB_WEBHOOK_PATH, hub_bot, hub_dp, setup_hub_webhook
from app.bots.runner import feed_seller_update, setup_all_seller_webhooks
from app.config import get_settings
from app.db import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await setup_hub_webhook()
    await setup_all_seller_webhooks()
    yield
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

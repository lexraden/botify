from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers.hub import start as hub_start

HUB_WEBHOOK_PATH = "/webhook/hub"

hub_bot = Bot(
    token=get_settings().hub_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

hub_dp = Dispatcher(storage=MemoryStorage())
hub_dp.include_router(hub_start.router)


async def setup_hub_webhook() -> None:
    settings = get_settings()
    if not settings.webhook_base_url:
        return
    url = f"{settings.webhook_base_url}{HUB_WEBHOOK_PATH}"
    info = await hub_bot.get_webhook_info()
    if info.url != url:
        await hub_bot.set_webhook(
            url=url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=True,
        )

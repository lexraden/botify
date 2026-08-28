from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers.hub import admin as hub_admin
from app.handlers.hub import mybots as hub_mybots
from app.handlers.hub import newshop as hub_newshop
from app.handlers.hub import start as hub_start

HUB_WEBHOOK_PATH = "/webhook/hub"

# Список обязателен: managed_bot в дефолтную выдачу Telegram не входит, и без
# явного перечисления апдейты о созданных нами ботах просто не придут.
# my_chat_member отдельного хендлера пока не имеет — он в списке, чтобы
# блокировку hub-бота продавцом можно было начать обрабатывать без правки
# вебхука (переустановка требует рестарта приложения).
HUB_ALLOWED_UPDATES = [
    "message",
    "callback_query",
    "my_chat_member",
    "managed_bot",
]

hub_bot = Bot(
    token=get_settings().hub_bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

hub_dp = Dispatcher(storage=MemoryStorage())
hub_dp.include_router(hub_admin.router)
hub_dp.include_router(hub_mybots.router)
# newshop раньше start: у него свой FSM на текст (название магазина),
# и он не должен перехватываться приветствием
hub_dp.include_router(hub_newshop.router)
hub_dp.include_router(hub_start.router)


async def setup_hub_webhook() -> None:
    settings = get_settings()
    if not settings.webhook_base_url:
        return
    from aiogram.types import BotCommand

    await hub_bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать / настройка"),
            BotCommand(command="mybots", description="Мои магазины"),
            BotCommand(command="newshop", description="Новый магазин"),
        ]
    )
    url = f"{settings.webhook_base_url}{HUB_WEBHOOK_PATH}"
    info = await hub_bot.get_webhook_info()
    if info.url != url:
        await hub_bot.set_webhook(
            url=url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=True,
            allowed_updates=HUB_ALLOWED_UPDATES,
        )

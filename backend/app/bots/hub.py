from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.handlers.hub import admin as hub_admin
from app.handlers.hub import lang as hub_lang
from app.handlers.hub import mybots as hub_mybots
from app.handlers.hub import newshop as hub_newshop
from app.handlers.hub import shop_admins as hub_shop_admins
from app.handlers.hub import start as hub_start
from app.handlers.hub import subscription as hub_subscription

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
# lang сразу после admin: команда /lang должна срабатывать и посреди чужих
# FSM-диалогов (newshop, приглашение админа), не попадая в их ловушки текста
hub_dp.include_router(hub_lang.router)
hub_dp.include_router(hub_mybots.router)
# shop_admins раньше newshop и start: свой FSM на текст (@username или ID
# приглашаемого админа) и кнопка «Магазины, где я администратор» из /start
hub_dp.include_router(hub_shop_admins.router)
# newshop раньше start: у него свой FSM на текст (название магазина),
# и он не должен перехватываться приветствием
hub_dp.include_router(hub_newshop.router)
hub_dp.include_router(hub_subscription.router)
hub_dp.include_router(hub_start.router)


async def setup_hub_webhook() -> None:
    settings = get_settings()
    if not settings.webhook_base_url:
        return
    # дефолтное меню — русское (исторический язык hub-бота); список общий
    # с пер-чатовыми перезаписями после выбора языка в /lang
    await hub_bot.set_my_commands(hub_lang.COMMANDS["ru"])
    url = f"{settings.webhook_base_url}{HUB_WEBHOOK_PATH}"
    info = await hub_bot.get_webhook_info()
    if info.url != url:
        await hub_bot.set_webhook(
            url=url,
            secret_token=settings.telegram_webhook_secret,
            drop_pending_updates=True,
            allowed_updates=HUB_ALLOWED_UPDATES,
        )

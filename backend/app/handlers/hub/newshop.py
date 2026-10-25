"""Онбординг магазина без BotFather: кнопка → окно Telegram → бот создан.

Как это работает:

1. Продавец принимает условия в Mini App. Сервер сам присылает ему в чат с
   hub-ботом сообщение с reply-кнопкой `KeyboardButtonRequestManagedBot`,
   а приложение закрывается — человек оказывается ровно там, где кнопка уже
   ждёт (`POST /api/seller/onboarding/bot-prompt`). Тот же ответ дают
   `/newshop` и диплинк `?start=newshop`.
2. Заодно заводится черновик — строка `seller_bots` с пустым токеном
   (app/services/shop_draft.py). Названия у него ещё нет.
3. Продавец жмёт кнопку, Telegram показывает своё окно: имя и адрес бота
   человек вводит там, Telegram же проверяет занятость адреса.
4. Нам приходит `managed_bot_created`; берём токен через
   `getManagedBotToken`, дописываем черновик — имя бота становится названием
   магазина — и ставим вебхук.

Названия мы раньше спрашивали отдельным сообщением, до кнопки. Это был тот же
вопрос, что Telegram задаёт в своём окне, только дважды; поля
`suggested_name`/`suggested_username` у кнопки необязательны. Отказались от
него 2026-10-12, вместе с возвратом в чат через диплинк: это и был самый
длинный кусок онбординга.

Владелец созданного бота — продавец: в `ManagedBotUpdated.user` Telegram
присылает «User that created the bot», а у владельца доступ неотнимаемый
(`BotAccessSettings`: «The bot's owner can always access it»). Мы — только
управляющий бот, как и раньше при ручном вводе токена.

Ручной путь (`POST /api/seller/bots` с токеном от BotFather) остаётся: у
существующих продавцов боты уже созданы, да и Bot Management Mode у hub-бота
может быть выключен.
"""

import asyncio
import html
import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import get_settings
from app.db import get_session
from app.models import Seller
from app.services.seller_texts import seller_locale, text
from app.services.shop_draft import (
    DraftPromotionError,
    can_create_managed_bots,
    create_draft,
    promote_draft,
    set_webhook_status,
)

logger = logging.getLogger(__name__)

router = Router()

REQUEST_ID = 1


async def _seller_for(message: types.Message) -> Seller | None:
    """Продавец по автору сообщения. Middleware у hub-бота нет — остальные
    хендлеры делают ровно так же."""
    from sqlalchemy import select

    if message.from_user is None:
        return None
    async with get_session() as session:
        return (
            await session.execute(
                select(Seller).where(Seller.telegram_id == message.from_user.id)
            )
        ).scalar_one_or_none()


def create_prompt(locale: str) -> tuple[str, types.ReplyKeyboardMarkup]:
    """Сообщение с кнопкой создания бота.

    Общее для /newshop, диплинка и сервера после принятия условий — за ними
    один сценарий, и расходиться им нельзя.
    """
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text=text(locale, "newshop.btn_create"),
                    # Ни имени, ни адреса не подсказываем: человек вводит их
                    # в окне Telegram, и отдельный вопрос до кнопки был тем
                    # же вопросом, заданным дважды
                    request_managed_bot=types.KeyboardButtonRequestManagedBot(
                        request_id=REQUEST_ID
                    ),
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    return text(locale, "newshop.prompt"), kb


async def needs_terms(seller: Seller) -> bool:
    """Нужно ли сначала принять условия.

    Правило то же, что в приложении: условия обязательны для первого
    магазина. Требовать их на каждый /newshop нельзя — у продавцов,
    подключившихся до появления галочки, terms_accepted_at пустой, а экран
    условий приложение показывает только тем, у кого магазинов ещё нет.
    Такой продавец навсегда упёрся бы в «прими условия», которых не увидит.
    """
    from sqlalchemy import select

    from app.models import SellerBot

    if seller.terms_accepted_at is not None:
        return False
    async with get_session() as session:
        has_shop = (
            await session.execute(
                select(SellerBot.id)
                .where(
                    SellerBot.seller_id == seller.id,
                    SellerBot.bot_token_encrypted.is_not(None),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    return has_shop is None


async def start_newshop(message: types.Message, state: FSMContext) -> None:
    """Показать кнопку создания бота. Общее тело для /newshop и для
    диплинка из Mini App."""
    seller = await _seller_for(message)
    locale = seller_locale(seller) if seller is not None else "ru"
    # хвост старого сценария, где тут ждали название магазина
    await state.clear()

    # Кнопку, которая заведомо упадёт с «this bot doesn't support managing
    # bots», не показываем вовсе — объясняем, как включить
    if not await can_create_managed_bots():
        await message.answer(
            text(locale, "newshop.management_off"),
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return
    if seller is None:
        await message.answer(text("ru", "hub.no_seller"))
        return

    # Галочка условий живёт в приложении (решение владельца от 2026-10-12);
    # без неё первый магазин из чата раньше заводился в обход неё
    if await needs_terms(seller):
        from app.handlers.hub.start import open_app_keyboard

        await message.answer(
            text(locale, "newshop.terms_first"),
            reply_markup=open_app_keyboard(with_bots=False, admin_bots=False, locale=locale),
        )
        return

    await create_draft(seller.id)
    body, kb = create_prompt(locale)
    await message.answer(body, reply_markup=kb)


@router.message(Command("newshop"))
async def cmd_newshop(message: types.Message, state: FSMContext) -> None:
    await start_newshop(message, state)


@router.message(F.managed_bot_created)
async def bot_created(message: types.Message) -> None:
    """Telegram создал бота по нашей кнопке — забираем токен и включаем магазин."""
    from app.bots.hub import hub_bot
    from app.bots.runner import setup_seller_webhook
    from app.services.shop_draft import latest_draft

    seller = await _seller_for(message)
    if seller is None:
        await message.answer(
            text("ru", "hub.no_seller"), reply_markup=types.ReplyKeyboardRemove()
        )
        return
    locale = seller_locale(seller)

    created = message.managed_bot_created.bot_user
    logger.info("Создан managed-бот %s (@%s)", created.id, created.username)

    # Черновика может не быть: кнопка осталась в старом сообщении, а прошлый
    # магазин уже собран. Бот при этом создан по-настоящему — отправлять
    # человека «начать заново» значило бы бросить живого бота без магазина.
    shop = await latest_draft(seller.id) or await create_draft(seller.id)

    try:
        token = await hub_bot.get_managed_bot_token(user_id=created.id)
    except Exception:
        logger.exception("Не удалось получить токен managed-бота %s", created.id)
        await message.answer(
            text(locale, "newshop.token_failed"),
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    try:
        shop = await promote_draft(
            shop.id,
            token,
            created.username or "",
            created.id,
            bot_name=getattr(created, "first_name", None),
        )
    except DraftPromotionError as exc:
        await message.answer(
            text(locale, "newshop.promote_failed", error=html.escape(str(exc))),
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return

    webhook_ok = await setup_seller_webhook(shop)
    if not webhook_ok:
        logger.warning("Вебхук для магазина %s не встал", shop.id)
    # статус пишем здесь же, как bot_connect и bot_recovery: иначе магазин
    # до перезапуска процесса значится «pending» и светится в /mybots жёлтым
    await set_webhook_status(shop.id, "active" if webhook_ok else "pending")

    # Кнопка прямо в свой магазин вместо «открой приложение» словами: человек
    # только что закончил создание бота и следующий его шаг — первый товар,
    # а искать вход руками после такого — лишний повод бросить.
    markup = None
    webapp_url = get_settings().effective_webapp_url
    if webapp_url:
        kb = InlineKeyboardBuilder()
        kb.button(
            text=text(locale, "newshop.btn_open_shop"),
            web_app=types.WebAppInfo(url=f"{webapp_url.rstrip('/')}/shop/{shop.id}"),
        )
        markup = kb.as_markup()

    if not webhook_ok:
        next_line = text(locale, "newshop.done_webhook")
    else:
        next_line = "" if markup else text(locale, "newshop.done_next")
    # Reply-клавиатуру «Создать бота» снимаем первым сообщением: one_time
    # только сворачивает её, и кнопка оставалась под иконкой клавиатуры
    # (замечено живьём 13.10). Inline-кнопка в том же сообщении remove
    # не даёт — она уходит вторым.
    await message.answer(
        text(
            locale,
            "newshop.done",
            title=html.escape(shop.title or ""),
            username=html.escape(shop.bot_username or ""),
            next=next_line,
        ).rstrip(),
        reply_markup=types.ReplyKeyboardRemove(),
    )
    if markup:
        await message.answer(text(locale, "newshop.done_next") + " 👇", reply_markup=markup)

    # Первый /start в новом боте часто теряется: Telegram доносит его сразу,
    # а вебхук встаёт чуть позже. Приветствуем создателя сами — с теми же
    # кнопками, что на /start, включая кабинет. В фоне: первый коннект нового
    # бота к api.telegram.org занимает секунды, ответ здесь ждать не должен.
    task = asyncio.create_task(
        welcome_creator_from_bot(shop, message.from_user),
        name=f"welcome-creator-{shop.id}",
    )
    _background.add(task)
    task.add_done_callback(_background.discard)


# сильные ссылки на фоновые задачи: event loop держит только слабые,
# и недожданная задача может быть собрана GC посреди работы
_background: set[asyncio.Task] = set()


async def welcome_creator_from_bot(shop, tg_user) -> None:
    """Первое приветствие от самого seller-бота его создателю.

    Исходящие не зависят от вебхука, поэтому приходят, даже если /start
    потерялся. Если Telegram не даёт написать первым — просто пишем в лог:
    создатель всё равно увидит приветствие, когда сам нажмёт /start.
    """
    from app.bots.runner import make_seller_bot
    from app.handlers.seller.start import start_keyboard, welcome_text_for
    from app.security import decrypt_bot_token

    if shop.bot_token_encrypted is None or tg_user is None:
        return
    bot = make_seller_bot(decrypt_bot_token(shop.bot_token_encrypted))
    try:
        kb = await start_keyboard(shop, None, tg_user)
        await bot.send_message(tg_user.id, welcome_text_for(shop), reply_markup=kb)
        logger.info("newshop: приветствие создателю ушло, магазин %s", shop.id)
    except Exception:
        logger.info("newshop: приветствие создателю не ушло, магазин %s", shop.id, exc_info=True)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


@router.managed_bot()
async def managed_bot_changed(event: types.ManagedBotUpdated) -> None:
    """Смена токена или владельца бота, которым мы управляем.

    Пока только пишем в лог: реакция зависит от того, что именно Telegram
    присылает в этих случаях — а это проверяется живьём.
    """
    logger.info(
        "managed_bot: бот %s (@%s), пользователь %s",
        event.bot_user.id,
        event.bot_user.username,
        event.user.id,
    )

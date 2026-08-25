"""Relay-чат: тексты и фото покупателя в диалоге с ботом магазина попадают
в историю чата заказа (продавец видит их в кабинете).

Роутер регистрируется ПОСЛЕДНИМ в seller_dp: /start, «Я не робот» и FSM
настроек перехватывают свои тексты раньше. Если у покупателя нет ни одного
чата, апдейт молча игнорируется — поведение бота для посторонних текстов
остаётся прежним.

Адресация при нескольких заказах: реплай на конкретное сообщение бота
(по tg_message_id, только свои чаты) адресует именно тот заказ; обычный
текст уходит в последний открытый чат.
"""

import io
import logging

from aiogram import F, Router, types
from sqlalchemy import select

from app.db import get_session
from app.models import ChatMessage, Customer, Order, OrderChat, Seller, SellerBot
from app.models.chat import ChatImage, ChatMessageArchive
from app.services import chat as chat_service
from app.services.images import MAX_IMAGE_BYTES, sniff_image_mime

logger = logging.getLogger(__name__)

router = Router()


async def _chat_id_by_reply(
    bot_id: int, customer_id: int, reply_tg_message_id: int
) -> int | None:
    """Чат по ответу-реплаю. Скоуп по bot+customer обязателен: message_id в
    разных Telegram-диалогах совпадают, чужой реплей не должен адресовать."""
    async with get_session() as session:
        live = await session.scalar(
            select(OrderChat.id)
            .join(ChatMessage, ChatMessage.chat_id == OrderChat.id)
            .where(
                ChatMessage.tg_message_id == reply_tg_message_id,
                OrderChat.bot_id == bot_id,
                OrderChat.customer_id == customer_id,
            )
            .limit(1)
        )
        if live is not None:
            return live
        # сообщения могли уже уехать в архивную таблицу
        return await session.scalar(
            select(OrderChat.id)
            .join(ChatMessageArchive, ChatMessageArchive.chat_id == OrderChat.id)
            .where(
                ChatMessageArchive.tg_message_id == reply_tg_message_id,
                OrderChat.bot_id == bot_id,
                OrderChat.customer_id == customer_id,
            )
            .limit(1)
        )


async def _customer_has_chats(session, bot_id: int, customer_id: int) -> bool:
    return (
        await session.scalar(
            select(OrderChat.id).where(
                OrderChat.bot_id == bot_id,
                OrderChat.customer_id == customer_id,
            )
        )
        is not None
    )


@router.message(F.text, ~F.text.startswith("/"))
async def relay_buyer_message(
    message: types.Message, customer: Customer, bot_record: SellerBot
) -> None:
    text = (message.text or "").strip()

    target_chat_id: int | None = None
    if message.reply_to_message is not None and message.reply_to_message.message_id:
        target_chat_id = await _chat_id_by_reply(
            bot_record.id, customer.id, message.reply_to_message.message_id
        )

    async with get_session() as session:
        chat: OrderChat | None = None
        if target_chat_id is not None:
            chat = await session.get(OrderChat, target_chat_id)

        if chat is not None:
            order = await session.get(Order, chat.order_id)
        else:
            # без реплая — последний заказ с открытым окном; чат создаётся
            # на месте, если продавец ещё ни разу не писал первым
            order = await chat_service.latest_open_order(session, bot_record.id, customer.id)
            chat = await chat_service.get_or_create_chat(session, order) if order else None

        if chat is None or order is None:
            # реплей в неизвестное/чужое сообщение и открытых чатов нет:
            # если чаты были — объясняем, если нет — молчим как раньше
            if await _customer_has_chats(session, bot_record.id, customer.id):
                await message.answer(chat_service.LOCKED_CHAT_TEXT)
            return

        if not chat_service.chat_is_open(order):
            await message.answer(chat_service.LOCKED_CHAT_TEXT)
            return

        try:
            await chat_service.send_message(session, chat, order, "customer", text)
        except chat_service.RateLimitedError:
            await message.answer(chat_service.RATE_LIMITED_TEXT)
            return
        except ValueError:
            await message.answer(chat_service.TOO_LONG_TEXT)
            return

        seller_tg = (await session.get(Seller, chat.seller_id)).telegram_id
        order_id = order.id
        await session.commit()

    await chat_service.notify_seller(seller_tg, order_id)


async def _download_photo(message: types.Message, photo) -> bytes:
    """Байты присланного фото. Отдельная функция — удобный шов для моков в
    тестах, чтобы не собирать настоящий aiogram-Bot."""
    buffer = io.BytesIO()
    await message.bot.download(photo, destination=buffer)
    return buffer.getvalue()


@router.message(F.photo)
async def relay_buyer_photo(
    message: types.Message, customer: Customer, bot_record: SellerBot
) -> None:
    """Фото от покупателя — адресация та же, что у текста (реплай на сообщение
    бота или последний открытый чат), подпись к фото играет роль тела."""
    photo = message.photo[-1]  # Telegram шлёт набор размеров — нужен самый большой
    caption = (message.caption or "").strip()
    if len(caption) > chat_service.MAX_MESSAGE_LEN:
        await message.answer(chat_service.TOO_LONG_TEXT)
        return
    if photo.file_size is not None and photo.file_size > MAX_IMAGE_BYTES:
        await message.answer(chat_service.PHOTO_TOO_BIG_TEXT)
        return

    target_chat_id: int | None = None
    if message.reply_to_message is not None and message.reply_to_message.message_id:
        target_chat_id = await _chat_id_by_reply(
            bot_record.id, customer.id, message.reply_to_message.message_id
        )

    async with get_session() as session:
        chat: OrderChat | None = None
        if target_chat_id is not None:
            chat = await session.get(OrderChat, target_chat_id)

        if chat is not None:
            order = await session.get(Order, chat.order_id)
        else:
            # без реплая — последний заказ с открытым окном; чат создаётся
            # на месте, если продавец ещё ни разу не писал первым
            order = await chat_service.latest_open_order(session, bot_record.id, customer.id)
            chat = await chat_service.get_or_create_chat(session, order) if order else None

        if chat is None or order is None:
            if await _customer_has_chats(session, bot_record.id, customer.id):
                await message.answer(chat_service.LOCKED_CHAT_TEXT)
            return

        if not chat_service.chat_is_open(order):
            await message.answer(chat_service.LOCKED_CHAT_TEXT)
            return

        try:
            data = await _download_photo(message, photo)
        except Exception:
            logger.exception("Не удалось скачать фото покупателя по заказу %s", order.id)
            await message.answer(chat_service.PHOTO_FAILED_TEXT)
            return

        if len(data) > MAX_IMAGE_BYTES:
            await message.answer(chat_service.PHOTO_TOO_BIG_TEXT)
            return
        mime = sniff_image_mime(data)
        if mime is None:
            await message.answer(chat_service.BAD_IMAGE_TEXT)
            return

        image = ChatImage(
            bot_id=bot_record.id, chat_id=chat.id, mime=mime, size=len(data), data=data
        )
        session.add(image)
        await session.flush()

        try:
            await chat_service.send_message(
                session, chat, order, "customer", caption, image_token=image.token
            )
        except chat_service.RateLimitedError:
            await message.answer(chat_service.RATE_LIMITED_TEXT)
            return

        seller_tg = (await session.get(Seller, chat.seller_id)).telegram_id
        order_id = order.id
        await session.commit()

    await chat_service.notify_seller(seller_tg, order_id, has_photo=True)

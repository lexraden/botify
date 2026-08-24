"""Relay-чат по оплаченному заказу (см. app/models/chat.py).

Правила:
- чат появляется у заказа, как только тот оплачен (PAID_STATUSES), и привязан
  к одному order_id;
- писать можно, пока заказ не доставлен либо с доставки прошло <= 72 часов;
  после — только чтение (история не удаляется никогда);
- отменённый заказ закрывает чат навсегда;
- личности сторон наружу не раскрываются: в API уходит только роль отправителя
  ('seller' | 'customer'), покупателю сообщения приходят от самого бота.

Источник истины об открытости считается на каждой отправке из delivered_at,
фоновый джоб лишь проставляет статус для выборок/UI. Архивация: через
archive_chat_after_days после блокировки сообщения переносятся в
chat_messages_archive, чтение смотрит в обе таблицы.
"""

import html
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from time import monotonic

from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.config import get_settings
from app.db import get_session
from app.models import ChatMessage, Order, OrderChat, SellerBot
from app.models.chat import ChatMessageArchive
from app.models.orders import PAID_STATUSES
from app.security import decrypt_bot_token

logger = logging.getLogger(__name__)

CHAT_LOCKED_DETAIL = "chat_locked"
MAX_MESSAGE_LEN = 1000

# Rate limit на участника чата: антиспам базовый, без модерации контента.
MIN_SEND_INTERVAL_SEC = 2.0
MAX_MESSAGES_PER_WINDOW = 30
WINDOW_SEC = 5 * 60


class ChatLockedError(Exception):
    """Чат закрыт для новых сообщений (истёкшее окно / отменённый заказ)."""


class RateLimitedError(Exception):
    """Слишком много сообщений от участника подряд."""


# --- rate limiting (in-process; деплой однопроцессный) ---

_sends: dict[tuple[int, str], deque[float]] = defaultdict(deque)
_last_send_at: dict[tuple[int, str], float] = {}


def _check_rate_limit(chat_id: int, sender_role: str) -> None:
    key = (chat_id, sender_role)
    now = monotonic()
    last = _last_send_at.get(key)
    if last is not None and now - last < MIN_SEND_INTERVAL_SEC:
        raise RateLimitedError()
    window = _sends[key]
    while window and now - window[0] > WINDOW_SEC:
        window.popleft()
    if len(window) >= MAX_MESSAGES_PER_WINDOW:
        raise RateLimitedError()
    window.append(now)
    _last_send_at[key] = now


# --- состояние чата ---


def _aware(dt: datetime) -> datetime:
    """Postgres возвращает aware-время, SQLite — наивное UTC; приводим к
    одному виду, иначе сравнение с now() падает по таймзоне."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def chat_is_open(order: Order) -> bool:
    """Писать в чат можно, пока заказ оплачен и (не доставлен либо с доставки
    не прошло окно). Считается на каждом вызове — джоб на решение не влияет."""
    if order.status not in PAID_STATUSES:
        return False
    if order.status != "delivered" or order.delivered_at is None:
        return True
    deadline = _aware(order.delivered_at) + timedelta(hours=get_settings().chat_window_hours)
    return datetime.now(timezone.utc) < deadline


def closes_at(order: Order) -> datetime | None:
    """Когда окно закроется (для UI-отсчёта); None — дедлайна пока нет."""
    if order.status == "delivered" and order.delivered_at is not None:
        return _aware(order.delivered_at) + timedelta(hours=get_settings().chat_window_hours)
    return None


async def get_or_create_chat(session, order: Order) -> OrderChat | None:
    """Чат заказа; None — заказ ни разу не был оплачен, обсуждать нечего.
    Отменённый после оплаты заказ получает закрытый read-only чат: история
    обсуждения должна остаться доступной обеим сторонам."""
    result = await session.execute(select(OrderChat).where(OrderChat.order_id == order.id))
    chat = result.scalar_one_or_none()
    if chat is not None:
        return chat
    if order.status not in PAID_STATUSES and order.paid_at is None:
        return None
    chat = OrderChat(
        order_id=order.id,
        bot_id=order.bot_id,
        seller_id=order.seller_id,
        customer_id=order.customer_id,
    )
    session.add(chat)
    await session.flush()
    return chat


async def read_history(session, chat_id: int) -> list[ChatMessage]:
    """Все сообщения чата, включая уже заархивированные. Порядок — по id."""
    live = (
        (await session.execute(select(ChatMessage).where(ChatMessage.chat_id == chat_id)))
        .scalars()
        .all()
    )
    archived = (
        (
            await session.execute(
                select(ChatMessageArchive).where(ChatMessageArchive.chat_id == chat_id)
            )
        )
        .scalars()
        .all()
    )
    # archived_at у архивных строк не участвует в сортировке истории —
    # порядок переписки восстанавливает исходный id
    merged = [*live, *archived]
    merged.sort(key=lambda m: m.id)
    return merged


async def send_message(session, chat: OrderChat, order: Order, sender_role: str, body: str) -> ChatMessage:
    """Записать сообщение от стороны сделки. Бросает ChatLockedError /
    RateLimitedError — вызывающий переводит их в ответы API или бота."""
    body = body.strip()
    if not body or len(body) > MAX_MESSAGE_LEN:
        raise ValueError("message body must be 1..1000 chars")
    if not chat_is_open(order):
        raise ChatLockedError()
    _check_rate_limit(chat.id, sender_role)

    message = ChatMessage(chat_id=chat.id, sender=sender_role, body=body)
    session.add(message)
    await session.flush()
    return message


async def notify_customer(bot_record: SellerBot, customer_tg: int, order_id: int, body: str) -> int | None:
    """Сообщение продавца -> покупателю от бота магазина. Возвращает message_id
    в Telegram (по реплаю на него ответ адресуется этому заказу)."""
    # импорт внутри функции: app.bots.runner сам импортирует хендлеры чата,
    # модульный импорт наверху даёт цикл runner → chat → services.chat → runner
    from app.bots.runner import make_seller_bot

    bot = make_seller_bot(decrypt_bot_token(bot_record.bot_token_encrypted))
    try:
        sent = await bot.send_message(
            customer_tg,
            f"💬 Заказ #{order_id}\n\n{html.escape(body)}",
        )
        return sent.message_id
    except Exception:
        logger.exception("Не удалось доставить сообщение по заказу %s покупателю", order_id)
        return None
    finally:
        await bot.session.close()


async def notify_seller(seller_tg: int, order_id: int) -> None:
    """Сообщение покупателя -> пуш продавцу в hub-бот (без деталей личности)."""
    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(
            seller_tg, f"💬 Новое сообщение по заказу #{order_id} — открой кабинет."
        )
    except Exception:
        logger.exception("Не удалось уведомить продавца о сообщении по заказу %s", order_id)


# --- фоновые джобы (вызываются из цикла в app/main.py) ---


async def lock_expired_chats() -> int:
    """Закрывает окна, истёкшие 72 часа назад. Возвращает число закрытых."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=get_settings().chat_window_hours)
    async with get_session() as session:
        expired_ids = list(
            (
                await session.execute(
                    select(OrderChat.id)
                    .join(Order, Order.id == OrderChat.order_id)
                    .where(
                        OrderChat.status == "active",
                        Order.status == "delivered",
                        # NULL delivered_at у legacy-строк окно не закрывает:
                        # честнее оставить чат открытым, чем запереть навсегда
                        Order.delivered_at.is_not(None),
                        Order.delivered_at < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not expired_ids:
            return 0
        await session.execute(
            update(OrderChat)
            .where(OrderChat.id.in_(expired_ids), OrderChat.status == "active")
            .values(status="locked_by_timeout", locked_at=func.now())
        )
        await session.commit()
        return len(expired_ids)


async def archive_old_chats() -> int:
    """Переносит сообщения чатов, заблокированных > archive_chat_after_days
    назад, в холодное хранилище. Чтение истории прозрачно объединяет таблицы."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=get_settings().archive_chat_after_days)
    moved = 0
    async with get_session() as session:
        chats = (
            (
                await session.execute(
                    select(OrderChat).where(
                        OrderChat.status == "locked_by_timeout",
                        OrderChat.locked_at.is_not(None),
                        OrderChat.locked_at < cutoff,
                    )
                )
            )
            .scalars()
            .all()
        )
        for chat in chats:
            messages = (
                (
                    await session.execute(
                        select(ChatMessage).where(ChatMessage.chat_id == chat.id)
                    )
                )
                .scalars()
                .all()
            )
            for message in messages:
                session.add(
                    ChatMessageArchive(
                        chat_id=message.chat_id,
                        sender=message.sender,
                        body=message.body,
                        tg_message_id=message.tg_message_id,
                        created_at=message.created_at,
                    )
                )
            if messages:
                moved += len(messages)
                for message in messages:
                    await session.delete(message)
            chat.status = "archived"
        await session.commit()
    if moved:
        logger.info("Заархивировано %d сообщений чатов старше %d дней", moved, get_settings().archive_chat_after_days)
    return moved


async def latest_open_order(session, bot_id: int, customer_id: int) -> Order | None:
    """Последний заказ клиента в этом магазине с открытым окном обсуждения —
    независимо от того, заводился ли уже чат. Туда падает текст покупателя без
    реплая; чат создаётся на месте (get_or_create_chat у вызывающего)."""
    result = await session.execute(
        select(Order)
        .where(
            Order.bot_id == bot_id,
            Order.customer_id == customer_id,
            Order.status.in_(PAID_STATUSES),
        )
        .order_by(Order.id.desc())
        .limit(20)
    )
    for order in result.scalars().all():
        if chat_is_open(order):
            return order
    return None


LOCKED_CHAT_TEXT = (
    "Этот чат закрыт для новых сообщений — окно для обсуждения заказа истекло."
)
RATE_LIMITED_TEXT = "Слишком много сообщений подряд — подожди немного."
TOO_LONG_TEXT = "Сообщение слишком длинное — максимум 1000 символов."

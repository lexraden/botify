"""Канал «Связаться с нами»: обращения покупателей и продавцов платформе.

Одна точка входа в профиле витрины и в кабинете продавца; внутри три типа —
проблема, идея, поддержка. Каждое обращение уходит пушем от hub-бота всем
админам платформы (ADMIN_TELEGRAM_IDS) с контекстом: кто, из какого магазина,
с какого экрана, версия приложения. Копию в БД не храним — история живёт
в Telegram (решение владельца от 2026-09-10).
"""

import logging
from collections import deque
from datetime import datetime, timezone
from html import escape
from time import monotonic
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings
from app.models import SellerBot

logger = logging.getLogger(__name__)

# Русские подписи типов в пуше владельцу: все продавецские пуши hub — русские
FEEDBACK_TYPES = {
    "bug": "🐛 Проблема",
    "idea": "💡 Идея",
    "support": "💬 Поддержка",
}

KIND_LABELS = {"buyer": "от покупателя", "seller": "от продавца"}


class FeedbackIn(BaseModel):
    """Общая форма для покупательского и продавцовского эндпоинтов."""

    type: Literal["bug", "idea", "support"]
    message: str = Field(min_length=1, max_length=1000)
    screen: str = Field(default="", max_length=128)
    app_version: str = Field(default="", max_length=32)


# --- простой rate-limit: 5 обращений в час на отправителя ---
# Ин-процесс и сознательно: Railway работает одним сервисом, а защита нужна
# от флуда в личку владельца, а не от распределённой атаки.
_RATE_LIMIT = 5
_RATE_WINDOW_SECONDS = 3600.0
_recent: dict[tuple[str, int], deque] = {}


def rate_limited(kind: str, sender_id: int) -> bool:
    """True, если лимит исчерпан. Иначе отмечает обращение в окне."""
    now = monotonic()
    hits = _recent.setdefault((kind, sender_id), deque())
    while hits and now - hits[0] > _RATE_WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= _RATE_LIMIT:
        return True
    hits.append(now)
    return False


def reset_rate_limit() -> None:
    """Сброс окна — для тестов."""
    _recent.clear()


async def send_feedback(
    *,
    kind: str,
    feedback_type: str,
    sender_id: int,
    sender_name: str | None,
    sender_username: str | None,
    bot: SellerBot,
    message: str,
    screen: str,
    app_version: str,
) -> bool:
    """Пуш всем админам платформы. True — хотя бы одна доставка прошла.

    Текст сообщения экранируется: hub-бот шлёт с ParseMode.HTML, а покупатель
    пишет что угодно. Падение доставки одному админу не мешает остальным.
    """
    from app.bots.hub import hub_bot

    who = " · ".join(
        part
        for part in (
            (sender_name or "").strip(),
            f"@{sender_username}" if sender_username else "",
            f"ID {sender_id}",
        )
        if part
    )
    shop = bot.shop_name or bot.display_name
    username_line = f" · @{bot.bot_username}" if bot.bot_username else ""
    text = (
        f"{FEEDBACK_TYPES[feedback_type]} · фидбек Botify ({KIND_LABELS[kind]})\n\n"
        f"{escape(message)}\n\n"
        f"— {escape(who)}\n"
        f"Магазин: {escape(shop)} · bot_id {bot.id}{username_line}\n"
        f"Экран: {escape(screen.strip()) or '—'} · Версия: {escape(app_version.strip()) or '—'}\n"
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    admin_ids = get_settings().admin_ids
    if not admin_ids:
        return False

    sent = False
    for admin_id in admin_ids:
        try:
            await hub_bot.send_message(admin_id, text)
            sent = True
        except Exception:
            logger.exception("Фидбек не доставлен админу %s", admin_id)
    return sent

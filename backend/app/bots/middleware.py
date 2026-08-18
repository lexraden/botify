"""Сбор базы: каждый, кто написал seller-боту, попадает в customers этого бота."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from app.services.channels import TgUserInfo, upsert_customer

logger = logging.getLogger(__name__)


class CustomerTrackerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        bot_record = data.get("bot_record")
        tg_user = event.from_user
        if bot_record is not None and tg_user is not None and not tg_user.is_bot:
            source = None
            if event.text and event.text.startswith("/start "):
                source = event.text.split(maxsplit=1)[1][:128]
            try:
                customer, _ = await upsert_customer(
                    bot_record,
                    TgUserInfo(
                        telegram_id=tg_user.id,
                        username=tg_user.username,
                        first_name=tg_user.first_name,
                        language_code=tg_user.language_code,
                    ),
                    source=source,
                )
                data["customer"] = customer
            except Exception:
                logger.exception("Не удалось сохранить покупателя bot_id=%s", bot_record.id)
        return await handler(event, data)

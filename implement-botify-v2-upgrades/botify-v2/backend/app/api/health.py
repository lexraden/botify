from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_api_session
from app.models import OrderChat

router = APIRouter()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_api_session)) -> dict:
    await session.execute(text("SELECT 1"))

    # базовые счётчики чатов для мониторинга (время первого ответа не считаем)
    counts: dict[str, int] = {}
    for status, total in (
        await session.execute(select(OrderChat.status, func.count()).group_by(OrderChat.status))
    ).all():
        counts[status] = total
    chats = {
        "total": sum(counts.values()),
        "active": counts.get("active", 0),
        "locked": counts.get("locked_by_timeout", 0) + counts.get("archived", 0),
    }
    return {"status": "ok", "chats": chats}

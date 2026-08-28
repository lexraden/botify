"""Отзывы: подпись автора, пуш продавцу о новом отзыве, автопубликация.

Подписывается отзыв именем из Telegram; псевдоним ниже — запасной вариант
для тех, у кого имени в профиле нет."""

import html
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.bots.hub import hub_bot
from app.config import get_settings
from app.db import get_session
from app.models import ProductReview

logger = logging.getLogger(__name__)

# Запасная подпись для профилей без имени. К покупателю не привязана:
# у разных его отзывов псевдонимы будут разные, так и задумано.
_NAMES = [
    "Александр", "Алексей", "Анатолий", "Андрей", "Анна", "Артём", "Борис",
    "Валерия", "Василий", "Вера", "Виктория", "Владимир", "Глеб", "Дарья",
    "Дмитрий", "Егор", "Екатерина", "Елена", "Иван", "Игорь", "Илья",
    "Кирилл", "Ксения", "Лев", "Мария", "Максим", "Михаил", "Никита",
    "Николай", "Ольга", "Павел", "Полина", "Роман", "Светлана", "Сергей",
    "Татьяна", "Фёдор", "Юлия", "Юрий", "Яна",
]
_INITIALS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"


def random_author_name() -> str:
    return f"{secrets.choice(_NAMES)} {secrets.choice(_INITIALS)}."


async def notify_new_review(
    seller_tg: int, product_title: str, rating: int, body: str | None
) -> None:
    """Новый отзыв -> пуш продавцу в hub-бот. Правки оценки не уведомляются.

    Название товара и текст отзыва экранируются: hub-бот шлёт с parse_mode=HTML,
    и один символ «<» в отзыве покупателя оставил бы продавца без уведомления.
    Обрезаем до экранирования — чтобы срез не разрубил html-сущность.
    """
    title = html.escape(product_title[:120])
    text = (
        f"⭐ Новый отзыв о «{title}»: {'★' * rating}\n"
        + (f"«{html.escape(body[:300])}»\n" if body else "")
        + "Ответить можно в кабинете, вкладка «Отзывы»."
    )
    try:
        await hub_bot.send_message(seller_tg, text)
    except Exception:
        logger.exception("Не удалось уведомить продавца о новом отзыве")


async def auto_publish_stale_reviews() -> int:
    """Отзывы, ждущие продавца дольше review_moderation_days, публикуются сами.

    Порог существует, чтобы продавец видел претензии, а не цензурировал их:
    если он не зашёл в кабинет, молчание не должно прятать отзыв вечно.
    Возвращает число опубликованных за проход (для лога джоба)."""
    deadline = datetime.now(timezone.utc) - timedelta(
        days=get_settings().review_moderation_days
    )
    async with get_session() as session:
        result = await session.execute(
            select(ProductReview)
            .where(ProductReview.status == "pending", ProductReview.created_at < deadline)
            .with_for_update()
        )
        stale = result.scalars().all()
        for review in stale:
            review.status = "published"
            review.moderated_at = datetime.now(timezone.utc)
        await session.commit()
    return len(stale)

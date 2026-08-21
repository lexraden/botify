"""Команды супер-админа платформы в hub-боте."""

from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import select

from app.config import get_settings
from app.db import get_session
from app.models import Payout, Seller

router = Router()


@router.message(Command("health"))
async def health(message: types.Message) -> None:
    """/health — состояние платёжной интеграции. Видно только админам."""
    if message.from_user is None:
        return
    async with get_session() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == message.from_user.id))
        ).scalar_one_or_none()
    is_admin = (seller is not None and seller.is_admin) or (
        message.from_user.id in get_settings().admin_ids
    )
    if not is_admin:
        return  # для обычных продавцов команды как будто не существует

    settings = get_settings()
    lines = [
        "<b>Платежи</b>",
        f"Сеть: <b>{settings.crypto_pay_network}</b>",
    ]

    from app.payments.client import get_crypto_pay

    crypto = get_crypto_pay()
    if crypto is None:
        lines.append("❌ CRYPTO_PAY_TOKEN не задан — оплата не работает")
    else:
        try:
            me = await crypto.get_me()
            lines.append(f"✅ Crypto Pay отвечает, приложение: <b>{getattr(me, 'name', '—')}</b>")
        except Exception as exc:
            lines.append(f"❌ Crypto Pay не отвечает: <code>{type(exc).__name__}: {exc}</code>")

    if settings.webhook_base_url:
        lines.append(
            "\nWebhook для настроек Crypto Pay:\n"
            f"<code>{settings.webhook_base_url}/webhook/cryptopay</code>"
        )
    else:
        lines.append("\n⚠️ WEBHOOK_BASE_URL не задан")

    lines.append(
        "\nНе забудь включить <b>Security → Transfers</b> в приложении Crypto Pay — "
        "без этого выплаты продавцам не пройдут."
    )
    await message.answer("\n".join(lines))


@router.message(Command("payouts"))
async def payouts(message: types.Message) -> None:
    """/payouts — незавершённые выплаты с причиной отказа. Только для админов."""
    if message.from_user is None:
        return
    async with get_session() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == message.from_user.id))
        ).scalar_one_or_none()
        is_admin = (seller is not None and seller.is_admin) or (
            message.from_user.id in get_settings().admin_ids
        )
        if not is_admin:
            return

        stuck = (
            (
                await session.execute(
                    select(Payout)
                    .where(Payout.status.in_(("pending", "failed")))
                    .order_by(Payout.id.desc())
                    .limit(10)
                )
            )
            .scalars()
            .all()
        )

    if not stuck:
        await message.answer("✅ Незавершённых выплат нет.")
        return

    lines = ["<b>Незавершённые выплаты</b>"]
    for payout in stuck:
        icon = "🔴" if payout.status == "failed" else "🟡"
        lines.append(f"\n{icon} Заказ #{payout.order_id} — {payout.amount} USDT")
        if payout.last_error:
            lines.append(f"<code>{payout.last_error}</code>")
    await message.answer("\n".join(lines))

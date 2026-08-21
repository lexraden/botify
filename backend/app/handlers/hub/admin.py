"""Команды супер-админа платформы в hub-боте."""

from decimal import Decimal, InvalidOperation

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy import func, select

from app.config import get_settings
from app.db import get_session
from app.models import Payout, PayoutBatch, Seller, SellerBot
from app.money import fmt

router = Router()

# Потолок на ручной тестовый перевод: команда трогает реальные деньги
TEST_PAYOUT_MAX = Decimal("5")


async def _is_admin(user_id: int) -> bool:
    async with get_session() as session:
        seller = (
            await session.execute(select(Seller).where(Seller.telegram_id == user_id))
        ).scalar_one_or_none()
    return (seller is not None and seller.is_admin) or user_id in get_settings().admin_ids


@router.message(Command("health"))
async def health(message: types.Message) -> None:
    """/health — состояние платёжной интеграции. Видно только админам."""
    if message.from_user is None or not await _is_admin(message.from_user.id):
        return  # для обычных продавцов команды как будто не существует

    settings = get_settings()
    lines = [
        "<b>Платежи</b>",
        f"Сеть: <b>{settings.crypto_pay_network}</b>",
        f"Минимум для выплаты: <b>{fmt(settings.min_payout_usdt)} USDT</b>",
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
        try:
            balances = await crypto.get_balance()
            non_zero = [b for b in balances if float(b.available) or float(b.onhold)]
            if non_zero:
                lines.append("\n<b>Баланс приложения</b>")
                for b in non_zero:
                    lines.append(
                        f"• {b.currency_code}: {fmt(b.available)} (в холде {fmt(b.onhold)})"
                    )
            else:
                lines.append("\n⚠️ Баланс приложения пуст — выплатам не из чего уходить")
        except Exception as exc:
            lines.append(f"\n⚠️ Баланс не прочитался: <code>{type(exc).__name__}: {exc}</code>")

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
    """/payouts — что накоплено и что застряло. Только для админов."""
    if message.from_user is None or not await _is_admin(message.from_user.id):
        return

    minimum = Decimal(str(get_settings().min_payout_usdt))
    async with get_session() as session:
        accrued = (
            await session.execute(
                select(
                    SellerBot.bot_username,
                    func.sum(Payout.amount),
                    func.count(),
                    Seller.telegram_id,
                )
                .join(Seller, Seller.id == Payout.seller_id)
                .join(SellerBot, SellerBot.id == Payout.bot_id)
                .where(Payout.status.in_(("pending", "failed")))
                .group_by(SellerBot.bot_username, Seller.telegram_id)
                .order_by(func.sum(Payout.amount).desc())
                .limit(10)
            )
        ).all()
        batches = list(
            (
                await session.execute(
                    select(PayoutBatch)
                    .where(PayoutBatch.status.in_(("pending", "failed", "too_small")))
                    .order_by(PayoutBatch.id.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

    if not accrued and not batches:
        await message.answer("✅ Незавершённых выплат нет.")
        return

    lines = []
    if accrued:
        lines.append("<b>Накоплено к выплате</b>")
        for bot_username, total, count, telegram_id in accrued:
            icon = "🟢" if Decimal(total) >= minimum else "🟡"
            lines.append(
                f"{icon} @{bot_username} (продавец <code>{telegram_id}</code>) — "
                f"{fmt(total)} USDT за {count} зак."
            )
        lines.append(f"\n🟡 = меньше минимума ({fmt(minimum)} USDT), ждёт следующих продаж")

    if batches:
        lines.append("\n<b>Пачки, которые не ушли</b>")
        for batch in batches:
            icon = {"failed": "🔴", "too_small": "🟡"}.get(batch.status, "⏳")
            lines.append(f"\n{icon} #{batch.id} — {fmt(batch.amount)} USDT ({batch.status})")
            if batch.last_error:
                lines.append(f"<code>{batch.last_error}</code>")

    await message.answer("\n".join(lines))


@router.message(Command("testpayout"))
async def testpayout(message: types.Message, command: CommandObject) -> None:
    """/testpayout <telegram_id> <сумма> — проверить, что перевод вообще проходит.

    Нужна ровно для одного вопроса: «могу ли я из своего Crypto Pay отправить
    деньги продавцу?» Отправляет реальные USDT, поэтому только для админа
    и с потолком в TEST_PAYOUT_MAX.
    """
    if message.from_user is None or not await _is_admin(message.from_user.id):
        return

    args = (command.args or "").split()
    if len(args) != 2:
        await message.answer(
            "Формат: <code>/testpayout telegram_id сумма</code>\n"
            "Например: <code>/testpayout 123456789 1</code>\n"
            f"Это настоящий перевод, максимум {fmt(TEST_PAYOUT_MAX)} USDT."
        )
        return
    try:
        user_id, amount = int(args[0]), Decimal(args[1])
    except (ValueError, InvalidOperation):
        await message.answer("Не разобрал аргументы: нужен telegram_id и сумма числом.")
        return
    if amount <= 0 or amount > TEST_PAYOUT_MAX:
        await message.answer(f"Сумма должна быть от 0 до {fmt(TEST_PAYOUT_MAX)} USDT.")
        return

    from app.payments.client import get_crypto_pay

    crypto = get_crypto_pay()
    if crypto is None:
        await message.answer("❌ CRYPTO_PAY_TOKEN не задан.")
        return

    import time

    spend_id = f"testpayout-{message.from_user.id}-{int(time.time())}"
    try:
        transfer = await crypto.transfer(
            user_id=user_id, asset="USDT", amount=float(amount), spend_id=spend_id
        )
    except Exception as exc:
        await message.answer(
            f"❌ Перевод {fmt(amount)} USDT на <code>{user_id}</code> не прошёл:\n"
            f"<code>{type(exc).__name__}: {exc}</code>\n\n"
            "AMOUNT_TOO_SMALL — сумма ниже минимума Crypto Pay, попробуй больше.\n"
            "USER_NOT_FOUND — получатель ни разу не открывал @CryptoBot.\n"
            "Ошибка про transfers — включи Security → Transfers в приложении."
        )
        return
    await message.answer(
        f"✅ Перевод прошёл: {fmt(amount)} USDT на <code>{user_id}</code>, "
        f"transfer_id <code>{transfer.transfer_id}</code>."
    )

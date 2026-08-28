"""Платёжный флоу: инвойс на заказ -> invoice_paid -> уведомления, выдача digital,
запись Payout (сам transfer продавцу — этап 6)."""

import html
import logging
from decimal import Decimal

from sqlalchemy import or_, select, update

from app.bots.runner import make_seller_bot
from app.config import get_settings
from app.db import get_session
from app.money import fmt
from app.models import Customer, Order, OrderItem, Payout, Product, Seller, SellerBot
from app.payments.client import get_crypto_pay
from app.security import decrypt_bot_token
from app.services import seller_texts
from app.services.notify_texts import buyer_text

logger = logging.getLogger(__name__)


async def discard_invoice(invoice_id: int | None) -> bool:
    """Снять неоплаченный счёт в Crypto Pay, чтобы по нему нельзя было заплатить.

    Нужно везде, где заказ перестаёт ждать оплату по этой ссылке: отмена и
    выдача новой ссылки. Иначе покупатель платит по мёртвой ссылке из
    переписки с @CryptoBot, вебхук приходит на отменённый (или уже
    переоформленный) заказ и молча ничего не делает — деньги приняты, товара
    нет, никто не уведомлён.

    Побочно это держит инвариант «у заказа не больше одного оплачиваемого
    счёта», на который опирается сверка (app/payments/reconcile.py).

    Неудача не критична и наверх не идёт: счёт протухнет сам через час.
    """
    crypto = get_crypto_pay()
    if crypto is None or invoice_id is None:
        return False
    try:
        await crypto.delete_invoice(invoice_id)
        return True
    except Exception:
        logger.warning("Не удалось снять счёт %s — истечёт сам", invoice_id, exc_info=True)
        return False


def invoice_description(order_id: int, shop: SellerBot | None) -> str:
    """Строка, которую покупатель видит в @CryptoBot над кнопкой оплаты.

    Название магазина здесь — единственное место, где оно вообще может
    появиться: «Recipient» в счёте — это имя приложения Crypto Pay, оно одно
    на всю платформу и per-invoice не задаётся. Без названия покупатель видит
    «Botify App» и «Заказ #12» и не понимает, кому платит.

    Имя берём то же, что покупатель минуту назад видел в шапке витрины
    (`api/store.py`, ShopOut.shop_name), а не `display_name`: последнее —
    название из /newshop, то есть имя магазина со стороны продавца. Если в
    счёте окажется третье название, платёж выглядит чужим.

    Магазин передаётся вызывающим — он у обоих уже в руках (`ctx.bot`).
    Собственный запрос в БД добавлял бы на платёжный путь и лишний рейс, и
    новую точку отказа там, где раньше не было ни одной.
    """
    if shop is None:
        return f"Заказ #{order_id}"
    name = shop.shop_name or (f"@{shop.bot_username}" if shop.bot_username else None)
    return f"Заказ #{order_id} — {name}" if name else f"Заказ #{order_id}"


async def create_invoice_for_order(
    order_id: int, total: Decimal, shop: SellerBot | None = None
) -> str | None:
    """Создаёт инвойс Crypto Pay. Возвращает ссылку на оплату (или None без токена)."""
    crypto = get_crypto_pay()
    if crypto is None:
        return None
    invoice = await crypto.create_invoice(
        asset="USDT",
        amount=float(total),
        description=invoice_description(order_id, shop),
        payload=f"order:{order_id}",
        allow_comments=False,
        allow_anonymous=False,
        expires_in=3600,
    )
    async with get_session() as session:
        order = await session.get(Order, order_id)
        if order is not None:
            order.invoice_id = invoice.invoice_id
            await session.commit()
    return invoice.bot_invoice_url


def _provider_fee(total: Decimal, fee_amount: Decimal | None) -> Decimal:
    """Сколько Crypto Pay удержал с этого платежа.

    На долю продавца не влияет — это расход платформы из её же комиссии.
    Пишем в БД, чтобы маржа была видна: наша комиссия минус эта сумма.
    Точное значение приходит в вебхуке (fee_amount), иначе — по ставке.
    """
    if fee_amount is not None and fee_amount >= 0:
        return Decimal(fee_amount).quantize(Decimal("0.000001"))
    rate = Decimal(str(get_settings().crypto_pay_fee_pct))
    return (total * rate / 100).quantize(Decimal("0.000001"))


async def handle_invoice_paid(
    invoice_id: int, payload: str | None, fee_amount: Decimal | None = None
) -> bool:
    """Обработка вебхука invoice_paid. Идемпотентна: повторный вызов — no-op.
    Возвращает True, если заказ был переведён в оплаченные этим вызовом."""
    from sqlalchemy.sql import func

    async with get_session() as session:
        # FOR UPDATE: Crypto Pay ретраит вебхук, и две доставки подряд могут
        # войти сюда одновременно. Без блокировки обе увидят pending_payment
        # и обе пойдут создавать выплату.
        order = (
            await session.execute(
                select(Order).where(Order.invoice_id == invoice_id).with_for_update()
            )
        ).scalar_one_or_none()
        if order is None and payload and payload.startswith("order:"):
            # инвойс успели создать, но записать invoice_id заказу не успели
            raw_id = payload.split(":", 1)[1]
            if raw_id.isdigit():
                order = (
                    await session.execute(
                        select(Order).where(Order.id == int(raw_id)).with_for_update()
                    )
                ).scalar_one_or_none()

        if order is None:
            logger.warning("invoice_paid для неизвестного invoice_id=%s", invoice_id)
            return False
        if order.status != "pending_payment":
            return False  # уже обработан (ретрай вебхука)

        order.status = "paid"
        order.paid_at = func.now()

        seller = await session.get(Seller, order.seller_id)
        customer = await session.get(Customer, order.customer_id)

        # С продавца берём только нашу комиссию. Комиссию Crypto Pay платформа
        # платит из неё же, поэтому доля продавца от неё не зависит; сама
        # комиссия сервиса пишется в provider_fee, чтобы видеть реальную маржу.
        commission = (order.total * seller.commission_pct / 100).quantize(Decimal("0.000001"))
        provider_fee = _provider_fee(order.total, fee_amount)
        payout = Payout(
            order_id=order.id,
            seller_id=seller.id,
            bot_id=order.bot_id,
            amount=order.total - commission,
            commission=commission,
            provider_fee=provider_fee,
        )
        session.add(payout)

        items = (
            await session.execute(
                select(OrderItem, Product)
                .join(Product, Product.id == OrderItem.product_id)
                .where(OrderItem.order_id == order.id)
            )
        ).all()

        # Списание стока живёт в этой же секции (после гарда статуса): ретрай
        # вебхука сюда не доходит, поэтому дважды списать невозможно. Условный
        # UPDATE атомарен — два заказа на последнюю штуку не уведут сток в минус.
        # Товары со стоком NULL учёту штук не подлежат.
        qty_by_product: dict[int, int] = {}
        titles: dict[int, str] = {}
        for item, product in items:
            titles[item.product_id] = product.title
            if product.stock is None:
                continue
            qty_by_product[item.product_id] = qty_by_product.get(item.product_id, 0) + item.qty
        # Товары, которых не хватило: деньги уже приняты, отправить их нечем.
        # Молча это оставлять нельзя — возврата в MVP нет, разбираться сторонам
        # придётся вручную, и узнать о проблеме они должны сразу.
        sold_out: list[str] = []
        for product_id, qty in qty_by_product.items():
            spent = await session.execute(
                update(Product)
                .where(
                    Product.id == product_id,
                    or_(Product.stock.is_(None), Product.stock >= qty),
                )
                .values(stock=Product.stock - qty)
                .execution_options(synchronize_session=False)
            )
            if spent.rowcount == 0:
                # гонка «чекнулись, пока сток кончился»: деньги уже приняты,
                # заказ не разворачиваем, но и отрицательный сток не пишем
                sold_out.append(titles.get(product_id, str(product_id)))
                logger.error(
                    "Недостаточно стока товара id=%s для заказа %s (нужно %s) — сток не списан",
                    product_id,
                    order.id,
                    qty,
                )

        # Digital/услуги с настроенной выдачей доставляются сразу.
        # Название и ссылка — от продавца, а сообщение уходит с parse_mode=HTML:
        # один «<» в названии оставил бы покупателя без подтверждения оплаты
        # и без самого контента (см. tests/test_html_safety.py)
        digital_lines = [
            f"• {html.escape(product.title)}: {html.escape(product.digital_content['url'])}"
            for _, product in items
            if product.type in ("digital", "service")
            and product.digital_content
            and product.digital_content.get("url")
        ]
        all_digital = all(product.type in ("digital", "service") for _, product in items)
        if digital_lines and all_digital:
            order.status = "delivered"
            # метка доставки: с неё считается окно чата заказа (72 часа)
            order.delivered_at = func.now()

        order_summary = "\n".join(
            f"• {html.escape(product.title)} × {item.qty}" for item, product in items
        )
        await session.commit()

        order_id, order_total = order.id, order.total
        customer_tg = customer.telegram_id
        seller_tg = seller.telegram_id
        # язык пуши продавцу фиксируем до коммита: дальше сессия закрыта
        seller_locale = seller_texts.seller_locale(seller)

        # Токен бота покупателя — для уведомления в ЛС
        await session.refresh(customer, ["bot"])
        seller_bot_token = decrypt_bot_token(customer.bot.bot_token_encrypted)

    await _notify(
        seller_bot_token,
        customer_tg,
        # язык уведомления — как в Mini App покупателя (notify_texts)
        buyer_text(customer, "paid.header", id=order_id)
        + f"\n\n{order_summary}\n"
        + (
            "\n" + buyer_text(customer, "paid.materials") + "\n" + "\n".join(digital_lines)
            if digital_lines
            else "\n" + buyer_text(customer, "paid.preparing")
        )
        # доставленные цифровые заказы можно оценивать — подводим к форме отзыва
        + ("\n" + buyer_text(customer, "paid.review") if all_digital else "")
        # закончился между заказом и оплатой: честнее сказать сразу, чем дать
        # человеку ждать посылку, которой не будет
        + (
            "\n\n"
            + buyer_text(
                customer, "paid.sold_out", items=", ".join(html.escape(t) for t in sold_out)
            )
            if sold_out
            else ""
        ),
    )

    from app.bots.hub import hub_bot

    try:
        await hub_bot.send_message(
            seller_tg,
            seller_texts.text(
                seller_locale,
                "push.paid",
                id=order_id,
                total=fmt(order_total),
                next=(
                    seller_texts.text(seller_locale, "push.paid_digital")
                    if digital_lines and all_digital
                    else seller_texts.text(seller_locale, "push.paid_fulfill")
                ),
            )
            + (
                seller_texts.text(
                    seller_locale,
                    "push.paid_sold_out",
                    items=", ".join(html.escape(t) for t in sold_out),
                )
                if sold_out
                else ""
            ),
        )
    except Exception:
        logger.exception("Не удалось уведомить продавца о заказе %s", order_id)

    # Доля продавца остаётся в кассе магазина: перевод запускает только
    # сам продавец кнопкой «Вывести» (авто-выплат нет по решению владельца).
    return True


async def _notify(bot_token: str, chat_id: int, text: str) -> None:
    bot = make_seller_bot(bot_token)
    try:
        await bot.send_message(chat_id, text)
    except Exception:
        logger.exception("Не удалось отправить уведомление chat_id=%s", chat_id)
    finally:
        await bot.session.close()

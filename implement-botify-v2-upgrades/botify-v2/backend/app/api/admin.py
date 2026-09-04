"""Служебные эндпоинты для супер-админа платформы."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_seller
from app.models import Seller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")


def require_admin(seller: Seller = Depends(get_seller)) -> Seller:
    if not seller.is_admin:
        raise HTTPException(status_code=403, detail="admins only")
    return seller


class PaymentsHealthOut(BaseModel):
    configured: bool          # задан ли CRYPTO_PAY_TOKEN
    network: str              # mainnet | testnet
    reachable: bool           # ответил ли Crypto Pay на getMe
    app_name: str | None
    error: str | None
    webhook_url: str | None   # что указать в настройках приложения Crypto Pay


@router.get("/payments/health", response_model=PaymentsHealthOut)
async def payments_health(_: Seller = Depends(require_admin)) -> PaymentsHealthOut:
    """Проверка платёжной интеграции: виден ли токен приложения и отвечает ли API.

    Нужен, чтобы отличить «оплата не настроена» от «оплата настроена, но
    что-то не так с сетью или токеном» — по одному запросу, без чтения логов.
    """
    from app.config import get_settings
    from app.payments.client import get_crypto_pay

    settings = get_settings()
    webhook_url = (
        f"{settings.webhook_base_url}/webhook/cryptopay" if settings.webhook_base_url else None
    )
    crypto = get_crypto_pay()
    if crypto is None:
        return PaymentsHealthOut(
            configured=False,
            network=settings.crypto_pay_network,
            reachable=False,
            app_name=None,
            error="CRYPTO_PAY_TOKEN is not set",
            webhook_url=webhook_url,
        )

    try:
        me = await crypto.get_me()
    except Exception as exc:
        logger.exception("Crypto Pay getMe не прошёл")
        return PaymentsHealthOut(
            configured=True,
            network=settings.crypto_pay_network,
            reachable=False,
            app_name=None,
            error=f"{type(exc).__name__}: {exc}",
            webhook_url=webhook_url,
        )

    return PaymentsHealthOut(
        configured=True,
        network=settings.crypto_pay_network,
        reachable=True,
        app_name=getattr(me, "name", None),
        error=None,
        webhook_url=webhook_url,
    )

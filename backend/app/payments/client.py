"""Клиент Crypto Pay (pay.crypt.bot). Один API-токен на всю платформу —
мультибот касается только приёма сообщений, платёжный слой единый (см. бриф)."""

import hashlib
import hmac
from functools import lru_cache

from aiocryptopay import AioCryptoPay, Networks

from app.config import get_settings


@lru_cache
def get_crypto_pay() -> AioCryptoPay | None:
    settings = get_settings()
    if not settings.crypto_pay_token:
        return None  # локальная разработка/тесты без платежей
    network = Networks.TEST_NET if settings.crypto_pay_network == "testnet" else Networks.MAIN_NET
    return AioCryptoPay(token=settings.crypto_pay_token, network=network)


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Подпись вебхука: HMAC-SHA256(body), ключ = SHA256(api_token)."""
    token = get_settings().crypto_pay_token
    if not token or not signature:
        return False
    secret = hashlib.sha256(token.encode()).digest()
    computed = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)

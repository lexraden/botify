"""Валидация Telegram WebApp initData.

Единственный источник истины о том, кто открыл Mini App: подпись HMAC-SHA256,
где ключ = HMAC("WebAppData", bot_token). Витрина покупателя подписана токеном
конкретного seller-бота, кабинет продавца — токеном hub-бота.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def validate_init_data(init_data: str, bot_token: str, max_age_sec: int = 86400) -> dict | None:
    """Возвращает распарсенные поля initData или None, если подпись/срок невалидны."""
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        return None
    if max_age_sec and time.time() - auth_date > max_age_sec:
        return None

    if "user" in parsed:
        try:
            parsed["user"] = json.loads(parsed["user"])
        except json.JSONDecodeError:
            return None
    return parsed


def sign_init_data(fields: dict, bot_token: str) -> str:
    """Собирает подписанную строку initData. Используется в тестах."""
    from urllib.parse import urlencode

    flat = {
        k: (json.dumps(v, separators=(",", ":")) if isinstance(v, dict) else str(v))
        for k, v in fields.items()
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(flat.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    flat["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(flat)

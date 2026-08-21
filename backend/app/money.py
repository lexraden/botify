"""Деньги для показа человеку.

В БД суммы лежат как Numeric(18, 6) — это нужно для точности расчётов, но
в тексте выглядит как «1.000000». Наружу (сообщения бота, ответы API) сумма
всегда идёт через fmt().
"""

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def fmt(amount: Decimal | float | int | str) -> str:
    """«1.00», «0.95», «19.98» — две цифры после точки, без хвоста нулей."""
    return f"{quantize(amount):.2f}"


def quantize(amount: Decimal | float | int | str) -> Decimal:
    """Округление до копеек для расчётов, которые увидит пользователь."""
    return Decimal(str(amount)).quantize(CENTS, rounding=ROUND_HALF_UP)

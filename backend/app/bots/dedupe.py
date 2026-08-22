"""Защита от повторной доставки апдейтов Telegram.

Telegram ретраит вебхук, пока не получит быстрый 200, поэтому один апдейт
может прийти дважды (таймаут, рестарт). Держим ограниченный LRU-кэш update_id
в памяти процесса. Процесс один (uvicorn без --workers), для нескольких
воркеров кэш стал бы несогласованным — тогда нужен общий стор (Redis/БД).
"""

from collections import OrderedDict

_MAX_SEEN = 8192

_seen: OrderedDict[tuple[str, int], None] = OrderedDict()


def duplicate_update(scope: str, update_id: int | None) -> bool:
    """True — такой апдейт уже обрабатывался недавно; False — первый раз."""
    if update_id is None:
        return False
    key = (scope, update_id)
    if key in _seen:
        _seen.move_to_end(key)
        return True
    _seen[key] = None
    while len(_seen) > _MAX_SEEN:
        _seen.popitem(last=False)
    return False

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


_WINDOWS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = Lock()
_WINDOW_SECONDS = 60.0


def check_chat_rate_limit(user_id: str, requests_per_minute: int) -> int:
    """In-process per-user sliding window. Returns retry-after seconds, or zero."""
    now = monotonic()
    cutoff = now - _WINDOW_SECONDS
    limit = max(1, int(requests_per_minute))
    with _LOCK:
        window = _WINDOWS[user_id]
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= limit:
            return max(1, int(window[0] + _WINDOW_SECONDS - now + 0.999))
        window.append(now)
        if len(_WINDOWS) > 10000:
            for key in tuple(_WINDOWS):
                if not _WINDOWS[key] or _WINDOWS[key][-1] <= cutoff:
                    _WINDOWS.pop(key, None)
    return 0


def clear_chat_rate_limits() -> None:
    with _LOCK:
        _WINDOWS.clear()

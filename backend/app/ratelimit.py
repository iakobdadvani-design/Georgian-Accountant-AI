"""In-memory sliding-window limits for sign-in, sign-up and password reset.

Per process: with several workers or servers, each keeps its own counts (limits then apply per worker), which
still stops password guessing at scale. Move to Redis if the app ever runs on more than one machine.
"""

import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: int):
        self.max_events, self.window = max_events, window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and events[0] <= now - self.window:
            events.popleft()
        return events

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._trim(key, time.monotonic())) >= self.max_events

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._trim(key, now).append(now)

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)


# Failed sign-ins: per account (guessing one password) and per address (trying many accounts).
LOGIN_BY_EMAIL = RateLimiter(5, 15 * 60)
LOGIN_BY_IP = RateLimiter(30, 15 * 60)
REGISTER_BY_IP = RateLimiter(10, 60 * 60)
RESET_BY_IP = RateLimiter(10, 60 * 60)
RESET_BY_EMAIL = RateLimiter(3, 60 * 60)
ALL = (LOGIN_BY_EMAIL, LOGIN_BY_IP, REGISTER_BY_IP, RESET_BY_IP, RESET_BY_EMAIL)

"""프로세스 내 슬라이딩 윈도우 제한기 — 단일 워커 전제, 재시작 시 초기화."""

import math
import threading
import time
from collections import deque

from app.config import settings


class SlidingWindowLimiter:
    """키별로 창 안 이벤트 수를 세는 슬라이딩 윈도우."""

    def __init__(self, max_events: int, window_seconds: float) -> None:
        if max_events < 0:
            raise ValueError("max_events는 0 이상이어야 합니다.")
        if window_seconds <= 0:
            raise ValueError("window_seconds는 양수여야 합니다.")
        self.max_events = max_events
        self.window_seconds = float(window_seconds)
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def try_acquire(self, key: str) -> int:
        """허용하면 이벤트를 기록하고 0, 차단이면 대기해야 하는 초(>0)를 반환."""
        if self.max_events == 0:
            return 0
        now = time.time()
        with self._lock:
            events = self._prune(key, now)
            if len(events) >= self.max_events:
                return self._retry_after(events, now)
            events.append(now)
            self._events[key] = events
            return 0

    def blocked_for(self, key: str) -> int:
        """차단 중이면 남은 대기 초(>0), 아니면 0. 이벤트를 기록하지 않는다."""
        if self.max_events == 0:
            return 0
        now = time.time()
        with self._lock:
            events = self._prune(key, now)
            if len(events) >= self.max_events:
                return self._retry_after(events, now)
        return 0

    def record(self, key: str) -> None:
        """이벤트 1건을 기록한다(허용 여부와 무관). 실패 횟수 집계용."""
        if self.max_events == 0:
            return
        now = time.time()
        with self._lock:
            events = self._prune(key, now)
            events.append(now)
            self._events[key] = events

    def clear(self, key: str) -> None:
        """키의 기록을 지운다(예: 로그인 성공 시 실패 카운터 초기화)."""
        with self._lock:
            self._events.pop(key, None)

    def reset(self) -> None:
        """모든 키의 기록을 지운다(테스트·운영 점검용)."""
        with self._lock:
            self._events.clear()

    def _prune(self, key: str, now: float) -> deque[float]:
        self._maybe_cleanup(now)
        events = self._events.get(key, deque())
        horizon = now - self.window_seconds
        while events and events[0] <= horizon:
            events.popleft()
        if events:
            self._events[key] = events
        else:
            self._events.pop(key, None)
        return events

    def _maybe_cleanup(self, now: float) -> None:
        """키가 너무 많이 쌓이면(500개 초과) 만료된 키를 일괄 정리해 메모리 누수를 방지한다."""
        if len(self._events) < 500:
            return
        horizon = now - self.window_seconds
        stale_keys = [k for k, q in self._events.items() if not q or q[-1] <= horizon]
        for k in stale_keys:
            self._events.pop(k, None)

    def _retry_after(self, events: deque[float], now: float) -> int:
        return max(1, math.ceil(events[0] + self.window_seconds - now))


login_limiter = SlidingWindowLimiter(settings.login_max_fails, settings.login_lockout_sec)

chat_limiter = SlidingWindowLimiter(settings.chat_rate_per_min, settings.rate_window_seconds)

signup_ip_limiter = SlidingWindowLimiter(
    settings.signup_rate_per_ip_per_min, settings.rate_window_seconds
)

password_reset_ip_limiter = SlidingWindowLimiter(
    settings.password_reset_rate_per_ip_per_min, settings.rate_window_seconds
)


def client_ip(request) -> str:
    """요청을 식별할 IP 키를 반환한다.

    프록시 환경(X-Forwarded-For, X-Real-IP)을 우선 해석하여 실제 클라이언트 IP를 식별한다.
    신뢰되지 않은 다중 프록시 헤더 중 맨 앞(원래 클라이언트)을 안전하게 취한다.
    """
    if request is None:
        return "unknown"
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client = xff.split(",")[0].strip()
        if client:
            return client
    x_real = request.headers.get("x-real-ip")
    if x_real:
        return x_real.strip()
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def retry_after_hint(seconds: int) -> str:
    """429 응답에 넣을 한국어 대기 안내. 60초 미만은 '약 N초 후', 그 이상은 '약 M분 S초 후'."""
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    if m:
        return f"약 {m}분 {s}초 후"
    return f"약 {s}초 후"

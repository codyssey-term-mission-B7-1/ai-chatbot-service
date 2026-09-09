"""프로세스 내 슬라이딩 윈도우 제한기 — 단일 워커 전제, 재시작 시 초기화.

다중 워커·재시작 간 지속·중앙 집계가 필요하면 Redis 같은 외부 저장소로 교체해야 한다.
현재 운영 명령(uvicorn 단일 프로세스)에서는 이 구현으로 충분하다.
"""

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
        events = self._events.get(key, deque())
        horizon = now - self.window_seconds
        while events and events[0] <= horizon:
            events.popleft()
        if events:
            self._events[key] = events
        else:
            self._events.pop(key, None)
        return events

    def _retry_after(self, events: deque[float], now: float) -> int:
        return max(1, math.ceil(events[0] + self.window_seconds - now))


# 로그인 실패 임금(lockout) — 이메일별 실패 누적(#72). 프로세스 메모리 기준.
login_limiter = SlidingWindowLimiter(settings.login_max_fails, settings.login_lockout_sec)

# 채팅 사용자별 분당 요청 상한(#73) — AI 비용 남용 방어. 0이면 비활성화.
chat_limiter = SlidingWindowLimiter(settings.chat_rate_per_min, 60.0)

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

# 회원가입 IP별 분당 요청 상한 — 봇 계정 생성 남용 최소 방어(AUDIT_HARDENING B-1 P0).
signup_ip_limiter = SlidingWindowLimiter(settings.signup_rate_per_ip_per_min, 60.0)

# 비밀번호 재설정 IP별 분당 요청 상한 — 메일 폭탄/계정 존재 열거 속도 제한.
password_reset_ip_limiter = SlidingWindowLimiter(settings.password_reset_rate_per_ip_per_min, 60.0)


def client_ip(request) -> str:
    """요청을 식별할 IP 키를 반환한다.

    Railway/프록시 환경에서는 X-Forwarded-For가 있을 수 있으나 이를 그대로 쓰면
    헤더 변조로 우회 가능하므로, 기본은 request.client.host를 쓰고 추후
    신뢰할 수 있는 프록시 확인 로직을 추가할 때까지 주석으로 남긴다.
    """
    if request is None or request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def retry_after_hint(seconds: int) -> str:
    """429 응답에 넣을 한국어 대기 안내. 60초 미만은 '약 N초 후', 그 이상은 '약 M분 S초 후'."""
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    if m:
        return f"약 {m}분 {s}초 후"
    return f"약 {s}초 후"

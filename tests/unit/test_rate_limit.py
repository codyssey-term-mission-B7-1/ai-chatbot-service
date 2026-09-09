"""유닛 테스트 — 슬라이딩 윈도우 제한기(#72)."""

import time

import pytest

from app.services.rate_limit import SlidingWindowLimiter


def test_try_acquire_allows_up_to_max_then_blocks():
    limiter = SlidingWindowLimiter(2, 60)
    assert limiter.try_acquire("a") == 0
    assert limiter.try_acquire("a") == 0
    wait = limiter.try_acquire("a")
    assert wait >= 1


def test_window_slides_and_old_events_expire():
    limiter = SlidingWindowLimiter(1, 0.05)
    assert limiter.try_acquire("a") == 0
    assert limiter.try_acquire("a") >= 1
    time.sleep(0.06)
    assert limiter.try_acquire("a") == 0


def test_record_and_blocked_for_drive_lockout():
    limiter = SlidingWindowLimiter(2, 60)
    limiter.record("a")
    assert limiter.blocked_for("a") == 0  # 아직 한도 전
    limiter.record("a")
    assert limiter.blocked_for("a") >= 1
    assert limiter.blocked_for("a") <= 60


def test_clear_resets_a_single_key():
    limiter = SlidingWindowLimiter(1, 60)
    limiter.record("a")
    limiter.record("b")
    limiter.clear("a")
    assert limiter.blocked_for("a") == 0
    assert limiter.blocked_for("b") >= 1  # 다른 키는 유지


def test_zero_max_events_disables_limiting():
    limiter = SlidingWindowLimiter(0, 60)
    for _ in range(20):
        assert limiter.try_acquire("a") == 0
    assert limiter.blocked_for("a") == 0


def test_keys_are_independent():
    limiter = SlidingWindowLimiter(1, 60)
    assert limiter.try_acquire("a") == 0
    assert limiter.try_acquire("b") == 0
    assert limiter.try_acquire("a") >= 1
    assert limiter.try_acquire("b") >= 1


def test_invalid_constructor_arguments():
    with pytest.raises(ValueError):
        SlidingWindowLimiter(-1, 60)
    with pytest.raises(ValueError):
        SlidingWindowLimiter(1, 0)
    with pytest.raises(ValueError):
        SlidingWindowLimiter(1, -5)


def test_reset_clears_every_key():
    limiter = SlidingWindowLimiter(1, 60)
    limiter.record("a")
    limiter.record("b")
    limiter.reset()
    assert limiter.blocked_for("a") == 0
    assert limiter.blocked_for("b") == 0


def test_retry_after_is_at_least_one_second():
    limiter = SlidingWindowLimiter(1, 60)
    limiter.record("a")
    # 창이 끝나기 직전이어도 대기 시간은 최소 1초로 반올림한다.
    assert limiter.blocked_for("a") >= 1

"""비밀번호 정책 — 흔한 비밀번호 블랙리스트."""

from __future__ import annotations

import re

_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password",
        "password1",
        "password123",
        "123456",
        "1234567",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty",
        "qwerty123",
        "qwe123",
        "abc123",
        "iloveyou",
        "letmein",
        "welcome",
        "monkey",
        "dragon",
        "master",
        "login",
        "passw0rd",
        "admin",
        "admin123",
        "root",
        "toor",
        "test",
        "test123",
        "guest",
        "111111",
        "000000",
        "123123",
        "654321",
        "666666",
        "987654321",
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm",
        "1q2w3e4r",
        "1qaz2wsx",
        "password1!",
        "p@ssw0rd",
        "p@ssword",
    }
)


def _normalize(password: str) -> str:
    """소문자화 + 공백/구두점 제거만 수행. 공격자 우회를 모두 잡으려 하기보다"""
    lowered = password.lower()
    return re.sub(r"[^a-z0-9]", "", lowered)


def is_common_password(password: str) -> bool:
    """블랙리스트 매치 여부. 반환값이 True면 사용자에게 거부 이유를 안내한다."""
    if not password:
        return False
    norm = _normalize(password)
    if norm in _COMMON_PASSWORDS:
        return True
    if len(norm) >= 4 and len(set(norm)) == 1:
        return True
    return False

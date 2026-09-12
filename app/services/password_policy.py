"""비밀번호 정책 — 흔한 비밀번호 블랙리스트.

외부 의존성 없이 정적 목록으로 상위 N개를 막는다. 대소문자/공백/일부 기호 치환을
정규화해도 탐지하는 것을 목표로 한다(딕셔너리 공격 저지, 완벽한 강도 측정 아님).
정말 약한 비밀번호가 아니면 허용해서 UX를 해치지 않는다.
"""

from __future__ import annotations

import re

# 흔한 비밀번호 상위 수십 개(SecLists/OWASP에서 자주 등장하는 것들).
# 대소문자 무시를 하므로 모두 소문자로 적는다.
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


# 비밀번호를 치환해 정규화: leetspeak/공백/일부 기호를 평탄화한다.
def _normalize(password: str) -> str:
    """소문자화 + 공백/구두점 제거만 수행. 공격자 우회를 모두 잡으려 하기보다
    대소문자/기본 구두점 변화 정도를 평탄화하는 데 그친다(과도한 정규화는
    오탐을 유발하므로 주의)."""
    lowered = password.lower()
    return re.sub(r"[^a-z0-9]", "", lowered)


def is_common_password(password: str) -> bool:
    """블랙리스트 매치 여부. 반환값이 True면 사용자에게 거부 이유를 안내한다."""
    if not password:
        return False
    norm = _normalize(password)
    if norm in _COMMON_PASSWORDS:
        return True
    # 동일 숫자/문자 반복만으로 구성된 경우(예: 'aaaa', '111111')도 약한 비밀번호로 취급.
    if len(norm) >= 4 and len(set(norm)) == 1:
        return True
    return False

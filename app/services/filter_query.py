"""간단한 필터 쿼리 파서 — 관리자 콘솔 공통(#201).

문법: ``키:값`` 토큰을 공백으로 나열하면 AND. 접두사 없는 단어는 전체 검색어로 묶인다.
키는 각 화면이 허용한 것만 인정하고, 나머지는 errors로 되돌려 힌트에 표시한다.
값은 쿼리의 바인딩 파라미터로만 사용된다 — 임의 SQL은 없다.
"""

import re

_TOKEN = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*):(?P<value>\S*)|(?P<bare>\S+)")


class FilterQuery:
    """파싱 결과 — 적용된 키:값 쌍, 전체 검색어, 미지 키 오류 목록."""

    def __init__(self, pairs: dict[str, str], errors: list[str]):
        self.pairs = pairs
        self.errors = errors

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.pairs.get(key, default)

    def int_or(self, key: str, default: int | None = None) -> int | None:
        value = self.pairs.get(key)
        if value is None:
            return default
        try:
            parsed = int(value)
        except ValueError:
            return default
        return parsed if parsed > 0 else default

    @property
    def search(self) -> str | None:
        return self.pairs.get("q")


def parse_filter(text: str, allowed: set[str], *, bare_key: str = "q") -> FilterQuery:
    """텍스트를 토큰으로 나눠 키:값 쌍으로 모은다. 미지 키는 errors에 남긴다."""
    pairs: dict[str, str] = {}
    errors: list[str] = []
    bare: list[str] = []
    for match in _TOKEN.finditer(text or ""):
        if match.group("bare") is not None:
            bare.append(match.group("bare"))
            continue
        key = match.group("key").lower()
        if key not in allowed:
            errors.append(f"{key}:")
            continue
        pairs[key] = match.group("value")
    if bare:
        joined = " ".join(bare)
        pairs[bare_key] = f"{pairs[bare_key]} {joined}" if bare_key in pairs else joined
    return FilterQuery(pairs, errors)

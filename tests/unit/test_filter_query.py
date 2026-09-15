"""필터 쿼리 파서 단위 테스트 — 관리자 콘솔 공통 문법(#201)."""

from app.services.filter_query import parse_filter


def test_pairs_and_bare_search():
    fq = parse_filter("email:a@b.com thread:3 헬로 우주", {"email", "thread", "status", "q"})
    assert fq.get("email") == "a@b.com"
    assert fq.int_or("thread") == 3
    assert fq.search == "헬로 우주"
    assert fq.errors == []


def test_unknown_key_is_flagged_not_applied():
    fq = parse_filter("emial:x status:success", {"email", "status"})
    assert fq.get("email") is None
    assert fq.get("status") == "success"
    assert fq.errors == ["emial:"]


def test_empty_and_int_edges():
    fq = parse_filter("", {"email"})
    assert fq.pairs == {} and fq.search is None
    fq = parse_filter("thread:abc user:0", {"thread", "user"})
    assert fq.int_or("thread", 7) == 7  # 숫자 아님 → 기본값
    assert fq.int_or("user", 5) == 5  # 0 이하 → 기본값

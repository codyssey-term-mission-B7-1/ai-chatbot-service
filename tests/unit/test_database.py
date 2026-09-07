"""유닛 테스트 — sqlite 부모 디렉터리 보장 (볼륨 경로 방어)."""
from app.database import ensure_sqlite_dir


def test_ensure_sqlite_dir_creates_missing_parent(tmp_path):
    target = tmp_path / "volume" / "app.db"
    ensure_sqlite_dir(f"sqlite:///{target}")
    assert target.parent.is_dir()


def test_ensure_sqlite_dir_skips_memory_and_relative():
    ensure_sqlite_dir("sqlite://")  # 인메모리 — 예외 없이 통과
    ensure_sqlite_dir("sqlite:///:memory:")
    ensure_sqlite_dir("sqlite:///./app.db")  # 현재 디렉터리 — 이미 존재

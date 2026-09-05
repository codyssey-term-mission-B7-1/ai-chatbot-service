#!/usr/bin/env python3
"""AI 연결 확인 스크립트 — .env 설정이 실제 API에서 동작하는지 1분 점검.

사용법 (프로젝트 루트에서):
    python scripts/ai_check.py

체크 항목: 모드(실제/데모) · 엔드포인트 · 모델 · 타임아웃 · 실제 호출 1회
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services.ai_client import (  # noqa: E402
    AIError,
    AITimeoutError,
    get_ai_provider,
    normalize_endpoint,
    reset_provider,
)


async def main() -> int:
    reset_provider()
    print("🔍 AI 연결 설정 확인")
    print(f"  모드     : {'REAL (실제 API)' if settings.ai_api_key else 'DEMO (AI_API_KEY 미설정)'}")
    print(f"  엔드포인트: {normalize_endpoint(settings.ai_base_url)}")
    print(f"  모델     : {settings.ai_model}")
    print(f"  타임아웃 : {settings.ai_timeout_sec}s (재시도 {settings.ai_max_retries}회)")
    print(f"  컨텍스트: 직전 {settings.context_turns}개 Q/A")
    print()

    provider = get_ai_provider()
    messages = [{"role": "user", "content": "핑 — '연결됨' 한 단어만 답해주세요."}]
    started = time.perf_counter()
    try:
        answer = await provider.generate(messages)
        latency = int((time.perf_counter() - started) * 1000)
        print(f"✅ 응답 수신 ({latency}ms)")
        print(f"   {answer[:300]}")
        print("\n🎉 AI 연결 정상 — 서비스를 그대로 실행하면 됩니다.")
        return 0
    except AITimeoutError:
        print("❌ 타임아웃 — AI_TIMEOUT_SEC 값을 늘리거나 엔드포인트/네트워크를 확인하세요.")
    except AIError as exc:
        print("❌ 호출 실패 — AI_BASE_URL / AI_API_KEY / AI_MODEL 값을 확인하세요.")
        print(f"   상세: {exc}")
    except Exception as exc:  # 예상 못한 오류도 서버처럼 안내
        print(f"❌ 알 수 없는 오류: {type(exc).__name__}: {exc}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

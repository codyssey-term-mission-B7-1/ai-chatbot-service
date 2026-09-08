#!/usr/bin/env python3
"""AI 진단. 데모 성공과 실제 외부 AI 연결 성공을 구분한다.

python scripts/ai_check.py                 # 키가 없으면 데모 점검(실 AI 미검증)
python scripts/ai_check.py --require-real  # 키가 없으면 종료 2, 호출하지 않음
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def safe_endpoint(value: str) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if parsed.port:
        host += ':' + str(parsed.port)
    return urlunsplit((parsed.scheme, host, parsed.path, '', ''))


async def run(require_real: bool = False) -> int:
    from app.config import settings
    from app.services.ai_client import AIError, AITimeoutError, get_ai_provider, reset_provider
    real = bool(settings.ai_api_key)
    print('모드: ' + ('REAL — 실제 외부 AI 연결 점검' if real else 'DEMO — 실 AI 연결 미검증'))
    if require_real and not real:
        print('AI_API_KEY가 없어 실 AI 점검을 수행하지 않았습니다.', file=sys.stderr)
        return 2
    print('엔드포인트: ' + safe_endpoint(settings.ai_base_url))
    print(f'모델: {settings.ai_model}')
    print(f'AI 호출 전체 예산: {settings.ai_timeout_sec}초 (DB 시간 제외)')
    print(f'논리 호출 1회 / HTTP 시도 최대 {settings.ai_max_retries + 1}회 (재시도 대상 오류만)')
    reset_provider()
    start = time.perf_counter()
    try:
        answer = await get_ai_provider().generate([
            {'role': 'user', 'content': '연결 확인입니다. 연결됨 한 단어로 답해주세요.'}
        ])
        print(f'응답 수신: {int((time.perf_counter() - start) * 1000)}ms')
        print(answer[:300])
        print('실 AI 연결 성공' if real else '데모 동작 정상 — 실 AI 연결 성공 증거가 아닙니다.')
        return 0
    except AITimeoutError:
        print('AI_TIMEOUT: 전체 시간 예산 또는 I/O 타임아웃', file=sys.stderr)
    except AIError:
        print('AI_ERROR: endpoint/model/key 및 제공사 상태를 안전한 환경에서 확인하세요.',
              file=sys.stderr)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-real', action='store_true')
    return asyncio.run(run(parser.parse_args(argv).require_real))


if __name__ == '__main__':
    raise SystemExit(main())

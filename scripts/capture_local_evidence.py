#!/usr/bin/env python3
"""격리 로컬 앱의 실제 브라우저 검증·캡처. 운영/실 AI 증빙으로 대체하지 않는다.

python scripts/capture_local_evidence.py --output artifacts/local-ui
실행 의존성: requirements-evidence.txt + playwright install --with-deps chromium
"""
import argparse
import asyncio
import hashlib
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for folder in ['app', 'templates', 'static']:
        for path in sorted((ROOT / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                digest.update(str(path.relative_to(ROOT)).encode())
                digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


async def browser_checks(base: str, output: Path, grant) -> dict:
    from playwright.async_api import async_playwright
    checks = []; screenshots = []
    async with async_playwright() as automation:
        browser = await automation.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 960}, locale='ko-KR')
        page = await context.new_page()
        page_errors = []
        page.on('pageerror', lambda error: page_errors.append(str(error)))
        requests = []
        page.on('request', lambda request: requests.append(request.url)
                if request.method == 'POST' and request.url.endswith('/api/chat') else None)

        async def capture(name, meaning):
            print('CAPTURE', name, page.url, await page.evaluate('({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight})'))
            await page.screenshot(path=output / name, full_page=False)
            screenshots.append({'file': name, 'meaning': meaning})

        await page.goto(base + '/signup')
        await capture('01-signup.png', '로컬 실제 회원가입 화면; 실 운영 아님')
        await page.locator('#email').fill('local-admin@example.com')
        await page.locator('#password').fill('가' * 25)
        await page.locator('#submit-btn').click()
        await page.get_by_text('비밀번호는 UTF-8 기준 72바이트 이하여야 해요.').wait_for()
        checks.append('UTF-8 비밀번호 바이트 제한 안내')
        await capture('09-password-byte-error.png', '한글 25자 비밀번호의 클라이언트 바이트 제한 안내')
        await page.locator('#password').fill('LocalEvidence123!')
        await page.locator('#password-confirm').fill('한 번 더, 다르게!')
        await page.locator('#submit-btn').click()
        mismatch = '비밀번호가 일치하지 않아요. 두 입력을 다시 확인해 주세요.'
        await page.get_by_text(mismatch).wait_for()
        checks.append('비밀번호 확인 불일치 클라이언트 가드')
        await capture(
            '10-password-confirm-mismatch.png',
            '가입 화면 비밀번호 확인 불일치 클라이언트 가드; 로컬 실제 앱',
        )
        await page.locator('#password-confirm').fill('LocalEvidence123!')
        await page.locator('#nickname').fill('로컬 검증 계정')
        await page.locator('#submit-btn').click()
        await page.wait_for_url('**/login?registered=1')
        await capture('02-login.png', '실제 가입 완료 후 로그인 안내; 로컬 합성 계정')
        await page.locator('#email').fill('local-admin@example.com')
        await page.locator('#password').fill('LocalEvidence123!')
        await page.locator('#submit-btn').click()
        await page.wait_for_url(base + '/')
        checks.append('가입 → 로그인 → 보호 화면 진입')

        before = len(requests)
        await page.locator('#question').fill(' ')
        await page.locator('#send-btn').click()
        assert len(requests) == before
        await page.locator('#question').fill('🙂' * 1001)
        assert await page.locator('#count').inner_text() == '1001'
        await page.locator('#send-btn').click()
        assert len(requests) == before
        checks.append('공백/1001 코드 포인트 전송 차단')
        await page.locator('#question').fill('🙂' * 501)
        assert await page.locator('#count').inner_text() == '501'
        checks.append('이모지 501개를 501자로 계산')

        await page.locator('#question').fill('줄바꿈')
        await page.locator('#question').press('Shift+Enter')
        assert '\n' in await page.locator('#question').input_value()
        assert len(requests) == before
        await page.locator('#question').dispatch_event('keydown', {'key': 'Enter', 'isComposing': True})
        assert len(requests) == before
        checks.append('Shift+Enter 줄바꿈 / 합성 IME 조합 이벤트는 전송하지 않음')

        async def delay(route):
            await asyncio.sleep(1.5)  # UI 로딩 캡처용 지연. 실 AI 지연 증거가 아니다.
            await route.continue_()
        await page.route('**/api/chat', delay)
        await page.locator('#question').fill('로컬에서 FastAPI를 실행하려면 무엇이 필요한가요?')
        await page.locator('#question').press('Enter')
        await page.locator('.loading').wait_for(state='visible')
        assert await page.locator('#send-btn').is_disabled()
        await page.locator('#question').press('Enter')
        await capture('03-loading.png', '네트워크 요청을 1.5초 지연시킨 로컬 로딩 UI')
        await page.locator('.loading').wait_for(state='detached')
        assert len(requests) == before + 1
        checks.append('Enter 1회 전송 / 전송 중 중복 요청 방지')
        await page.unroute('**/api/chat', delay)
        await page.locator('#question').fill('내가 방금 뭘 물어봤지?')
        await page.locator('#send-btn').click()
        await page.locator('.loading').wait_for(state='detached')
        await capture('04-context-chat.png', '내부 Fake 제공자의 문맥 응답; 실 AI 연결 증거 아님')
        assert '직전 질문 인용' in await page.locator('#chat-window').inner_text()
        checks.append('연속 2질문 문맥 전달/인용 — Fake 모드')
        await page.reload()
        await page.locator('.history-divider').wait_for()
        assert await page.locator('.bubble.user').count() == 2
        checks.append('복귀 시 저장된 성공 대화 복원')

        async def timeout_response(route):
            await route.fulfill(status=504, content_type='application/json', body=json.dumps({
                'detail': '현재 응답이 지연되고 있어요. (error: AI_TIMEOUT)',
            }, ensure_ascii=False))
        await page.route('**/api/chat', timeout_response)
        await page.locator('#question').fill('UI 타임아웃 안내 확인')
        await page.locator('#send-btn').click()
        await page.locator('.error-bubble').wait_for()
        await capture('05-timeout-ui.png', '프론트에 모의 HTTP 504를 주어 오류 표시 검증')
        checks.append('모의 504 오류 안내·전송 버튼 복구')
        await page.unroute('**/api/chat', timeout_response)
        assert await page.locator('#send-btn').is_enabled()

        other = await automation.request.new_context(base_url=base)
        assert (await other.post('/api/auth/signup', data={
            'email': 'local-other@example.com', 'password': 'LocalEvidence123!',
            'nickname': '다른 로컬 계정',
        })).status == 201
        assert (await other.post('/api/auth/login', data={
            'email': 'local-other@example.com', 'password': 'LocalEvidence123!',
        })).status == 200
        assert (await other.post('/api/chat', data={'question': '두 번째 로컬 계정의 질문'})).status == 200
        await other.dispose()
        checks.append('실제 로컬 HTTP로 두 사용자 기록 분리 확인')
        await page.goto(base + '/logs')
        assert '두 번째 로컬 계정의 질문' not in await page.locator('body').inner_text()
        await capture('06-my-logs.png', '실제 로컬 DB의 본인 로그; 시각 KST/UTC 병기')
        assert '시각 (KST / UTC)' in await page.locator('body').inner_text()
        checks.append('본인 기록 화면·KST/UTC 병기 표기')
        grant('local-admin@example.com')
        await page.goto(base + '/admin/logs')
        await capture('07-admin-logs.png', '로컬 운영자 함수로 명시 부여한 관리자 계정의 실제 조회 화면')
        checks.append('명시적으로 권한 부여한 관리자 조회')
        assert '두 번째 로컬 계정의 질문' in await page.locator('body').inner_text()
        await page.goto(base + '/')
        await page.set_viewport_size({'width': 390, 'height': 844})
        await capture('08-mobile-chat.png', '390px 로컬 Chromium 뷰포트; 실기기 검증과 구분')
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        checks.append('390px 뷰포트 가로 넘침 없음')
        await page.get_by_role('button', name='로그아웃').click()
        await page.wait_for_url('**/login')
        await page.goto(base + '/logs')
        await page.wait_for_url('**/login')
        checks.append('로그아웃 후 보호 HTML은 로그인 화면으로 이동')
        assert not page_errors, page_errors
        await browser.close()
    return {'checks': checks, 'screenshots': screenshots, 'browser_page_errors': page_errors}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/local-ui'))
    args = parser.parse_args(argv)
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chatbot-local-evidence-') as temp:
        os.environ.update({'DATABASE_URL': 'sqlite:///' + str(Path(temp) / 'evidence.db'),
                           'DEBUG': 'true', 'SESSION_SECRET': secrets.token_hex(32),
                           'AI_API_KEY': '', 'CONTEXT_TURNS': '5', 'MAX_QUESTION_LENGTH': '1000'})
        import uvicorn
        from app.main import app
        from app.database import SessionLocal
        from app.services.admin import grant_admin
        original = app.router.lifespan_context
        ready = threading.Event()

        @asynccontextmanager
        async def signal_ready(application):
            async with original(application):
                ready.set()
                yield
        app.router.lifespan_context = signal_ready
        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen(128)
        base = 'http://127.0.0.1:' + str(sock.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, access_log=False))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        if not ready.wait(15):
            server.should_exit = True
            raise RuntimeError('Local test app startup failed')
        def grant(email):
            with SessionLocal() as db:
                grant_admin(db, email)
        try:
            result = asyncio.run(browser_checks(base, output, grant))
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            sock.close()
            app.router.lifespan_context = original
        result.update({'created_at_utc': datetime.now(timezone.utc).isoformat(),
                       'scope': 'LOCAL_SYNTHETIC_NOT_PRODUCTION', 'external_AI_requests': 0,
                       'source_code_sha256': source_fingerprint(),
                       'backend_timeout_is_separately_verified_by_tests': True})
        (output / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

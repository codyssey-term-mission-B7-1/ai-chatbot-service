"""실제 JS 유틸리티의 Unicode 계산과 렌더링 계약. Node가 없으면 해당 검사만 건너뜀."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_counts_codepoints_like_pydantic():
    if not shutil.which("node"):
        pytest.skip("Node is needed for JS contract checks")
    code = """
    require('./static/js/form-utils.js');
    console.log(JSON.stringify({
      count: FormUtils.codepointLength('🙂'.repeat(501)),
      passwordBytes: FormUtils.utf8Length('가'.repeat(25))
    }));
    """
    output = subprocess.check_output(["node", "-e", code], cwd=ROOT, text=True)
    assert json.loads(output) == {"count": 501, "passwordBytes": 75}


def test_templates_have_no_inline_event_handlers():
    """CSP script-src 'self' 하에서 인라인 핸들러는 무시된다 — 템플릿에 남으면 안 된다(#75)."""
    import re

    for name in [
        "base.html",
        "chat.html",
        "login.html",
        "logs.html",
        "admin-logs.html",
        "forgot-password.html",
        "reset-password.html",
    ]:
        html = (ROOT / "templates" / name).read_text()
        assert not re.search(r"\son(click|submit|change|error|load|input|key\w*)=", html), name


def test_template_does_not_apply_a_different_native_utf16_cap():
    html = (ROOT / "templates/chat.html").read_text()
    assert 'maxlength="1000"' not in html
    assert 'data-max-question-length="{{ max_question_length }}"' in html
    code = (ROOT / "static/js/chat.js").read_text()
    assert "status=success&limit=${HISTORY_TURNS}" in code
    assert "question.length > MAX_LEN" not in code
    assert "sendBtn.disabled) return" in code


def test_base_template_declares_favicon_and_color_scheme():
    """파비콘(404 방지)과 운영체제 색상 스킴 선언(다크 모드 폼 컨트롤)이 있어야 한다."""
    html = (ROOT / "templates" / "base.html").read_text()
    assert 'rel="icon"' in html and "favicon.svg" in html
    assert 'name="color-scheme"' in html
    assert (ROOT / "static" / "favicon.svg").exists()


def test_styles_meet_contrast_tap_target_and_dark_mode_contract():
    """WCAG AA 대비용 팔레트, 44px 모바일 탭 타깃, prefers-color-scheme 다크 모드가 있어야 한다."""
    css = (ROOT / "static" / "css" / "style.css").read_text()
    # 실측 대비 — #5c6474: 흰색 5.95:1 / 배경 5.50:1, #c43a3a: 흰색 5.23:1 (WCAG AA 4.5:1 충족)
    assert "--muted: #5c6474;" in css
    assert "--danger: #c43a3a;" in css
    assert "@media (prefers-color-scheme: dark)" in css
    assert "min-height: 44px" in css  # 모바일 탭 타깃


def test_chat_js_attaches_timestamps_and_session_scoped_banner_dismiss():
    """말풍선 시각 표시와 데모 배너의 세션 범위 닫기가 있어야 한다(영구 숨김 금지)."""
    code = (ROOT / "static" / "js" / "chat.js").read_text()
    assert "bubble-time" in code
    assert "nowTime" in code and "historyTime" in code
    assert "sessionStorage.getItem('demo-banner-dismissed')" in code
    html = (ROOT / "templates" / "chat.html").read_text()
    assert 'id="banner-close"' in html


def test_log_pages_show_kst_with_utc():
    """사용자·관리자 로그 화면은 KST 기본 표기와 UTC 병기(오해 방지)를 함께 제공한다."""
    for name in ["logs.html", "admin-logs.html"]:
        html = (ROOT / "templates" / name).read_text()
        assert "| kst" in html, name
        assert "UTC" in html, name


def test_chat_validation_errors_render_inside_window_without_layout_shift():
    """채팅 검증 오류는 창 안 말풍선로 표시해야 한다 — 폼 아래 박스는 레이아웃 시프트를 일으킨다."""
    code = (ROOT / "static" / "js" / "chat.js").read_text()
    html = (ROOT / "templates" / "chat.html").read_text()
    # 검증/네트워크 오류가 창 내부 말풍선(error-bubble)과 role=alert으로 표시된다
    assert "addBubble(text, 'ai error-bubble')" in code
    assert "setAttribute('role', 'alert')" in code
    assert "errorBox" not in code
    # 시프트 원인이던 폼 하단 에러 박스는 제거되어 있다
    assert "chat-error" not in html


def test_auth_forms_treat_blank_input_as_empty():
    """로그인 빈 값·회원가입 공백 전용 비밀번호는 서버 왕복 전에 안내해야 한다."""
    code = (ROOT / "static" / "js" / "auth.js").read_text()
    assert "이메일과 비밀번호를 모두 입력해 주세요." in code
    assert "비밀번호는 공백만으로 구성될 수 없어요." in code


def test_auth_form_uses_custom_validation_not_native_tooltip():
    """인증 폼은 novalidate — 브라우저 기본 툴팁이 아니라 앱 안내 문구로 검증한다."""
    html = (ROOT / "templates" / "login.html").read_text()
    assert "novalidate" in html


def test_password_confirmation_fields_and_client_guard_present():
    """회원가입·재설정 화면에 비밀번호 확인 필드와 불일치 가드(제출 차단)가 있어야 한다."""
    login = (ROOT / "templates/login.html").read_text()
    reset = (ROOT / "templates/reset-password.html").read_text()
    # 회원가입 화면에만 확인 필드(로그인 모드는 단일 입력 유지)
    assert 'id="password-confirm"' in login
    assert 'id="password-confirm"' in reset
    auth_js = (ROOT / "static/js/auth.js").read_text()
    assert "password-confirm" in auth_js and "일치하지 않아요" in auth_js
    reset_js = (ROOT / "static/js/password-reset.js").read_text()
    assert "password-confirm" in reset_js and "일치하지 않아요" in reset_js


def test_theme_toggle_contract():
    """다크/라이트 수동 토글 — localStorage·no-JS 폴백·FOUC 방지 부트스트랩이 있어야 한다."""
    init = (ROOT / "static/js/theme-init.js").read_text()
    theme = (ROOT / "static/js/theme.js").read_text()
    base = (ROOT / "templates/base.html").read_text()
    css = (ROOT / "static/css/style.css").read_text()
    # head에서 스타일시트보다 먼저(첫 페인트 전 data-theme 적용 — FOUC 방지)
    assert "theme-init.js" in base
    assert base.index("theme-init.js") < base.index("style.css")
    assert "data-theme" in init and "prefers-color-scheme: dark" in init
    # 수동 선택은 localStorage에 저장되어 전 페이지·세션 유지
    assert "localStorage" in init and "localStorage" in theme
    assert 'id="theme-toggle"' in base
    assert "/static/js/theme.js" in base
    # CSS는 data-theme="dark" 토큰 재지정 + no-JS 폴백(시스템 설정) 모두 지원
    assert 'data-theme="dark"' in css
    assert "@media (prefers-color-scheme: dark)" in css
    # 3상태(시스템→라이트→다크) 순환
    for mode in ("system", "light", "dark"):
        assert f'"{mode}"' in theme


def test_mobile_first_layout_contract():
    """모바일 퍼스트 — 기본=모바일, ≥768px에서 데스크톱 조정. 16px 입력·100dvh·터치 힌트 숨김."""
    css = (ROOT / "static/css/style.css").read_text()
    assert "min-width: 768px" in css  # 모바일 퍼스트(기본=모바일) 증거
    assert "100dvh" in css  # 모바일 주소창 고려
    assert "font-size: 16px" in css  # iOS 포커스 시 자동 줌 방지
    # 터치 디바이스(hover 없으면)에서 키보드 조합키 힌트 숨김
    assert "hover: none" in css
    html = (ROOT / "templates/chat.html").read_text()
    assert 'class="kbd-only"' in html
    # 모바일 탭 타깃 44px 유지(기존 계약)
    assert "min-height: 44px" in css


def test_chat_js_autoscroll_and_thread_states():
    """채팅 하단 고정(읽기 중엔 안 당김) + 대화 목록 비동기 4상태(로드 중/실패/빈/성공)."""
    code = (ROOT / "static/js/chat.js").read_text()
    assert "stickToBottom" in code and "pinToBottom" in code
    assert "threadsLoaded" in code and "threadsLoadError" in code
    assert "thread-retry" in code  # 실패 상태의 '다시 시도'
    css = (ROOT / "static/css/style.css").read_text()
    assert ".thread-state" in css and ".thread-retry" in css

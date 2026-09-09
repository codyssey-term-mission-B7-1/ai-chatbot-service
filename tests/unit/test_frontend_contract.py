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

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

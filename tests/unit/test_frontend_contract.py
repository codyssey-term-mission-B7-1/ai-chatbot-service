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


def test_template_does_not_apply_a_different_native_utf16_cap():
    html = (ROOT / "templates/chat.html").read_text()
    assert 'maxlength="1000"' not in html
    assert 'data-max-question-length="{{ max_question_length }}"' in html
    code = (ROOT / "static/js/chat.js").read_text()
    assert "status=success&limit=${HISTORY_TURNS}" in code
    assert "question.length > MAX_LEN" not in code
    assert "sendBtn.disabled) return" in code

// 비밀번호 찾기/재설정 화면 — 서버 API 호출과 안내 표시만 담당 (CSP: 인라인 금지, 외부 의존 없음)
const form = document.getElementById('forgot-form') || document.getElementById('reset-form');
const message = document.getElementById('msg');

function showMessage(text, ok = false) {
  message.hidden = false;
  message.textContent = text;
  message.className = 'msg ' + (ok ? 'ok' : 'error');
}

if (form) {
  const mode = form.dataset.mode;  // 'forgot' | 'reset'
  const button = document.getElementById('submit-btn');

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (button.disabled) return;

    let url, body;
    if (mode === 'forgot') {
      url = '/api/auth/password/reset-request';
      body = { email: document.getElementById('email').value.trim() };
    } else {
      const password = document.getElementById('password').value;
      // 회원가입과 동일한 클라이언트 측 정책 점검 — 서버 검증이 최종 기준
      const length = FormUtils.codepointLength(password);
      if (length < 8 || length > 64) return showMessage('비밀번호는 8~64자여야 해요.');
      if (FormUtils.utf8Length(password) > 72) {
        return showMessage('비밀번호는 UTF-8 기준 72바이트 이하여야 해요.');
      }
      url = '/api/auth/password/reset';
      body = { token: document.getElementById('token').value, new_password: password };
    }

    button.disabled = true;
    button.textContent = '처리 중…';
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        showMessage(FormUtils.validationText(data) || '요청을 처리할 수 없어요. 잠시 후 다시 시도해 주세요.');
        return;
      }
      if (mode === 'forgot') {
        showMessage('요청을 받았어요. 이메일이 가입되어 있다면 재설정 안내를 보냈습니다. 받은 편지함(및 스팸 함)을 확인해 주세요.', true);
      } else {
        location.href = '/login?reset=1';
      }
    } catch {
      showMessage('네트워크 오류예요. 잠시 후 다시 시도해 주세요.');
    } finally {
      button.disabled = false;
      button.textContent = mode === 'forgot' ? '재설정 메일 보내기' : '비밀번호 변경';
    }
  });
}

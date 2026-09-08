const authForm = document.getElementById('auth-form');
const authMode = authForm.dataset.mode;
const authMessage = document.getElementById('msg');
function showAuthMessage(text, failed = true) {
  authMessage.hidden = false;
  authMessage.textContent = text;
  authMessage.className = 'msg ' + (failed ? 'error' : 'ok');
}
if (authMode === 'login' && new URLSearchParams(location.search).has('registered')) {
  showAuthMessage('가입이 완료됐어요. 로그인해 주세요.', false);
}
authForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = document.getElementById('submit-btn');
  if (button.disabled) return;
  const body = {
    email: document.getElementById('email').value.trim(),
    password: document.getElementById('password').value,
  };
  if (authMode === 'signup') {
    const length = FormUtils.codepointLength(body.password);
    if (length < 8 || length > 64) return showAuthMessage('비밀번호는 8~64자여야 해요.');
    if (FormUtils.utf8Length(body.password) > 72) {
      return showAuthMessage('비밀번호는 UTF-8 기준 72바이트 이하여야 해요.');
    }
    body.nickname = document.getElementById('nickname').value.trim();
    if (FormUtils.codepointLength(body.nickname) > 20) {
      return showAuthMessage('닉네임은 20자 이하여야 해요.');
    }
  }
  button.disabled = true;
  button.textContent = '처리 중…';
  try {
    const response = await fetch('/api/auth/' + authMode, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) return showAuthMessage(FormUtils.validationText(data));
    location.href = authMode === 'signup' ? '/login?registered=1' : '/';
  } catch {
    showAuthMessage('네트워크 오류예요. 잠시 후 다시 시도해 주세요.');
  } finally {
    button.disabled = false;
    button.textContent = authMode === 'signup' ? '가입하기' : '로그인';
  }
});

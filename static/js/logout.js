// 로그아웃 — 인라인 핸들러 대신 addEventListener(CSP script-src 'self' 호환, #75)
const logoutButton = document.getElementById('logout-btn');
if (logoutButton) {
  logoutButton.addEventListener('click', async () => {
    await fetch('/api/session', { method: 'DELETE' });
    location.href = '/login';
  });
}

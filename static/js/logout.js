const logoutButton = document.getElementById('logout-btn');
if (logoutButton) {
  logoutButton.addEventListener('click', async () => {
    await fetch('/api/session', { method: 'DELETE' });
    location.href = '/login';
  });
}

document.getElementById('admin-filter').addEventListener('submit', (event) => {
  event.preventDefault();
  const email = document.getElementById('admin-user-email').value.trim();
  const reason = document.getElementById('admin-reason').value.trim();
  const params = new URLSearchParams();
  if (email) params.set('email', email);
  if (reason) params.set('reason', reason);
  const query = params.toString();
  location.href = '/admin/logs' + (query ? '?' + query : '');
});

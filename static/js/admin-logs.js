document.getElementById('admin-filter').addEventListener('submit', (event) => {
  event.preventDefault();
  const userId = document.getElementById('admin-user-id').value.trim();
  const reason = document.getElementById('admin-reason').value.trim();
  const params = new URLSearchParams();
  if (userId) params.set('user_id', userId);
  if (reason) params.set('reason', reason);
  const query = params.toString();
  location.href = '/admin/logs' + (query ? '?' + query : '');
});

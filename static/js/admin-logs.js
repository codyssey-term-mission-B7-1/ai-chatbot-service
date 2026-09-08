document.getElementById('admin-filter').addEventListener('submit', (event) => {
  event.preventDefault();
  const value = document.getElementById('admin-user-id').value.trim();
  location.href = value ? '/admin/logs?user_id=' + encodeURIComponent(value) : '/admin/logs';
});

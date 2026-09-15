(function () {
  'use strict';
  const menuToggle = document.getElementById('menu-toggle');
  const sidebarEl = document.getElementById('sidebar');
  if (!menuToggle || !sidebarEl) return;
  const threadList = document.getElementById('thread-list');
  const threadCount = document.getElementById('thread-count');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const sidebarClose = document.getElementById('sidebar-close');
  const newThreadBtn = document.getElementById('new-thread-btn');
  const expandMQ = window.matchMedia('(min-width: 900px)');
  const shrinkMQ = window.matchMedia('(max-width: 700px)');
  let _isDesktop = window.innerWidth >= 900 || (window.innerWidth > 700 && window.innerWidth < 900
    ? (function () { try { return localStorage.getItem('sidebar-mode') !== 'mobile'; } catch (e) { return true; } })()
    : false);

  let threadsCache = [];
  let threadsLoaded = false;
  let threadsLoadError = false;
  let activeId = null;
  const firstLoad = (async () => {
    await loadThreads();
    return threadsCache;
  })();

  async function loadThreads() {
    let res;
    try {
      res = await fetch('/api/thread/list');
    } catch {
      if (!threadsLoaded) threadsLoadError = true;
      renderThreadList();
      return; // 네트워크 오류 → 조용히 스킵
    }
    if (res.status === 401) { location.href = '/login'; return; }
    if (!res.ok) {
      if (!threadsLoaded) threadsLoadError = true;
      renderThreadList();
      return;
    }
    threadsLoadError = false;
    threadsCache = await res.json();
    threadsLoaded = true;
    renderThreadList();
  }

  function renderThreadState(message) {
    const li = document.createElement('li');
    li.className = 'thread-state';
    li.textContent = message;
    return li;
  }

  function renderThreadList() {
    threadCount.textContent = String(threadsCache.length);
    threadList.textContent = '';

    if (!threadsLoaded) {
      if (threadsLoadError) {
        const li = renderThreadState('대화 목록을 불러오지 못했어요. 연결을 확인해 주세요.');
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'thread-retry';
        retry.textContent = '다시 시도';
        retry.addEventListener('click', () => loadThreads());
        li.appendChild(document.createElement('br'));
        li.appendChild(retry);
        threadList.appendChild(li);
      } else {
        threadList.appendChild(renderThreadState('대화 목록을 불러오는 중…'));
      }
      return;
    }
    if (threadsCache.length === 0) {
      threadList.appendChild(renderThreadState("아직 대화가 없어요. '＋ 새 채팅'으로 시작해 보세요."));
      return;
    }

    for (const t of threadsCache) {
      const li = document.createElement('li');
      li.className = 'thread-item' + (t.id === activeId ? ' active' : '');

      const label = document.createElement('button');
      label.type = 'button';
      label.className = 'thread-label';
      label.dataset.id = String(t.id);
      label.textContent = t.title || '새 대화';
      label.title = t.title || '새 대화';
      label.addEventListener('click', () => onThreadPick(t.id));

      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'thread-delete';
      del.setAttribute('aria-label', '대화 삭제');
      del.textContent = '×';
      del.addEventListener('click', () => deleteThread(t.id));

      li.append(label, del);
      threadList.appendChild(li);
    }
  }

  function onThreadPick(id) {
    if (hooks.pick) {
      hooks.pick(id);
      return;
    }
    closeSidebarIfMobile();
    location.href = '/?thread=' + id;
  }

  async function newThread() {
    let res;
    try {
      res = await fetch('/api/thread', { method: 'POST' });
    } catch {
      if (hooks.error) hooks.error('네트워크 오류예요. 연결을 확인하고 다시 시도해 주세요.');
      return;
    }
    if (res.status === 401) { location.href = '/login'; return; }
    if (!res.ok) {
      let data = null;
      try { data = await res.json(); } catch (e) { /* 무시 */ }
      if (hooks.error) hooks.error(errorText(data, res.status));
      return;
    }
    if (hooks.create) {
      const t = await res.json();
      hooks.create(t);
      return;
    }
    const t = await res.json();
    location.href = '/?thread=' + t.id;
  }

  async function deleteThread(id) {
    if (!confirm('이 대화와 그 기록을 삭제할까요? 되돌릴 수 없어요.')) return;
    let res;
    try {
      res = await fetch('/api/thread/' + id, { method: 'DELETE' });
    } catch {
      if (hooks.error) hooks.error('네트워크 오류예요. 연결을 확인하고 다시 시도해 주세요.');
      return;
    }
    if (res.status === 401) { location.href = '/login'; return; }
    if (!res.ok) {
      let data = null;
      try { data = await res.json(); } catch (e) { /* 무시 */ }
      if (hooks.error) hooks.error(errorText(data, res.status));
      return;
    }
    await loadThreads();
    if (hooks.afterDelete) hooks.afterDelete(id);
    closeSidebarIfMobile();
  }

  const errorText = (data, status) => FormUtils.errorText(data, status);

  function isDesktop() {
    return _isDesktop;
  }

  function saveMode() {
    try { localStorage.setItem('sidebar-mode', _isDesktop ? 'desktop' : 'mobile'); } catch (e) { /* 무시 */ }
  }

  function setSidebar(open) {
    if (isDesktop()) {
      document.body.classList.toggle('sidebar-collapsed', !open);
      try { localStorage.setItem('sidebar-collapsed', open ? '0' : '1'); } catch (e) { /* 무시 */ }
    } else {
      document.body.classList.toggle('sidebar-open', open);
      if (sidebarBackdrop) sidebarBackdrop.hidden = !open;
    }
    menuToggle.setAttribute('aria-expanded', String(open));
    menuToggle.setAttribute('aria-label', open ? '대화 메뉴 닫기' : '대화 메뉴 열기');
  }

  function sidebarOpenNow() {
    return isDesktop()
      ? !document.body.classList.contains('sidebar-collapsed')
      : document.body.classList.contains('sidebar-open');
  }

  function closeSidebarIfMobile() {
    if (!isDesktop() && document.body.classList.contains('sidebar-open')) setSidebar(false);
  }

  let open = false;
  if (isDesktop()) {
    let collapsed = '0';
    try { collapsed = localStorage.getItem('sidebar-collapsed') || '0'; } catch (e) { /* 무시 */ }
    open = collapsed !== '1';
  }
  setSidebar(open);
  menuToggle.addEventListener('click', () => setSidebar(!sidebarOpenNow()));
  if (sidebarClose) sidebarClose.addEventListener('click', () => setSidebar(false));
  if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', () => setSidebar(false));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !isDesktop() && document.body.classList.contains('sidebar-open')) {
      setSidebar(false);
    }
  });
  function onShrink(e) {
    if (e.matches && _isDesktop) {
      _isDesktop = false;
      saveMode();
      setSidebar(false);
    }
  }
  function onExpand(e) {
    if (e.matches && !_isDesktop) {
      _isDesktop = true;
      saveMode();
      document.body.classList.remove('sidebar-open');
      if (sidebarBackdrop) sidebarBackdrop.hidden = true;
      setSidebar(!document.body.classList.contains('sidebar-collapsed'));
    }
  }
  if (shrinkMQ.addEventListener) {
    shrinkMQ.addEventListener('change', onShrink);
    expandMQ.addEventListener('change', onExpand);
  } else if (shrinkMQ.addListener) {
    shrinkMQ.addListener(onShrink);
    expandMQ.addListener(onExpand);
  }

  if (newThreadBtn) newThreadBtn.addEventListener('click', newThread);

  const hooks = {
    pick: null,
    create: null,
    afterDelete: null, // (deletedId) => void — 삭제 후 현재 대화 처리
    error: null,
  };
  window.SidebarUI = {
    ready: () => firstLoad,
    refresh: loadThreads,
    threads: () => threadsCache, // 현재 목록 캐시(동기)
    setActive: (id) => { activeId = id; renderThreadList(); },
    activeId: () => activeId,
    closeIfMobile: closeSidebarIfMobile,
    open: () => setSidebar(true),
    register: (h) => { Object.assign(hooks, h); },
  };
})();

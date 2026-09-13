// 전역 사이드바 — 로그인한 모든 페이지(채팅·기록·관리자)에서 공통으로 동작한다.
//  - 모바일: 오프캔버스 드로어(☰ 열기, ✕/백드롭/Esc 닫기)
//  - 데스크톱: 상시 280px, ☰로 접기(접힘 상태 localStorage 저장)
//  - 대화 목록(4상태) + 새 채팅 + 삭제
// 채팅 페이지는 window.SidebarUI에 훅을 등록해 목록과 창을 연동한다.
(function () {
  'use strict';
  const menuToggle = document.getElementById('menu-toggle');
  const sidebarEl = document.getElementById('sidebar');
  if (!menuToggle || !sidebarEl) return;  // 비로그인 페이지 — 사이드바 없음
  const threadList = document.getElementById('thread-list');
  const threadCount = document.getElementById('thread-count');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const sidebarClose = document.getElementById('sidebar-close');
  const newThreadBtn = document.getElementById('new-thread-btn');
  const desktopMQ = window.matchMedia('(min-width: 768px)');

  // ---- 대화 목록 ---------------------------------------------------------
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
      res = await fetch('/api/threads');
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

    // 비동기 상태 — 404/오류가 아닌 '로드 중'·'실패'·'빈' 상태도 명시적으로 표시
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

  // 대화 선택 — 채팅 페이지면 훅으로 전환, 다른 페이지면 해당 대화 URL로 이동
  function onThreadPick(id) {
    if (hooks.pick) {
      hooks.pick(id);
      return;
    }
    closeSidebarIfMobile();
    location.href = '/?thread=' + id;
  }

  // 새 채팅 — 채팅 페이지면 훅(창 초기화), 다른 페이지면 생성 후 채팅으로 이동
  async function newThread() {
    let res;
    try {
      res = await fetch('/api/threads', { method: 'POST' });
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
    // 다른 페이지(기록·관리자) — 방금 만든 대화가 아니라 기본 대화로 돌아가면
    // "세션이 바뀌었다"고 인식될 수 있다. 새 대화가 ?thread=로 열리도록 이동한다.
    const t = await res.json();
    location.href = '/?thread=' + t.id;
  }

  // 대화 삭제 — 확인 후 DELETE. 채팅 페이지 훅(현재 대화 처리)이 있으면 호출
  async function deleteThread(id) {
    if (!confirm('이 대화와 그 기록을 삭제할까요? 되돌릴 수 없어요.')) return;
    let res;
    try {
      res = await fetch('/api/threads/' + id, { method: 'DELETE' });
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
    // 목록을 먼저 갱신(삭제된 대화 소멸)한 뒤 채팅 페이지 훅을 호출 —
    // 채팅창·현재 대화가 갱신된 목록 기준으로 동기화돼야 컨텍스트 어긋남(꼬임)이 없다.
    await loadThreads();
    if (hooks.afterDelete) hooks.afterDelete(id);
    closeSidebarIfMobile();
  }

  // 서버 오류 메시지를 안전하고 읽기 쉽게 정규화
  function errorText(data, status) {
    const d = data && data.detail;
    if (typeof d === 'string' && d) return '오류: ' + d;
    if (Array.isArray(d) && d.length) return '오류: ' + FormUtils.validationText(data);
    if (status === 504) return '응답 지연 — AI가 시간이 걸리고 있어요.';
    return '오류가 발생했어요. 다시 시도해 주세요.';
  }

  // ---- 사이드바 열기/닫기 ------------------------------------------------
  function isDesktop() {
    return desktopMQ.matches;
  }

  // 모바일: body.sidebar-open(드로어+백드롭), 데스크톱: body.sidebar-collapsed(저장 유지)
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

  // 모바일 드로어에서 대화를 고른 뒤에는 자동으로 닫힌다(데스크톱은 유지)
  function closeSidebarIfMobile() {
    if (!isDesktop() && document.body.classList.contains('sidebar-open')) setSidebar(false);
  }

  // 초기 상태: 모바일=항상 닫힘(드로어), 데스크톱=저장값 복원(기본 열림)
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
  if (desktopMQ.addEventListener) {
    desktopMQ.addEventListener('change', (e) => {
      if (e.matches) {
        // 데스크톱으로 전환 — 드로어 상태 정리, 접힘 여부는 저장값(기본 열림)
        document.body.classList.remove('sidebar-open');
        if (sidebarBackdrop) sidebarBackdrop.hidden = true;
        setSidebar(!document.body.classList.contains('sidebar-collapsed'));
      } else {
        setSidebar(false);  // 모바일로 전환 — 드로어 닫힘
      }
    });
  }

  if (newThreadBtn) newThreadBtn.addEventListener('click', newThread);

  // ---- 채팅 페이지 연동 API ---------------------------------------------
  // 채팅 페이지(chat.js)는 이 훅들을 등록해 목록 ↔ 채팅창을 동기화한다.
  const hooks = {
    pick: null,      // (id) => void — 대화 전환(채팅창 로드)
    create: null,    // (thread) => void — 새 채팅 생성 후 처리
    afterDelete: null, // (deletedId) => void — 삭제 후 현재 대화 처리
    error: null,     // (message) => void — 오류 표시(채팅창 말풍선 등)
  };
  window.SidebarUI = {
    ready: () => firstLoad,     // 첫 목록 로드 완료 시 resolve(캐시 배열 반환)
    refresh: loadThreads,       // 목록 재로드
    threads: () => threadsCache, // 현재 목록 캐시(동기)
    setActive: (id) => { activeId = id; renderThreadList(); },
    activeId: () => activeId,
    closeIfMobile: closeSidebarIfMobile,
    open: () => setSidebar(true),
    register: (h) => { Object.assign(hooks, h); },
  };
})();

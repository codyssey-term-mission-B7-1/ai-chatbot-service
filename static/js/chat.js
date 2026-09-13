// 채팅 화면 로직 — 입력 검증(빈 값/길이), 로딩/에러 상태 표시, 대화(스레드) 전환
const form = document.getElementById('chat-form');
const input = document.getElementById('question');
const window_ = document.getElementById('chat-window');
const sendBtn = document.getElementById('send-btn');
const counter = document.getElementById('count');
const welcomeBubble = document.getElementById('welcome-bubble');
const newThreadBtn = document.getElementById('new-thread-btn');
const threadsToggle = document.getElementById('threads-toggle');
const threadList = document.getElementById('thread-list');
const threadCount = document.getElementById('thread-count');

const MAX_LEN = parseInt(window_.dataset.maxQuestionLength || '1000', 10);

// 이전 대화 복원 범위 — 서버 CONTEXT_TURNS와 동일 (AI가 기억하는 맥락과 일치)
const HISTORY_TURNS = parseInt(window_.dataset.contextTurns || '5', 10);

// 현재 대화(스레드) — null이면 서버 기본 대화(첫 채팅 시 자동 생성)
let currentThreadId = null;
// 마지막으로 로드한 대화 목록 — active 표시·삭제 처리에 사용
let threadsCache = [];

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  counter.textContent = FormUtils.codepointLength(input.value);
});

input.addEventListener('keydown', (e) => {
  // Enter 전송 / Shift+Enter 줄바꿈 — IME 조합 중 Enter 오발송 방지 (#29)
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!sendBtn.disabled) form.requestSubmit();  // 전송 중 중복 발송 방지
  }
});

// 폼 제출 바인딩 — 인라인 onsubmit 대신 addEventListener(CSP script-src 'self' 호환, #75).
// send는 함수 선언이라 호이스팅되어 아래 정의를 그대로 참조한다.
form.addEventListener('submit', send);

// 하단 자동 스크롤 — 사용자가 위로 스크롤해 이전 내용을 읽고 있으면 새 말풍선에 강제로 당기지 않는다.
// 사용자가 전송/대화 전환(자신의 의사로 최신 보기)을 하면 다시 고정된다.
let stickToBottom = true;
window_.addEventListener('scroll', () => {
  stickToBottom = window_.scrollTop + window_.clientHeight >= window_.scrollHeight - 60;
});
function pinToBottom() {
  if (stickToBottom) window_.scrollTop = window_.scrollHeight;
}

function addBubble(text, cls, timeText) {
  const div = document.createElement('div');
  div.className = 'bubble ' + cls;
  // 텍스트만 삽입한다(innerHTML 금지 — 서버/사용자 문자열 보간 XSS 방어). null/undefined는 빈 문자열로
  div.textContent = text ?? '';
  if (timeText) {
    const time = document.createElement('span');
    time.className = 'bubble-time';
    time.textContent = timeText;  // 문자열만 — 서버 값도 textContent로 삽입
    div.appendChild(time);
  }
  window_.appendChild(div);
  pinToBottom();
  return div;
}

// 말풍선 시각 — 현재는 HH:MM, 이력은 MM-DD HH:MM(다른 날 대화 구분)
function nowTime() {
  return new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
}
function historyTime(isoUtc) {
  const d = new Date(isoUtc);
  if (isNaN(d)) return '';
  const pad = (n) => String(n).padStart(2, '0');
  const sameDay = new Date().toDateString() === d.toDateString();
  const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return sameDay ? hm : `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${hm}`;
}

// 서버 오류 메시지를 안전하고 읽기 쉽게 정규화
// (FastAPI 422의 detail은 배열이고 사용자 입력이 포함될 수 있어 textContent 전용 사용)
function errorText(data, status) {
  const d = data?.detail;
  if (typeof d === 'string' && d) return `오류: ${d}`;
  if (Array.isArray(d) && d.length) {
    return '오류: ' + FormUtils.validationText(data);
  }
  if (status === 504) return '응답 지연 — AI가 시간이 걸리고 있어요.';
  return '오류가 발생했어요. 다시 시도해 주세요.';
}

// 검증·네트워크 오류도 채팅창 안에 말풍선으로 표시한다.
// 폼 아래 별도 박스를 쓰면 나타날 때 입력 영역이 위로 밀려나 레이아웃이 흔들린다(약 52~70px 실측).
// 창 안 말풍선은 서버 오류(error-bubble)와 동일한 패턴이라 시각적으로도 일관된다.
function showError(text) {
  const bubble = addBubble(text, 'ai error-bubble');
  bubble.setAttribute('role', 'alert');
}

async function send(e) {
  e.preventDefault();
  if (sendBtn.disabled) return;
  const question = input.value.trim();

  // 클라이언트 측 입력 검증 — 빈 입력 차단 + 길이 제한
  if (!question) return showError('질문을 입력해 주세요. (빈 입력은 전송되지 않아요)');
  if (FormUtils.codepointLength(question) > MAX_LEN) return showError(`질문이 너무 길어요. ${MAX_LEN}자 이하로 줄여주세요.`);

  stickToBottom = true;  // 본인이 보낸 질문 — 답은 반드시 하단에 보여줘야 한다
  addBubble(question, 'user', nowTime());
  input.value = '';
  counter.textContent = '0';
  input.style.height = 'auto';

  const loading = addBubble('AI가 생각 중…', 'ai loading');
  sendBtn.disabled = true;

  try {
    const body = currentThreadId ? { question, thread_id: currentThreadId } : { question };
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    // 401은 로그인 페이지로(비로그인 진입 차단 요구사항)
    if (res.status === 401) {
      location.href = '/login';
      return;
    }

    // 서버에서 반환한 JSON/에러 메시지 파싱(네트워크 오류로 인해 json 파싱이 실패할 수 있음)
    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }

    loading.remove();

    if (!res.ok) { // 타임아웃(504)/AI 오류(502) 등 서버 안내 메시지 표시
      addBubble(errorText(data, res.status), 'ai error-bubble');
      return;
    }

    // 정상 응답
    if (typeof data?.answer !== 'string') {
      addBubble('응답 형식을 확인할 수 없어요. 잠시 후 다시 시도해 주세요.', 'ai error-bubble');
      return;
    }
    addBubble(data.answer, 'ai', nowTime());
    // 제목 자동 생성·활동순 정렬 반영 — 대화 목록 조용히 갱신
    loadThreads();
  } catch (err) {
    loading.remove();
    showError('네트워크 오류예요. 연결을 확인하고 다시 시도해 주세요.');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function addDivider(text) {
  const div = document.createElement('div');
  div.className = 'history-divider';
  div.textContent = text;
  window_.appendChild(div);
}

// 이전 대화 복원 — 채팅방에 돌아왔을 때 AI 맥락(현재 대화의 직전 N개 성공 Q/A)을 말풍선으로 표시
async function loadHistory() {
  if (HISTORY_TURNS <= 0) return;
  let logs;
  try {
    const url = currentThreadId
      ? `/api/me/chats?status=success&limit=${HISTORY_TURNS}&thread_id=${currentThreadId}`
      : `/api/me/chats?status=success&limit=${HISTORY_TURNS}`;
    const res = await fetch(url);
    if (res.status === 401) {  // 세션 만료 → 입력 전에 로그인 페이지로 (입력 유실 방지)
      location.href = '/login';
      return;
    }
    if (!res.ok) return;       // 조회 실패해도 새 채팅은 가능 → 조용히 스킵
    logs = await res.json();
  } catch {
    return;                    // 네트워크 오류 → 인사말만 표시하고 시작
  }
  // API가 사용자·성공 조건을 먼저 적용한 후 N개 제한 → AI와 동일한 범위
  const recent = logs.filter((log) => log.status === 'success').slice(0, HISTORY_TURNS).reverse();
  if (recent.length === 0) return;
  addDivider(`이전 대화 ${recent.length}개`);
  for (const log of recent) {
    const when = historyTime(log.created_at);
    addBubble(log.question, 'user', when);
    addBubble(log.answer, 'ai', when);
  }
}

// ---- 대화(스레드) 관리 -------------------------------------------------

// 비동기 상태 플래그 — 목록 렌더가 4상태(로드 중/실패/빈/성공)로 나뉘게 한다
let threadsLoaded = false;
let threadsLoadError = false;

// 대화 목록 로드 + 렌더. 401은 로그인으로.
// 첫 로드가 실패하면 '실패 + 다시 시도' 상태를 표시하고, 그 뒤의 실패는 기존 목록을 유지한다.
async function loadThreads() {
  let res;
  try {
    res = await fetch('/api/threads');
  } catch {
    if (!threadsLoaded) threadsLoadError = true;
    renderThreadList(threadsCache);
    return; // 네트워크 오류 → 조용히 스킵
  }
  if (res.status === 401) { location.href = '/login'; return; }
  if (!res.ok) {
    if (!threadsLoaded) threadsLoadError = true;
    renderThreadList(threadsCache);
    return;
  }
  threadsLoadError = false;
  threadsCache = await res.json();
  threadsLoaded = true;
  renderThreadList(threadsCache);
  // 현재 대화가 목록에서 사라졌다면(삭제) 서버 기본 대화(가장 오래된)로 복귀
  if (currentThreadId !== null && !threadsCache.some((t) => t.id === currentThreadId)) {
    currentThreadId = threadsCache.length ? Math.min(...threadsCache.map((t) => t.id)) : null;
  }
  if (currentThreadId === null && threadsCache.length) {
    // 페이지 첫 진입 — /api/chat에 thread_id 미전달 때 서버가 쓰는 기본 대화와 정렬
    currentThreadId = Math.min(...threadsCache.map((t) => t.id));
  }
}

function renderThreadState(message) {
  const li = document.createElement('li');
  li.className = 'thread-state';
  li.textContent = message;
  return li;
}

function renderThreadList(threads) {
  threadCount.textContent = String(threads.length);
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
  if (threads.length === 0) {
    threadList.appendChild(renderThreadState("아직 대화가 없어요. '＋ 새 채팅'으로 시작해 보세요."));
    return;
  }

  for (const t of threads) {
    const li = document.createElement('li');
    li.className = 'thread-item' + (t.id === currentThreadId ? ' active' : '');

    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'thread-label';
    label.dataset.id = String(t.id);
    label.textContent = t.title || '새 대화';
    label.title = t.title || '새 대화';
    label.addEventListener('click', () => switchThread(t.id));

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

// 인사말 제외하고 말풍선·구분선 모두 지움
function clearWindow() {
  for (const node of [...window_.children]) {
    if (node !== welcomeBubble) node.remove();
  }
}

function closeThreadList() {
  threadList.hidden = true;
  threadsToggle.setAttribute('aria-expanded', 'false');
}

// 대화 전환 — 창 비우고 해당 대화의 이전 대화만 복원
function switchThread(id) {
  if (id === currentThreadId) return;
  currentThreadId = id;
  clearWindow();
  stickToBottom = true;  // 대화 전환 = 최신 메시지부터 보기(의도적)
  renderThreadList(threadsCache);  // active 표시 갱신
  loadHistory();
  closeThreadList();
}

// 새 채팅 — 빈 기록의 대화 만들고 바로 전환
async function newThread() {
  let res;
  try {
    res = await fetch('/api/threads', { method: 'POST' });
  } catch {
    showError('네트워크 오류예요. 연결을 확인하고 다시 시도해 주세요.');
    return;
  }
  if (res.status === 401) { location.href = '/login'; return; }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }
    showError(errorText(data, res.status));
    return;
  }
  const t = await res.json();
  currentThreadId = t.id;
  clearWindow();
  await loadThreads();
  closeThreadList();
  input.focus();
}

// 대화 삭제 — 확인 후 DELETE, 지운 게 현재면 남은 것 중 기본 대화로 복귀
async function deleteThread(id) {
  if (!confirm('이 대화와 그 기록을 삭제할까요? 되돌릴 수 없어요.')) return;
  let res;
  try {
    res = await fetch(`/api/threads/${id}`, { method: 'DELETE' });
  } catch {
    showError('네트워크 오류예요. 연결을 확인하고 다시 시도해 주세요.');
    return;
  }
  if (res.status === 401) { location.href = '/login'; return; }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }
    showError(errorText(data, res.status));
    return;
  }
  if (id === currentThreadId) {
    // 남은 대화 중 가장 오래된(id 최소)이 새 기본 대화 — loadThreads에서 재계산된다.
    clearWindow();
  }
  await loadThreads();
  loadHistory();
  closeThreadList();
}

newThreadBtn.addEventListener('click', newThread);
threadsToggle.addEventListener('click', () => {
  threadList.hidden = !threadList.hidden;
  threadsToggle.setAttribute('aria-expanded', String(!threadList.hidden));
});

// ---- 초기화 -----------------------------------------------------------
async function init() {
  await loadThreads();
  await loadHistory();
}

// 데모 모드 배너 — 현재 세션에서만 닫을 수 있다(새 세션에서는 재표시)
const banner = document.getElementById('demo-banner');
const bannerClose = document.getElementById('banner-close');
if (banner && bannerClose) {
  if (sessionStorage.getItem('demo-banner-dismissed') === '1') banner.hidden = true;
  bannerClose.addEventListener('click', () => {
    banner.hidden = true;
    sessionStorage.setItem('demo-banner-dismissed', '1');
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

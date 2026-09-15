const form = document.getElementById('chat-form');
const input = document.getElementById('question');
const window_ = document.getElementById('chat-window');
const sendBtn = document.getElementById('send-btn');
const counter = document.getElementById('count');
const welcomeBubble = document.getElementById('welcome-bubble');

const MAX_LEN = parseInt(window_.dataset.maxQuestionLength || '1000', 10);

const HISTORY_TURNS = parseInt(window_.dataset.contextTurns || '5', 10);

let currentThreadId = null;

const INFLIGHT_KEY = 'chat-inflight';
const INFLIGHT_TTL_MS = 5 * 60 * 1000;

function saveInflight(threadId, question) {
  try {
    sessionStorage.setItem(INFLIGHT_KEY, JSON.stringify({ threadId, question, at: Date.now() }));
  } catch { /* 저장소 사용 불가 환경 — 복원 기능만 동작하지 않는다 */ }
}
function clearInflight() {
  try { sessionStorage.removeItem(INFLIGHT_KEY); } catch { /* 무시 */ }
}
function readInflight() {
  try {
    const v = JSON.parse(sessionStorage.getItem(INFLIGHT_KEY) || 'null');
    if (v && typeof v.question === 'string' && Date.now() - v.at < INFLIGHT_TTL_MS) return v;
  } catch { /* 손상된 기록은 없는 것과 같다 */ }
  return null;
}

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  counter.textContent = FormUtils.codepointLength(input.value);
});

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!sendBtn.disabled) form.requestSubmit();
  }
});

form.addEventListener('submit', send);

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
  div.textContent = text ?? '';
  if (timeText) {
    const time = document.createElement('span');
    time.className = 'bubble-time';
    time.textContent = timeText;
    div.appendChild(time);
  }
  window_.appendChild(div);
  pinToBottom();
  return div;
}

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

function errorText(data, status) {
  const d = data?.detail;
  if (typeof d === 'string' && d) return `오류: ${d}`;
  if (Array.isArray(d) && d.length) {
    return '오류: ' + FormUtils.validationText(data);
  }
  if (status === 504) return '응답 지연 — AI가 시간이 걸리고 있어요.';
  return '오류가 발생했어요. 다시 시도해 주세요.';
}

function showError(text) {
  const bubble = addBubble(text, 'ai error-bubble');
  bubble.setAttribute('role', 'alert');
}

async function send(e) {
  e.preventDefault();
  if (sendBtn.disabled) return;
  const question = input.value.trim();

  if (!question) return showError('질문을 입력해 주세요. (빈 입력은 전송되지 않아요)');
  if (FormUtils.codepointLength(question) > MAX_LEN) return showError(`질문이 너무 길어요. ${MAX_LEN}자 이하로 줄여주세요.`);

  stickToBottom = true;
  addBubble(question, 'user', nowTime());
  input.value = '';
  counter.textContent = '0';
  input.style.height = 'auto';

  const loading = addBubble('AI가 생각 중…', 'ai loading');
  sendBtn.disabled = true;
  saveInflight(currentThreadId, question);

  try {
    const body = currentThreadId ? { question, thread_id: currentThreadId } : { question };
    const res = await fetch('/api/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (res.status === 401) {
      location.href = '/login';
      return;
    }

    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }

    loading.remove();
    clearInflight();

    await SidebarUI.refresh();
    if (currentThreadId === null) {
      const ts = SidebarUI.threads();
      if (ts.length) {
        currentThreadId = Math.min(...ts.map((t) => t.id));
        SidebarUI.setActive(currentThreadId);
      }
    }

    if (!res.ok) { // 타임아웃(504)/AI 오류(502) 등 서버 안내 메시지 표시
      addBubble(FormUtils.errorText(data, res.status), 'ai error-bubble');
      return;
    }

    if (typeof data?.answer !== 'string') {
      addBubble('응답 형식을 확인할 수 없어요. 잠시 후 다시 시도해 주세요.', 'ai error-bubble');
      return;
    }
    addBubble(data.answer, 'ai', nowTime());
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

async function loadHistory() {
  if (HISTORY_TURNS <= 0) return;
  const loadingHistory = addBubble('이전 대화 불러오는 중…', 'ai loading');
  try {
  let logs;
  try {
    const url = currentThreadId
      ? `/api/users/me/chats?status=success&limit=${HISTORY_TURNS}&thread_id=${currentThreadId}`
      : `/api/users/me/chats?status=success&limit=${HISTORY_TURNS}`;
    const res = await fetch(url);
    if (res.status === 401) {
      location.href = '/login';
      return;
    }
    if (!res.ok) return;
    logs = await res.json();
  } catch {
    return;
  }
  const recent = logs.filter((log) => log.status === 'success').slice(0, HISTORY_TURNS).reverse();
  if (recent.length === 0) return;
  addDivider(`이전 대화 ${recent.length}개`);
  for (const log of recent) {
    const when = historyTime(log.created_at);
    addBubble(log.question, 'user', when);
    addBubble(log.answer, 'ai', when);
  }
  } finally {
    loadingHistory.remove();
  }
}

function clearWindow() {
  for (const node of [...window_.children]) {
    if (node !== welcomeBubble) node.remove();
  }
}

async function restoreInflight() {
  const inflight = readInflight();
  if (!inflight) return;
  const pendingThread = inflight.threadId ?? currentThreadId;
  if (pendingThread !== currentThreadId) return;

  const threadQ = currentThreadId != null ? `&thread_id=${currentThreadId}` : '';
  const findSaved = async () => {
    const res = await fetch(`/api/users/me/chats?limit=5${threadQ}`);
    if (res.status === 401) { location.href = '/login'; return null; }
    if (!res.ok) return undefined;
    return res.json();
  };

  try {
    const logs = await findSaved();
    if (logs === null) return;
    if (Array.isArray(logs) && logs.some((l) => l.question === inflight.question)) {
      clearInflight();
      return;
    }
  } catch { /* 네트워크 오류 — 아래 폴링에서 재시도 */ }

  stickToBottom = true;
  addBubble(inflight.question, 'user', historyTime(new Date(inflight.at).toISOString()));
  const loading = addBubble('AI가 생각 중…', 'ai loading');
  sendBtn.disabled = true;

  const started = Date.now();
  const POLL_MS = 2000;
  try {
    while (Date.now() - started < INFLIGHT_TTL_MS) {
      await new Promise((r) => setTimeout(r, POLL_MS));
      let logs;
      try { logs = await findSaved(); } catch { continue; }
      if (logs === null) return;
      const hit = Array.isArray(logs)
        ? logs.find((l) => l.question === inflight.question)
        : null;
      if (hit?.status === 'success') {
        const bubble = addBubble(hit.answer, 'ai', historyTime(hit.created_at));
        loading.replaceWith(bubble);
        clearInflight();
        await SidebarUI.refresh();
        return;
      }
      if (hit?.status === 'ai_error') {
        loading.remove();
        showError('AI가 응답하지 못했어요. 다시 시도해 주세요.');
        clearInflight();
        await SidebarUI.refresh();
        return;
      }
    }
    loading.remove();
    showError('응답 확인이 늦어지고 있어요. 잠시 후 새로고침해 주세요.');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function switchThread(id) {
  if (id === currentThreadId) {
    SidebarUI.closeIfMobile();
    return;
  }
  currentThreadId = id;
  clearWindow();
  stickToBottom = true;
  SidebarUI.setActive(id);
  loadHistory();
  SidebarUI.closeIfMobile();
}

SidebarUI.register({
  pick: switchThread,
  create: (t) => {
    currentThreadId = t.id;
    clearWindow();
    SidebarUI.setActive(t.id);
    SidebarUI.refresh();
    SidebarUI.closeIfMobile();
    input.focus();
  },
  afterDelete: (deletedId) => {
    if (deletedId === currentThreadId) {
      clearWindow();
      const ts = SidebarUI.threads().filter((t) => t.id !== deletedId);
      currentThreadId = ts.length ? Math.min(...ts.map((t) => t.id)) : null;
      SidebarUI.setActive(currentThreadId);
      stickToBottom = true;
      loadHistory();
    }
  },
  error: showError,
});

async function init() {
  const threads = await SidebarUI.ready();
  const urlId = Number(new URLSearchParams(location.search).get('thread') || 0);
  if (threads.some((t) => t.id === urlId)) {
    currentThreadId = urlId;
  } else if (threads.length) {
    currentThreadId = Math.min(...threads.map((t) => t.id));
  }
  SidebarUI.setActive(currentThreadId);
  await loadHistory();
  await restoreInflight();
}

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

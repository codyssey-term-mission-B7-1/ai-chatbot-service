// 채팅 화면 로직 — 입력 검증(빈 값/길이), 로딩/에러 상태 표시
const form = document.getElementById('chat-form');
const input = document.getElementById('question');
const window_ = document.getElementById('chat-window');
const sendBtn = document.getElementById('send-btn');
const errorBox = document.getElementById('chat-error');
const counter = document.getElementById('count');

const MAX_LEN = 1000;

// 이전 대화 복원 범위 — 서버 CONTEXT_TURNS와 동일 (AI가 기억하는 맥락과 일치)
const HISTORY_TURNS = parseInt(window_.dataset.contextTurns || '5', 10);

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  counter.textContent = input.value.length;
});

input.addEventListener('keydown', (e) => {
  // Enter 전송 / Shift+Enter 줄바꿈 — IME 조합 중 Enter 오발송 방지 (#29)
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    if (!sendBtn.disabled) form.requestSubmit();  // 전송 중 중복 발송 방지
  }
});

function addBubble(text, cls) {
  const div = document.createElement('div');
  div.className = 'bubble ' + cls;
  div.textContent = text;
  window_.appendChild(div);
  window_.scrollTop = window_.scrollHeight;
  return div;
}

function showError(text) {
  errorBox.hidden = false;
  errorBox.textContent = text;
  setTimeout(() => { errorBox.hidden = true; }, 6000);
}

async function send(e) {
  e.preventDefault();
  const question = input.value.trim();

  // 클라이언트 측 입력 검증 — 빈 입력 차단 + 길이 제한
  if (!question) return showError('질문을 입력해 주세요. (빈 입력은 전송되지 않아요)');
  if (question.length > MAX_LEN) return showError(`질문이 너무 길어요. ${MAX_LEN}자 이하로 줄여주세요.`);

  errorBox.hidden = true;
  addBubble(question, 'user');
  input.value = '';
  counter.textContent = '0';
  input.style.height = 'auto';

  const loading = addBubble('AI가 생각 중…', 'ai loading');
  sendBtn.disabled = true;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    loading.remove();

    if (res.status === 401) {           // 접근 제어: 비로그인 → 로그인 페이지로
      location.href = '/login';
      return;
    }
    if (!res.ok) {                       // 타임아웃(504)/AI 오류(502) 등 서버 안내 메시지 표시
      addBubble(data.detail || '오류가 발생했어요. 다시 시도해 주세요.', 'ai error-bubble');
      return;
    }
    addBubble(data.answer, 'ai');
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

// 이전 대화 복원 — 채팅방에 돌아왔을 때 AI 맥락(직전 N개 성공 Q/A)을 말풍선으로 표시
async function loadHistory() {
  let logs;
  try {
    const res = await fetch('/api/me/chats?limit=50');
    if (res.status === 401) {  // 세션 만료 → 입력 전에 로그인 페이지로 (입력 유실 방지)
      location.href = '/login';
      return;
    }
    if (!res.ok) return;       // 조회 실패해도 새 채팅은 가능 → 조용히 스킵
    logs = await res.json();
  } catch {
    return;                    // 네트워크 오류 → 인사말만 표시하고 시작
  }
  // API는 최신순 → 성공 건만 N개 추려 오래된 순으로 복원 (AI 컨텍스트와 동일 범위)
  const recent = logs.filter((log) => log.status === 'success').slice(0, HISTORY_TURNS).reverse();
  if (recent.length === 0) return;
  addDivider(`이전 대화 ${recent.length}개`);
  for (const log of recent) {
    addBubble(log.question, 'user');
    addBubble(log.answer, 'ai');
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', loadHistory);
} else {
  loadHistory();
}

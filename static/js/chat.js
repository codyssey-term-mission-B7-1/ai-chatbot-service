// 채팅 화면 로직 — 입력 검증(빈 값/길이), 로딩/에러 상태 표시
const form = document.getElementById('chat-form');
const input = document.getElementById('question');
const window_ = document.getElementById('chat-window');
const sendBtn = document.getElementById('send-btn');
const errorBox = document.getElementById('chat-error');
const counter = document.getElementById('count');

const MAX_LEN = 1000;

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  counter.textContent = input.value.length;
});

function addBubble(text, cls) {
  const div = document.createElement('div');
  div.className = 'bubble ' + cls;
  if (typeof text === 'string') div.textContent = text;
  else div.appendChild(text); // 노드가 들어올 수 있음
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
      const detail = data?.detail || (res.status === 504 ? '응답 지연 — AI가 시간이 걸리고 있어요.' : '오류가 발생했어요. 다시 시도해 주세요.');
      const node = document.createElement('div');
      node.innerHTML = `<strong>오류:</strong> ${detail}`;
      addBubble(node, 'ai error-bubble');
      return;
    }

    // 정상 응답
    addBubble(data.answer, 'ai');
  } catch (err) {
    loading.remove();
    showError('네트워크 오류예요. 연결을 확인하고 다시 시도해 주세요.');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

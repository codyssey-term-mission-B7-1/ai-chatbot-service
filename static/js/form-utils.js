// API와 같은 Unicode 코드 포인트 기준. UTF-8 바이트 제약은 비밀번호에 별도 적용.
(function (root) {
  function codepointLength(value) { return Array.from(String(value)).length; }
  function utf8Length(value) { return new TextEncoder().encode(String(value)).length; }
  function validationText(data, fallback = '입력을 확인해 주세요.') {
    const detail = data?.detail;
    if (typeof detail === 'string') return detail;
    if (!Array.isArray(detail) || !detail.length) return fallback;
    const item = detail[0];
    const field = (item.loc || []).filter((v) => typeof v === 'string').at(-1);
    const label = { question: '질문', password: '비밀번호', nickname: '닉네임', email: '이메일' }[field] || '입력';
    if (field === 'email') return '이메일 형식을 확인해 주세요.';
    if (item.type === 'string_too_long') return `${label}은 ${item.ctx?.max_length}자 이하여야 해요.`;
    if (item.type === 'string_too_short') return `${label}은 ${item.ctx?.min_length}자 이상이어야 해요.`;
    const message = typeof item.msg === 'string' ? item.msg.replace(/^Value error, /, '') : '';
    return message || fallback;
  }
  // 서버 오류 메시지를 안전하고 읽기 쉽게 정규화 — chat.js·sidebar.js 공용(#150)
  function errorText(data, status, fallback = '오류가 발생했어요. 다시 시도해 주세요.') {
    const detail = data?.detail;
    if (typeof detail === 'string' && detail) return `오류: ${detail}`;
    if (Array.isArray(detail) && detail.length) return '오류: ' + validationText(data);
    if (status === 504) return '응답 지연 — AI가 시간이 걸리고 있어요.';
    return fallback;
  }
  root.FormUtils = { codepointLength, utf8Length, validationText, errorText };
})(typeof window === 'undefined' ? globalThis : window);

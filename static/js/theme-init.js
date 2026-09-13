/* 테마 부트스트랩 — 첫 페인트 전에 <html data-theme>를 적용해 FOUC(라이트→다크 깜빡임)을 막는다.
 * 수동 선택은 light/dark만 — localStorage('theme')에 저장.
 * 'system'(구 버전 값)/미설정/무효는 로드 시 OS 설정으로 한 번 해석한다.
 * CSP script-src 'self' 제약 때문에 인라인 스크립트 대신 head에서 CSS보다 앞서 로딩한다. */
(function () {
  var KEY = "theme";
  var saved = "";
  try {
    saved = localStorage.getItem(KEY) || "";
  } catch (e) {
    saved = "";
  }
  var mode = saved;
  if (mode !== "light" && mode !== "dark") {
    mode = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", mode);
  document.documentElement.setAttribute("data-theme-mode", mode);
})();

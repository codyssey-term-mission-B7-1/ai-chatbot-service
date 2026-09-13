/* 테마 부트스트랩 — 첫 페인트 전에 <html data-theme>를 적용해 FOUC(라이트→다크 깜빡임)를 막는다.
 * 저장 우선순위: localStorage('theme') > 시스템 설정(prefers-color-scheme).
 * CSP script-src 'self' 제약 때문에 인라인 스크립트 대신 head에서 CSS보다 앞서 로딩한다. */
(function () {
  var MODES = ["system", "light", "dark"];
  var KEY = "theme";
  var saved = "system";
  try {
    saved = localStorage.getItem(KEY) || "system";
  } catch (e) {
    saved = "system";
  }
  if (MODES.indexOf(saved) < 0) saved = "system";
  var dark =
    saved === "dark" ||
    (saved === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme-mode", saved);
})();

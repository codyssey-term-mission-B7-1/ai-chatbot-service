/* 다크/라이트 수동 토글 — 라이트 ↔ 다크 2상태(시스템 모드 없음).
 * 선택은 localStorage('theme')에 저장되어 전 페이지·세션을 유지한다.
 * 기존 'system'/미설정/무효 값은 로드 시 OS 설정으로 한 번 해석해 고정한다. */
(function () {
  var KEY = "theme";
  var MODES = { light: "dark", dark: "light" };
  var LABELS = { light: "라이트", dark: "다크" };
  var ICONS = { light: "☀", dark: "☾" };
  var root = document.documentElement;

  function osPrefersDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function current() {
    var s = "";
    try {
      s = localStorage.getItem(KEY) || "";
    } catch (e) {
      s = "";
    }
    if (s !== "light" && s !== "dark") {
      s = osPrefersDark() ? "dark" : "light";
      try {
        localStorage.setItem(KEY, s);
      } catch (e) {
        /* 저장 불가(사생활 모드) — 이번 로드에서만 해석 */
      }
    }
    return s;
  }

  function apply(mode) {
    root.setAttribute("data-theme", mode);
    root.setAttribute("data-theme-mode", mode);
  }

  function updateButton() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var mode = current();
    btn.textContent = ICONS[mode] + " " + LABELS[mode];
    btn.setAttribute("aria-label", "테마: " + LABELS[mode] + " — 클릭하여 " + LABELS[MODES[mode]] + "으로 변경");
    btn.title = "테마: " + LABELS[mode] + " → 다음: " + LABELS[MODES[mode]];
  }

  var btn = document.getElementById("theme-toggle");
  if (btn) {
    btn.addEventListener("click", function () {
      var next = MODES[current()];
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* 사생활 모드 등 저장 불가 — 현재 세션만 적용 */
      }
      apply(next);
      updateButton();
    });
    updateButton();
  }
})();

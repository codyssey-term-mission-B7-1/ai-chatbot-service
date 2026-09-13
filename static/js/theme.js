/* 다크/라이트 수동 토글 — 시스템 → 라이트 → 다크 순환(3상태).
 * 선택은 localStorage('theme')에 저장되어 전 페이지·세션을 유지한다.
 * 'system' 모드에서는 운영체제 설정 변화에 실시간으로 따른다. */
(function () {
  var KEY = "theme";
  var MODES = { system: "light", light: "dark", dark: "system" };
  var LABELS = { system: "시스템", light: "라이트", dark: "다크" };
  var ICONS = { system: "◐", light: "☀", dark: "☾" };
  var root = document.documentElement;

  function current() {
    var s = "system";
    try {
      s = localStorage.getItem(KEY) || "system";
    } catch (e) {
      s = "system";
    }
    return ["system", "light", "dark"].indexOf(s) >= 0 ? s : "system";
  }

  function apply(mode) {
    var dark =
      mode === "dark" ||
      (mode === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    root.setAttribute("data-theme", dark ? "dark" : "light");
    root.setAttribute("data-theme-mode", mode);
  }

  function updateButton() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var mode = current();
    btn.textContent = ICONS[mode];
    btn.setAttribute("aria-label", "테마: " + LABELS[mode] + " — 클릭하여 " + LABELS[MODES[mode]] + "(으)로 변경");
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

  /* system 모드 — 운영체제 설정 변화 추적 */
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  var onSystemChange = function () {
    if (current() === "system") {
      apply("system");
      updateButton();
    }
  };
  if (mq.addEventListener) mq.addEventListener("change", onSystemChange);
})();

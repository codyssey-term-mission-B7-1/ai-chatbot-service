/** 필터 쿼리 값 자동완성 — 마지막 토큰의 키:값에 대해 서버 후보를 드롭다운으로 제시한다(#204).
 * 키보드: ↑↓ 이동 · Enter 확정(폼 제출 아님) · Esc 닫기. 서버는 관리자 전용 /api/admin/suggest.
 * XSS 방어: 후보는 textContent로만 삽입한다.
 */
(function () {
  'use strict';

  var KEY_FIELD = {
    email: 'email',
    thread: 'thread',
    event: 'event',
    path: 'path',
    table: 'table',
  };

  function lastTokenState(value, caret) {
    var before = value.slice(0, caret);
    var m = before.match(/(^|\s)([A-Za-z_][A-Za-z0-9_]*):(\S*)$/);
    if (!m) return null;
    return { key: m[2].toLowerCase(), value: m[3], start: before.length - m[3].length };
  }

  document.querySelectorAll('.filter-query').forEach(function (box) {
    var form = box.closest('form');
    var list = document.createElement('div');
    list.className = 'suggest-list';
    list.setAttribute('role', 'listbox');
    list.hidden = true;
    box.parentNode.appendChild(list);

    var items = [];
    var active = -1;

    function close() {
      list.hidden = true;
      list.innerHTML = '';
      items = [];
      active = -1;
    }

    function choose(index) {
      var item = items[index];
      if (!item) return;
      var state = lastTokenState(box.value, box.selectionStart || box.value.length);
      var caret = box.selectionStart || box.value.length;
      var replacement = String(item.replace_value != null ? item.replace_value : item.value);
      var before = box.value.slice(0, state.start) + replacement + ' ';
      var after = box.value.slice(caret);
      box.value = before + after;
      var pos = before.length;
      box.focus();
      box.setSelectionRange(pos, pos);
      close();
      box.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function render() {
      list.innerHTML = '';
      items.forEach(function (item, i) {
        var el = document.createElement('button');
        el.type = 'button';
        el.className = 'suggest-item' + (i === active ? ' active' : '');
        el.setAttribute('role', 'option');
        el.textContent = item.label;
        el.addEventListener('mousedown', function (e) {
          e.preventDefault();
          choose(i);
        });
        list.appendChild(el);
      });
      list.hidden = items.length === 0;
    }

    var timer = null;
    function fetchSuggestions() {
      var caret = box.selectionStart || box.value.length;
      var state = lastTokenState(box.value, caret);
      if (!state || !KEY_FIELD[state.key]) {
        close();
        return;
      }
      var params = new URLSearchParams();
      params.set('field', KEY_FIELD[state.key]);
      params.set('q', state.value);
      fetch('/api/admin/suggest?' + params.toString(), { credentials: 'same-origin' })
        .then(function (res) { return res.ok ? res.json() : { items: [] }; })
        .then(function (data) {
          items = (data.items || []).map(function (it) {
            if (typeof it === 'string') {
              return { label: it, value: it, replace_value: it };
            }
            var label = it.label != null ? it.label : String(it.id);
            return { label: label, value: String(it.id), replace_value: String(it.id) };
          });
          active = items.length ? 0 : -1;
          render();
        })
        .catch(function () { close(); });
    }

    box.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(fetchSuggestions, 120);
    });
    box.addEventListener('keydown', function (e) {
      if (list.hidden) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        active = Math.min(active + 1, items.length - 1);
        render();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        active = Math.max(active - 1, 0);
        render();
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault();
        e.stopPropagation();
        choose(active);
      } else if (e.key === 'Escape') {
        close();
      }
    });
    box.addEventListener('blur', function () { setTimeout(close, 150); });
    form.addEventListener('submit', close);
  });
})();

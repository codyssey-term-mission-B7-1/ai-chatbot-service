/** 관리자 콘솔 필터 쿼리 실시간 힌트 — 입력 중 지원 키·적용 요약·미지 키를 표시한다(#201).
 * 문법은 app/services/filter_query.py 파서와 동일하다: 키:값 나열(AND), 접두사 없으면 전체 검색.
 */
(function () {
  'use strict';

  function parse(box) {
    var keys = (box.dataset.filterKeys || '')
      .split(',')
      .map(function (k) { return k.trim(); })
      .filter(Boolean);
    var applied = [];
    var errors = [];
    var bare = [];
    var tokens = box.value.match(/\S+/g) || [];
    tokens.forEach(function (tok) {
      var m = tok.match(/^([A-Za-z_][A-Za-z0-9_]*):(\S*)$/);
      if (!m) { bare.push(tok); return; }
      var key = m[1].toLowerCase();
      if (keys.indexOf(key) === -1) { errors.push(key + ':'); return; }
      applied.push(key + '=' + m[2]);
    });
    return { keys: keys, applied: applied, errors: errors, bare: bare };
  }

  document.querySelectorAll('.filter-query').forEach(function (box) {
    var form = box.closest('form');
    var hint = form ? form.querySelector('#filter-hint') : document.getElementById('filter-hint');
    if (!hint) return;

    function render() {
      var state = parse(box);
      if (!box.value.trim()) {
        hint.textContent = '지원 필터: ' + state.keys.map(function (k) { return k + ':값'; }).join(' · ')
          + ' — 공백으로 AND, 접두사 없는 단어는 전체 검색어';
        hint.className = 'input-live-hint';
        return;
      }
      if (state.errors.length) {
        hint.textContent = '알 수 없는 필터: ' + state.errors.join(' ')
          + ' — 지원: ' + state.keys.join(' / ');
        hint.className = 'input-live-hint error';
        return;
      }
      var parts = [];
      if (state.applied.length) parts.push(state.applied.join(' · '));
      if (state.bare.length) parts.push('전체 검색 "' + state.bare.join(' ') + '"');
      hint.textContent = parts.length ? '적용: ' + parts.join(' + ') : '조건 없음 — 엔터로 조회';
      hint.className = 'input-live-hint';
    }

    box.addEventListener('input', render);
    render();
  });
})();

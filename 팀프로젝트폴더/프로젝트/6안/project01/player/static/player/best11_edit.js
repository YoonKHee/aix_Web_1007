/* 나만의 BEST11 (BEST11 화면 안에서 쓰는 도구 모음)
 *  - 가중치(프리셋·지표별 배율)·케미 중시·상대 맞춤을 이 화면에서 바로 조절한다. 바꾸면 선수 점수와 자동 선발이 다시 계산된다.
 *  - 카드의 점수 옆에 케미 가산점을 다른 색(초록=가산 / 빨강=감점)으로 붙인다. 선수 팝업에는 이름 옆에 작게 표시한다.
 *  - 카드의 ⇄ 교체 버튼으로 같은 포지션 선수만 골라 바꿀 수 있다. (라인업 총점이 가장 많이 오르는 후보가 추천)
 *  - 선수 팝업의 'VS 비교'는 두 선수의 육각형 그래프를 색을 달리해 겹쳐 그리고, '보정 반영'을 켜면 케미·가중치·소표본 보정을 반영한 면을 점선으로 겹친다.
 *  - 포메이션 추천은 백분위가 아니라 점수(선수별 최종 점수, 상한 200점)로 비교한다.
 * 점수 계산은 모두 서버가 DB 기록으로 다시 한다. 내 설정·라인업은 이 브라우저(localStorage)에만 저장되고 서버 DB 는 바뀌지 않는다.
 * 계산이 끝나면 document 에 'b11:result' 이벤트를 보내 아래쪽 분석 패널(lab.js)이 같은 결과를 보여 준다.
 */
(function () {
  'use strict';
  var script = document.currentScript;
  if (!script) return;
  var D = script.dataset;
  var URLS = { evaluate: D.evaluateUrl, candidates: D.candidatesUrl, report: D.reportUrl, reportsFile: D.reportsFile, lineup: D.lineupUrl, formations: D.formationsUrl, chem: D.chemUrl, init: D.initUrl };
  var INFO = D.infoBase || '/player/info/';
  var field = document.querySelector('.football-field');
  if (!field || !URLS.evaluate || !URLS.candidates) return;
  var cards = Array.prototype.slice.call(field.querySelectorAll('.player-card'));
  if (cards.length !== 11) return;
  /* 화면(DOM)은 FW → MF → DF → GK 줄 순서인데 서버 라인업은 GK → DF → MF → FW 순서다.
     카드를 서버 순서(GK, DF, MF, FW)로 다시 늘어놓아야 공격수 칸에 골키퍼가 들어가지 않는다. */
  (function () {
    var LINE = { 'fw-line': 'FW', 'mf-line': 'MF', 'df-line': 'DF', 'gk-line': 'GK' }, RANK = { GK: 0, DF: 1, MF: 2, FW: 3 };
    var tagged = cards.map(function (c, i) {
      var ln = c.closest('.formation-line'), pos = null;
      if (ln) Object.keys(LINE).forEach(function (k) { if (ln.classList.contains(k)) pos = LINE[k]; });
      return { c: c, i: i, pos: pos };
    });
    if (tagged.some(function (t) { return !t.pos; })) return;       // 줄 정보가 없으면 건드리지 않는다
    tagged.sort(function (a, b) { return RANK[a.pos] - RANK[b.pos] || a.i - b.i; });
    cards = tagged.map(function (t) { return t.c; });
  })();                      // 포메이션을 만들 수 없는 화면이면 사용하지 않음

  var KEY = 'kleague-my-best11-v1', SKEY = 'kleague-b11-settings-v1';
  var POS_ORDER = ['FW', 'MF', 'DF', 'GK'], POS_LABEL = { FW: '공격수', MF: '미드필더', DF: '수비수', GK: '골키퍼' };
  var teamSel = document.getElementById('teamSelect'), formSel = document.getElementById('formationSelect');
  // 화면에 실제 적용된 값(페이지를 열 때의 값)을 기억한다. 적용 버튼을 누르기 전에 선택 상자만 바꿔도 영향 없음
  var appliedTeam = teamSel ? teamSel.value : '', appliedFormation = formSel ? formSel.value : '4-3-3';
  function team() { return appliedTeam; }
  function formation() { return appliedFormation; }
  function storeKey() { return (team() || 'all') + '|' + formation(); }
  function csrfToken() { var i = document.querySelector('input[name=csrfmiddlewaretoken]'); return i ? i.value : ''; }
  function sign(n) { return (n >= 0 ? '+' : '') + n; }
  function num1(n) { return Math.round(n * 10) / 10; }
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k]; else if (k === 'class') e.className = attrs[k];
      else if (k.indexOf('on') === 0) e.addEventListener(k.slice(2), attrs[k]); else e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function post(url, body) {
    return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok || j.error) throw new Error(j.error || '요청 실패'); return j; }); });
  }
  function readJSON(k, d) { try { return JSON.parse(localStorage.getItem(k) || 'null') || d; } catch (e) { return d; } }
  function writeJSON(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* 저장 불가여도 동작 */ } }

  function cardId(card) {
    var a = card.querySelector('.player-popup-link');
    var m = a && /openPlayerModal\((\d+)\)/.exec(a.getAttribute('onclick') || '');
    return m ? Number(m[1]) : null;
  }
  var originalIds = cards.map(cardId);
  if (originalIds.some(function (x) { return x == null; })) return;
  var ids = originalIds.slice();
  var last = null;                     // 마지막 평가 결과
  var INIT = null;                     // 서버 초기 정보 (구단·프리셋·지표)
  var ST = readJSON(SKEY, {});
  var S = { preset: ST.preset || 'default', mult: ST.mult || {}, chem: typeof ST.chem === 'number' ? ST.chem : 1, exp: typeof ST.exp === 'number' ? ST.exp : 1.5, opponent: ST.opponent || '' };
  function saveSettings() { writeJSON(SKEY, S); }
  function isDefaultSettings() { return S.preset === 'default' && !Object.keys(S.mult).length && S.chem === 1 && S.exp === 1.5 && !S.opponent; }
  function params() { return { team: team(), formation: formation(), lineup: ids, preset: S.preset, mult: S.mult, chem_scale: S.chem, exp_scale: S.exp, opponent: S.opponent || null }; }
  function isCustom() { return ids.some(function (x, i) { return x !== autoIds[i]; }); }
  var autoIds = originalIds.slice();   // '자동 선발' 기준 라인업 (설정이 기본이면 화면이 원래 보여 준 선수, 아니면 서버가 가중치로 다시 뽑은 선수)

  /* ---------- 화면 요소 ---------- */
  var tools = el('div', { class: 'b11-tools' });
  var bar = el('div', { class: 'b11-bar' });
  field.parentNode.insertBefore(tools, field);
  field.parentNode.insertBefore(bar, field);
  cards.forEach(function (card, i) {
    card.style.position = card.style.position || 'relative';
    var b = el('button', { type: 'button', class: 'b11-swap', title: '이 자리 선수 교체', 'aria-label': '선수 교체', text: '⇄ 교체' });
    b.addEventListener('click', function (e) { e.preventDefault(); e.stopPropagation(); openCands(i); });
    card.appendChild(b);
  });
  var modal = el('div', { class: 'lab-modal b11-modal', hidden: '' }, [
    el('div', { class: 'lab-modal-box', role: 'dialog', 'aria-modal': 'true' }, [
      el('div', { class: 'lab-modal-head' }, [el('b', { id: 'b11Title', text: '' }), el('button', { type: 'button', id: 'b11Close', 'aria-label': '닫기', text: '✕' })]),
      el('div', { id: 'b11Body' })])]);
  document.body.appendChild(modal);
  function openModal(title, node, wide) {
    modal.querySelector('#b11Title').textContent = title;
    clear(modal.querySelector('#b11Body')).appendChild(node);
    modal.querySelector('.lab-modal-box').className = 'lab-modal-box' + (wide ? ' wide' : '');
    modal.hidden = false;
  }
  function closeModal() { modal.hidden = true; }
  modal.addEventListener('click', function (e) { if (e.target === modal) closeModal(); });
  modal.querySelector('#b11Close').addEventListener('click', closeModal);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeModal(); });
  function badge(t) { return el('span', { class: 'lab-badge' + (t === '출전 적음' ? ' soft' : ''), text: t }); }

  /* ---------- 가중치 도구 모음 ---------- */
  var presetBox = el('span', { class: 'b11-presets' });
  var chemVal = el('b', { text: S.chem.toFixed(2).replace(/0$/, '') + '×' });
  var chemInp = el('input', { type: 'range', min: '0', max: '2', step: '0.25', value: String(S.chem), 'aria-label': '케미 중시' });
  var expVal = el('b', { text: S.exp.toFixed(2).replace(/0$/, '') + '×' });
  var expInp = el('input', { type: 'range', min: '0', max: '2', step: '0.25', value: String(S.exp), 'aria-label': '경험 중시' });
  var oppSel = el('select', { 'aria-label': '상대 맞춤' }, [el('option', { value: '', text: '선택 안 함' })]);
  var oppNote = el('span', { class: 'lab-muted' });
  var oppRptBtn = el('button', { type: 'button', text: '상대 맞춤 보고서', hidden: '', onclick: function () { openOppReport(); } });
  var metricsBox = el('div', { class: 'lab-metrics' });
  function buildTools() {
    clear(tools);
    tools.appendChild(el('div', { class: 'b11-tools-row' }, [
      el('b', { text: '가중치' }), presetBox,
      el('label', { class: 'b11-slider' }, ['케미 중시 ', chemInp, ' ', chemVal]),
      el('label', { class: 'b11-slider', title: '출전시간이 적은 선수의 점수를 깎는 정도 (0 = 보정 없음)' }, ['경험(출전시간) 중시 ', expInp, ' ', expVal]),
      el('label', {}, ['상대 맞춤 ', oppSel]), oppNote]));
    tools.appendChild(el('div', { class: 'b11-tools-row' }, [
      el('button', { type: 'button', text: '이 가중치로 선발', title: '지금 가중치로 선수를 다시 뽑습니다', onclick: function () { pick(false); } }),
      el('button', { type: 'button', text: '케미 반영 최적화', title: '케미까지 반영해 선수를 다듬습니다', onclick: function () { pick(true); } }),
      el('button', { type: 'button', text: '교체·대체 보고서', title: '빠지면 점수가 얼마나 떨어지는지', onclick: openIrrReport }),
      oppRptBtn,
      el('button', { type: 'button', text: '포메이션 추천', title: '이 구단·가중치에서 점수가 가장 높은 포메이션', onclick: openFormations }),
      el('span', { class: 'lab-muted', text: '카드 숫자 = 능력 점수, 옆의 색 숫자 = 케미 가산점' })]));
    var det = el('details', { class: 'lab-detail' }, [el('summary', { text: '지표별 가중치 자세히 (점수 0~100, 포지션 합계 100 기준)' }), metricsBox]);
    tools.appendChild(det);
  }
  function fmtMult(v) { return v.toFixed(2).replace(/0$/, '') + '×'; }
  // 지표별 가중치는 점수(0~100)로 보여주고, 서버에는 기본 가중치 대비 배율(mult)로 보낸다.
  var MAX_WEIGHT_SUM = 100;
  // 배율은 포지션별로 저장한다('FW:goals'). 예전에 저장된 'goals' 형식도 읽는다.
  function multOf(pos, x) { var k = pos + ':' + x.key; return S.mult[k] != null ? S.mult[k] : (S.mult[x.key] != null ? S.mult[x.key] : 1); }
  function weightOf(pos, x) { return Math.min(100, Math.round(x.weight * multOf(pos, x))); }
  function setWeight(pos, x, w) {
    if (S.mult[x.key] != null) {                       // 예전 형식이 남아 있으면 포지션별로 나눠 옮긴다
      var old = S.mult[x.key]; delete S.mult[x.key];
      POS_ORDER.forEach(function (p) { (INIT.metrics[p] || []).forEach(function (y) { if (y.key === x.key && Math.abs(old - 1) > 1e-9) S.mult[p + ':' + y.key] = old; }); });
    }
    var k = pos + ':' + x.key, m = x.weight ? w / x.weight : 1;
    if (Math.abs(m - 1) < 1e-9) delete S.mult[k]; else S.mult[k] = Math.round(m * 10000) / 10000;
  }
  function resetWeightSliders() {
    Array.prototype.forEach.call(metricsBox.querySelectorAll('input'), function (i) { i.value = i.getAttribute('data-base'); i.nextSibling.textContent = i.value; });
    Array.prototype.forEach.call(metricsBox.querySelectorAll('fieldset'), function (f) { if (f.updateSum) f.updateSum(); });
  }
  function fillTools() {
    clear(presetBox);
    Object.keys(INIT.presets).forEach(function (k) {
      presetBox.appendChild(el('button', { type: 'button', 'data-k': k, class: k === S.preset ? 'on' : '', text: INIT.presets[k], onclick: function () { setPreset(k); } }));
    });
    INIT.teams.forEach(function (t) { oppSel.appendChild(el('option', { value: t.id, text: t.name + (t.style ? ' (' + t.style + ')' : '') })); });
    oppSel.value = S.opponent;
    clear(metricsBox);
    POS_ORDER.forEach(function (pos) {
      var fs = el('fieldset', {}, [el('legend', { text: POS_LABEL[pos] })]);
      var inputs = [];
      var sumOut = el('p', { class: 'b11-wsum' });
      function updateSum() {                          // 포지션 가중치 합계: 100을 넘으면 경고
        var t = inputs.reduce(function (a, i) { return a + Number(i.value); }, 0);
        var over = t > MAX_WEIGHT_SUM;
        sumOut.className = 'b11-wsum' + (over ? ' over' : '');
        sumOut.textContent = '합계 ' + t + ' / ' + MAX_WEIGHT_SUM + (over ? ' — MAX(100)를 ' + (t - MAX_WEIGHT_SUM) + '점 넘었습니다. 계산할 때는 비율대로 합계 100에 맞춰집니다.' : '');
      }
      INIT.metrics[pos].forEach(function (x) {
        var cur = weightOf(pos, x);
        var out = el('b', { text: String(cur) });
        var inp = el('input', { type: 'range', min: '0', max: '100', step: '1', value: String(cur), 'data-key': x.key, 'data-base': String(x.weight) });
        inputs.push(inp);
        inp.addEventListener('input', function () { out.textContent = inp.value; updateSum(); });
        inp.addEventListener('change', function () { setWeight(pos, x, Number(inp.value)); saveSettings(); settingsChanged(); });
        fs.appendChild(el('label', { title: '기본 가중치 ' + x.weight }, [x.label + ' (기본 ' + x.weight + ')', inp, out]));
      });
      fs.appendChild(sumOut);
      fs.updateSum = updateSum;
      updateSum();
      metricsBox.appendChild(fs);
    });
    chemInp.addEventListener('input', function () { chemVal.textContent = fmtMult(parseFloat(chemInp.value)); });
    chemInp.addEventListener('change', function () { S.chem = parseFloat(chemInp.value); saveSettings(); settingsChanged(); });
    expInp.addEventListener('input', function () { expVal.textContent = fmtMult(parseFloat(expInp.value)); });
    expInp.addEventListener('change', function () { S.exp = parseFloat(expInp.value); saveSettings(); settingsChanged(); });
    oppSel.addEventListener('change', function () { S.opponent = oppSel.value; saveSettings(); settingsChanged(); });
  }
  function setPreset(k) {
    S.preset = k; S.mult = {}; saveSettings();
    Array.prototype.forEach.call(presetBox.children, function (b) { b.className = b.getAttribute('data-k') === k ? 'on' : ''; });
    resetWeightSliders();
    settingsChanged();
  }

  /* ---------- 서버 호출 (계산 중에 바뀐 설정은 끝난 뒤 한 번 더 계산) ---------- */
  var busy = false, again = null;
  function run(fn) {
    if (busy) { again = fn; return; }
    busy = true; bar.classList.add('busy');
    fn().catch(showErr).then(function () { busy = false; bar.classList.remove('busy'); if (again) { var f = again; again = null; run(f); } });
  }
  function settingsChanged() {
    // 내가 직접 바꾼 라인업이 있으면 선수는 그대로 두고 점수만 다시 계산, 아니면 가중치로 다시 선발
    run(function () { return isCustom() ? evaluate() : autoPick(false); });
  }
  function autoPick(optimize) {
    var b = params(); b.optimize = !!optimize; delete b.lineup;
    return post(URLS.lineup, b).then(function (r) { autoIds = r.lineup.slice(); ids = r.lineup.slice(); save(); return evaluate(); });
  }
  function pick(optimize) { run(function () { return autoPick(optimize); }); }
  function evaluate() { return post(URLS.evaluate, params()).then(render); }

  /* ---------- 카드 다시 그리기 ---------- */
  function paint(card, p) {
    var a = card.querySelector('.player-popup-link');
    a.setAttribute('onclick', 'openPlayerModal(' + p.id + '); return false;');
    var photo = card.querySelector('.player-photo'); clear(photo);
    if (p.photo) photo.appendChild(el('img', { src: p.photo, alt: p.name })); else photo.appendChild(el('div', { class: 'no-photo', text: 'NO PHOTO' }));
    card.querySelector('.player-name').textContent = p.name;
    var tn = card.querySelector('.team-name'); clear(tn);
    if (p.team_logo) tn.appendChild(el('img', { src: p.team_logo, alt: p.team, class: 'team-mini-logo' }));
    tn.appendChild(el('span', { text: p.team + ' · ' + p.position }));
    var sc = card.querySelector('.player-score'); clear(sc);
    sc.appendChild(document.createTextNode('BEST11 ' + p.ability + '점'));
    sc.appendChild(el('span', { class: 'b11-cn ' + (p.chem_bonus > 0 ? 'pos' : p.chem_bonus < 0 ? 'neg' : 'zero'), text: ' ' + sign(p.chem_bonus),
      title: '케미 가산점 ' + sign(p.chem_bonus) + ' → 최종 ' + p.final + '점' }));
    if (p.chem_reason) sc.appendChild(el('small', { class: 'b11-cr', text: p.chem_reason, title: p.chem_reason }));
    var old = card.querySelector('.b11-chem'); if (old) old.remove();
    var mark = card.querySelector('.b11-mark'); if (mark) mark.remove();
    if (p.id !== autoIds[cards.indexOf(card)]) a.appendChild(el('div', { class: 'b11-mark', text: '내 선택' }));
  }
  function render(r) {
    last = r;
    r.players.forEach(function (p, i) { paint(cards[i], p); });
    var changed = isCustom();
    var parts = [
      el('span', { text: changed ? '내 BEST11 (직접 교체함)' : (isDefaultSettings() ? 'BEST11 (자동 선발)' : 'BEST11 (가중치 적용 자동 선발)') }),
      el('span', { text: '라인업 총점 ' + r.total + ' · 라인업 평균 ' + (r.players.length ? (r.total / r.players.length).toFixed(1) : '-') + ' · 팀 케미 평균 ' + sign(r.chem_team) }),
      el('span', { class: 'lab-muted', text: '카드의 ⇄ 교체 버튼으로 선수를 바꿀 수 있습니다' }),
      changed ? el('button', { type: 'button', text: '자동 선발로 되돌리기', onclick: reset }) : null,
      isDefaultSettings() ? null : el('button', { type: 'button', text: '가중치 초기화', onclick: resetSettings })];
    clear(bar);
    parts.filter(Boolean).forEach(function (n) { bar.appendChild(n); });
    oppRptBtn.hidden = !r.opponent;
    oppNote.textContent = r.opponent ? r.opponent.name + ' 상대 맞춤: ' + (r.opponent.reasons.length ? r.opponent.reasons.join(' / ') : '조정할 규칙 없음') : '';
    document.dispatchEvent(new CustomEvent('b11:result', { detail: { result: r, params: params() } }));
    updateModalTag();
  }
  function save() {
    var o = readJSON(KEY, {});
    if (isCustom()) o[storeKey()] = ids; else delete o[storeKey()];
    writeJSON(KEY, o);
  }
  function reset() { run(function () { ids = autoIds.slice(); save(); return evaluate(); }); }
  function resetSettings() {
    S = { preset: 'default', mult: {}, chem: 1, exp: 1.5, opponent: '' }; saveSettings();
    chemInp.value = '1'; chemVal.textContent = '1×'; expInp.value = '1.5'; expVal.textContent = '1.5×'; oppSel.value = '';
    Array.prototype.forEach.call(presetBox.children, function (b) { b.className = b.getAttribute('data-k') === 'default' ? 'on' : ''; });
    resetWeightSliders();
    settingsChanged();
  }
  function showErr(e) { bar.appendChild(el('span', { class: 'lab-msg err', text: e.message })); }

  /* ---------- 교체 ---------- */
  function openCands(slot) {
    var box = el('div', {}, [el('p', { class: 'lab-muted', text: '불러오는 중…' })]);
    openModal(cards[slot].querySelector('.player-name').textContent + ' 교체 후보', box);
    var b = params(); b.out_id = ids[slot];
    post(URLS.candidates, b).then(function (r) {
      clear(box);
      box.appendChild(el('p', { class: 'lab-muted', text: '같은 포지션만 나옵니다. 라인업 총점(능력+케미)이 가장 많이 오르는 순서이고, 위쪽 후보가 추천입니다.' }));
      if (!r.candidates.length) box.appendChild(el('p', { text: '교체할 수 있는 선수가 없습니다.' }));
      r.candidates.forEach(function (c) {
        var d = c.delta;
        var kids = [el('div', {}, [el('b', { text: c.name }), ' ', el('span', { class: 'lab-muted', text: c.team + ' · BEST11 ' + c.ability + '점 ' }),
          el('span', { class: 'b11-cn ' + (c.chem_bonus > 0 ? 'pos' : c.chem_bonus < 0 ? 'neg' : 'zero'), text: sign(c.chem_bonus) }),
          c.recommended ? el('span', { class: 'lab-badge info', text: '추천' }) : null].concat(c.badges.map(badge)).concat(
          [c.partners.length ? el('div', { class: 'lab-muted', text: '케미: ' + c.partners.map(function (q) { return q.name; }).join(', ') }) : null])),
          el('div', {}, [el('span', { class: 'lab-delta ' + (d >= 0 ? 'pos' : 'neg'), text: sign(d) + ' ' }),
            el('button', { type: 'button', text: '교체', onclick: function () { choose(slot, c.id); } })])];
        box.appendChild(el('div', { class: 'lab-cand' + (c.recommended ? ' rec' : '') }, kids));
      });
    }).catch(function (e) { clear(box).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }
  function choose(slot, id) {
    ids[slot] = id; closeModal(); save();
    run(evaluate);
  }

  /* ---------- 포메이션 추천 (점수 기준) ---------- */
  /* ---------- 화면별 보고서: 포메이션 / 상대 맞춤 / 교체·대체 / VS ---------- */
  var POSK = { FW: '공격수', MF: '미드필더', DF: '수비수', GK: '골키퍼' };
  function formationReport(fs) {
    var a = fs[0], b = fs[1], w = fs[fs.length - 1];
    var best = Object.keys(a.by_pos || {}).sort(function (x, y) { return a.by_pos[y].vs / a.by_pos[y].n - a.by_pos[x].vs / a.by_pos[x].n; });
    var lines = [
      '1위 ' + a.formation + ': 같은 포지션 주전급 평균보다 합계 ' + sign(a.vs_avg) + '점 높습니다 (선수당 ' + sign(num1(a.vs_avg / 11)) + '점).',
      b ? '2위 ' + b.formation + '와는 ' + num1(a.vs_avg - b.vs_avg) + '점 차이' + (a.vs_avg - b.vs_avg < 3 ? ' — 차이가 작아 사실상 비슷합니다.' : ' — 의미 있는 차이입니다.') : '',
      '꼴찌 ' + w.formation + '와는 ' + num1(a.vs_avg - w.vs_avg) + '점 차이입니다.'].filter(Boolean);
    if (best.length) lines.push('1위 포메이션에서 강한 포지션: ' + best.slice(0, 2).map(function (k) { return (POSK[k] || k) + ' ' + a.by_pos[k].n + '명 합계 ' + sign(a.by_pos[k].vs) + '점'; }).join(', ') + '.');
    lines.push('케미 팀 점수는 ' + sign(a.chem_team) + '입니다. 순위 기준은 합계가 아니라 평균 대비 점수입니다(인원이 많은 포메이션이 유리해지는 것을 막기 위함).');
    return section('📋 포메이션 추천 보고서', lines.concat(['한계: 포메이션 자체의 전술 효과와 구단의 실제 사용 포메이션은 반영하지 않고 선수 점수의 합만 비교합니다.']));
  }
  function openOppReport() {
    if (!last || !last.opponent) return;
    var box = el('div', { class: 'b11-rpt' }, [el('p', { class: 'lab-muted', text: '상대 맞춤 전/후를 비교하는 중…' })]);
    openModal(last.opponent.name + ' 상대 맞춤 보고서', box, true);
    var base = params(); base.opponent = null;
    post(URLS.evaluate, base).then(function (r0) {
      var before = {}; r0.players.forEach(function (p) { before[p.id] = p; });
      var rows = last.players.map(function (p) { var o = before[p.id]; return { name: p.name, pos: p.position, d: o ? num1(p.final - o.final) : 0, a: o ? o.final : null, b: p.final }; })
        .sort(function (x, y) { return Math.abs(y.d) - Math.abs(x.d); });
      clear(box);
      var mult = last.opponent.mult || {};
      var lab = {}; Object.keys(INIT.metrics).forEach(function (ps) { INIT.metrics[ps].forEach(function (m) { lab[m.key] = m.label || m.name || m.key; }); });
      var ml = Object.keys(mult).map(function (k) { return (lab[k] || k) + ' ×' + (Math.round(mult[k] * 100) / 100); });
      box.appendChild(section('📋 왜 이렇게 조정했나', last.opponent.reasons.length ? last.opponent.reasons : ['이 상대에게는 조정할 규칙이 없었습니다.']));
      box.appendChild(section('조정된 지표 비중', ml.length ? ml : ['변경 없음']));
      box.appendChild(section('현재 라인업 선수별 점수 변화 (큰 순서)', rows.slice(0, 11).map(function (x) { return x.name + '(' + x.pos + '): ' + x.a + ' → ' + x.b + '점 (' + sign(x.d) + ')'; })));
      box.appendChild(el('p', { class: 'lab-muted', text: '근거: 상대의 시즌 득실점 기록으로 약점을 찾아 해당 지표 비중을 최대 0.6~1.8배 범위에서 조정합니다(강도 2.5). 한계: 시즌 평균 기준이라 그날의 전술은 모르며, 조정 폭은 의도적으로 제한됩니다.' }));
    }).catch(function (e) { clear(box).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }
  function openIrrReport() {
    if (!last || !last.irreplaceability) return;
    var box = el('div', { class: 'b11-rpt' });
    var rows = last.irreplaceability.slice().sort(function (a, b) { return b.drop - a.drop; });
    openModal('교체·대체 보고서', box, true);
    box.appendChild(section('📋 읽는 법', ['각 선수를 같은 포지션 최선의 대체 후보로 바꿨을 때 라인업 총점이 얼마나 떨어지는지로 "빠지면 아픈 정도"를 계산합니다.',
      '핵심 = 하락폭 상위 3명, 대체 용이 = 하락폭이 라인업 최대치의 25% 미만. 핵심 선수는 로테이션을 아끼고, 대체 용이 선수는 먼저 쉬게 하는 것이 유리합니다.']));
    var tb = el('table', { class: 'b11-cmp-table b11-rpt-table' }, [el('tr', {}, ['선수', '빠지면', '대체 1순위', '구분'].map(function (h) { return el('th', { text: h }); }))]);
    var mx = rows.length ? rows[0].drop || 1 : 1;
    rows.forEach(function (x) {
      tb.appendChild(el('tr', {}, [el('td', { text: x.name + ' (' + x.position + ')' }),
        el('td', {}, [el('span', { class: 'lab-bar', style: 'width:' + Math.max(2, Math.round(x.drop / mx * 90)) + 'px' }), ' -' + x.drop + '점']),
        el('td', { text: x.replacement || '-' }), el('td', { text: x.label || '보통' })]));
    });
    box.appendChild(el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: '선수별 대체 영향' }), tb]));
    box.appendChild(el('p', { class: 'lab-muted', text: '피로·경고 누적에 따른 실제 휴식 제안(경기당 피로 30~35, 하루 회복 4, 라운드당 최대 3명)은 모의 경기 화면에서 계산됩니다. 이 수치들은 경험적 기준이며 체력 데이터로 검증하지 않았습니다.' }));
  }
  function vsSummary(A, B, labels, va, vb) {
    var diffs = labels.map(function (lb, i) { return { lb: lb, d: va[i] - vb[i] }; }).sort(function (x, y) { return Math.abs(y.d) - Math.abs(x.d); });
    var aw = diffs.filter(function (x) { return x.d > 0; }).length, bw = diffs.filter(function (x) { return x.d < 0; }).length;
    var lead = diffs.slice(0, 3).map(function (x) { return x.lb + ' ' + (x.d > 0 ? A.name : B.name) + ' +' + num1(Math.abs(x.d)); });
    var lines = ['앞선 항목 수: ' + A.name + ' ' + aw + ' : ' + bw + ' ' + B.name + '. 차이가 큰 항목: ' + lead.join(', ') + '.',
      '최종 점수(케미·가중치 반영): ' + A.name + ' ' + A.final + ' vs ' + B.name + ' ' + B.final + ' → ' + (A.final >= B.final ? A.name + ' 우세' : B.name + ' 우세') + ' (' + num1(Math.abs(A.final - B.final)) + '점 차).',
      '한계: 육각형은 포지션별 기준 점수이며, 서로 다른 포지션끼리의 비교는 의미가 약합니다.'];
    return section('📋 VS 비교 보고서', lines);
  }
  function openFormations() {
    var box = el('div', {}, [el('p', { class: 'lab-muted', text: '계산 중…' })]);
    openModal('포메이션 추천', box, true);
    var b = params(); delete b.lineup;
    post(URLS.formations, b).then(function (r) {
      clear(box);
      var who = team() ? '선택한 구단' : '리그 전체';
      box.appendChild(el('p', { class: 'lab-muted', text: who + '에서 포메이션별로 자동 선발한 라인업을 같은 가중치로 계산했습니다. 점수는 선수별 최종 점수(능력 + 케미, 상한 ' + (r.formations[0] ? r.formations[0].cap : 200) +
        '점)이고, 포메이션마다 포지션 인원이 달라서 "리그 같은 포지션 주전급 평균보다 몇 점 높은가"로 순위를 매깁니다. (백분위가 아닙니다)' }));
      var max = Math.max.apply(null, r.formations.map(function (x) { return Math.abs(x.vs_avg); }).concat([1]));
      var tb = el('table', { class: 'b11-ftable' }, [el('tr', {}, ['순위', '포메이션', '평균 대비 점수', '선수당', '총점', '선수 평균', '케미', ''].map(function (h) { return el('th', { text: h }); }))]);
      r.formations.forEach(function (f) {
        var cur = f.formation === formation();
        tb.appendChild(el('tr', { class: cur ? 'cur' : '' }, [
          el('td', { text: String(f.rank) }),
          el('td', {}, [el('b', { text: f.formation }), f.rank === 1 ? el('span', { class: 'lab-badge info', text: '추천' }) : null, cur ? el('span', { class: 'lab-badge soft', text: '현재' }) : null]),
          el('td', {}, [el('span', { class: 'lab-bar', style: 'width:' + Math.max(2, Math.round(Math.abs(f.vs_avg) / max * 120)) + 'px' }), ' ' + sign(f.vs_avg) + '점']),
          el('td', { text: sign(num1(f.vs_avg / 11)) }), el('td', { text: String(f.total) }), el('td', { text: String(f.avg) }), el('td', { text: sign(f.chem_team) }),
          el('td', {}, [cur ? null : el('button', { type: 'button', text: '이 포메이션', onclick: function () { useFormation(f.formation); } })])]));
      });
      box.appendChild(tb);
      if (r.formations.length) box.appendChild(formationReport(r.formations));
      box.appendChild(el('p', { class: 'lab-muted', text: '실제 구단이 쓰는 포메이션 기록은 데이터에 없어서, 이 구단 선수들의 기록으로 계산한 "잘 맞는 포메이션"입니다. 선수 기록이 적은 구단은 오차가 큽니다.' }));
    }).catch(function (e) { clear(box).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }
  function useFormation(f) {
    closeModal();
    if (!formSel) return;
    formSel.value = f;
    if (formSel.form) formSel.form.submit();     // 추천 표의 "이 포메이션" 버튼은 누르면 바로 적용
  }

  /* ---------- 선수 팝업: 이름 옆 케미 표시 + VS 비교 ---------- */
  /* ---------- 팝업 "90분당 주요 기록": 박스 → 가로바 (막대=선수, 세로선=같은 포지션 주전급 평균, 끝=리그 최고) ---------- */
  var P90 = [['per90Goals', 'goals', '득점'], ['per90Assists', 'assists', '도움'], ['per90Shots', 'shots', '슈팅'], ['per90ShotsTarget', 'shots_on_target', '유효슈팅'],
    ['per90KeyPasses', 'key_passes', '키패스'], ['per90PassRate', 'pass_rate', '패스 성공률(%)'], ['per90Dribble', 'dribble', '드리블'],
    ['per90Interceptions', 'interceptions', '인터셉트'], ['per90Clearances', 'clearances', '클리어링'], ['per90Recoveries', 'recoveries', '볼 회수']];
  function initPer90Bars() {
    var grid = document.querySelector('.per90-grid');
    if (!grid || !URLS.reportsFile) return;
    var wrap = el('div', { class: 'b11-p90' });
    grid.parentNode.insertBefore(wrap, grid.nextSibling);
    var pending = false;
    function draw() {
      pending = false;
      loadReports().then(function (j) {
        var rp = j.players[String(curId)];
        var sc = j.meta.per90_scale && rp && j.meta.per90_scale[rp.position];
        if (!sc) { grid.style.display = ''; wrap.hidden = true; return; }     // 기준이 없으면 원래 박스를 그대로 둔다
        grid.style.display = 'none'; wrap.hidden = false; clear(wrap);
        wrap.appendChild(el('p', { class: 'lab-muted', text: '막대=이 선수 · 세로선=같은 포지션(' + rp.position + ') 주전급 평균 · 끝=리그 최고 · 평균 이상은 초록' }));
        P90.forEach(function (m) {
          var node = document.getElementById(m[0]); if (!node) return;
          var v = parseFloat(String(node.textContent).replace(/[^0-9.\-]/g, '')) || 0;
          var s = sc[m[1]]; if (!s) return;
          var mx = Math.max(s.max, v, 0.0001), w = Math.max(1, Math.min(100, v / mx * 100)), mp = Math.max(0, Math.min(100, s.mean / mx * 100));
          wrap.appendChild(el('div', { class: 'b11-hb' }, [
            el('span', { class: 'b11-hb-l', text: m[2] }),
            el('span', { class: 'b11-hb-t' }, [el('span', { class: 'b11-hb-f ' + (v >= s.mean ? 'above' : 'below'), style: 'width:' + w + '%' }), el('span', { class: 'b11-hb-m', style: 'left:' + mp + '%', title: '주전급 평균 ' + s.mean })]),
            el('span', { class: 'b11-hb-v', text: v + ' (평균 ' + s.mean + ')' })]));
        });
      }).catch(function () { grid.style.display = ''; wrap.hidden = true; });
    }
    function sched() { if (!pending) { pending = true; setTimeout(draw, 30); } }
    new MutationObserver(sched).observe(grid, { childList: true, characterData: true, subtree: true });
    sched();
  }
  initPer90Bars();

  /* ---------- 케미 파트너: 이 선수가 누구와 어떤 케미를 보이는가 ---------- */
  var TIERK = { strong: '강한 케미', normal: '케미 있음', none: '케미 약함' };
  function partnerRow(x, extra) {
    var cls = x.tier === 'strong' ? 'pos' : x.tier === 'normal' ? 'mid' : 'zero';
    return el('div', { class: 'lab-cand b11-prow' }, [
      el('div', {}, [el('b', { text: x.name }), ' ', el('span', { class: 'lab-muted', text: (extra || '') + (POSK[x.position] || x.position) }), ' ',
        el('span', { class: 'b11-cn ' + (x.tier === 'none' ? 'zero' : 'pos'), text: x.score + '점 · ' + (x.overlap ? '약점 중복' : TIERK[x.tier]) + (x.bonus != null ? ' (' + sign(x.bonus) + ')' : '') })]),
      el('div', { class: 'lab-muted', text: x.reasons.length ? x.reasons.join(' / ') : '뚜렷한 보완·연계 근거가 없습니다.' })]);
  }
  function openChem(pid) {
    if (pid == null || !URLS.chem) return;
    var box = el('div', { class: 'b11-rpt' }, [el('p', { class: 'lab-muted', text: '케미를 계산하는 중…' })]);
    openModal('케미 파트너', box, true);
    var b = params(); b.player_id = pid;
    post(URLS.chem, b).then(function (r) {
      clear(box);
      modal.querySelector('#b11Title').textContent = r.player.name + ' 케미 파트너';
      box.appendChild(el('p', { class: 'b11-rpt-concl', text: r.player.team + ' ' + r.player.name + (r.chem_bonus != null ? ' — 현재 라인업 케미 가산 ' + sign(r.chem_bonus) + '점' : '') +
        (r.player.low_minutes ? ' (출전 450분 미만이라 가산은 절반만 적용)' : '') }));
      var ins = el('div', { class: 'b11-rpt-sec hire' }, [el('h4', { text: '현재 라인업 안에서 (케미 점수 높은 순)' })]);
      if (!r.inside.length) ins.appendChild(el('p', { class: 'lab-muted', text: '이 선수는 현재 라인업에 없거나 연결된 선수가 없습니다.' }));
      r.inside.forEach(function (x) { ins.appendChild(partnerRow(x, x.team + ' · ')); });
      box.appendChild(ins);
      var out = el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: '라인업 밖에서 케미가 좋은 선수 (리그 전체, 55점 이상)' })]);
      if (!r.outside.length) out.appendChild(el('p', { class: 'lab-muted', text: '조건(55점 이상)을 만족하는 선수가 없습니다.' }));
      r.outside.forEach(function (x) { out.appendChild(partnerRow(x, x.team + ' · ')); });
      box.appendChild(out);
      box.appendChild(el('p', { class: 'lab-muted', text: r.rule + ' 기록 기반 추정이며 실제 호흡(패스 주고받기)을 검증한 값이 아닙니다.' }));
    }).catch(function (e) { clear(box).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }
  var curId = null;
  var nameEl = document.getElementById('modalPlayerName');
  var tag = el('span', { class: 'b11-mtag', hidden: '' });
  var crTag = el('small', { class: 'b11-cr-pop' });
  var vsBtn = el('button', { type: 'button', class: 'b11-vs', text: '⚔ VS 비교', onclick: function () { openCompare(curId); } });
  var chemBtn = el('button', { type: 'button', class: 'b11-vs', text: '🤝 케미 파트너', onclick: function () { openChem(curId); } });
  var rptBtn = el('button', { type: 'button', class: 'b11-vs', text: '📋 분석 보고서', onclick: function () { openReport(curId); } });
  var tagWrap = el('span', { class: 'b11-mwrap' }, [tag, crTag, vsBtn, URLS.chem ? chemBtn : null, (URLS.report || URLS.reportsFile) ? rptBtn : null].filter(Boolean));
  function updateModalTag() {
    if (!nameEl) return;
    var p = last && last.players.filter(function (x) { return x.id === curId; })[0];
    tagWrap.hidden = curId == null;
    if (!p) { tag.hidden = true; return; }
    tag.hidden = false;
    tag.className = 'b11-mtag ' + (p.chem_bonus > 0 ? 'pos' : p.chem_bonus < 0 ? 'neg' : 'zero');
    tag.textContent = '케미 ' + sign(p.chem_bonus);
    crTag.textContent = p.chem_reason || '';
    tag.title = '능력 ' + p.ability + ' + 케미 ' + sign(p.chem_bonus) + ' = 최종 ' + p.final + '점' + (p.partners.length ? ' · 잘 맞는 선수: ' + p.partners.map(function (q) { return q.name; }).join(', ') : '');
  }
  if (nameEl && nameEl.parentNode) {
    if (window.getComputedStyle(nameEl).display === 'block') nameEl.style.display = 'inline-block';   // 이름 바로 옆에 표시되도록
    nameEl.parentNode.insertBefore(tagWrap, nameEl.nextSibling);
    tagWrap.hidden = true;
    var orig = window.openPlayerModal;
    if (typeof orig === 'function') {
      window.openPlayerModal = function (id) { curId = Number(id); updateModalTag(); return orig.apply(this, arguments); };
    }
    new MutationObserver(function () { updateModalTag(); }).observe(nameEl, { childList: true, characterData: true, subtree: true });
  }

  /* ---------- 선수 분석 보고서: 왜 이 점수인가 + 왜 쓰는가 ---------- */
  var reportsCache = null;
  function loadReports() {
    if (reportsCache) return Promise.resolve(reportsCache);
    return fetch(URLS.reportsFile, { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('보고서 파일이 없습니다. python manage.py build_player_reports 를 먼저 실행하세요.'); return r.json(); })
      .then(function (j) { reportsCache = j; return j; });
  }
  var VCLS = { '강력 추천': 'good', '추천': 'good', '무난': 'mid', '대안 검토': 'bad', '표본 부족': 'bad' };
  function section(title, arr, cls) {
    var ul = el('ul', {}); arr.forEach(function (x) { ul.appendChild(el('li', { text: x })); });
    return el('div', { class: 'b11-rpt-sec ' + (cls || '') }, [el('h4', { text: title }), ul]);
  }
  /* 90분당 주요 기록 가로바: 막대=선수 값, 세로 눈금=주전급 평균, 막대 길이=리그 최고 대비 */
  function statBars(r) {
    var sec = el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: '90분당 주요 기록 (막대=이 선수, 세로선=주전급 평균, 끝=리그 최고)' })]);
    r.rows.forEach(function (x) {
      if (x.unit !== 'per90') return;
      var mx = x.max || 1, w = Math.max(1, Math.min(100, x.value / mx * 100)), m = Math.max(0, Math.min(100, x.mean / mx * 100));
      var cls = x.value >= x.mean ? 'above' : 'below';
      sec.appendChild(el('div', { class: 'b11-hb' }, [
        el('span', { class: 'b11-hb-l', text: x.label }),
        el('span', { class: 'b11-hb-t' }, [
          el('span', { class: 'b11-hb-f ' + cls, style: 'width:' + w + '%' }),
          el('span', { class: 'b11-hb-m', style: 'left:' + m + '%', title: '주전급 평균 ' + x.mean })]),
        el('span', { class: 'b11-hb-v', text: x.value + ' (평균 ' + x.mean + ' · ' + x.rank + '위)' })]));
    });
    if (sec.children.length === 1) sec.appendChild(el('p', { class: 'lab-muted', text: '90분당으로 비교할 기록이 없는 포지션 지표입니다. 아래 표를 보세요.' }));
    return sec;
  }
  /* 보고서 설명: 칩을 누르면 펼쳐집니다 */
  var HELP = [
    ['가중치', '포지션마다 중요 기록의 비중이 다릅니다(공격수: 득점 35·도움 20 등). 비중은 팀이 정한 경험적 값이며 선정 이유 문서화와 외부 평점 검증이 남아 있습니다. 수비수 비중은 외부 평점과 상관이 0.24로 약합니다.'],
    ['소표본·경험 보정', '출전 450분 미만은 점수를 평균 쪽으로 당기고, 1800분 미만은 최대 30%까지 낮춥니다. 보정 기준은 합리적 기준이지 통계로 도출한 값이 아닙니다. 표본 부족 선수는 "참고"로만 보세요.'],
    ['케미', '같은 구단·스타일과 보완 관계로 추정한 값입니다. 패스 데이터가 없어 실제 호흡과 맞는지 검증하지 못했습니다.'],
    ['교체·로테이션', '피로도는 경기당 30~35 누적, 하루 4 회복(경험적 기준)이며 경고 위험은 포아송 분포로 계산합니다. 체력 데이터로 검증하지는 않았습니다.'],
    ['포메이션·상대 맞춤', '포메이션은 선수 점수 합을 리그 같은 포지션 평균과 비교해 순위를 매깁니다. 전술 효과는 반영하지 않습니다. 상대 맞춤은 시즌 평균 기준이며 영향 폭은 제한됩니다.'],
    ['승부예측', '득점 기대값의 포아송 모델입니다. 홀드아웃 로그손실 1.150으로 무작위 기준(1.099)보다 낮은 신뢰도이니 참고용입니다. 라인업 효과는 최대 8%p의 규칙입니다.']
  ];
  function helpChips() {
    var out = el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: 'ⓘ 이 보고서의 근거 설명 (눌러서 보기)' })]);
    var row = el('div', { class: 'b11-help-row' }), body = el('p', { class: 'b11-help-body', hidden: true });
    var cur = null;
    HELP.forEach(function (h) {
      var b = el('button', { type: 'button', class: 'b11-help-chip', text: h[0] });
      b.addEventListener('click', function () {
        if (cur === b) { body.hidden = true; b.classList.remove('on'); cur = null; return; }
        if (cur) cur.classList.remove('on');
        cur = b; b.classList.add('on'); body.hidden = false; body.textContent = h[0] + ' — ' + h[1];
      });
      row.appendChild(b);
    });
    out.appendChild(row); out.appendChild(body); return out;
  }
  /* ---------- 스카우터 양식 보고서 (20-80 스케일: 50 = 같은 포지션 주전급 평균, 10점 = 표준편차 1) ---------- */
  function probit(p) {                       // 표준정규 역함수 (Abramowitz-Stegun 26.2.23)
    p = Math.min(0.995, Math.max(0.005, p));
    var q = p < 0.5 ? p : 1 - p, tt = Math.sqrt(-2 * Math.log(q));
    var z = tt - (2.515517 + 0.802853 * tt + 0.010328 * tt * tt) / (1 + 1.432788 * tt + 0.189269 * tt * tt + 0.001308 * tt * tt * tt);
    return p < 0.5 ? -z : z;
  }
  function grade(pct) { var g = 50 + 10 * probit(pct / 100); return Math.max(20, Math.min(80, Math.round(g / 5) * 5)); }
  function gradeWord(g) { return g >= 70 ? '최상급' : g >= 60 ? '상급' : g >= 55 ? '평균 이상' : g >= 45 ? '평균' : g >= 40 ? '평균 이하' : '취약'; }
  function gradeCls(g) { return g >= 60 ? 'hi' : g >= 45 ? 'mid' : 'lo'; }
  var RECS = { '강력 추천': ['영입 권장', 'A'], '추천': ['영입 고려', 'B'], '무난': ['관찰', 'C'], '대안 검토': ['보류', 'D'], '표본 부족': ['추가 관찰 필요', '-'] };
  function boldLead(x) {                     // "강점: …" → 앞의 짧은 라벨만 굵게
    var m = /^(\[?[^:\[\]]{1,8}\]?):\s*(.*)$/.exec(x);
    return m ? el('li', {}, [el('b', { class: 'b11-lead', text: m[1] }), ' ' + m[2]]) : el('li', { text: x });
  }
  function bulletBox(title, arr, cls) {
    var ul = el('ul', {}); arr.forEach(function (x) { ul.appendChild(boldLead(x)); });
    if (!arr.length) ul.appendChild(el('li', { text: '해당 없음' }));
    return el('div', { class: 'b11-sc-box ' + cls }, [el('h4', { text: title }), ul]);
  }
  function renderScout(o) {
    var box = el('div', { class: 'b11-rpt b11-scout' });
    if (o.banner) box.appendChild(o.banner);
    var rec = RECS[o.verdict] || ['관찰', 'C'];
    var ovr = grade(Math.max(1, Math.min(99, 100 - o.top_pct)));
    box.appendChild(el('div', { class: 'b11-sc-head' }, [
      el('div', { class: 'b11-sc-id' }, [el('small', { text: 'SCOUTING REPORT' }), el('h3', { text: o.name }),
        el('div', { text: o.team + ' · ' + (POSK[o.pos] || o.pos) + (o.club_style ? ' · 구단 스타일 ' + o.club_style : '') }),
        el('div', { class: 'lab-muted', text: o.basis + ' · 기록 신뢰도 ' + o.confidence })]),
      el('div', { class: 'b11-sc-ovr' }, [el('small', { text: 'OVR (20–80)' }), el('b', { class: gradeCls(ovr), text: String(ovr) }), el('span', { text: gradeWord(ovr) })]),
      el('div', { class: 'b11-sc-rec' }, [el('small', { text: '스카우트 의견' }), el('b', { class: 'b11-verdict ' + (VCLS[o.verdict] || 'mid'), text: rec[0] }),
        el('span', { text: o.rank_total ? o.rank_total + '명 중 ' + o.rank + '위 · 상위 ' + o.top_pct + '%' : '순위 참고용' })])]));
    var sc = [el('div', {}, [el('small', { text: '능력 점수' }), el('b', { text: String(o.ability) })])];
    if (o.final != null) {
      sc.push(el('span', { text: '+' }), el('div', {}, [el('small', { text: '케미' }), el('b', { class: 'b11-cn ' + (o.chem > 0 ? 'pos' : o.chem < 0 ? 'neg' : 'zero'), text: sign(o.chem) })]),
        el('span', { text: '=' }), el('div', {}, [el('small', { text: '최종 점수' }), el('b', { text: String(o.final) })]));
    }
    box.appendChild(el('div', { class: 'b11-rpt-score' }, sc));
    box.appendChild(el('div', { class: 'b11-sc-sum' }, [el('small', { text: '한 줄 평가' }), el('p', { text: o.conclusion })]));

    // 능력치 평가
    var at = el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: '능력치 평가' }), el('p', { class: 'b11-sc-sub', text: '20–80 등급 · 가운데 선(50) = 같은 포지션 주전급 평균' })]);
    o.rows.forEach(function (x) {
      var g = grade(x.pct), w = (g - 20) / 60 * 100;
      at.appendChild(el('div', { class: 'b11-sc-item' }, [
        el('div', { class: 'b11-hb b11-sc-row' }, [
          el('span', { class: 'b11-hb-l', text: x.label }),
          el('span', { class: 'b11-hb-t' }, [el('span', { class: 'b11-hb-f g-' + gradeCls(g), style: 'width:' + w + '%' }), el('span', { class: 'b11-hb-m', style: 'left:50%' })]),
          el('b', { class: 'b11-sc-g ' + gradeCls(g), text: String(g) }),
          el('span', { class: 'b11-sc-w ' + gradeCls(g), text: gradeWord(g) })]),
        el('div', { class: 'b11-sc-d', text: x.value + (x.unit === 'rate' ? '' : ' /90분') + ' · 평균 ' + x.mean + ' · ' + x.rank + '위 · 비중 ' + x.weight + '%' })]));
    });
    box.appendChild(at);

    box.appendChild(el('div', { class: 'b11-sc-cols' }, [bulletBox('✅ 강점 · 영입 이유', o.hire, 'hire'), bulletBox('⚠ 약점 · 리스크', o.cautions, 'warn')]));
    box.appendChild(el('details', { class: 'b11-rpt-sec b11-sc-more' }, [el('summary', { text: '📊 점수 구성 근거 (펼쳐 보기)' }), el('ul', {}, o.why.map(boldLead))]));
    if (o.h2h) box.appendChild(o.h2h);
    if (o.alt) box.appendChild(o.alt);
    box.appendChild(el('div', { class: 'b11-rpt-sec b11-sc-final' }, [el('h4', { text: '최종 의견: ' + rec[0] + (rec[1] !== '-' ? ' (등급 ' + rec[1] + ')' : '') }),
      el('p', { text: o.conclusion }), el('p', { class: 'lab-muted', text: o.rule })]));
    box.appendChild(helpChips());
    box.appendChild(el('p', { class: 'lab-muted', text: '등급 읽는 법: 20–80 스케일은 스카우팅에서 쓰는 표기로, 같은 포지션 주전급(450분 이상) 선수들 사이의 위치를 정규분포로 환산해 5점 단위로 반올림했습니다. 50 평균, 60 상위 약 16%, 70 상위 약 2%, 40 하위 약 16%입니다. ' + (o.notes || '') }));
    return box;
  }
  function renderLeagueReport(r, meta) {
    var alt = null;
    if (r.similar && r.similar.length) alt = section('비교 대상 — 같은 포지션에서 능력이 더 높은 선수 (바로 위부터)', r.similar.map(function (s) { return s.team + ' ' + s.name + ' — 능력 ' + s.ability + '점 (출전 ' + s.minutes + '분)'; }));
    return renderScout({ name: r.name, team: r.team, pos: r.position, club_style: r.club_style, basis: r.basis, confidence: r.confidence, verdict: r.verdict,
      rank: r.ranked ? r.rank : null, rank_total: r.ranked ? r.rank_total : null, top_pct: r.top_pct, ability: r.ability, conclusion: r.conclusion, rows: r.rows,
      hire: r.hire, cautions: r.cautions, why: r.why, alt: alt, rule: r.rule, notes: meta.note + ' 기준: ' + meta.settings + ' · 작성일 ' + meta.generated });
  }
  function openReport(pid) {
    if (pid == null) return;
    if (URLS.reportsFile && isDefaultSettings()) {
      var box0 = el('div', { class: 'b11-rpt' }, [el('p', { class: 'lab-muted', text: '불러오는 중…' })]);
      openModal('분석 보고서', box0, true);
      loadReports().then(function (j) {
        var r = j.players[String(pid)];
        if (!r) throw new Error('이 선수의 보고서가 없습니다. (올 시즌 기록이 없는 선수)');
        modal.querySelector('#b11Title').textContent = r.name + ' 분석 보고서';
        clear(modal.querySelector('#b11Body')).appendChild(renderLeagueReport(r, j.meta));
      }).catch(function (e) { clear(box0).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
      return;
    }
    openReportLive(pid);
  }
  /* 내 가중치 설정 반영 보고서: 설정 요약 + 기본 설정 대비 변화 */
  function settingsBanner(banner, pid, r) {
    var nm = (INIT && INIT.presets && INIT.presets[S.preset]) || S.preset;
    var parts = ['프리셋 ' + nm];
    POS_ORDER.forEach(function (pos) { (INIT && INIT.metrics && INIT.metrics[pos] || []).forEach(function (x) {
      if (multOf(pos, x) !== 1) parts.push(POS_LABEL[pos] + ' ' + x.label + ' ' + x.weight + '→' + weightOf(pos, x));
    }); });
    if (S.chem !== 1) parts.push('케미 ×' + S.chem);
    if (S.exp !== 1.5) parts.push('경험 보정 기준 ' + S.exp);
    if (S.opponent) parts.push('상대 맞춤 적용');
    banner.appendChild(el('h4', { text: '⚙ 내 가중치 설정이 반영된 보고서' }));
    banner.appendChild(el('p', { class: 'lab-muted', text: '적용 설정: ' + parts.join(' · ') + ' — 아래 점수·순위·근거는 모두 이 설정 기준이며 기본 설정과 다를 수 있습니다.' }));
    var cmp = el('p', { class: 'b11-set-cmp', text: '기본 설정과 비교 중…' });
    banner.appendChild(cmp);
    loadReports().then(function (j) {
      var d = j.players[String(pid)];
      if (!d) { cmp.textContent = '기본 설정 보고서가 없는 선수라 비교할 수 없습니다.'; return; }
      var diff = Math.round((r.ability - d.ability) * 10) / 10;
      var txt = '능력 점수 ' + d.ability + ' → ' + r.ability + '점 (' + (diff >= 0 ? '+' : '') + diff + '), 순위 ' + d.rank + '위 → ' + r.rank + '위, 평가 "' + d.verdict + '" → "' + r.verdict + '"';
      var dm = {}; d.rows.forEach(function (x) { dm[x.key] = x; });
      var ch = r.rows.filter(function (x) { return dm[x.key] && Math.abs(dm[x.key].weight - x.weight) >= 0.5; })
        .map(function (x) { return x.label + ' 비중 ' + dm[x.key].weight + '% → ' + x.weight + '%'; });
      cmp.textContent = txt + (ch.length ? '. 비중 변화: ' + ch.join(', ') : '. 지표 비중은 같고 보정만 다릅니다.');
    }).catch(function () { cmp.textContent = '기본 설정 비교 파일을 불러오지 못했습니다.'; });
  }
  function openReportLive(pid) {
    if (pid == null || !last) return;
    var box = el('div', { class: 'b11-rpt' }, [el('p', { class: 'lab-muted', text: '분석 중…' })]);
    var nm = last.players.filter(function (x) { return x.id === pid; })[0];
    openModal((nm ? nm.name : '') + ' 분석 보고서', box, true);
    var b = params(); b.player_id = pid;
    post(URLS.report, b).then(function (r) {
      clear(box);
      var banner = el('div', { class: 'b11-rpt-sec warn b11-set' });
      settingsBanner(banner, pid, r);
      var h2h = null, alt = null;
      if (r.h2h && r.h2h.rows.length) {
        var h = r.h2h, ht = el('table', { class: 'b11-cmp-table b11-rpt-table' }, [el('tr', {}, [el('th', { text: '지표' }), el('th', { text: r.player.name, style: 'color:' + COL.a }), el('th', { text: h.name + ' (대체 1순위)', style: 'color:' + COL.b })])]);
        h.rows.forEach(function (x) {
          ht.appendChild(el('tr', {}, [el('td', { text: x.label + (x.unit === 'rate' ? '' : ' (90분당)') }), el('td', { text: String(x.me), class: x.lead === 'me' ? 'win' : '' }), el('td', { text: String(x.other), class: x.lead === 'other' ? 'win' : '' })]));
        });
        h2h = el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: '비교 대상 — ' + h.name + '(' + h.team + ', 출전 ' + h.minutes + '분) · 능력 ' + r.ability + ' vs ' + h.ability + '점, 앞선 지표 ' + h.me_wins + ' : ' + h.other_wins }), ht]);
      }
      if (r.alternatives.length) {
        alt = el('div', { class: 'b11-rpt-sec' }, [el('h4', { text: '이 자리의 대안 (라인업 총점이 오르는 선수)' })]);
        r.alternatives.forEach(function (a) {
          alt.appendChild(el('div', { class: 'lab-cand' }, [el('div', {}, [el('b', { text: a.name }), ' ', el('span', { class: 'lab-muted', text: a.team + ' · BEST11 ' + a.ability + '점 ' + sign(a.chem_bonus) })]),
            el('div', {}, [el('span', { class: 'lab-delta pos', text: sign(a.delta) + ' ' }),
              el('button', { type: 'button', text: '교체', onclick: function () { var slot = ids.indexOf(pid); closeModal(); var pm = document.getElementById('playerModal'); if (pm) pm.style.display = 'none'; choose(slot, a.id); } })])]));
        });
      }
      box.appendChild(renderScout({ name: r.player.name, team: r.player.team, pos: r.player.position, club_style: r.player.club_style, basis: r.basis, confidence: r.confidence,
        verdict: r.verdict, rank: r.rank, rank_total: r.rank_total, top_pct: r.top_pct, ability: r.ability, chem: r.chem_bonus, final: r.final, conclusion: r.conclusion, rows: r.rows,
        hire: r.hire, cautions: r.cautions, why: r.why, h2h: h2h, alt: alt, banner: banner, rule: r.rule, notes: r.notes }));
    }).catch(function (e) { clear(box).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }

  var infoCache = {};
  function getInfo(id) {
    if (infoCache[id]) return Promise.resolve(infoCache[id]);
    return fetch(INFO + id + '/', { credentials: 'same-origin' }).then(function (r) { if (!r.ok) throw new Error('선수 정보를 불러오지 못했습니다.'); return r.json(); })
      .then(function (j) { if (j.success === false) throw new Error(j.message || '기록이 없는 선수입니다.'); infoCache[id] = j; return j; });
  }
  var COL = { a: '#2563eb', b: '#ea580c' };
  var SVGNS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs, kids) {
    var e = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { e.appendChild(c); });
    return e;
  }
  function radarSvg(labels, series) {
    var cx = 210, cy = 170, R = 112, n = labels.length;
    function pt(i, v) { var a = -Math.PI / 2 + i * 2 * Math.PI / n, r = R * Math.max(0, Math.min(100, v)) / 100; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; }
    var svg = s('svg', { viewBox: '0 0 420 340', class: 'b11-radar', role: 'img', 'aria-label': '선수 비교 육각형 그래프' });
    [25, 50, 75, 100].forEach(function (lv) {
      svg.appendChild(s('polygon', { points: labels.map(function (_, i) { return pt(i, lv).join(','); }).join(' '), fill: 'none', stroke: '#d1d5db', 'stroke-width': '1' }));
    });
    labels.forEach(function (lb, i) {
      var e = pt(i, 100), t = pt(i, 122);
      svg.appendChild(s('line', { x1: cx, y1: cy, x2: e[0], y2: e[1], stroke: '#e5e7eb' }));
      var tx = s('text', { x: t[0], y: t[1], 'text-anchor': Math.abs(t[0] - cx) < 6 ? 'middle' : (t[0] > cx ? 'start' : 'end'), 'dominant-baseline': 'middle', 'font-size': '13', fill: '#374151' });
      tx.textContent = lb; svg.appendChild(tx);
    });
    series.forEach(function (sr, k) {
      var g = s('g', { class: 'b11-grow', style: 'animation-delay:' + (k * 0.08) + 's' });
      var pts = sr.vals.map(function (v, i) { return pt(i, v).join(','); }).join(' ');
      g.appendChild(s('polygon', { points: pts, fill: sr.dashed ? 'none' : sr.color, 'fill-opacity': sr.dashed ? '0' : '0.18', stroke: sr.color, 'stroke-width': sr.dashed ? '2' : '2.5',
        'stroke-dasharray': sr.dashed ? '6 4' : '', 'stroke-linejoin': 'round' }));
      if (!sr.dashed) sr.vals.forEach(function (v, i) { var p = pt(i, v); g.appendChild(s('circle', { cx: p[0], cy: p[1], r: '3.5', fill: sr.color })); });
      svg.appendChild(g);
    });
    return svg;
  }
  function correctedVals(vals, finalScore, baseScore) {
    // 보정 = 최종 점수(가중치·소표본 보정·케미 반영) ÷ 기본 BEST11 점수 비율을 각 축에 곱한 모양 (100 이 상한)
    var f = baseScore > 0 ? finalScore / baseScore : 1;
    return vals.map(function (v) { return Math.min(100, v * f); });
  }

  function openCompare(aId) {
    if (aId == null || !last) return;
    var slot = ids.indexOf(aId);
    var A = last.players.filter(function (x) { return x.id === aId; })[0];
    if (!A || slot < 0) { alert('이 선수는 현재 내 BEST11에 없어 비교할 수 없습니다.'); return; }
    var box = el('div', { class: 'b11-cmp' }, [el('p', { class: 'lab-muted', text: '불러오는 중…' })]);
    openModal(A.name + ' VS 비교', box, true);
    var b = params(); b.out_id = aId;
    post(URLS.candidates, b).then(function (r) {
      if (!r.candidates.length) { clear(box).appendChild(el('p', { text: '같은 포지션에 비교할 선수가 없습니다.' })); return; }
      var cmap = {}; r.candidates.forEach(function (c) { cmap[c.id] = c; });
      var cur = r.candidates[0].id, showFix = true;
      var sel = el('select', { 'aria-label': '비교할 선수' }, r.candidates.map(function (c) {
        return el('option', { value: c.id, text: c.name + ' (' + c.team + ') · ' + c.ability + '점 ' + sign(c.chem_bonus) + (c.recommended ? ' ★추천' : '') });
      }));
      var chk = el('input', { type: 'checkbox', id: 'b11Fix', checked: '' });
      var out = el('div', { class: 'b11-cmp-out' });
      var head = el('div', { class: 'b11-cmp-head' }, [
        el('label', {}, ['비교할 선수 ', sel]),
        el('label', { class: 'b11-fix', title: '케미·가중치·소표본 보정을 반영한 최종 점수 비율로 그래프를 키우거나 줄인 모양을 점선으로 겹칩니다' }, [chk, ' 보정 반영 (점선)'])]);
      clear(box); box.appendChild(head); box.appendChild(out);
      function draw() {
        var B = cmap[cur];
        clear(out).appendChild(el('p', { class: 'lab-muted', text: '불러오는 중…' }));
        Promise.all([getInfo(A.id), getInfo(B.id)]).then(function (res) {
          var ia = res[0], ib = res[1], labels = ia.radar_labels;
          var va = ia.radar_scores, vb = ib.radar_scores;
          var ba = ia.best11.score, bb = ib.best11.score;
          var series = [{ color: COL.a, vals: va }, { color: COL.b, vals: vb }];
          if (showFix) { series.push({ color: COL.a, vals: correctedVals(va, A.final, ba), dashed: true }); series.push({ color: COL.b, vals: correctedVals(vb, B.final, bb), dashed: true }); }
          function pcard(p, color, fin, chem, ab) {
            return el('div', { class: 'b11-pc', style: 'border-color:' + color }, [
              el('b', { style: 'color:' + color, text: p.name }), el('span', { class: 'lab-muted', text: ' ' + p.team + ' · ' + p.position }),
              el('div', {}, ['BEST11 ' + ab + '점 ', el('span', { class: 'b11-cn ' + (chem > 0 ? 'pos' : chem < 0 ? 'neg' : 'zero'), text: sign(chem) }), ' → 최종 ', el('b', { text: fin + '점' })])]);
          }
          var tb = el('table', { class: 'b11-cmp-table' }, [el('tr', {}, [el('th', { text: '항목' }), el('th', { text: A.name, style: 'color:' + COL.a }), el('th', { text: B.name, style: 'color:' + COL.b })])]);
          labels.forEach(function (lb, i) {
            tb.appendChild(el('tr', {}, [el('td', { text: lb }),
              el('td', { text: String(num1(va[i])) + (showFix ? ' → ' + num1(correctedVals(va, A.final, ba)[i]) : ''), class: va[i] >= vb[i] ? 'win' : '' }),
              el('td', { text: String(num1(vb[i])) + (showFix ? ' → ' + num1(correctedVals(vb, B.final, bb)[i]) : ''), class: vb[i] >= va[i] ? 'win' : '' })]));
          });
          clear(out);
          out.appendChild(el('div', { class: 'b11-cmp-grid' }, [
            el('div', {}, [radarSvg(labels, series),
              el('div', { class: 'b11-legend' }, [el('span', { class: 'sw', style: 'background:' + COL.a }), A.name, el('span', { class: 'sw', style: 'background:' + COL.b }), B.name,
                showFix ? el('span', { class: 'lab-muted', text: ' · 점선 = 보정 반영' }) : null])]),
            el('div', {}, [pcard(A, COL.a, A.final, A.chem_bonus, A.ability), pcard(B, COL.b, B.final, B.chem_bonus, B.ability), tb,
              el('p', { class: 'lab-muted', text: '실선 = 기록 그대로의 육각형. 점선 = 최종 점수 ÷ 기본 점수 비율을 곱한 보정 모양입니다. ' +
                (B.name + '로 바꾸면 라인업 총점이 ') + sign(B.delta) + '점 달라집니다. (케미 변화 포함)' }),
              vsSummary(A, B, labels, va, vb),
              el('button', { type: 'button', text: B.name + '(으)로 교체', onclick: function () { closeModal(); var pm = document.getElementById('playerModal'); if (pm) pm.style.display = 'none'; choose(slot, B.id); } })])]));
        }).catch(function (e) { clear(out).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
      }
      sel.addEventListener('change', function () { cur = Number(sel.value); draw(); });
      chk.addEventListener('change', function () { showFix = chk.checked; draw(); });
      draw();
    }).catch(function (e) { clear(box).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }

  /* ---------- 시작 ---------- */
  buildTools();
  var saved = readJSON(KEY, {})[storeKey()];
  function startAuto() {
    // 기본 설정이면 화면이 원래 보여 준 선수 그대로, 설정을 바꿔 둔 상태면 그 가중치로 다시 선발
    run(function () { return autoPick(false); });
  }
  function startSaved() {
    var keep = ids; ids = saved.map(Number);
    return post(URLS.evaluate, params()).then(function (r) {
      var okPos = r.players.every(function (p, i) { return p.position === cards[i].querySelector('.team-name span').textContent.split('·').pop().trim(); });
      if (!okPos) throw new Error('saved lineup mismatch');
      render(r);
    }).catch(function () { ids = keep; var o = readJSON(KEY, {}); delete o[storeKey()]; writeJSON(KEY, o); return autoPick(false); });
  }
  function begin() {
    if (Array.isArray(saved) && saved.length === 11) {
      // 직접 고른 라인업이 있으면 '자동 선발' 기준(autoIds)은 현재 설정으로 다시 구해 둔다
      run(function () {
        var b = params(); delete b.lineup;
        var base = post(URLS.lineup, b).then(function (r) { return r.lineup; });
        return base.then(function (a) { autoIds = a.slice(); return startSaved(); });
      });
    } else startAuto();
  }
  if (URLS.init) {
    post(URLS.init, {}).then(function (r) { INIT = r; fillTools(); begin(); })
      .catch(function (e) { bar.textContent = '가중치 도구를 불러오지 못했습니다: ' + e.message; });
  } else { run(evaluate); }
})();

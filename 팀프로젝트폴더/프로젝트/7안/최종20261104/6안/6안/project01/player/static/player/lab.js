/* 감독 연구실: 서버(JSON API)가 계산한 결과를 보여 주고, 선수 교체·감독 모드 진행을 관리한다. */
(function () {
  'use strict';
  var root = document.getElementById('lab');
  if (!root) return;
  var URLS = JSON.parse(root.getAttribute('data-urls'));
  var $ = function (id) { return document.getElementById(id); };
  var POS_ORDER = ['FW', 'MF', 'DF', 'GK'];
  var POS_LABEL = { FW: '공격수', MF: '미드필더', DF: '수비수', GK: '골키퍼' };
  var CAT = { ok: 'lab-badge info' };
  var S = { last: null, tab: 'irr' };

  /* ---------- 작은 도구 ---------- */
  function el(tag, attrs, kids) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') e.textContent = attrs[k];
      else if (k === 'class') e.className = attrs[k];
      else if (k.indexOf('on') === 0) e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    });
    (kids || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return e;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function csrf() { var i = root.querySelector('input[name=csrfmiddlewaretoken]'); return i ? i.value : ''; }
  function post(url, body) {
    return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify(body) })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok || j.error) throw new Error(j.error || '요청 실패'); return j; }); });
  }
  function msg(text, isErr) { var m = $('labMsg'); m.textContent = text || ''; m.className = 'lab-msg' + (isErr ? ' err' : ''); }
  function store(k, v) { try { localStorage.setItem('lab.' + k, JSON.stringify(v)); } catch (e) { /* 저장 불가여도 동작 */ } }
  function load(k, d) { try { var v = localStorage.getItem('lab.' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function badge(t) { var soft = (t === '신중 플레이' || t === '약간 피곤' || t === '경고 주의' || t === '출전 적음'); return el('span', { class: 'lab-badge' + (soft ? ' soft' : ''), text: t }); }

  /* ---------- 결과 표시 (계산은 best11_edit.js 가 한다. 여기서는 받은 결과를 보여 주기만 한다) ---------- */
  function render() {
    var r = S.last; if (!r) return;
    if (r.partial) {      // 나만의 BEST11을 채우는 중: 분석은 11명이 필요
      clear($('labSummary')).appendChild(el('span', { class: 'lab-muted', text: '라인업 11명을 모두 채우면 분석이 나옵니다. (지금 ' + r.players.length + '/11명)' }));
      clear($('labRecs')); clear($('labTab'));
      return;
    }
    var sum = clear($('labSummary'));
    sum.appendChild(el('span', { text: '라인업 총점 ' + r.total }));
    sum.appendChild(el('span', { text: '팀 케미 평균 +' + r.chem_team }));
    var recs = clear($('labRecs'));
    if (!r.recommend.length) recs.appendChild(el('span', { class: 'lab-muted', text: '추천할 케미 선수가 없습니다.' }));
    r.recommend.forEach(function (x) {
      recs.appendChild(el('div', { class: 'lab-rec' }, [
        el('span', { text: x.name + ' (' + x.position + ') — ' + x.for_name + '와(과) 케미 효과가 있습니다. 같이 쓰기를 추천합니다. [' + x.reasons.join(' · ') + ']' + (x.low_minutes ? ' ※출전 적음' : '') })
      ]));
    });
    renderTab();
  }

  /* ---------- 탭 ---------- */
  function renderTab() {
    var r = S.last, t = clear($('labTab'));
    if (r && r.partial && S.tab !== 'quality') return;
    Array.prototype.forEach.call($('labTabs').children, function (b) { b.className = b.getAttribute('data-tab') === S.tab ? 'on' : ''; });
    if (S.tab === 'irr') return tabIrr(r, t);
    if (S.tab === 'quality') return tabQuality(t);
    return tabReport(r, t);
  }
  function tabIrr(r, t) {
    var rows = r.irreplaceability.slice().sort(function (a, b) { return b.drop - a.drop; });
    var tb = el('table', {}, [el('tr', {}, ['선수', '지수(0~100)', '평가', '빠지면 총점 하락', '대체 1순위'].map(function (h) { return el('th', { text: h }); }))]);
    rows.forEach(function (x) {
      tb.appendChild(el('tr', {}, [el('td', { text: x.name }), el('td', {}, [el('span', { class: 'lab-bar', style: 'width:' + Math.max(2, x.index100) + 'px' }), ' ' + x.index100]),
        el('td', { text: x.label }), el('td', { text: '-' + x.drop }), el('td', { text: x.replacement || '-' })]));
    });
    t.appendChild(tb);
    t.appendChild(el('p', { class: 'lab-muted', text: '그 선수를 같은 포지션의 최선 대체 선수로 바꿨을 때 줄어드는 라인업 총점(케미 포함)입니다. 구단을 고르면 그 구단 선수 중에서 대체합니다.' }));
  }
  var qualityCache = null;
  function tabQuality(t) {
    t.appendChild(el('p', { class: 'lab-muted', text: '불러오는 중…' }));
    var show = function (q) {
      clear(t);
      var s = q.summary;
      t.appendChild(el('p', { text: '선수 ' + s.players + '명 점검 — 오류 ' + s.error + '건 · 의심 ' + s.warn + '건 · 참고 ' + s.info + '건' }));
      var names = { error: '오류', warn: '의심', info: '참고' };
      var tb = el('table', {}, [el('tr', {}, ['구분', '내용', '건수', '예시'].map(function (h) { return el('th', { text: h }); }))]);
      q.issues.forEach(function (b) {
        tb.appendChild(el('tr', {}, [el('td', { text: names[b.severity] }), el('td', { text: b.title }), el('td', { text: b.count }),
          el('td', { text: b.examples.slice(0, 3).map(function (e) { return e.name + (e.team ? '(' + e.team + ')' : '') + (e.detail ? ' ' + e.detail : ''); }).join(' · ') })]));
      });
      t.appendChild(tb);
      t.appendChild(el('p', { class: 'lab-muted', text: '값을 고치지 않고 찾아서 알려 주기만 합니다. 관리자 제외선수와 테스트 선수도 점검 대상에 포함됩니다.' }));
    };
    if (qualityCache) return show(qualityCache);
    post(URLS.quality, {}).then(function (q) { qualityCache = q; if (S.tab === 'quality') show(q); })
      .catch(function (e) { clear(t).appendChild(el('p', { class: 'lab-msg err', text: e.message })); });
  }
  function tabReport(r, t) {
    var R = r.report, ul = el('ul', {});
    R.notes.forEach(function (n) { ul.appendChild(el('li', { text: n })); });
    t.appendChild(ul);
    var tb = el('table', {}, [el('tr', {}, [el('th', { text: '라인' }), el('th', { text: '리그 내 수준 (백분위)' })])]);
    R.lines.forEach(function (l) { tb.appendChild(el('tr', {}, [el('td', { text: l.label + ' ' + l.count + '명' }), el('td', {}, [el('span', { class: 'lab-bar', style: 'width:' + l.percentile * 2 + 'px' }), ' ' + l.percentile])])); });
    t.appendChild(tb);
    var f = R.facts;
    t.appendChild(el('p', { class: 'lab-muted', text: '평균 나이 ' + (f.avg_age != null ? f.avg_age : '-') + ' · 팀 케미 +' + f.chemistry_team_score }));
  }

  /* ---------- 연결 ---------- */
  document.addEventListener('b11:result', function (e) { S.last = e.detail.result; render(); });
  $('labTabs').onclick = function (e) { var k = e.target.getAttribute && e.target.getAttribute('data-tab'); if (k) { S.tab = k; renderTab(); } };
})();

/* 모의 경기 피로 누적 (연속 출전)
 * - lineup_simulation.js 는 건드리지 않고 화면의 선수 선택칸만 읽고/바꾼다.
 * - 경기를 '치른 것으로 기록'하면 그 선수들의 피로가 쌓이고, 다음 경기 날짜에 맞춰 회복된다.
 * - 기록은 이 브라우저(localStorage)에만 저장된다. 베스트11 연구실도 같은 기록을 읽어 피로를 보여 준다.
 * - 피로·회복 숫자는 사이트의 게임 규칙이며 실제 선수 상태가 아니다. (player/lab/management.py 맨 위 참고)
 */
(() => {
    'use strict';

    const script = document.currentScript;
    const url = script && script.dataset.conditionUrl;
    const scheduleUrl = script && script.dataset.scheduleUrl;
    const anchor = document.getElementById('result-empty');
    const form = document.getElementById('simulation-form');
    if (!url || !anchor || !form) return;

    // 육각형 비교 그래프(player_comparison.js 가 그린 SVG)가 가운데에서부터 퍼지게 하는 스타일. 그래프 코드는 바꾸지 않는다.
    const grow = document.createElement('style');
    grow.textContent = `
        @keyframes recordRadarGrow {
            from { transform: scale(0); opacity: 0.2; }
            to { transform: scale(1); opacity: 1; }
        }
        .record-radar polygon[stroke-width="2"],
        .record-radar line[stroke-width="2"],
        .record-radar circle {
            transform-origin: 210px 170px;
            animation: recordRadarGrow 0.8s ease-out both;
        }
        @media (prefers-reduced-motion: reduce) {
            .record-radar polygon[stroke-width="2"],
            .record-radar line[stroke-width="2"],
            .record-radar circle { animation: none; }
        }`;
    document.head.append(grow);

    const KEY = 'kleague-mock-fatigue-log-v1';
    const byId = id => document.getElementById(id);

    function readLog() {
        try {
            const v = JSON.parse(localStorage.getItem(KEY) || '[]');
            return Array.isArray(v) ? v : [];
        } catch (e) {
            return [];
        }
    }

    function writeLog(log) {
        try {
            localStorage.setItem(KEY, JSON.stringify(log));
            return true;
        } catch (e) {
            return false;
        }
    }

    function el(tag, text, cls) {
        const e = document.createElement(tag);
        if (text != null) e.textContent = text;
        if (cls) e.className = cls;
        return e;
    }

    const box = el('section', null, 'mock-fatigue');
    box.setAttribute('aria-label', '피로 누적');
    box.style.cssText = 'border:1px solid #d9dde3;border-radius:10px;padding:10px 12px;margin:10px 0;font-size:14px';

    const title = el('b', '🔋 피로 누적 (연속 출전)');
    const info = el('p', null, 'muted');
    info.style.margin = '6px 0';
    const btns = el('div');
    btns.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;margin:6px 0';
    const check = el('button', '피로 확인 · 컨디션 자동 반영', 'secondary');
    const record = el('button', '이 경기를 치른 것으로 기록', 'secondary');
    const reset = el('button', '기록 초기화', 'secondary');
    const sideSel = el('select');
    sideSel.setAttribute('aria-label', '일정을 볼 팀');
    [['home', '홈팀'], ['away', '원정팀']].forEach(([v, t]) => { const o = el('option', t); o.value = v; sideSel.append(o); });
    const plan = el('button', '남은 일정 · 로테이션 보기', 'secondary');
    [check, record, reset, sideSel, plan].forEach(b => { if (b.tagName === 'BUTTON') b.type = 'button'; btns.append(b); });
    const out = el('div');
    const msg = el('p', null, 'muted');
    msg.setAttribute('role', 'status');
    const list = el('ul');
    list.style.cssText = 'margin:6px 0 0;padding-left:18px';
    const note = el('p', '피로·회복 수치는 게임 규칙이며 실제 선수 상태가 아닙니다. 한 경기 풀타임 30, 연속 출전이면 35, 하프타임 회복 3, 하루 회복 4(30세 이상 3.5). 피로 71 이상이면 컨디션을 "안 좋음"으로 바꿉니다.', 'muted');
    note.style.cssText = 'font-size:12px;margin:6px 0 0';
    box.append(title, info, btns, msg, list, out, note);
    anchor.parentNode.insertBefore(box, anchor);

    function refreshInfo() {
        const n = readLog().length;
        info.textContent = n
            ? `기록된 모의 경기 ${n}건. 다음 경기는 기록한 날짜보다 뒤 날짜로 정해야 피로가 반영됩니다.`
            : '기록된 모의 경기가 없습니다. 경기를 치른 것으로 기록하면 그 선수들의 피로가 쌓입니다.';
    }

    function rows() {
        const out = [];
        for (const side of ['home', 'away']) {
            document.querySelectorAll(`#${side}-lineup .player-row`).forEach(row => {
                const sel = row.querySelector('.player-select');
                const cond = row.querySelector('.condition-select');
                if (sel && sel.value) out.push({side, row, id: Number(sel.value), cond, name: sel.selectedOptions[0] ? sel.selectedOptions[0].textContent : sel.value});
            });
        }
        return out;
    }

    function csrf() {
        const i = form.querySelector('[name=csrfmiddlewaretoken]');
        return i ? i.value : '';
    }

    async function ask(ids, date) {
        const r = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
            body: JSON.stringify({mock_log: readLog(), date, ids}),
        });
        const j = await r.json();
        if (!r.ok || j.error) throw new Error(j.error || '요청 실패');
        return j;
    }

    check.addEventListener('click', async () => {
        const date = byId('match-date').value;
        const rs = rows();
        if (!date || rs.length < 11) { msg.textContent = '경기 기준일과 선수 명단을 먼저 확인하세요.'; return; }
        msg.textContent = '확인 중…';
        try {
            const data = await ask(rs.map(r => r.id), date);
            list.replaceChildren();
            let changed = 0;
            rs.forEach(r => {
                const p = data.players[r.id];
                if (!p) return;
                if (p.suggest_bad && r.cond && r.cond.value !== 'bad') {
                    r.cond.value = 'bad';
                    r.cond.dispatchEvent(new Event('change', {bubbles: true}));
                    changed++;
                }
                if (p.label !== '정상' || p.badges.length) {
                    list.append(el('li', `${r.side === 'home' ? '홈' : '원정'} ${r.name} — 피로 ${p.fatigue} (${p.label}${p.streak ? `, ${p.streak}경기 연속 출전` : ''})${p.badges.length ? ' · ' + p.badges.join(', ') : ''}`));
                }
            });
            if (!list.children.length) list.append(el('li', '피로가 쌓인 선수가 없습니다.'));
            msg.textContent = `${date} 기준 확인 완료. 컨디션을 "안 좋음"으로 바꾼 선수 ${changed}명.`;
        } catch (e) {
            msg.textContent = e.message;
        }
    });

    record.addEventListener('click', () => {
        const date = byId('match-date').value;
        const ids = rows().map(r => r.id);
        if (!date || ids.length < 11) { msg.textContent = '경기 기준일과 선수 명단을 먼저 확인하세요.'; return; }
        const key = ids.slice().sort((a, b) => a - b).join(',');
        const log = readLog().filter(e => !(e.date === date && Array.isArray(e.ids) && e.ids.slice().sort((a, b) => a - b).join(',') === key));
        log.push({date, ids});
        log.sort((a, b) => a.date.localeCompare(b.date));
        const ok = writeLog(log.slice(-60));
        refreshInfo();
        msg.textContent = ok
            ? `${date} 경기를 기록했습니다. 날짜를 뒤로 옮긴 뒤 "피로 확인"을 누르면 쌓인 피로가 반영됩니다.`
            : '이 브라우저에서는 기록을 저장할 수 없습니다.';
    });

    reset.addEventListener('click', () => {
        writeLog([]);
        list.replaceChildren();
        refreshInfo();
        msg.textContent = '기록을 모두 지웠습니다.';
    });

    function table(headers, rows) {
        const t = el('table');
        t.style.cssText = 'width:100%;border-collapse:collapse;font-size:13px;margin:6px 0';
        const hr = el('tr');
        headers.forEach(h => { const th = el('th', h); th.style.cssText = 'text-align:left;border-bottom:1px solid #d9dde3;padding:4px'; hr.append(th); });
        t.append(hr);
        rows.forEach(r => {
            const tr = el('tr');
            r.forEach(c => { const td = el('td', String(c)); td.style.cssText = 'border-bottom:1px solid #eee;padding:4px'; tr.append(td); });
            t.append(tr);
        });
        return t;
    }

    plan.addEventListener('click', async () => {
        if (!scheduleUrl) { msg.textContent = '일정 기능을 사용할 수 없습니다.'; return; }
        const date = byId('match-date').value;
        const ids = rows().filter(r => r.side === sideSel.value).map(r => r.id);
        if (!date || ids.length !== 11) { msg.textContent = '경기 기준일과 선수 명단을 먼저 확인하세요.'; return; }
        msg.textContent = '계산 중…';
        out.replaceChildren();
        try {
            const r = await fetch(scheduleUrl, {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
                body: JSON.stringify({mock_log: readLog(), date, ids}),
            });
            const j = await r.json();
            if (!r.ok || j.error) throw new Error(j.error || '요청 실패');
            msg.textContent = `${j.team} 기준 (${j.date}의 피로 상태에서 출발)${j.mixed ? ' · 여러 구단 선수가 섞여 있어 가장 많은 구단 기준입니다' : ''}`;
            const o = j.outlook;
            out.append(el('b', '다음 상대 예상 (현재 라인업 보정은 실험 기능)'));
            if (!o.available) {
                out.append(el('p', o.reason, 'muted'));
            } else {
                out.append(table(['라운드', '날짜', '상대', '예상 득점', '승/무/패 (%)'], o.rows.map(x => x.available
                    ? [x.round, x.date, `${x.opponent} (${x.home ? '홈' : '원정'})`, `${x.my_goals.toFixed(1)} : ${x.opp_goals.toFixed(1)}`, `${x.win} / ${x.draw} / ${x.loss}`]
                    : [x.round, x.date, `${x.opponent} (${x.home ? '홈' : '원정'})`, '예측 불가', x.reason])));
                out.append(el('p', `예측 모델 학습 기준일 ${o.trained_through}. ${o.note}`, 'muted'));
            }
            out.append(el('b', '로테이션 계획'));
            const R = j.rotation;
            if (!R) {
                out.append(el('p', '남은 정규 일정 정보가 없습니다.', 'muted'));
            } else {
                out.append(el('p', `같은 선발을 계속 쓰면 최고 피로 ${R.peak_without_rotation} → 계획대로 로테이션하면 ${R.peak_with_rotation} (게임 규칙 기준 추정)`));
                out.append(table(['라운드', '교체 계획', '평균 피로', '최고 피로'], R.rounds.map(x =>
                    [x.round, x.swaps.length ? x.swaps.map(s => `${s.out_name} → ${s.in_name}`).join(', ') : '교체 없음', x.avg_fatigue, x.max_fatigue])));
                out.append(el('p', '피로 50을 넘을 선수를 같은 포지션 후보로 바꾸는 단순 규칙입니다. 한 라운드 최대 3명.', 'muted'));
            }
        } catch (e) {
            msg.textContent = e.message;
        }
    });

    refreshInfo();
})();

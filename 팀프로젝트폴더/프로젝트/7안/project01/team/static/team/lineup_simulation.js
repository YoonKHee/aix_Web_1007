(() => {
    'use strict';

    const boot = document.getElementById('simulation-bootstrap');
    if (!boot) return;

    const config = JSON.parse(boot.textContent);
    const form = document.getElementById('simulation-form');
    const byId = id => document.getElementById(id);

    const sideState = {
        home: {generation: 0},
        away: {generation: 0},
    };

    const storageKey = 'kleague-lineup-presets-v1';

    let pending = 0;
    let revision = 0;
    let comparing = false;
    let editorSide = null;
    let autoTimer;

    function scheduleCalculation() {
        clearTimeout(autoTimer);

        autoTimer = setTimeout(() => {
            if (
                !pending &&
                !comparing &&
                sideState.home.data &&
                sideState.away.data
            ) {
                if (!form.checkValidity()) {
                    status(
                        '경기 기준일을 허용된 범위에서 선택하세요.',
                        true
                    );

                    byId('result-empty').textContent =
                        '경기 기준일을 확인하면 자동으로 다시 계산합니다.';

                    return;
                }

                form.requestSubmit();
            }
        }, 300);
    }

    function el(tag, text, className) {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        if (className) node.className = className;
        return node;
    }

    function option(select, value, text) {
        const node = el('option', text);
        node.value = value;
        select.append(node);
    }

    function status(message, error = false) {
        byId('status').textContent = message;
        byId('status').classList.toggle('error', error);
    }

    function busy() {
        byId('compare').disabled =
            pending > 0 ||
            comparing ||
            !sideState.home.data ||
            !sideState.away.data;
    }

    function changed() {
        revision++;

        byId('result').hidden = true;
        byId('result-details').hidden = true;
        byId('result-empty').hidden = false;

        byId('result-empty').textContent =
            '설정 변경을 반영하고 있습니다…';

        renderVisuals();
        status('변경 사항 반영 대기 중');
        scheduleCalculation();
    }

    async function request(url, options) {
        const response = await fetch(url, options);
        let data;

        try {
            data = await response.json();
        } catch (_) {
            throw new Error(
                '응답을 읽지 못했습니다. 서버 상태를 확인하세요.'
            );
        }

        if (!response.ok) {
            throw new Error(
                data.error || '요청을 처리하지 못했습니다.'
            );
        }

        return data;
    }

    // 후보 표시 전용 상태입니다.
    // 선수 구성과 예측 계산에는 영향을 주지 않습니다.
    const recordFilter = {
        includeMissing: false,

        status(player, role) {
            const axes = player.comparison?.[role]?.axes;

            const finite = value =>
                typeof value === 'number' &&
                Number.isFinite(value);

            const count = Array.isArray(axes)
                ? axes.filter(axis => finite(axis.raw)).length
                : 0;

            if (!Array.isArray(axes) || axes.length !== 6) {
                return {
                    hasData: false,
                    kind: 'none',
                    label: '비교 자료 미확인',
                    lowMinutes: false,
                };
            }

            if (!(player.minutes > 0) || count === 0) {
                return {
                    hasData: false,
                    kind: 'none',
                    label: '기록 없음',
                    lowMinutes: false,
                };
            }

            const referenceMissing = axes.some(
                axis => finite(axis.raw) && !finite(axis.score)
            );

            return {
                hasData: true,
                kind: count < 6 || referenceMissing
                    ? 'partial'
                    : 'full',
                label: count < 6
                    ? `일부 자료 없음 (${count}/6)`
                    : referenceMissing
                        ? '일부 비교 불가'
                        : '기록 있음',
                lowMinutes: player.minutes < 600,
            };
        },

        set(value) {
            this.includeMissing = Boolean(value);

            document.querySelectorAll(
                'input[data-missing-records]'
            ).forEach(input => {
                input.checked = this.includeMissing;
            });

            document.dispatchEvent(
                new CustomEvent('lineup:record-filter-change')
            );
        },

        control(id) {
            const label = el(
                'label',
                undefined,
                'record-filter-toggle'
            );

            const input = el('input');
            input.type = 'checkbox';
            input.id = id;
            input.dataset.missingRecords = 'true';
            input.checked = this.includeMissing;

            input.addEventListener(
                'change',
                () => this.set(input.checked)
            );

            label.append(
                input,
                el('span', '기록 없는 선수도 보기')
            );

            return label;
        },
    };

    window.lineupRecordFilter = recordFilter;

    document.addEventListener(
        'lineup:record-filter-change',
        () => renderVisuals()
    );

    const recordFilterStyle = el('style');

    recordFilterStyle.textContent = `
        .record-filter-toolbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
            margin: 0 0 16px;
            padding: 12px 14px;
            border: 1px solid #e5ebef;
            border-radius: 10px;
            background: #f8fafb;
        }

        .record-filter-toggle {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            margin: 0;
        }

        .record-filter-toggle input[type="checkbox"] {
            width: 16px;
            height: 16px;
            min-width: 16px;
            margin: 0;
            padding: 0;
            accent-color: #0b8268;
        }

        .record-filter-help {
            font-size: 10px;
            color: #82929e;
            margin: 0;
            line-height: 1.6;
        }

        .record-state {
            display: block;
            font-size: 9px;
            font-weight: 500;
            margin-top: 4px;
            line-height: 1.5;
            color: #3a876f;
        }

        .record-state.partial {
            color: #a17a39;
        }

        .record-state.none {
            color: #8796a2;
        }

        .record-candidates .record-filter-toggle {
            margin: 10px 0 4px;
        }

        .record-filter-count {
            font-size: 10px;
            color: #82929e;
            margin: 6px 0;
        }

        .record-filter-empty {
            font-size: 11px;
            color: #82929e;
            line-height: 1.8;
            padding: 10px;
        }
    `;

    document.head.append(recordFilterStyle);

    // 육각형 비교 화면 파일 불러오기
    const sourceScript = document.currentScript;

    if (sourceScript && sourceScript.src) {
        const comparisonScript = document.createElement('script');

        comparisonScript.src = new URL(
            'player_comparison.js',
            sourceScript.src
        ).href;

        comparisonScript.addEventListener('error', () => {
            status(
                '선수 비교 화면 파일을 불러오지 못했습니다. ' +
                '같은 폴더의 player_comparison.js 파일을 확인하세요.',
                true
            );
        });

        document.head.append(comparisonScript);
    }

    // 선수 사진 디자인
    const portraitStyle = document.createElement('style');

    portraitStyle.textContent = `
        .player-portrait {
            position: relative;
            display: grid;
            place-items: center;
            width: 54px;
            height: 54px;
            border: 3px solid #64a9ff;
            border-radius: 50%;
            background: #173e37;
            box-shadow: 0 4px 12px #0004;
            flex-shrink: 0;
        }

        .away-player .player-portrait {
            border-color: #ff9683;
        }

        .player-portrait img {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            object-position: center top;
            border-radius: 50%;
            background: #fff;
        }

        .portrait-number {
            position: absolute;
            right: -6px;
            bottom: -4px;
            min-width: 20px;
            height: 20px;
            padding: 0 3px;
            display: grid;
            place-items: center;
            border: 2px solid #154b3b;
            border-radius: 7px;
            background: #2975eb;
            color: white;
            font-size: 10px;
            font-weight: 800;
            z-index: 1;
        }

        .away-player .portrait-number {
            background: #ee6957;
        }

        .pitch-team[data-formation="4-2-3-1"] .pitch-player {
            width: 72px;
        }

        .pitch-team[data-formation="4-2-3-1"] .player-name {
            max-width: 72px;
        }

        .pitch-team[data-formation="4-2-3-1"] .player-rating {
            white-space: nowrap;
        }

        @media (max-width: 600px) {
            .pitch-team[data-formation="4-2-3-1"] .pitch-player {
                width: 58px;
                left: var(--mobile-lateral) !important;
            }

            .pitch-team[data-formation="4-2-3-1"] .player-name {
                max-width: 58px;
            }

            .player-portrait {
                width: 40px;
                height: 40px;
                border-width: 2px;
            }

            .portrait-number {
                min-width: 17px;
                height: 17px;
                font-size: 8px;
                right: -5px;
                bottom: -3px;
            }
        }
    `;

    document.head.append(portraitStyle);

    function playerPortrait(player) {
        const portrait = el(
            'span',
            undefined,
            'player-portrait'
        );

        const fallback = el(
            'span',
            String(player.number || '·'),
            'jersey'
        );

        portrait.append(fallback);

        if (player.photo) {
            const image = el('img');
            image.alt = `${player.name} 선수 사진`;
            image.hidden = true;
            image.decoding = 'async';

            image.addEventListener('load', () => {
                fallback.hidden = true;
                image.hidden = false;
            }, {once: true});

            image.addEventListener('error', () => {
                image.remove();
                fallback.hidden = false;
            }, {once: true});

            image.src = player.photo;
            portrait.append(image);
        }

        portrait.append(
            el(
                'span',
                String(player.number || '·'),
                'portrait-number'
            )
        );

        return portrait;
    }

    /* 화면에 보여 주는 선수 점수 = 종합 점수 (기존 역할 지수 + 추가 지표 점수) */
    function shownScore(p, role) {
        return p.total_scores && Number.isFinite(p.total_scores[role]) ? p.total_scores[role] : p.scores[role];
    }

    function scoreText(p, role) {
        if (!p.total_scores || !p.detail) return `선수 점수 ${p.scores[role].toFixed(1)}`;
        return `종합 ${shownScore(p, role).toFixed(1)} (기존 ${p.scores[role].toFixed(1)} · 추가 지표 ${p.detail.score.toFixed(1)})`;
    }

    function updatePlayer(side, row, role) {
        const p = sideState[side].data.roster.find(
            p => p.id === Number(
                row.querySelector('.player-select').value
            )
        );

        const meta = row.querySelector('.player-meta');
        meta.replaceChildren();

        if (!p) return;

        if (p.photo) {
            const image = el('img');
            image.src = p.photo;
            image.alt = p.name;

            image.addEventListener(
                'error',
                () => image.remove(),
                {once: true}
            );

            meta.append(image);
        }

        const note = p.notes[role] || '';

        meta.append(el(
            'span',
            `원 포지션 ${p.position} · ${scoreText(p, role)} · ${p.minutes}분${note ? ' · ' + note : ''}`
        ));
    }

    function renderLineup(side, saved) {
        const data = sideState[side].data;
        const players = saved || data.recommended.players;

        if (!Array.isArray(players) || players.length !== 11) {
            throw new Error(
                '저장된 선수 구성이 올바르지 않습니다.'
            );
        }

        const parent = byId(`${side}-lineup`);
        parent.replaceChildren();

        data.roles.forEach((role, index) => {
            const item = players[index];

            if (
                !item ||
                !['bad', 'normal', 'good'].includes(item.condition)
            ) {
                throw new Error(
                    '저장된 컨디션을 확인하세요.'
                );
            }

            const row = el('div', undefined, 'player-row');
            row.dataset.role = role;

            row.dataset.slotLabel = formationPositions(
                byId(`${side}-formation`).value
            )[index]?.label || role;

            row.append(el('span', role, 'role'));

            const select = el(
                'select',
                undefined,
                'player-select'
            );

            select.setAttribute(
                'aria-label',
                `${side === 'home' ? '홈' : '원정'} ${role} ${index + 1} 선수`
            );

            data.roster
                .filter(p => Object.hasOwn(p.scores, role))
                .forEach(p => option(
                    select,
                    p.id,
                    `${p.number} ${p.name} (${p.position})`
                ));

            select.value = String(item.id);

            if (!select.value) {
                throw new Error(
                    '저장된 선수가 현재 구단 명단에 없습니다.'
                );
            }

            const condition = el(
                'select',
                undefined,
                'condition-select'
            );

            condition.setAttribute(
                'aria-label',
                `${side === 'home' ? '홈' : '원정'} ${role} ${index + 1} 컨디션`
            );

            [
                ['bad', '안 좋음'],
                ['normal', '보통'],
                ['good', '좋음'],
            ].forEach(([key, text]) => {
                option(condition, key, text);
            });

            condition.value = item.condition;

            row.append(
                select,
                condition,
                el('div', undefined, 'player-meta')
            );

            parent.append(row);
            updatePlayer(side, row, role);

            select.addEventListener('change', () => {
                updatePlayer(side, row, role);
                changed();
            });

            condition.addEventListener('change', changed);
        });

        renderVisuals();
    }

    async function loadSide(side) {
        const state = sideState[side];
        const generation = ++state.generation;

        state.data = null;
        byId('player-dialog').close();

        byId(`${side}-lineup`).textContent =
            '선수 명단을 불러오는 중입니다…';

        changed();
        pending++;
        busy();

        try {
            const url = new URL(
                form.dataset.rosterUrl,
                location.origin
            );

            url.searchParams.set(
                'team',
                byId(`${side}-team`).value
            );

            url.searchParams.set(
                'formation',
                byId(`${side}-formation`).value
            );

            const data = await request(url);

            if (generation !== state.generation) return false;

            state.data = data;
            renderLineup(side);

            return true;
        } catch (error) {
            if (generation === state.generation) {
                state.data = null;

                byId(`${side}-lineup`).textContent =
                    error.message;

                status(error.message, true);
            }

            return false;
        } finally {
            pending--;
            busy();

            if (!pending) scheduleCalculation();
        }
    }

    function payload() {
        if (
            pending ||
            !sideState.home.data ||
            !sideState.away.data
        ) {
            throw new Error(
                '명단을 먼저 불러와주세요.'
            );
        }

        const result = {
            home_team: byId('home-team').value,
            away_team: byId('away-team').value,
            date: byId('match-date').value,
        };

        // BEST11 화면에서 넘어온 내 라인업 그대로(같은 구단·같은 11명)면 '내 BEST11'로 표시
        if (config.best11 && result.home_team === config.best11.team) {
            const now = rowsFor('home').map(row => Number(row.querySelector('.player-select').value)).sort((a, b) => a - b).join(',');
            const mine = [...config.best11.players].sort((a, b) => a - b).join(',');
            result.home_best11 = now === mine;
            if (result.home_best11 && config.best11.settings) {
                result.home_best11_settings = config.best11.settings;
            }
        }

        if (result.home_team === result.away_team) {
            throw new Error(
                '서로 다른 두 팀을 선택하세요.'
            );
        }

        for (const side of ['home', 'away']) {
            const players = rowsFor(side).map(row => ({
                id: Number(
                    row.querySelector('.player-select').value
                ),
                condition: row.querySelector(
                    '.condition-select'
                ).value,
            }));

            if (
                players.length !== 11 ||
                new Set(players.map(p => p.id)).size !== 11
            ) {
                throw new Error(
                    `${side === 'home' ? '홈' : '원정'}팀 선수가 중복되었거나 11명이 아닙니다.`
                );
            }

            result[side] = {
                formation: byId(`${side}-formation`).value,
                players,
            };
        }

        return result;
    }

    function signed(n) {
        return `${n > 0 ? '+' : ''}${n.toFixed(1)}`;
    }

    function table(headers, rows) {
        const wrap = el('div', undefined, 'table-wrap');
        const node = el('table');
        const head = el('thead');
        const hr = el('tr');

        headers.forEach(h => hr.append(el('th', h)));
        head.append(hr);

        const body = el('tbody');

        rows.forEach(values => {
            const row = el('tr');

            values.forEach(v => {
                row.append(el('td', String(v)));
            });

            body.append(row);
        });

        node.append(head, body);
        wrap.append(node);

        return wrap;
    }

    /* 승부예측 비율: 팀 기록 (100-w)% + 선수 능력치 w% */
    function playerBlock(data) {
        const x = data.player_part;
        const box = el('section', undefined, 'extra-box');
        box.append(el('h3', `승부예측 구성: 팀 기록 ${100 - x.weight}% + 선수 능력치 ${x.weight}%`));
        box.append(el(
            'p',
            `팀 기록(최근 5경기·홈/원정·시즌 성적)으로 낸 확률 ${100 - x.weight}%와, 양 팀 라인업의 선수 점수(BEST11과 같은 통합 점수)만으로 낸 확률 ${x.weight}%를 합쳤습니다. 선수 능력치 확률은 리그 평균 득점에서 출발해 공격 지수 ÷ 상대 수비 지수(12개 구단 기본 선발 평균 = 기준)로 예상 득점을 정합니다.`,
            'muted'
        ));
        box.append(table(
            ['', '공격 지수', '수비 지수', '예상 득점 (리그 평균 → 선수 능력치)'],
            [
                [data.home_name, x.home.attack.toFixed(1), x.home.defense.toFixed(1), `${x.base_goals.home.toFixed(2)} → ${x.goals.home_goals.toFixed(2)}`],
                [data.away_name, x.away.attack.toFixed(1), x.away.defense.toFixed(1), `${x.base_goals.away.toFixed(2)} → ${x.goals.away_goals.toFixed(2)}`],
                ['기준 (기본 선발 평균)', x.reference.attack.toFixed(1), x.reference.defense.toFixed(1), ''],
            ]
        ));
        const t = x.team_probabilities, q = x.probabilities;
        box.append(el('p', `팀 기록만: ${data.home_name} 승 ${t.H}% · 무 ${t.D}% · ${data.away_name} 승 ${t.A}%   |   선수 능력치만: ${data.home_name} 승 ${q.H}% · 무 ${q.D}% · ${data.away_name} 승 ${q.A}%`));
        if (data.best11_recent) {
            const r = data.best11_recent;
            const recent = el('div', undefined, 'best11-recent');
            recent.append(el('b', `🏆 내 BEST11 (${r.team}) 최근 5경기 `), el('span', '가상', 'virtual-badge'));
            const chips = el('div', undefined, 'recent-chips');
            r.games.forEach(g => {
                chips.append(el('span', `${g.result} ${g.score} vs ${g.opponent}`, `recent-chip r-${g.result}`));
            });
            recent.append(chips, el(
                'p',
                `경기당 ${r.points_per_game}점 → 예상 득점 ×${r.form_factor} (선수 능력치 ${x.weight}% 안에서만 반영). ${r.note}`,
                'muted'
            ));
            box.append(recent);
        }
        box.append(el('p', `⚠ 선수 점수의 일부 컬럼은 가상 데이터입니다 (골키퍼 선방·실점·무실점·공중볼 처리, 활동량·스프린트). ${x.virtual_note}`, 'virtual-note'));
        return box;
    }

    /* 가산점(케미) 포함 결과 — 위의 기존 결과(능력치만)와 따로 보여 준다 */
    function bonusBlock(data) {
        const r = data.bonus_result;
        let main = {};
        if (data.views) main = {...data.views.weighted.probabilities};
        else data.probabilities.forEach(p => { main[p.code] = p.after; });
        const box = el('section', undefined, 'weighted-box bonus-box');
        box.append(el('h3', '➕ 가산점(케미) 포함 결과'));
        box.append(el('p', "'가중치 포함' 결과의 선수 점수에 케미 가산점을 더한 결과입니다 (BEST11 화면과 같은 케미 계산, 기본 가중치 기준).", 'muted'));
        const row = el('div', undefined, 'weighted-row');
        [['H', `${data.home_name} 승`], ['D', '무승부'], ['A', `${data.away_name} 승`]].forEach(([k, label]) => {
            const v = r.probabilities[k];
            const d = Math.round((v - main[k]) * 10) / 10;
            const card = el('div', undefined, 'weighted-card');
            card.append(el('span', label), el('strong', `${v.toFixed(1)}%`), el('small', `가중치 포함 결과 대비 ${signed(d)}%p`));
            row.append(card);
        });
        box.append(row);
        box.append(el(
            'p',
            `팀 케미 평균: ${data.home_name} ${signed(r.team_chem.home)} · ${data.away_name} ${signed(r.team_chem.away)}  |  공격/수비 지수 (가산점 포함): ${data.home_name} ${r.home.attack.toFixed(1)}/${r.home.defense.toFixed(1)} · ${data.away_name} ${r.away.attack.toFixed(1)}/${r.away.defense.toFixed(1)} (기준 ${r.reference.attack.toFixed(1)}/${r.reference.defense.toFixed(1)})`,
            'muted'
        ));
        const list = el('details', undefined, 'extra-players');
        list.append(el('summary', '선수별 케미 가산점 보기'));
        for (const side of ['home', 'away']) {
            const name = side === 'home' ? data.home_name : data.away_name;
            list.append(el('p', `${name}: ` + r.players[side].map(p => `${p.name} ${signed(p.bonus)}`).join(' · ')));
        }
        list.append(el('p', '케미 가산점은 패스 주고받기 데이터가 없어 역할 보완·인접 라인 연계·같은 구단으로 추정한 값입니다 (선수당 -2 ~ +5).', 'muted'));
        box.append(list);
        return box;
    }

    /* 내 BEST11 가중치(BEST11 화면의 감독 연구실 설정)로 평가한 확률 — 기본 확률과 나란히 */
    function weightedBlock(data) {
        const m = data.best11_weighted;
        const main = {};
        data.probabilities.forEach(p => { main[p.code] = p.after; });
        const box = el('section', undefined, 'weighted-box');
        box.append(el('h3', '🏆 내 BEST11 가중치 반영 확률'));
        const row = el('div', undefined, 'weighted-row');
        [['H', `${data.home_name} 승`], ['D', '무승부'], ['A', `${data.away_name} 승`]].forEach(([k, label]) => {
            const v = m.probabilities[k];
            const d = Math.round((v - main[k]) * 10) / 10;
            const card = el('div', undefined, 'weighted-card');
            card.append(el('span', label), el('strong', `${v.toFixed(1)}%`), el('small', `위 결과 대비 ${signed(d)}%p`));
            row.append(card);
        });
        box.append(row);
        const summary = config.best11 && config.best11.settings_summary ? config.best11.settings_summary : '';
        box.append(el(
            'p',
            `BEST11 화면에서 정한 내 가중치(${summary || '기본'})로 ${data.home_name} 선수 점수를 다시 계산해 선수 능력치(${data.player_part.weight}%) 부분에 넣었습니다. ${data.home_name} 공격 지수 ${m.home.attack.toFixed(1)} · 수비 지수 ${m.home.defense.toFixed(1)} (기본 점수 대비 공격 ${signed(m.change)}). 팀 기록 부분과 원정팀은 같습니다.`,
            'muted'
        ));
        return box;
    }

    /* 결과 보기 선택: 기록만 / 가중치 포함 */
    let resultMode = 'weighted';
    let lastResult = null;
    try { resultMode = localStorage.getItem('kleague-sim-result-mode') || 'weighted'; } catch (e) { /* 저장 불가여도 동작 */ }

    function viewData(data) {
        // 고른 결과를 카드에 크게, 다른 결과를 비교선(이전 막대)으로 보여 준다
        if (!data.views) return {data, compare: '기본'};
        const mode = data.views[resultMode] ? resultMode : 'weighted';
        const other = mode === 'record' ? 'weighted' : 'record';
        const now = data.views[mode].probabilities, cmp = data.views[other].probabilities;
        const probabilities = data.probabilities.map(p => ({
            ...p, before: cmp[p.code], after: now[p.code], change: Math.round((now[p.code] - cmp[p.code]) * 10) / 10,
        }));
        return {data: {...data, probabilities}, compare: data.views[other].label, mode};
    }

    function modeBar(data, mode) {
        const bar = el('div', undefined, 'result-mode');
        ['record', 'weighted'].forEach(key => {
            const v = data.views[key];
            const b = el('button', `${v.label}`, key === mode ? 'on' : '');
            b.type = 'button';
            b.title = v.detail;
            b.addEventListener('click', () => {
                resultMode = key;
                try { localStorage.setItem('kleague-sim-result-mode', key); } catch (e) { /* 무시 */ }
                showResult(lastResult);
            });
            bar.append(b);
        });
        bar.append(el('span', data.views[mode].detail, 'muted'));
        return bar;
    }

    function showResult(raw) {
        lastResult = raw;
        const picked = viewData(raw);
        const data = picked.data;
        const root = byId('result');
        const details = byId('result-details');

        details.replaceChildren(
            el('h2', '변화의 근거')
        );

        details.hidden = false;
        root.replaceChildren();

        byId('result-title').textContent =
            `${data.home_name} vs ${data.away_name} · 예측 결과`;

        byId('result-empty').hidden = true;

        const cards = el('div', undefined, 'result-bars');
        if (raw.views) root.append(modeBar(raw, picked.mode));

        data.probabilities.forEach(p => {
            const card = el('div', undefined, 'prob-card');

            card.append(el(
                'h3',
                p.code === 'H'
                    ? `${data.home_name} 승`
                    : p.code === 'A'
                        ? `${data.away_name} 승`
                        : '무승부'
            ));

            const before = el('div', undefined, 'track');
            const bbar = el('div');
            bbar.style.width = `${p.before}%`;
            before.append(bbar);

            const after = el(
                'div',
                undefined,
                'track after'
            );

            const abar = el('div');
            abar.style.width = `${p.after}%`;
            after.append(abar);

            card.append(
                before,
                el('strong', `${p.after.toFixed(1)}%`),
                after,
                el(
                    'p',
                    `${picked.compare} 대비 ${signed(p.change)}%p`
                )
            );

            cards.append(card);
        });

        const stack = (key, className) => {
            const bar = el(
                'div',
                undefined,
                `probability-stack ${className}`
            );

            bar.setAttribute(
                'aria-label',
                data.probabilities
                    .map(p => `${p.label} ${p[key]}%`)
                    .join(', ')
            );

            data.probabilities.forEach(p => {
                const part = el('div', undefined, p.code);
                part.style.width = `${p[key]}%`;
                part.title = `${p.label} ${p[key]}%`;
                bar.append(part);
            });

            return bar;
        };

        root.append(
            cards,
            stack('after', '')
        );

        if (data.long_gap) {
            root.append(el(
                'p',
                `기록 기준일에서 ${data.stale_days}일 지난 가상 경기입니다. 그 사이의 실제 경기는 미반영입니다.`,
                'notice'
            ));
        }

        if (data.bonus_result) {
            root.append(bonusBlock(data));
        }

        // 내 BEST11 가중치 결과는 위의 '가중치 포함'에 합쳐졌다 (views.weighted)

        if (data.player_part) {
            root.append(playerBlock(data));
        }

        details.append(el(
            'p',
            `기본 모델 평가: ${data.test_count}경기 정확도 ${data.baseline_accuracy}%. 선수 능력치 혼합·케미·컨디션·가상 최근 경기 보정은 이 평가에 포함되지 않았습니다.`,
            'notice'
        ));

        for (const side of ['home', 'away']) {
            const current = data[side];

            const name = side === 'home'
                ? data.home_name
                : data.away_name;

            details.append(el(
                'h3',
                `${name} · 기본 4-3-3 → ${current.formation}`
            ));

            details.append(table(
                ['포지션 평균점수', '기본', '변경 후', '변화'],
                current.parts.map(p => [
                    p.label,
                    p.before.toFixed(1),
                    p.after.toFixed(1),
                    signed(p.change),
                ])
            ));

            const reasons = [...current.parts].sort(
                (a, b) =>
                    Math.abs(b.change) -
                    Math.abs(a.change)
            );

            const top = reasons.find(
                p => Math.abs(p.change) > 0.01
            );

            details.append(el(
                'p',
                top
                    ? `평균점수 변화가 가장 큰 포지션: ${top.label} ${signed(top.change)}점`
                    : '기본 구성과 전력 차이가 없습니다.'
            ));

            const changes = el('ul');

            current.changes.forEach(p => {
                changes.append(el(
                    'li',
                    `${p.name} · ${p.role} · ${p.condition} · ${p.reason}`
                ));
            });

            if (!current.changes.length) {
                changes.append(
                    el('li', '선수·배치·컨디션 변경 없음')
                );
            }

            details.append(changes);

            if (current.low_evidence_count) {
                details.append(el(
                    'p',
                    `기록이 부족하거나 보정된 선수 ${current.low_evidence_count}명. 중립값이 포함된 전력은 불확실성이 큽니다.`,
                    'muted'
                ));
            }

            const reference = el('details');

            reference.append(
                el('summary', '비교 기준 명단 확인')
            );

            reference.append(el(
                'p',
                current.baseline_lineup
                    .map(p => `${p.role} ${p.name}`)
                    .join(' · ')
            ));

            details.append(reference);
        }

        root.hidden = false;
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();
        clearTimeout(autoTimer);

        if (comparing) return;

        let body;

        try {
            body = payload();
        } catch (error) {
            status(error.message, true);

            byId('result-empty').textContent =
                '팀·경기 기준일·선수 구성을 확인하세요.';

            return;
        }

        const atRevision = revision;
        comparing = true;

        byId('result').setAttribute('aria-busy', 'true');

        busy();
        status('변경 전후를 계산하고 있습니다…');

        try {
            const data = await request(
                form.dataset.resultUrl,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': form.querySelector(
                            '[name=csrfmiddlewaretoken]'
                        ).value,
                    },
                    body: JSON.stringify(body),
                }
            );

            if (atRevision !== revision) {
                status('최신 설정으로 다시 계산합니다…');
                return;
            }

            showResult(data);
            status('✓ 최신 설정 반영 완료');
        } catch (error) {
            if (atRevision === revision) {
                status(error.message, true);

                byId('result-empty').hidden = false;

                byId('result-empty').textContent =
                    '계산하지 못했습니다. 설정을 확인하거나 다시 계산을 눌러주세요.';
            }
        } finally {
            comparing = false;

            byId('result').setAttribute('aria-busy', 'false');

            busy();

            if (atRevision !== revision) {
                scheduleCalculation();
            }
        }
    });

    function rowsFor(side) {
        return [
            ...byId(`${side}-lineup`).querySelectorAll(
                '.player-row'
            ),
        ];
    }

    function currentPlayer(side, row) {
        return sideState[side].data.roster.find(
            p => p.id === Number(
                row.querySelector('.player-select').value
            )
        );
    }

    function formationPositions(formation) {
        if (formation === '4-2-3-1') {
            return [
                {
                    depth: 6,
                    lateral: 50,
                    label: 'GK',
                    line: 'goalkeeper',
                },
                {
                    depth: 16,
                    lateral: 12,
                    label: 'DF',
                    line: 'defense',
                },
                {
                    depth: 16,
                    lateral: 37,
                    label: 'DF',
                    line: 'defense',
                },
                {
                    depth: 16,
                    lateral: 63,
                    label: 'DF',
                    line: 'defense',
                },
                {
                    depth: 16,
                    lateral: 88,
                    label: 'DF',
                    line: 'defense',
                },
                {
                    depth: 26,
                    lateral: 32,
                    mobileLateral: 22,
                    label: 'MF(후방)',
                    line: 'holding',
                },
                {
                    depth: 26,
                    lateral: 68,
                    mobileLateral: 78,
                    label: 'MF(후방)',
                    line: 'holding',
                },
                {
                    depth: 36,
                    lateral: 16,
                    label: 'MF(전방)',
                    line: 'attacking',
                },
                {
                    depth: 33,
                    lateral: 50,
                    label: 'MF(전방)',
                    line: 'attacking',
                },
                {
                    depth: 36,
                    lateral: 84,
                    label: 'MF(전방)',
                    line: 'attacking',
                },
                {
                    depth: 45,
                    lateral: 50,
                    label: 'FW',
                    line: 'striker',
                },
            ];
        }

        const counts = [
            1,
            ...formation.split('-').map(Number),
        ];

        return counts.flatMap((count, line) =>
            Array.from({length: count}, (_, spot) => ({
                depth: 6 + line * (
                    38 / (counts.length - 1)
                ),
                lateral: count === 1
                    ? 50
                    : 12 + spot * 76 / (count - 1),
                line: [
                    'goalkeeper',
                    'defense',
                    'midfield',
                    'attack',
                ][line],
            }))
        );
    }

    function renderVisuals() {
        if (!byId('record-filter-toolbar')) {
            const toolbar = el(
                'div',
                undefined,
                'record-filter-toolbar'
            );

            toolbar.id = 'record-filter-toolbar';

            toolbar.append(
                recordFilter.control('show-missing-records'),
                el(
                    'p',
                    '기본은 기록 있는 선수 표시 · 600분 미만 기록은 주의해서 비교하세요.',
                    'record-filter-help'
                )
            );

            document.querySelector(
                '.formation-controls'
            ).after(toolbar);
        }

        for (const side of ['home', 'away']) {
            const team = config.teams.find(
                t => t.id === byId(`${side}-team`).value
            );

            const identity = byId(`${side}-identity`);
            identity.replaceChildren();

            if (team?.logo) {
                const img = el('img');
                img.src = team.logo;
                img.alt = `${team.name} 로고`;

                img.addEventListener('error', () => {
                    img.replaceWith(el(
                        'span',
                        team.name.slice(0, 1),
                        'club-fallback'
                    ));
                }, {once: true});

                identity.append(img);
            } else if (team) {
                identity.append(el(
                    'span',
                    team.name.slice(0, 1),
                    'club-fallback'
                ));
            }

            const pitch = byId(`${side}-pitch`);
            const bench = byId(`${side}-bench`);

            pitch.replaceChildren();
            bench.replaceChildren();

            byId(`${side}-bench-name`).textContent =
                team?.name ||
                (side === 'home' ? '홈팀' : '원정팀');

            byId(`${side}-bench-count`).textContent = '—';

            if (!sideState[side].data) {
                pitch.append(
                    el('span', '', 'loading')
                );

                bench.append(el(
                    'p',
                    '선수 명단을 불러오는 중입니다…',
                    'bench-loading'
                ));

                continue;
            }

            const rows = rowsFor(side);
            const selected = new Set();

            const formation =
                byId(`${side}-formation`).value;

            pitch.dataset.formation = formation;

            formationPositions(formation).forEach(
                (position, slot) => {
                    const row = rows[slot];
                    if (!row) return;

                    const p = currentPlayer(side, row);
                    if (!p) return;

                    selected.add(p.id);

                    const condition = row.querySelector(
                        '.condition-select'
                    ).value;

                    const role = row.dataset.role;

                    const pitchRole =
                        position.line === 'holding'
                            ? '후방'
                            : position.line === 'attacking'
                                ? '전방'
                                : role;

                    const button = el(
                        'button',
                        undefined,
                        `pitch-player ${side}-player ${role === 'GK' ? 'gk' : ''}`
                    );

                    button.type = 'button';

                    button.style.left =
                        `${side === 'home' ? position.depth : 100 - position.depth}%`;

                    button.style.top =
                        `${position.lateral}%`;

                    button.dataset.line = position.line;
                    button.dataset.slot = String(slot);

                    button.style.setProperty(
                        '--mobile-lateral',
                        `${position.mobileLateral ?? position.lateral}%`
                    );

                    button.style.setProperty(
                        '--field-x',
                        button.style.left
                    );

                    button.style.setProperty(
                        '--field-y',
                        button.style.top
                    );

                    const conditionLabel = {
                        good: '좋음',
                        normal: '보통',
                        bad: '안 좋음',
                    }[condition];

                    button.setAttribute(
                        'aria-label',
                        `${side === 'home' ? '홈' : '원정'} ${row.dataset.slotLabel || role} ${p.name}, 컨디션 ${conditionLabel}. 선수 설정 열기`
                    );

                    button.append(
                        playerPortrait(p),
                        el('span', p.name, 'player-name')
                    );

                    const rating = el(
                        'span',
                        undefined,
                        'player-rating'
                    );

                    rating.append(
                        el(
                            'span',
                            `${pitchRole} · ${shownScore(p, role).toFixed(1)}`
                        ),
                        el(
                            'span',
                            {
                                good: '↑',
                                normal: '·',
                                bad: '↓',
                            }[condition],
                            `condition-${condition}`
                        )
                    );

                    button.append(rating);

                    const recommended =
                        sideState[side].data
                            .recommended.players[slot];

                    if (
                        recommended &&
                        Number(recommended.id) !== p.id
                    ) {
                        button.append(el(
                            'span',
                            '교체',
                            'pitch-change-badge'
                        ));
                    }

                    button.dataset.condition = condition;

                    button.addEventListener(
                        'click',
                        () => openEditor(side, slot)
                    );

                    pitch.append(button);
                }
            );

            const available =
                sideState[side].data.roster.filter(
                    p => !selected.has(p.id)
                );

            const visible = available.filter(
                p =>
                    recordFilter.includeMissing ||
                    recordFilter.status(
                        p,
                        p.position
                    ).hasData
            );

            byId(`${side}-bench-count`).textContent =
                `${visible.length} / ${available.length}명`;

            byId(`${side}-bench-count`).title =
                `표시 ${visible.length}명 / 전체 후보 ${available.length}명`;

            if (!visible.length) {
                bench.append(el(
                    'p',
                    '표시할 후보가 없습니다. 기록 없는 선수도 보려면 위 옵션을 켜세요.',
                    'record-filter-empty'
                ));
            }

            visible.forEach(p => {
                const button = el('button');
                button.type = 'button';
                button.dataset.playerId = String(p.id);

                button.setAttribute(
                    'aria-label',
                    `${team?.name || ''} ${p.position} ${p.name}, 교체 비교 열기`
                );

                const avatar = el(
                    'span',
                    String(p.number || '·'),
                    'bench-avatar'
                );

                avatar.setAttribute('aria-hidden', 'true');

                if (p.photo) {
                    const image = el('img');
                    image.src = p.photo;
                    image.alt = '';

                    image.addEventListener(
                        'error',
                        () => image.remove(),
                        {once: true}
                    );

                    avatar.append(image);
                }

                const text = el(
                    'span',
                    undefined,
                    'bench-player-text'
                );

                const record = recordFilter.status(
                    p,
                    p.position
                );

                const statusText =
                    record.label +
                    (record.lowMinutes ? ' · 600분 미만' : '');

                text.append(
                    el('strong', p.name),
                    el(
                        'small',
                        `${p.position} · ${p.minutes}분`
                    ),
                    el(
                        'span',
                        statusText,
                        `record-state ${record.kind}`
                    )
                );

                button.append(avatar, text);

                button.addEventListener('click', () => {
                    let slot = rows.findIndex(
                        r => r.dataset.role === p.position
                    );

                    if (slot < 0) {
                        slot = rows.findIndex(
                            r => Object.hasOwn(
                                p.scores,
                                r.dataset.role
                            )
                        );
                    }

                    if (slot >= 0) {
                        openEditor(side, slot, p.id);
                    }
                });

                bench.append(button);
            });
        }

        let note = byId('formation-layout-note');

        if (!note) {
            note = el('p', undefined, 'muted');
            note.id = 'formation-layout-note';

            document.querySelector(
                '.pitch-legend'
            ).after(note);
        }

        note.hidden = !['home', 'away'].some(
            side =>
                byId(`${side}-formation`).value === '4-2-3-1'
        );

        note.textContent =
            '4-2-3-1: 수비 4명 → 후방 중원 2명 → 전방 중원 3명 → 공격수 1명. 후방·전방은 가상 배치 구분이며 등록 포지션과 기록 계산은 MF를 사용합니다.';

        renderHistory();
    }

    function openEditor(side, slot, preferred) {
        editorSide = side;

        const select = byId('editor-slot');
        select.replaceChildren();

        rowsFor(side).forEach((row, index) => {
            const p = currentPlayer(side, row);

            option(
                select,
                index,
                `${row.dataset.slotLabel || row.dataset.role} · ${p.name}`
            );
        });

        select.value = String(slot);
        fillEditor(preferred);

        byId('editor-title').textContent =
            `${side === 'home' ? '홈팀' : '원정팀'} 선수 설정`;

        byId('player-dialog').showModal();

        window.lineupComparisonContext = {
            side,
            roster: sideState[side].data.roster,
        };

        document.dispatchEvent(
            new CustomEvent('lineup:editor-open', {
                detail: window.lineupComparisonContext,
            })
        );
    }

    function fillEditor(preferred) {
        const rows = rowsFor(editorSide);
        const index = Number(byId('editor-slot').value);
        const row = rows[index];

        const used = new Set(
            rows
                .filter((_, i) => i !== index)
                .map(r => currentPlayer(editorSide, r).id)
        );

        const select = byId('editor-player');
        select.replaceChildren();

        sideState[editorSide].data.roster
            .filter(p => Object.hasOwn(
                p.scores,
                row.dataset.role
            ))
            .forEach(p => {
                option(
                    select,
                    p.id,
                    `${p.number || '·'} ${p.name} (${p.position})${used.has(p.id) ? ' · 이미 선발' : ''}`
                );

                select.lastChild.disabled = used.has(p.id);
            });

        const target = [...select.options].find(
            o =>
                o.value === String(preferred) &&
                !o.disabled
        );

        select.value = target
            ? target.value
            : row.querySelector('.player-select').value;

        byId('editor-condition').value =
            row.querySelector('.condition-select').value;

        updateEditorNote();
    }

    function updateEditorNote() {
        const row = rowsFor(editorSide)[
            Number(byId('editor-slot').value)
        ];

        const p = sideState[editorSide].data.roster.find(
            p => p.id === Number(
                byId('editor-player').value
            )
        );

        byId('editor-note').textContent = p
            ? `원 포지션 ${p.position} · ${row.dataset.role} ${scoreText(p, row.dataset.role)} · 출전 ${p.minutes}분. ${p.notes[row.dataset.role] || ''}`
            : '';

        document.querySelector(
            'label[for="editor-condition"]'
        ).textContent = p
            ? `적용할 선수 · ${p.name}의 컨디션`
            : '적용할 선수의 컨디션';
    }

    byId('editor-slot').addEventListener(
        'change',
        () => fillEditor()
    );

    byId('editor-player').addEventListener(
        'change',
        updateEditorNote
    );

    byId('close-editor').addEventListener(
        'click',
        () => byId('player-dialog').close()
    );

    byId('apply-editor').addEventListener('click', () => {
        const row = rowsFor(editorSide)[
            Number(byId('editor-slot').value)
        ];

        row.querySelector('.player-select').value =
            byId('editor-player').value;

        row.querySelector('.condition-select').value =
            byId('editor-condition').value;

        updatePlayer(
            editorSide,
            row,
            row.dataset.role
        );

        byId('player-dialog').close();
        changed();
    });

    function svgNode(tag, attributes = {}, text) {
        const node = document.createElementNS(
            'http://www.w3.org/2000/svg',
            tag
        );

        Object.entries(attributes).forEach(([key, value]) => {
            node.setAttribute(key, value);
        });

        if (text !== undefined) {
            node.textContent = text;
        }

        return node;
    }

    function scoreChart(rows, maximum, name) {
        const svg = svgNode('svg', {
            viewBox: '0 0 470 210',
            role: 'img',
            'aria-label':
                `${name} 최근 ${rows.length}경기 득점·실점 추이`,
            class: 'score-chart',
        });

        svg.append(svgNode(
            'title',
            {},
            `${name} 득점·실점. 상세 수치는 아래 경기표에서 확인할 수 있습니다.`
        ));

        const x = i => rows.length === 1
            ? 247
            : 35 + i * 420 / (rows.length - 1);

        const y = v => 167 - v * 135 / maximum;

        for (let i = 0; i <= maximum; i++) {
            svg.append(
                svgNode('line', {
                    x1: 35,
                    x2: 455,
                    y1: y(i),
                    y2: y(i),
                    stroke: '#e9eef2',
                    'stroke-dasharray': '3 4',
                }),
                svgNode(
                    'text',
                    {x: 16, y: y(i) + 4},
                    String(i)
                )
            );
        }

        for (const [key, color] of [
            ['gf', '#2975eb'],
            ['ga', '#ee6957'],
        ]) {
            const points = rows
                .map((r, i) => `${x(i)},${y(r[key])}`)
                .join(' ');

            svg.append(svgNode('polyline', {
                points,
                fill: 'none',
                stroke: color,
                'stroke-width': 2.5,
                'stroke-linejoin': 'round',
            }));

            rows.forEach((r, i) => {
                const circle = svgNode('circle', {
                    cx: x(i),
                    cy: y(r[key]),
                    r: 4,
                    fill: 'white',
                    stroke: color,
                    'stroke-width': 2,
                });

                circle.append(svgNode(
                    'title',
                    {},
                    `${r.date} ${r.opponent} · ${key === 'gf' ? '득점' : '실점'} ${r[key]}`
                ));

                svg.append(circle);
            });
        }

        rows.forEach((r, i) => {
            svg.append(svgNode(
                'text',
                {
                    x: x(i),
                    y: 194,
                    'text-anchor': 'middle',
                },
                r.date.slice(5).replace('-', '/')
            ));
        });

        return svg;
    }

    function historyRows(side) {
        if (!sideState[side].data) return [];

        const cutoff = byId('match-date').value;

        return (sideState[side].data.history || [])
            .filter(r => (
                r.date < cutoff &&
                (
                    byId('history-filter').value !== 'venue' ||
                    r.home === (side === 'home')
                )
            ))
            .sort((a, b) => a.date.localeCompare(b.date));
    }

    function renderHistory() {
        renderHeadToHead();

        const root = byId('history-content');
        root.replaceChildren();

        const histories = {
            home: historyRows('home'),
            away: historyRows('away'),
        };

        const maximum = Math.max(
            3,
            ...Object.values(histories).flatMap(
                rows => rows.slice(-5).flatMap(
                    r => [r.gf, r.ga]
                )
            )
        );

        for (const side of ['home', 'away']) {
            const name = config.teams.find(
                t => t.id === byId(`${side}-team`).value
            )?.name || '';

            const rows = histories[side];
            const recent = rows.slice(-5);

            const card = el(
                'article',
                undefined,
                'history-card'
            );

            const heading = el(
                'div',
                undefined,
                'history-title'
            );

            const badges = el(
                'div',
                undefined,
                'form-badges'
            );

            const result = r =>
                r.gf > r.ga
                    ? 'W'
                    : r.gf < r.ga
                        ? 'L'
                        : 'D';

            const label = {
                W: '승',
                D: '무',
                L: '패',
            };

            recent.forEach(r => {
                const badge = el(
                    'span',
                    label[result(r)],
                    `form-badge form-${result(r)}`
                );

                badge.title =
                    `${r.date} ${r.opponent} ${r.gf}:${r.ga}`;

                badges.append(badge);
            });

            heading.append(
                el('h3', name),
                badges
            );

            card.append(heading);

            if (!rows.length) {
                card.append(el(
                    'p',
                    '표시할 완료 경기 기록이 없습니다.',
                    'muted'
                ));

                root.append(card);
                continue;
            }

            const legend = el(
                'div',
                undefined,
                'chart-legend'
            );

            legend.append(
                el('span', '● 득점', 'gf'),
                el('span', '● 실점', 'ga')
            );

            card.append(
                legend,
                scoreChart(recent, maximum, name),
                el(
                    'p',
                    `최근 ${recent.length}경기 · 왼쪽부터 오래된 경기 순`,
                    'chart-hint'
                )
            );

            const wins = rows.filter(
                r => result(r) === 'W'
            ).length;

            const draws = rows.filter(
                r => result(r) === 'D'
            ).length;

            const losses = rows.length - wins - draws;
            const gf = rows.reduce((a, r) => a + r.gf, 0);
            const ga = rows.reduce((a, r) => a + r.ga, 0);

            const tiles = el(
                'div',
                undefined,
                'stat-tiles'
            );

            [
                [
                    `${(wins / rows.length * 100).toFixed(1)}%`,
                    '과거 승률',
                ],
                [
                    (gf / rows.length).toFixed(2),
                    '경기당 득점',
                ],
                [
                    (ga / rows.length).toFixed(2),
                    '경기당 실점',
                ],
                [
                    `${rows.filter(r => !r.ga).length}회`,
                    '무실점 경기',
                ],
                [
                    `${rows.filter(r => !r.gf).length}회`,
                    '무득점 경기',
                ],
                [
                    `${rows.length}경기`,
                    '통계 표본',
                ],
            ].forEach(([value, text]) => {
                const tile = el(
                    'div',
                    undefined,
                    'stat-tile'
                );

                tile.append(
                    el('strong', value),
                    el('small', text)
                );

                tiles.append(tile);
            });

            const bar = el(
                'div',
                undefined,
                'historic-bar'
            );

            [
                [wins, 'win'],
                [draws, 'draw'],
                [losses, 'loss'],
            ].forEach(([n, cls]) => {
                const segment = el(
                    'div',
                    undefined,
                    cls
                );

                segment.style.width =
                    `${n / rows.length * 100}%`;

                bar.append(segment);
            });

            card.append(
                tiles,
                bar,
                el(
                    'p',
                    `${rows[0].date} ~ ${rows.at(-1).date} · ${wins}승 ${draws}무 ${losses}패 · 다음 경기 예측 확률과 다릅니다.`,
                    'historic-caption'
                )
            );

            card.append(table(
                ['날짜', '상대팀', '홈/원정', '득점 : 실점', '결과'],
                [...recent].reverse().map(r => [
                    r.date.slice(5),
                    r.opponent,
                    r.home ? '홈' : '원정',
                    `${r.gf} : ${r.ga}`,
                    label[result(r)],
                ])
            ));

            root.append(card);
        }
    }

    function renderHeadToHead() {
        let root = byId('head-to-head');

        if (!root) {
            root = el('section');
            root.id = 'head-to-head';

            root.setAttribute(
                'aria-label',
                '선택한 두 팀의 상대전적'
            );

            document.querySelector(
                '.history-panel'
            ).before(root);
        }

        root.replaceChildren();

        const heading = el(
            'div',
            undefined,
            'section-heading'
        );

        const title = el('div');

        title.append(
            el('span', 'HEAD TO HEAD', 'eyebrow'),
            el('h2', '두 팀이 만났을 때')
        );

        heading.append(title);
        root.append(heading);

        const home = config.teams.find(
            t => t.id === byId('home-team').value
        );

        const away = config.teams.find(
            t => t.id === byId('away-team').value
        );

        if (!home || !away) return;

        if (home.id === away.id) {
            root.append(el(
                'p',
                '상대전적을 보려면 서로 다른 두 팀을 선택하세요.',
                'muted'
            ));

            return;
        }

        if (
            !sideState.home.data ||
            !sideState.away.data
        ) {
            root.append(el(
                'p',
                '상대전적을 불러오는 중입니다…',
                'muted'
            ));

            return;
        }

        const cutoff = byId('match-date').value;

        const rows = (
            sideState.home.data.history || []
        )
            .filter(r => (
                r.opponent === away.name &&
                r.date < cutoff
            ))
            .sort((a, b) =>
                a.date.localeCompare(b.date)
            );

        root.append(el(
            'p',
            `2026년 보유 기록 · ${cutoff || '선택 날짜'} 이전 완료 경기 · 실제 경기의 홈·원정을 모두 포함합니다.`,
            'muted'
        ));

        if (!rows.length) {
            root.append(el(
                'p',
                '해당 날짜 이전에 보유한 두 팀의 맞대결 기록이 없습니다.',
                'muted'
            ));

            return;
        }

        const wins = rows.filter(
            r => r.gf > r.ga
        ).length;

        const draws = rows.filter(
            r => r.gf === r.ga
        ).length;

        const losses = rows.length - wins - draws;

        const gf = rows.reduce(
            (sum, r) => sum + r.gf,
            0
        );

        const ga = rows.reduce(
            (sum, r) => sum + r.ga,
            0
        );

        const tiles = el(
            'div',
            undefined,
            'stat-tiles'
        );

        [
            [`${wins}승`, home.name],
            [`${draws}무`, '무승부'],
            [`${losses}승`, away.name],
        ].forEach(([value, label]) => {
            const tile = el(
                'div',
                undefined,
                'stat-tile'
            );

            tile.append(
                el('strong', value),
                el('small', label)
            );

            tiles.append(tile);
        });

        const bar = el(
            'div',
            undefined,
            'probability-stack'
        );

        bar.setAttribute(
            'aria-label',
            `${rows.length}경기 중 ${home.name} ${wins}승, 무승부 ${draws}회, ${away.name} ${losses}승`
        );

        [
            [wins, 'H'],
            [draws, 'D'],
            [losses, 'A'],
        ].forEach(([count, code]) => {
            const segment = el(
                'div',
                undefined,
                code
            );

            segment.style.width =
                `${count / rows.length * 100}%`;

            bar.append(segment);
        });

        root.append(
            tiles,
            bar,
            el(
                'p',
                `총 ${rows.length}경기 · 누적 득점 ${home.name} ${gf}골 : ${away.name} ${ga}골 · 과거 상대전적이며 다음 경기 예측 확률이 아닙니다.`,
                'muted'
            )
        );

        root.append(table(
            ['경기 날짜', '실제 홈팀', '스코어', '실제 원정팀', '결과'],
            [...rows].reverse().map(r => [
                r.date,
                r.home ? home.name : away.name,
                r.home
                    ? `${r.gf} : ${r.ga}`
                    : `${r.ga} : ${r.gf}`,
                r.home ? away.name : home.name,
                r.gf === r.ga
                    ? '무승부'
                    : `${r.gf > r.ga ? home.name : away.name} 승`,
            ])
        ));
    }

    function readPresets() {
        const raw = localStorage.getItem(storageKey);

        if (!raw) return [];

        if (raw.length > 256000) {
            throw new Error(
                '저장된 설정 데이터가 너무 큽니다.'
            );
        }

        const doc = JSON.parse(raw);

        if (
            doc.version !== 1 ||
            !Array.isArray(doc.items) ||
            doc.items.length > 10
        ) {
            throw new Error(
                '저장된 설정 형식을 확인하세요.'
            );
        }

        return doc.items;
    }

    function refreshPresets() {
        const select = byId('preset-list');
        select.replaceChildren();

        option(select, '', '설정 선택');

        readPresets().forEach((item, i) => {
            option(select, i, item.name);
        });
    }

    byId('save-preset').addEventListener('click', () => {
        try {
            const data = payload();
            const name = byId('preset-name').value.trim();

            if (!name || name.length > 40) {
                throw new Error(
                    '설정 이름을 1~40자로 입력하세요.'
                );
            }

            const items = readPresets();

            const existing = items.findIndex(
                p => p.name === name
            );

            if (existing < 0 && items.length >= 10) {
                throw new Error(
                    '최대 10개까지 저장할 수 있습니다. 기존 설정을 삭제해주세요.'
                );
            }

            if (existing >= 0) {
                items[existing] = {name, data};
            } else {
                items.push({name, data});
            }

            localStorage.setItem(
                storageKey,
                JSON.stringify({
                    version: 1,
                    items,
                })
            );

            refreshPresets();
            status('이 브라우저에 설정을 저장했습니다.');
        } catch (error) {
            status(
                `저장하지 못했습니다: ${error.message}`,
                true
            );
        }
    });

    byId('delete-preset').addEventListener('click', () => {
        try {
            const value = byId('preset-list').value;

            if (value === '') {
                throw new Error(
                    '삭제할 설정을 선택하세요.'
                );
            }

            const items = readPresets();
            items.splice(Number(value), 1);

            localStorage.setItem(
                storageKey,
                JSON.stringify({
                    version: 1,
                    items,
                })
            );

            refreshPresets();
            status('선택한 저장 설정을 삭제했습니다.');
        } catch (error) {
            status(error.message, true);
        }
    });

    byId('load-preset').addEventListener('click', async () => {
        try {
            const value = byId('preset-list').value;

            if (value === '') {
                throw new Error(
                    '불러올 설정을 선택하세요.'
                );
            }

            const saved = readPresets()[Number(value)];
            const data = saved.data;

            for (const side of ['home', 'away']) {
                if (
                    !data[side] ||
                    !config.teams.some(
                        t =>
                            t.id ===
                            data[`${side}_team`]
                    ) ||
                    !config.formations.includes(
                        data[side].formation
                    )
                ) {
                    throw new Error(
                        '현재 지원하지 않는 팀 또는 포메이션입니다.'
                    );
                }
            }

            byId('match-date').value = data.date;

            for (const side of ['home', 'away']) {
                byId(`${side}-team`).value =
                    data[`${side}_team`];

                byId(`${side}-formation`).value =
                    data[side].formation;
            }

            const loaded = await Promise.all(
                ['home', 'away'].map(loadSide)
            );

            if (!loaded.every(Boolean)) return;

            for (const side of ['home', 'away']) {
                renderLineup(
                    side,
                    data[side].players
                );
            }

            byId('preset-name').value = saved.name;

            changed();

            status(
                '저장한 설정으로 자동 계산합니다…'
            );
        } catch (error) {
            status(
                `불러오지 못했습니다: ${error.message}`,
                true
            );
        }
    });

    byId('reset').addEventListener('click', async () => {
        for (const side of ['home', 'away']) {
            byId(`${side}-formation`).value =
                '4-3-3';
        }

        await Promise.all(
            ['home', 'away'].map(loadSide)
        );
    });

    for (const [index, side] of [
        'home',
        'away',
    ].entries()) {
        config.teams.forEach(team => {
            option(
                byId(`${side}-team`),
                team.id,
                team.name
            );
        });

        config.formations.forEach(name => {
            option(
                byId(`${side}-formation`),
                name,
                name
            );
        });

        byId(`${side}-team`).value =
            config.teams[index].id;

        byId(`${side}-formation`).value =
            '4-3-3';

        byId(`${side}-team`).addEventListener(
            'change',
            () => loadSide(side)
        );

        byId(`${side}-formation`).addEventListener(
            'change',
            () => loadSide(side)
        );
    }

    byId('match-date').min = config.minDate;
    byId('match-date').max = '2026-12-31';
    byId('match-date').value = config.defaultDate;

    byId('match-date').addEventListener(
        'change',
        changed
    );

    byId('history-filter').addEventListener(
        'change',
        renderHistory
    );

    document.addEventListener('click', event => {
        const menu = byId('settings-menu');

        if (menu && !menu.contains(event.target)) {
            menu.open = false;
        }
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            byId('settings-menu').open = false;
        }
    });

    try {
        refreshPresets();
    } catch (error) {
        status(
            `저장 설정을 읽지 못했습니다: ${error.message}`,
            true
        );
    }

    async function startWithBest11(b11) {
        // 홈 = 내 BEST11 구단, 원정 = 다른 구단 하나
        byId('home-team').value = b11.team;
        byId('home-formation').value = b11.formation;
        if (byId('away-team').value === b11.team) {
            byId('away-team').value = config.teams.find(t => t.id !== b11.team).id;
        }
        const loaded = await Promise.all(['home', 'away'].map(loadSide));
        if (!loaded.every(Boolean)) return;
        try {
            renderLineup('home', b11.players.map(id => ({id, condition: 'normal'})));
            changed();
            status('🏆 BEST11 화면에서 고른 내 라인업으로 시작했습니다. 원정팀을 골라 보세요.');
        } catch (error) {
            status(`내 BEST11을 불러오지 못해 기본 명단으로 시작합니다: ${error.message}`, true);
        }
    }

    if (config.best11 && config.teams.some(t => t.id === config.best11.team)) {
        startWithBest11(config.best11);
    } else {
        Promise.all(
            ['home', 'away'].map(loadSide)
        );
    }
})();
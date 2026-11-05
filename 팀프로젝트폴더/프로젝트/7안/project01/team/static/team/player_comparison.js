(() => {
    'use strict';

    const byId = id => document.getElementById(id);
    const dialog = byId('player-dialog');

    if (!dialog) return;

    const recordFilter = window.lineupRecordFilter;
    if (!recordFilter) return;

    let state = null;
    let root = null;
    let ui = null;

    const factors = {
        bad: 0.9,
        normal: 1,
        good: 1.1,
    };

    const conditionNames = {
        bad: '안 좋음',
        normal: '보통',
        good: '좋음',
    };

    function el(tag, text, className) {
        const node = document.createElement(tag);

        if (text !== undefined) {
            node.textContent = text;
        }

        if (className) {
            node.className = className;
        }

        return node;
    }

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

    function finite(value) {
        return (
            typeof value === 'number' &&
            Number.isFinite(value)
        );
    }

    function number(value, decimals = 2) {
        return finite(value)
            ? value.toFixed(decimals)
            : '자료 없음';
    }

    function rows() {
        if (!state) return [];

        return [
            ...byId(`${state.side}-lineup`).querySelectorAll(
                '.player-row'
            ),
        ];
    }

    function currentRow() {
        return rows()[
            Number(byId('editor-slot').value)
        ];
    }

    function player(id) {
        return state?.roster.find(
            p => p.id === Number(id)
        );
    }

    function baselinePlayer() {
        const row = currentRow();

        return row
            ? player(
                row.querySelector('.player-select').value
            )
            : null;
    }

    function profile(p, role) {
        return p?.comparison?.[role] || null;
    }

    const style = el('style');

    style.textContent = `
        dialog.has-record-comparison {
            width: 920px;
            max-height: 90vh;
            overflow-y: auto;
        }

        .has-record-comparison #editor-player,
        .has-record-comparison label[for="editor-player"] {
            display: none;
        }

        .record-comparison {
            margin: 16px 0;
            color: #263d4d;
        }

        .record-intro {
            color: #7a8a96;
            font-size: 12px;
            line-height: 1.7;
        }

        .record-toolbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }

        .record-toolbar h3 {
            margin: 0;
            font-size: 17px;
        }

        .record-layout {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: 18px;
        }

        .record-comparison.candidate-open .record-layout {
            grid-template-columns: minmax(0, 1fr) 260px;
        }

        .record-graph-area {
            min-width: 0;
            border: 1px solid #e5ebef;
            border-radius: 14px;
            padding: 14px;
            background: #fafcfd;
        }

        .record-persons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .record-person {
            display: flex;
            gap: 9px;
            align-items: center;
            min-width: 0;
        }

        .record-person img {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            object-fit: cover;
            object-position: center top;
            border: 2px solid #2975eb;
            background: white;
        }

        .record-person.candidate img {
            border-color: #ee6957;
        }

        .record-person strong {
            display: block;
            font-size: 12px;
        }

        .record-person small {
            display: block;
            font-size: 10px;
            color: #7a8b98;
            margin-top: 4px;
        }

        .record-radar {
            display: block;
            width: 100%;
            max-width: 440px;
            height: auto;
            margin: auto;
        }

        .record-radar text {
            font-family: inherit;
            font-size: 10px;
            fill: #627989;
        }

        .record-legend {
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 14px;
            font-size: 11px;
            margin-bottom: 8px;
        }

        .record-legend .current {
            color: #2975eb;
        }

        .record-legend .candidate {
            color: #d66350;
        }

        .record-preview-label {
            font-size: 11px;
            color: #748795;
            min-height: 20px;
        }

        .record-candidates {
            min-width: 0;
            padding: 12px;
            border: 1px solid #e5ebef;
            border-radius: 14px;
        }

        .record-candidates input {
            width: 100%;
            font-size: 12px;
        }

        .record-candidate-list {
            display: grid;
            gap: 6px;
            max-height: 320px;
            overflow-y: auto;
            padding: 5px 2px;
            margin-top: 8px;
        }

        .record-candidate-button {
            display: block;
            width: 100%;
            background: white;
            border: 1px solid #e1e8ed;
            color: #354f60;
            text-align: left;
            padding: 10px;
            font-size: 12px;
        }

        .record-candidate-button small {
            display: block;
            margin-top: 5px;
            font-size: 10px;
            color: #82929e;
        }

        .record-candidate-button:hover,
        .record-candidate-button:focus-visible {
            background: #fff4ef;
            border-color: #f0ac9d;
        }

        .record-candidate-button[aria-pressed="true"] {
            background: #fff0e9;
            border-color: #ee6957;
        }

        .record-evidence {
            margin: 10px 0;
            font-size: 11px;
            color: #8a744f;
            line-height: 1.7;
        }

        .record-condition {
            padding: 10px 12px;
            background: #edf5f8;
            border-radius: 9px;
            font-size: 11px;
            line-height: 1.8;
        }

        .record-method {
            color: #7c8d99;
            font-size: 11px;
            line-height: 1.7;
        }

        .record-comparison table {
            font-size: 11px;
        }

        .record-comparison td,
        .record-comparison th {
            padding: 9px 8px;
        }

        @media (max-width: 700px) {
            dialog.has-record-comparison {
                padding: 18px;
            }

            .record-comparison.candidate-open .record-layout {
                grid-template-columns: minmax(0, 1fr);
            }

            .record-candidates {
                grid-row: 1;
            }

            .record-candidate-list {
                max-height: 190px;
            }

            .record-toolbar {
                align-items: start;
            }

            .record-toolbar button {
                font-size: 11px;
                white-space: nowrap;
            }

            .record-person strong {
                font-size: 11px;
            }
        }
    `;

    document.head.append(style);

    function personCard(p, className) {
        const card = el(
            'div',
            undefined,
            `record-person ${className}`
        );

        if (!p) return card;

        if (p.photo) {
            const image = el('img');
            image.src = p.photo;
            image.alt = `${p.name} 선수 사진`;

            image.addEventListener(
                'error',
                () => image.remove(),
                {once: true}
            );

            card.append(image);
        }

        const text = el('div');

        text.append(
            el('strong', `${p.number || '·'} ${p.name}`),
            el(
                'small',
                `${p.position} · 출전 ${p.minutes}분`
            )
        );

        card.append(text);

        return card;
    }

    function point(index, radius) {
        const angle =
            -Math.PI / 2 +
            index * Math.PI / 3;

        return [
            210 + Math.cos(angle) * radius,
            170 + Math.sin(angle) * radius,
        ];
    }

    function radar(
        axes,
        currentAxes,
        candidateAxes,
        names
    ) {
        const svg = svgNode('svg', {
            viewBox: '0 0 420 340',
            class: 'record-radar',
            role: 'img',
            'aria-label': (
                `${names.current}와 ${names.candidate}의 ` +
                '자리별 기록 비교. 실제 수치는 아래 표에 표시됩니다.'
            ),
        });

        svg.append(svgNode(
            'title',
            {},
            '기록 기반 비교 지수. 실선은 현재 선수, ' +
            '점선은 교체 후보입니다. 미확인 자료는 그리지 않습니다.'
        ));

        for (const level of [
            20,
            40,
            60,
            80,
            100,
        ]) {
            const points = axes.map(
                (_, i) => point(i, level).join(',')
            ).join(' ');

            svg.append(svgNode('polygon', {
                points,
                fill: 'none',
                stroke: '#dce6ec',
                'stroke-width': 1,
            }));
        }

        axes.forEach((axis, i) => {
            const edge = point(i, 100);
            const label = point(i, 137);

            svg.append(svgNode('line', {
                x1: 210,
                y1: 170,
                x2: edge[0],
                y2: edge[1],
                stroke: '#e1e9ef',
            }));

            let anchor = 'middle';

            if (label[0] > 230) {
                anchor = 'start';
            }

            if (label[0] < 190) {
                anchor = 'end';
            }

            svg.append(svgNode(
                'text',
                {
                    x: label[0],
                    y: label[1] + 4,
                    'text-anchor': anchor,
                },
                axis.label
            ));
        });

        function draw(
            values,
            color,
            dashed,
            name
        ) {
            const scores = axes.map((axis, i) => {
                const value = values[i]?.score;

                return finite(value)
                    ? Math.max(
                        0,
                        Math.min(100, value)
                    )
                    : null;
            });

            const coordinates = scores.map(
                (value, i) => (
                    value === null
                        ? null
                        : point(i, value)
                )
            );

            if (
                scores.every(
                    value => value !== null
                )
            ) {
                svg.append(svgNode('polygon', {
                    points: coordinates
                        .map(p => p.join(','))
                        .join(' '),
                    fill: color,
                    'fill-opacity': dashed
                        ? 0.08
                        : 0.12,
                    stroke: color,
                    'stroke-width': 2,
                    'stroke-dasharray': dashed
                        ? '5 3'
                        : 'none',
                }));
            } else {
                coordinates.forEach((p, i) => {
                    const next =
                        coordinates[(i + 1) % 6];

                    if (!p || !next) return;

                    svg.append(svgNode('line', {
                        x1: p[0],
                        y1: p[1],
                        x2: next[0],
                        y2: next[1],
                        stroke: color,
                        'stroke-width': 2,
                        'stroke-dasharray': dashed
                            ? '5 3'
                            : 'none',
                    }));
                });
            }

            coordinates.forEach((p, i) => {
                if (!p) return;

                const dot = svgNode('circle', {
                    cx: p[0],
                    cy: p[1],
                    r: dashed ? 4 : 3,
                    fill: dashed
                        ? 'white'
                        : color,
                    stroke: color,
                    'stroke-width': 2,
                });

                dot.append(svgNode(
                    'title',
                    {},
                    `${name} · ${axes[i].label} ` +
                    `${number(scores[i], 1)}점`
                ));

                svg.append(dot);
            });
        }

        draw(
            currentAxes,
            '#2975eb',
            false,
            names.current
        );

        if (names.compare) {
            draw(
                candidateAxes,
                '#ee6957',
                true,
                names.candidate
            );
        }

        return svg;
    }

    function comparisonTable(
        axes,
        currentAxes,
        candidateAxes
    ) {
        const wrap = el(
            'div',
            undefined,
            'table-wrap'
        );

        const table = el('table');
        const head = el('thead');
        const header = el('tr');

        [
            '실제 기록',
            '단위',
            '현재 선수',
            '교체 후보',
            '차이: 후보−현재',
        ].forEach(text => {
            header.append(
                el('th', text)
            );
        });

        head.append(header);

        const body = el('tbody');

        axes.forEach((axis, i) => {
            const before =
                currentAxes[i]?.raw;

            const after =
                candidateAxes[i]?.raw;

            let difference = '—';

            if (
                finite(before) &&
                finite(after)
            ) {
                const change =
                    after - before;

                difference =
                    `${change > 0 ? '+' : ''}${change.toFixed(2)}`;
            }

            const row = el('tr');

            [
                axis.label,
                axis.unit,
                number(before),
                number(after),
                difference,
            ].forEach(value => {
                row.append(
                    el('td', value)
                );
            });

            body.append(row);
        });

        table.append(head, body);
        wrap.append(table);

        return wrap;
    }

    function showPreview(
        id,
        preview = false
    ) {
        if (!state || !ui) return;

        const row = currentRow();
        const current = baselinePlayer();
        const candidate = player(id);

        if (
            !row ||
            !current ||
            !candidate
        ) {
            return;
        }

        const role = row.dataset.role;
        const before = profile(current, role);
        const after = profile(candidate, role);

        ui.graph.replaceChildren();
        ui.values.replaceChildren();

        const compare =
            current.id !== candidate.id;

        ui.people.replaceChildren(
            personCard(
                current,
                'current'
            )
        );

        if (compare) {
            ui.people.append(
                personCard(
                    candidate,
                    'candidate'
                )
            );
        }

        ui.legend.replaceChildren(
            el(
                'span',
                `━ 현재 선발: ${current.name}`,
                'current'
            )
        );

        if (compare) {
            ui.legend.append(el(
                'span',
                `┄ 교체 후보: ${candidate.name}`,
                'candidate'
            ));
        }

        ui.previewLabel.textContent = preview
            ? `미리보기: ${candidate.name} · 아직 선택되지 않았습니다.`
            : compare
                ? `선택한 후보: ${candidate.name} · ‘변경 적용’으로 확정합니다.`
                : '현재 선발 선수의 기록입니다.';

        if (
            !before ||
            !after ||
            before.axes.length !== 6 ||
            after.axes.length !== 6
        ) {
            ui.graph.append(el(
                'p',
                '비교 데이터를 받지 못했습니다. ' +
                '서버의 비교 데이터 연결을 확인하세요.',
                'notice'
            ));
        } else {
            ui.graph.append(radar(
                before.axes,
                before.axes,
                after.axes,
                {
                    current: current.name,
                    candidate: candidate.name,
                    compare,
                }
            ));

            ui.values.append(comparisonTable(
                before.axes,
                before.axes,
                after.axes
            ));
        }

        const notices = [];

        if (before?.note) {
            notices.push(
                `${current.name}: ${before.note}`
            );
        }

        if (
            compare &&
            after?.note
        ) {
            notices.push(
                `${candidate.name}: ${after.note}`
            );
        }

        if (
            before?.axes.some(
                a => !finite(a.score)
            ) ||
            after?.axes.some(
                a => !finite(a.score)
            )
        ) {
            notices.push(
                '미확인 기록이나 비교 기준이 없는 항목은 ' +
                '빈칸으로 표시하며, 그래프 점과 면을 생략합니다.'
            );
        }

        ui.evidence.textContent =
            notices.join(' ');

        const condition =
            byId('editor-condition').value;

        const baseScore =
            candidate.scores[role];

        if (finite(baseScore)) {
            const adjusted = Math.min(
                100,
                baseScore * factors[condition]
            );

            ui.condition.textContent = (
                `${candidate.name} · ${role} 역할 지수 ` +
                `${baseScore.toFixed(1)} → ` +
                `컨디션 ${conditionNames[condition]} 가정 적용 ` +
                `${adjusted.toFixed(1)}. ` +
                '위 기록 그래프에는 컨디션을 적용하지 않습니다.'
            );
        } else {
            ui.condition.textContent = '';
        }
    }

    function refreshSelection() {
        if (!state || !ui) return;

        const selected = Number(
            byId('editor-player').value
        );

        ui.list.querySelectorAll(
            '.record-candidate-button'
        ).forEach(button => {
            button.setAttribute(
                'aria-pressed',
                String(
                    Number(button.dataset.id) === selected
                )
            );
        });

        showPreview(selected);
    }

    function renderCandidates() {
        if (!state || !ui) return;

        const row = currentRow();
        const current = baselinePlayer();

        if (!row || !current) return;

        const role = row.dataset.role;

        const used = new Set(
            rows()
                .filter(r => r !== row)
                .map(r => Number(
                    r.querySelector('.player-select').value
                ))
        );

        const keyword = ui.search.value
            .trim()
            .toLowerCase();

        function samePosition(p) {
            return (
                (p.position || '')
                    .trim()
                    .toUpperCase() === role
            );
        }

        function hasRecords(p) {
            return recordFilter.status(
                p,
                role
            ).hasData;
        }

        function roleScore(p) {
            return finite(p.scores[role])
                ? p.scores[role]
                : 0;
        }

        const selectedId = Number(
            byId('editor-player').value
        );

        const allCandidates =
            state.roster.filter(p => (
                Object.hasOwn(
                    p.scores,
                    role
                ) &&
                !used.has(p.id)
            ));

        const eligible = allCandidates
            .filter(p => (
                (
                    recordFilter.includeMissing ||
                    hasRecords(p) ||
                    p.id === current.id ||
                    p.id === selectedId
                ) &&
                `${p.name} ${p.number} ${p.position}`
                    .toLowerCase()
                    .includes(keyword)
            ))
            .sort((a, b) => {
                // 같은 포지션 우선
                const positionOrder =
                    Number(samePosition(b)) -
                    Number(samePosition(a));

                if (positionOrder !== 0) {
                    return positionOrder;
                }

                // 같은 그룹에서는 기록이 있는 선수 우선
                const recordOrder =
                    Number(hasRecords(b)) -
                    Number(hasRecords(a));

                if (recordOrder !== 0) {
                    return recordOrder;
                }

                // 역할 지수가 높은 선수 우선
                const scoreOrder =
                    roleScore(b) - roleScore(a);

                if (scoreOrder !== 0) {
                    return scoreOrder;
                }

                // 동점이면 이름과 선수 ID 순
                return (
                    a.name.localeCompare(
                        b.name,
                        'ko'
                    ) ||
                    a.id - b.id
                );
            });

        ui.count.textContent =
            `표시 ${eligible.length}명 / 전체 후보 ${allCandidates.length}명`;

        ui.list.replaceChildren();

        eligible.forEach(p => {
            const button = el(
                'button',
                undefined,
                'record-candidate-button'
            );

            button.type = 'button';
            button.dataset.id = String(p.id);

            const record = recordFilter.status(
                p,
                role
            );

            const recordLabel =
                record.label +
                (
                    record.lowMinutes
                        ? ' · 600분 미만'
                        : ''
                );

            button.append(
                el(
                    'span',
                    `${p.number || '·'} ${p.name}` +
                    (
                        p.id === current.id
                            ? ' · 현재 선발'
                            : ''
                    )
                ),
                el(
                    'small',
                    `${p.position} · ${p.minutes}분 · 역할 지수 ` +
                    `${p.scores[role].toFixed(1)}`
                ),
                el(
                    'span',
                    recordLabel,
                    `record-state ${record.kind}`
                )
            );

            button.addEventListener(
                'mouseenter',
                () => showPreview(
                    p.id,
                    true
                )
            );

            button.addEventListener(
                'focus',
                () => showPreview(
                    p.id,
                    true
                )
            );

            button.addEventListener('click', () => {
                const select =
                    byId('editor-player');

                select.value =
                    String(p.id);

                select.dispatchEvent(
                    new Event('change', {
                        bubbles: true,
                    })
                );
            });

            ui.list.append(button);
        });

        if (!eligible.length) {
            ui.list.append(el(
                'p',
                '조건에 맞는 후보가 없습니다. 검색어나 기록 없는 선수 보기 옵션을 확인하세요.',
                'muted'
            ));
        }

        refreshSelection();
    }

    function mount(detail) {
        if (
            !dialog.open ||
            !detail ||
            !['home', 'away'].includes(detail.side) ||
            !Array.isArray(detail.roster)
        ) {
            return;
        }

        state = detail;

        if (root) {
            root.remove();
        }

        root = el(
            'div',
            undefined,
            'record-comparison'
        );

        dialog.classList.add(
            'has-record-comparison'
        );

        const toolbar = el(
            'div',
            undefined,
            'record-toolbar'
        );

        const toggle = el(
            'button',
            '선수 교체',
            'secondary'
        );

        toggle.type = 'button';

        toggle.setAttribute(
            'aria-expanded',
            'false'
        );

        toggle.setAttribute(
            'aria-controls',
            'record-candidates'
        );

        toolbar.append(
            el(
                'h3',
                '기록 기반 비교 지수'
            ),
            toggle
        );

        root.append(
            toolbar,
            el(
                'p',
                '실제 능력을 확정한 점수가 아닌 시즌 기록 비교입니다. ' +
                '같은 자리에 배치할 두 선수를 같은 기준으로 비교합니다.',
                'record-intro'
            )
        );

        const layout = el(
            'div',
            undefined,
            'record-layout'
        );

        const main = el(
            'div',
            undefined,
            'record-graph-area'
        );

        const people = el(
            'div',
            undefined,
            'record-persons'
        );

        const graph = el('div');

        const legend = el(
            'div',
            undefined,
            'record-legend'
        );

        const previewLabel = el(
            'p',
            undefined,
            'record-preview-label'
        );

        const evidence = el(
            'p',
            undefined,
            'record-evidence'
        );

        const condition = el(
            'p',
            undefined,
            'record-condition'
        );

        const values = el('div');

        const recordDetails = el(
            'details',
            undefined,
            'record-details'
        );

        recordDetails.append(
            el(
                'summary',
                '항목별 기록 · 비교 기준'
            ),
            values
        );

        main.append(
            people,
            graph,
            legend,
            previewLabel,
            evidence,
            condition
        );

        const candidates = el(
            'div',
            undefined,
            'record-candidates'
        );

        candidates.id =
            'record-candidates';

        candidates.hidden = true;

        const searchLabel = el(
            'label',
            '교체 후보 검색'
        );

        searchLabel.htmlFor =
            'record-player-search';

        const search = el('input');

        search.id =
            'record-player-search';

        search.type = 'search';

        search.placeholder =
            '선수 이름 · 등번호';

        const list = el(
            'div',
            undefined,
            'record-candidate-list'
        );

        const missingControl =
            recordFilter.control(
                'comparison-show-missing-records'
            );

        const count = el(
            'p',
            undefined,
            'record-filter-count'
        );

        candidates.append(
            searchLabel,
            search,
            missingControl,
            el(
                'p',
                '현재 선발·선택 중인 후보는 필터를 꺼도 유지합니다.',
                'record-filter-help'
            ),
            count,
            el(
                'p',
                '같은 포지션 우선 · 그룹 내 기록 보유·역할 지수순. ' +
                '마우스·키보드 이동: 미리보기 / 클릭: 후보 선택',
                'record-intro'
            ),
            list
        );

        layout.append(
            main,
            candidates
        );

        root.append(
            layout,
            recordDetails
        );

        recordDetails.append(el(
            'p',
            '그래프는 같은 자리의 리그 450분 이상 후보 최고 기록을 ' +
            '100으로 환산하고 0~100으로 표시합니다. ' +
            '최고 기록을 넘는 경우에도 실제 수치는 표에 표시합니다. ' +
            '경기당 실점은 적을수록 그래프가 커지며, ' +
            '실점 차이는 음수일수록 유리합니다. ' +
            '그래프 항목은 역할 지수의 전체 계산식을 뜻하지 않습니다.',
            'record-method'
        ));

        const anchor = dialog.querySelector(
            'label[for="editor-slot"]'
        );

        if (anchor) {
            dialog.insertBefore(
                root,
                anchor
            );
        } else {
            dialog.append(root);
        }

        ui = {
            graph,
            people,
            legend,
            previewLabel,
            evidence,
            condition,
            values,
            search,
            list,
            count,
        };

        toggle.addEventListener('click', () => {
            const open =
                candidates.hidden;

            candidates.hidden = !open;

            root.classList.toggle(
                'candidate-open',
                open
            );

            toggle.setAttribute(
                'aria-expanded',
                String(open)
            );

            toggle.textContent = open
                ? '후보 목록 닫기'
                : '선수 교체';

            if (open) {
                search.focus();
            }
        });

        search.addEventListener(
            'input',
            renderCandidates
        );

        candidates.addEventListener(
            'mouseleave',
            refreshSelection
        );

        candidates.addEventListener(
            'focusout',
            event => {
                if (
                    !candidates.contains(
                        event.relatedTarget
                    )
                ) {
                    refreshSelection();
                }
            }
        );

        renderCandidates();
    }

    document.addEventListener(
        'lineup:record-filter-change',
        () => {
            if (state && dialog.open) {
                renderCandidates();
            }
        }
    );

    document.addEventListener(
        'lineup:editor-open',
        event => mount(event.detail)
    );

    byId('editor-slot').addEventListener(
        'change',
        () => {
            if (state && dialog.open) {
                mount(state);
            }
        }
    );

    byId('editor-player').addEventListener(
        'change',
        refreshSelection
    );

    byId('editor-condition').addEventListener(
        'change',
        refreshSelection
    );

    dialog.addEventListener('close', () => {
        if (dialog.open) return;

        state = null;
        ui = null;

        if (root) {
            root.remove();
            root = null;
        }

        dialog.classList.remove(
            'has-record-comparison'
        );
    });

    if (
        dialog.open &&
        window.lineupComparisonContext
    ) {
        mount(
            window.lineupComparisonContext
        );
    }
})();
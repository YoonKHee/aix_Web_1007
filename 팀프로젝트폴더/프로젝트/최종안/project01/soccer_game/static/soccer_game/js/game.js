/**
 * 🎮 game.js - 메인 게임 컨트롤러
 * - PitchGeometry, PlayerController, ScreenManager, Ball, MatchRuleEngine 모듈과 완전 동기화
 */
// 📌 game.js 최상단 (다른 함수나 이벤트 리스너보다 위에 위치해야 합니다)
// 1. 게임 상태 및 홈/어웨이 관련 전역 변수들을 파일 맨 처음에 직접 선언합니다.

let homePlayers = [];
let awayPlayers = [];
let allPlayers = [];
let matchSeconds = 0;
let homeGoalsTotal = 0;
let awayGoalsTotal = 0;
let isPlaying = false;
let isKickOffPhase = true;

// 전역 혹은 상단에 인스턴스 선언
const tacticalEngine = new TacticalEngine();

document.addEventListener('DOMContentLoaded', () => {
// 이후에 이벤트 리스너나 함수, 애니메이션 루프가 위치해야 합니다.
    // 📌 1. 화면 스케일링/레이아웃 전담 ScreenManager 인스턴스 생성
    const screenManager = new ScreenManager('.main-game-wrapper', 1920, 1080);

    const canvas = document.getElementById('pitchCanvas');
    if (!canvas) {
        console.error("pitchCanvas 요소를 찾을 수 없습니다.");
        return;
    }
    const ctx = canvas.getContext('2d');

    const PITCH_WIDTH = canvas.width;
    const PITCH_HEIGHT = canvas.height;

    // 📌 2. 경기장 규격 및 룰 엔진 인스턴스 단일 생성 (중복 제거 완료)
    const pitchGeo = new PitchGeometry(PITCH_WIDTH, PITCH_HEIGHT);
    const ruleEngine = new MatchRuleEngine(pitchGeo, 0.5);
    

    // 📌 3. 공(Ball) 객체 생성
    let ball = new Ball(PITCH_WIDTH / 2, PITCH_HEIGHT / 2);

    const LEAGUE_DATA = {
        "1부리그": ['강원', '광주', '김천', '대전', '부천', '서울', '안양', '울산', '인천', '전북', '제주', '포항'],
        "2부리그": ['경남', '김포', '김해', '대구', '부산', '서울E', '성남', '수원', '수원FC', '안산', '아산', '용인', '전남', '천안', '청주', '파주', '화성']
    };

    const staticBaseUrlInput = document.getElementById('static-url-base');
    const dataUrlBaseInput = document.getElementById('data-url-base');
    const staticBaseUrl = staticBaseUrlInput ? staticBaseUrlInput.value : '';
    const dataUrlBase = dataUrlBaseInput ? dataUrlBaseInput.value : '';
    const placeholderUrl = document.getElementById('player-placeholder-url').value;

    const homeLeagueSelect = document.getElementById('home-league-select');
    const homeTeamSelect = document.getElementById('home-team-select');
    const awayLeagueSelect = document.getElementById('away-league-select');
    const awayTeamSelect = document.getElementById('away-team-select');

    const homeFormationSelect = document.getElementById('home-formation-select');
    const awayFormationSelect = document.getElementById('away-formation-select');

    const homeTacticSelect = document.getElementById('home-tactic-select');
    const awayTacticSelect = document.getElementById('away-tactic-select');

    const homeTeamNameEl = document.getElementById('home-team-name');
    const awayTeamNameEl = document.getElementById('away-team-name');
    const homeLogoEl = document.getElementById('home-logo');
    const awayLogoEl = document.getElementById('away-logo');

    const homeScoreEl = document.getElementById('home-score');
    const awayScoreEl = document.getElementById('away-score');

    // animate() 루프 내부
    const homeTactic = homeTacticSelect ? homeTacticSelect.value : '밸런스';
    const awayTactic = awayTacticSelect ? awayTacticSelect.value : '밸런스';

    // 실시간 전술 지침(Context) 산출 (스코어, 시간 반영)
    const homeTacticalContext = tacticalEngine.evaluateContext(homeTactic, true, matchSeconds, homeGoalsTotal, awayGoalsTotal);
    const awayTacticalContext = tacticalEngine.evaluateContext(awayTactic, false, matchSeconds, homeGoalsTotal, awayGoalsTotal);

    // 선수 업데이트 호출 시 컨텍스트 전달
    homePlayers.forEach(player => {
        player.update(ball, allPlayers, PITCH_WIDTH, PITCH_HEIGHT, isPlaying, isKickOffPhase, homeTactic, homeTacticalContext);
    });
    awayPlayers.forEach(player => {
        player.update(ball, allPlayers, PITCH_WIDTH, PITCH_HEIGHT, isPlaying, isKickOffPhase, awayTactic, awayTacticalContext);
    });


    let lastTouchIsHome = true;
    
    const modal = document.getElementById('player-modal');
    const modalCloseBtn = document.getElementById('modal-close');
    const modalThumb = document.getElementById('modal-player-thumb');
    const modalName = document.getElementById('modal-player-name');
    const modalSub = document.getElementById('modal-player-sub');
    const modalClub = document.getElementById('modal-club');
    const modalHW = document.getElementById('modal-hw');
    const modalBirth = document.getElementById('modal-birth');

    const statsModal = document.getElementById('stats-modal');
    const statsModalClose = document.getElementById('stats-modal-close');

    if (modalCloseBtn) modalCloseBtn.addEventListener('click', () => { modal.style.display = 'none'; });
    if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
    if (statsModalClose) statsModalClose.addEventListener('click', () => { statsModal.style.display = 'none'; });
    if (statsModal) statsModal.addEventListener('click', (e) => { if (e.target === statsModal) statsModal.style.display = 'none'; });

    const FORMATION_PRESETS = {
        "4-3-3": [
            { pos: 'GK', x: 100, y: 325 },
            { pos: 'DF', x: 230, y: 120 }, { pos: 'DF', x: 210, y: 250 }, { pos: 'DF', x: 210, y: 400 }, { pos: 'DF', x: 230, y: 530 },
            { pos: 'MF', x: 350, y: 180 }, { pos: 'MF', x: 330, y: 325 }, { pos: 'MF', x: 350, y: 470 },
            { pos: 'FW', x: 440, y: 160 }, { pos: 'FW', x: 460, y: 325 }, { pos: 'FW', x: 440, y: 490 }
        ],
        "4-4-2": [
            { pos: 'GK', x: 100, y: 325 },
            { pos: 'DF', x: 230, y: 120 }, { pos: 'DF', x: 210, y: 250 }, { pos: 'DF', x: 210, y: 400 }, { pos: 'DF', x: 230, y: 530 },
            { pos: 'MF', x: 340, y: 130 }, { pos: 'MF', x: 330, y: 260 }, { pos: 'MF', x: 330, y: 390 }, { pos: 'MF', x: 340, y: 520 },
            { pos: 'FW', x: 450, y: 240 }, { pos: 'FW', x: 450, y: 410 }
        ],
        "3-5-2": [
            { pos: 'GK', x: 100, y: 325 },
            { pos: 'DF', x: 220, y: 180 }, { pos: 'DF', x: 200, y: 325 }, { pos: 'DF', x: 220, y: 470 },
            { pos: 'MF', x: 340, y: 100 }, { pos: 'MF', x: 320, y: 210 }, { pos: 'MF', x: 310, y: 325 }, { pos: 'MF', x: 320, y: 440 }, { pos: 'MF', x: 340, y: 550 },
            { pos: 'FW', x: 450, y: 240 }, { pos: 'FW', x: 450, y: 410 }
        ],
        "4-2-3-1": [
            { pos: 'GK', x: 100, y: 325 },
            { pos: 'DF', x: 230, y: 120 }, { pos: 'DF', x: 210, y: 250 }, { pos: 'DF', x: 210, y: 400 }, { pos: 'DF', x: 230, y: 530 },
            { pos: 'MF', x: 310, y: 250 }, { pos: 'MF', x: 310, y: 400 },
            { pos: 'MF', x: 390, y: 160 }, { pos: 'MF', x: 390, y: 325 }, { pos: 'MF', x: 390, y: 490 },
            { pos: 'FW', x: 460, y: 325 }
        ]
    };

    const TACTIC_WEIGHTS = {
        // 기본 및 기존 전술
        "밸런스": { pass: 1.0, goal: 1.0, tackle: 1.0 },
        "점유율": { pass: 2.5, goal: 1.1, tackle: 0.7 },
        "공격형": { pass: 0.8, goal: 2.2, tackle: 0.9 },
        "수비형": { pass: 0.7, goal: 1.0, tackle: 2.5 },
        
        // 1. 압박 방식
        "하이프레스": { pass: 0.7, goal: 1.2, tackle: 2.8 },
        "미드블록":   { pass: 1.5, goal: 1.0, tackle: 1.5 },
        "로우블록":   { pass: 0.9, goal: 0.8, tackle: 2.2 },

        // 2. 빌드업 방식
        "짧은 패스":  { pass: 3.0, goal: 1.0, tackle: 0.8 },
        "롱 패스":    { pass: 0.6, goal: 1.8, tackle: 1.0 },
        "측면 공략":  { pass: 1.8, goal: 1.5, tackle: 1.0 },
        "역습":       { pass: 0.8, goal: 2.5, tackle: 1.2 },

        // 3. 수비 방식
        "지역방어":   { pass: 1.1, goal: 1.0, tackle: 1.6 },
        "맨마킹":     { pass: 0.8, goal: 0.9, tackle: 2.4 },
        "혼합방어":   { pass: 1.0, goal: 1.0, tackle: 2.0 },

        // 4. 공수 균형
        "풀백 오버래핑": { pass: 1.4, goal: 1.3, tackle: 1.1 },
        "수비형 미드필더 배치": { pass: 1.3, goal: 0.7, tackle: 2.1 },

        // 5. 선수 역할 변경
        "윙어 중앙 이동": { pass: 1.2, goal: 1.7, tackle: 0.9 },
        "센터백 전진":    { pass: 1.0, goal: 1.4, tackle: 1.8 },
        "가짜 9번":       { pass: 2.2, goal: 1.6, tackle: 0.8 },

        // 6. 세트피스 전략
        "코너킥 집중": { pass: 1.1, goal: 1.8, tackle: 1.0 },
        "프리킥 패턴": { pass: 1.3, goal: 1.7, tackle: 1.0 },

        // 7. 템포와 시간관리
        "속도 조절": { pass: 1.6, goal: 1.1, tackle: 1.1 },
        "리드 시간 끌기": { pass: 2.0, goal: 0.5, tackle: 1.8 },

        // 8. 마킹 대상 지정
        "상대 핵심선수 봉쇄": { pass: 0.8, goal: 0.8, tackle: 2.6 },

        // 9. 골키퍼 전략
        "골키퍼 공격 가담": { pass: 0.5, goal: 1.2, tackle: 1.0 },
        "빌드업 참여": { pass: 2.0, goal: 0.9, tackle: 1.0 }
    };

    function getPlayerScoreWithTactic(stat, tacticType) {
        if (!stat) return 10;
        const weights = TACTIC_WEIGHTS[tacticType] || TACTIC_WEIGHTS["밸런스"];
        const mins = parseFloat(String(stat["출전시간(분)_출전시간(분)"] || "0").replace(/,/g, '')) || 0;
        const goals = parseFloat(String(stat["득점_득점"] || "0").replace(/,/g, '')) || 0;
        const assists = parseFloat(String(stat["도움_도움"] || "0").replace(/,/g, '')) || 0;
        const passes = parseFloat(String(stat["패스_성공%"] || "0").replace(/,/g, '')) || 0;
        const tackles = parseFloat(String(stat["태클_성공"] || "0").replace(/,/g, '')) || 0;
        const keyPass = parseFloat(String(stat["키패스_키패스"] || "0").replace(/,/g, '')) || 0;

        return (mins * 0.05) + (goals * 40 * weights.goal) + (assists * 30) + (keyPass * 2 * weights.pass) + (tackles * 2 * weights.tackle) + (passes * 0.3 * weights.pass);
    }

    homePlayers = []; //------------------------------------------------------------------------------------------------------
    awayPlayers = [];  //------------------------------------------------------------------------------------------------------
    matchStats = { home: {}, away: {} };

    function initMatchStats(playersArray, isHome) {
        const targetObj = isHome ? matchStats.home : matchStats.away;
        playersArray.forEach(p => {
            targetObj[p.name] = { goals: 0, shots: 0, passes: 0, successPasses: 0 };
        });
    }

    let matchTimerInterval = null;
    let isTimerRunning = false;

    function startMatchTimer() {
        const timerElement = document.getElementById('match-timer');
        if (matchTimerInterval) clearInterval(matchTimerInterval);

        isTimerRunning = true;
        matchTimerInterval = setInterval(() => {
            if (isPlaying) {
                matchSeconds++;
                if (isKickOffPhase) {
                    if (ball.possessor === null && Math.abs(ball.x - PITCH_WIDTH / 2) > 20) {
                        isKickOffPhase = false; 
                    }
                }

                const mins = String(Math.floor(matchSeconds / 60)).padStart(2, '0');
                const secs = String(matchSeconds % 60).padStart(2, '0');
                if (timerElement) timerElement.innerText = `${mins}:${secs}`;
            }
        }, 1000);
    }

    function stopMatchTimer() {
        if (matchTimerInterval) clearInterval(matchTimerInterval);
        isTimerRunning = false;
        const timerElement = document.getElementById('match-timer');
        const finalTimeText = timerElement ? timerElement.innerText : '00:00';
        return `${Math.floor(matchSeconds / 60)}분 ${matchSeconds % 60}초 (${finalTimeText})`;
    }

    function updateTeamOptions(leagueSelect, teamSelect) {
        if (!leagueSelect || !teamSelect) return;
        const selectedLeague = leagueSelect.value;
        const teams = LEAGUE_DATA[selectedLeague] || [];
        teamSelect.innerHTML = '';
        teams.forEach(team => {
            const opt = document.createElement('option');
            opt.value = team;
            opt.textContent = team;
            teamSelect.appendChild(opt);
        });
    }

    function updateScoreboardTeam(isHome) {
        const leagueSelect = isHome ? homeLeagueSelect : awayLeagueSelect;
        const teamSelect = isHome ? homeTeamSelect : awayTeamSelect;
        const nameEl = isHome ? homeTeamNameEl : awayTeamNameEl;
        const logoEl = isHome ? homeLogoEl : awayLogoEl;
        
        if (!leagueSelect || !teamSelect) return;
        const selectedLeague = leagueSelect.value;
        const selectedTeamName = teamSelect.value;

        if (nameEl) nameEl.textContent = selectedTeamName || (isHome ? "홈팀" : "어웨이팀");
        if (selectedTeamName && logoEl && staticBaseUrl) {
            logoEl.src = `${staticBaseUrl}${selectedLeague}/구단마크/${selectedTeamName}.png`;
            logoEl.style.display = 'block';
            logoEl.onerror = () => { logoEl.style.display = 'none'; };
        }
    }

    function drawRadarChart(metrics) {
        const rCanvas = document.getElementById('radarCanvas');
        if (!rCanvas) return;
        const rCtx = rCanvas.getContext('2d');
        const w = rCanvas.width;
        const h = rCanvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const radius = 60;

        rCtx.clearRect(0, 0, w, h);
        const total = metrics.length;

        for (let level = 1; level <= 4; level++) {
            rCtx.beginPath();
            rCtx.strokeStyle = '#333';
            rCtx.lineWidth = 1;
            const curR = (radius / 4) * level;
            for (let i = 0; i < total; i++) {
                const angle = (Math.PI * 2 / total) * i - Math.PI / 2;
                const x = cx + curR * Math.cos(angle);
                const y = cy + curR * Math.sin(angle);
                if (i === 0) rCtx.moveTo(x, y);
                else rCtx.lineTo(x, y);
            }
            rCtx.closePath();
            rCtx.stroke();
        }

        rCtx.font = '10px sans-serif';
        rCtx.fillStyle = '#bbb';
        rCtx.textAlign = 'center';
        rCtx.textBaseline = 'middle';

        const points = [];
        metrics.forEach((m, i) => {
            const angle = (Math.PI * 2 / total) * i - Math.PI / 2;
            rCtx.beginPath();
            rCtx.strokeStyle = '#333';
            rCtx.moveTo(cx, cy);
            rCtx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
            rCtx.stroke();

            const labelR = radius + 18;
            const lx = cx + labelR * Math.cos(angle);
            const ly = cy + labelR * Math.sin(angle);
            rCtx.fillText(m.label, lx, ly);

            const ratio = Math.min(1, Math.max(0, m.val / m.max));
            const px = cx + radius * ratio * Math.cos(angle);
            const py = cy + radius * ratio * Math.sin(angle);
            points.push({ x: px, y: py });
        });

        rCtx.beginPath();
        points.forEach((p, i) => {
            if (i === 0) rCtx.moveTo(p.x, p.y);
            else rCtx.lineTo(p.x, p.y);
        });
        rCtx.closePath();
        rCtx.fillStyle = 'rgba(25, 118, 210, 0.4)';
        rCtx.fill();
        rCtx.strokeStyle = '#1976d2';
        rCtx.lineWidth = 2;
        rCtx.stroke();

        points.forEach(p => {
            rCtx.beginPath();
            rCtx.arc(p.x, p.y, 3, 0, Math.PI * 2);
            rCtx.fillStyle = '#90caf9';
            rCtx.fill();
        });
    }

    function openPlayerModal(playerRecord, photoPath, statRecord, role) {
        if (!modal) return;
        modalThumb.src = photoPath;
        modalThumb.onerror = () => { modalThumb.onerror = null; modalThumb.src = placeholderUrl; };
        modalName.textContent = playerRecord.성명;
        modalSub.textContent = `No. ${playerRecord.등번 || '-'} | 포지션: ${role}`;
        modalClub.textContent = playerRecord["소속 클럽"] || "-";
        modalHW.textContent = `${playerRecord["키"] || '-'} / ${playerRecord["몸무게"] || '-'}`;
        modalBirth.textContent = playerRecord["생년월일"] || '-';

        let metrics = [
            { label: '득점', val: parseInt(statRecord["득점_득점"] || 0), max: 12 },
            { label: '도움', val: parseInt(statRecord["도움_도움"] || 0), max: 10 },
            { label: '슈팅', val: parseInt(statRecord["슈팅_슈팅"] || 0), max: 50 },
            { label: '키패스', val: parseInt(statRecord["키패스_키패스"] || 0), max: 30 },
            { label: '패스성공%', val: parseFloat(statRecord["패스_성공%"] || 0), max: 100 },
            { label: '태클성공', val: parseInt(statRecord["태클_성공"] || 0), max: 25 }
        ];

        drawRadarChart(metrics);
        modal.style.display = 'flex';
    }

    async function setupSquad(isHome) {
        const leagueSelect = isHome ? homeLeagueSelect : awayLeagueSelect;
        const teamSelect = isHome ? homeTeamSelect : awayTeamSelect;
        const formationSelect = isHome ? homeFormationSelect : awayFormationSelect;
        const tacticSelect = document.getElementById(isHome ? 'home-tactic-select' : 'away-tactic-select');
        const listEl = document.getElementById(isHome ? 'home-player-list' : 'away-player-list');
        const subListEl = document.getElementById(isHome ? 'home-sub-list' : 'away-sub-list');

        if (!listEl) return;

        const selectedLeague = leagueSelect ? leagueSelect.value : "1부리그";
        const selectedTeam = teamSelect ? teamSelect.value : (isHome ? "강원" : "광주");
        const formationKey = formationSelect ? formationSelect.value : "4-4-2";
        const selectedTactic = tacticSelect ? tacticSelect.value : "밸런스";
        const presets = FORMATION_PRESETS[formationKey] || FORMATION_PRESETS["4-4-2"];
        
        listEl.innerHTML = '';
        if (subListEl) subListEl.innerHTML = '';

        let infoData = [];
        let statsData = [];

        try {
            if (dataUrlBase) {
                const infoRes = await fetch(`${dataUrlBase}${selectedLeague}/${selectedTeam}_선수정보.json`);
                if (infoRes.ok) infoData = await infoRes.json();

                const statsRes = await fetch(`${dataUrlBase}${selectedLeague}/${selectedTeam}_선수성적.json`);
                if (statsRes.ok) statsData = await statsRes.json();
            }
        } catch (e) {
            console.warn("외부 JSON 파일 로드 실패, 기본 선수 데이터로 대체합니다.", e);
        }

        if (!infoData || infoData.length === 0) {
            const positions = ['GK', 'DF', 'DF', 'DF', 'DF', 'MF', 'MF', 'MF', 'MF', 'FW', 'FW', 'GK', 'DF', 'DF', 'MF', 'MF', 'FW', 'FW'];
            infoData = positions.map((pos, idx) => ({
                "성명": `${selectedTeam}선수${idx+1}`,
                "등번": `${idx+1}`,
                "포지션": pos,
                "소속 클럽": selectedTeam,
                "키": "180cm", "몸무게": "75kg", "생년월일": "2000-01-01"
            }));
        }

        infoData = infoData.map(player => ({
            ...player,
            포지션: player.포지션 || player.포자션,
        }));

        infoData.forEach(player => {
            const stat = statsData.find(
                s => s.선수명_선수명 === player.성명
                && String(s.등번호_등번호) === String(player.등번)
            ) || {};
            player.score = getPlayerScoreWithTactic(stat, selectedTactic);
            player.stat = stat;
        });

        const pool = {
            'GK': infoData.filter(p => p.포지션 === 'GK').sort((a, b) => b.score - a.score),
            'DF': infoData.filter(p => p.포지션 === 'DF').sort((a, b) => b.score - a.score),
            'MF': infoData.filter(p => p.포지션 === 'MF').sort((a, b) => b.score - a.score),
            'FW': infoData.filter(p => p.포지션 === 'FW').sort((a, b) => b.score - a.score)
        };

        ['GK', 'DF', 'MF', 'FW'].forEach(pos => {
            if (!pool[pos]) pool[pos] = [];
            while(pool[pos].length < 5) {
                pool[pos].push({ "성명": `${selectedTeam}_${pos}_${pool[pos].length+1}`, "등번": `${Math.floor(Math.random()*90)+10}`, "포지션": pos, "소속 클럽": selectedTeam, "score": 50 });
            }
        });

        const squad = [];
        const color = isHome ? '#ff5252' : '#448aff';
        const selectedNames = new Set();
        const availablePool = {
            'GK': [...pool['GK']], 'DF': [...pool['DF']], 'MF': [...pool['MF']], 'FW': [...pool['FW']]
        };

        presets.forEach((slot, idx) => {
            const role = slot.pos;
            let playerRecord = availablePool[role].shift() || pool[role][0] || { "성명": `선수${idx+1}`, "등번": `${idx+1}`, "포지션": role };
            selectedNames.add(playerRecord.성명);

            const statRecord = playerRecord.stat || {};
            let posX = slot.x;
            let posY = slot.y;
            if (!isHome) posX = PITCH_WIDTH - slot.x;

            const photoPath = staticBaseUrl ? `${staticBaseUrl}${selectedLeague}/${selectedTeam}/${playerRecord.성명}.png` : '';
            squad.push(new PlayerController(posX, posY, color, playerRecord.등번 || idx+1, playerRecord.성명, role, photoPath, isHome));

            const card = document.createElement('div');
            card.className = `player-card ${isHome ? '' : 'away'}`;
            card.innerHTML = `
                <img src="${photoPath}" class="player-thumb" onerror="this.onerror=null;this.src='${placeholderUrl}'">
                <div class="player-info">
                    <div class="player-main-text">No.${playerRecord.등번 || idx+1} ${playerRecord.성명} (${role})</div>
                    <div class="player-sub-text">적합도: ${Math.round(playerRecord.score || 0)}점</div>
                </div>
                <span class="badge-pos pos-${role.toLowerCase()}">선발</span>
            `;
            card.addEventListener('click', () => { openPlayerModal(playerRecord, photoPath, statRecord, role); });
            listEl.appendChild(card);
        });

        if (subListEl) {
            const subReqs = { 'GK': 1, 'DF': 2, 'MF': 2, 'FW': 2 };
            Object.keys(subReqs).forEach(pos => {
                const candidates = (pool[pos] || []).filter(p => !selectedNames.has(p.성명));
                candidates.slice(0, subReqs[pos]).forEach(subP => {
                    selectedNames.add(subP.성명);
                    const subStat = subP.stat || {};
                    const subPhotoPath = staticBaseUrl ? `${staticBaseUrl}${selectedLeague}/${selectedTeam}/${subP.성명}.png` : '';

                    const subCard = document.createElement('div');
                    subCard.className = `player-card substitute ${isHome ? '' : 'away'}`;
                    subCard.innerHTML = `
                        <img src="${subPhotoPath}" class="player-thumb" onerror="this.onerror=null;this.src='${placeholderUrl}'">
                        <div class="player-info">
                            <div class="player-main-text">No.${subP.등번 || '0'} ${subP.성명} (${pos})</div>
                            <div class="player-sub-text">후보 | 적합도: ${Math.round(subP.score || 0)}점</div>
                        </div>
                        <span class="badge-pos pos-${pos.toLowerCase()}">후보</span>
                    `;
                    subCard.addEventListener('click', () => { openPlayerModal(subP, subPhotoPath, subStat, pos); });
                    subListEl.appendChild(subCard);
                });
            });
        }

        if (isHome) homePlayers = squad;
        else awayPlayers = squad;
    }

    updateTeamOptions(homeLeagueSelect, homeTeamSelect);
    updateTeamOptions(awayLeagueSelect, awayTeamSelect);
    if (awayLeagueSelect) awayLeagueSelect.value = "2부리그";
    updateTeamOptions(awayLeagueSelect, awayTeamSelect);

    updateScoreboardTeam(true);
    updateScoreboardTeam(false);

    Promise.all([setupSquad(true), setupSquad(false)]).catch(err => {
        console.error("스쿼드 초기화 오류:", err);
    });

    if (homeLeagueSelect) homeLeagueSelect.addEventListener('change', () => { updateTeamOptions(homeLeagueSelect, homeTeamSelect); updateScoreboardTeam(true); setupSquad(true); });
    if (homeTeamSelect) homeTeamSelect.addEventListener('change', () => { updateScoreboardTeam(true); setupSquad(true); });
    if (homeFormationSelect) homeFormationSelect.addEventListener('change', () => setupSquad(true));
    if (homeTacticSelect) homeTacticSelect.addEventListener('change', () => {
    // 전술은 실시간으로 반영되므로 별도의 스쿼드 재로딩이 필요 없습니다.
    });

    if (awayLeagueSelect) awayLeagueSelect.addEventListener('change', () => { 
        updateTeamOptions(awayLeagueSelect, awayTeamSelect); 
        updateScoreboardTeam(false); 
        setupSquad(false); 
    });
    if (awayTeamSelect) awayTeamSelect.addEventListener('change', () => { updateScoreboardTeam(false); setupSquad(false); });
    if (awayFormationSelect) awayFormationSelect.addEventListener('change', () => setupSquad(false));
    if (awayTacticSelect) awayTacticSelect.addEventListener('change', () => {
    // 전술은 실시간으로 반영되므로 별도의 스쿼드 재로딩이 필요 없습니다.
    });

    const bgImageInput = document.getElementById('bg-img-path');
    const pitchImage = new Image();
    let imageLoaded = false;
    
    if (bgImageInput && bgImageInput.value) {
        pitchImage.src = bgImageInput.value;
        pitchImage.onload = () => { imageLoaded = true; };
        pitchImage.onerror = () => { imageLoaded = false; };
    }

    // ⚽ 메인 애니메이션 루프
    function animate() {
        if (!ctx) return;
        
        // 📌 1. 경기장 잔디/라인 렌더링
        pitchGeo.draw(ctx, pitchImage, imageLoaded);

        const allPlayers = [...homePlayers, ...awayPlayers];

        if (isPlaying) {
            // 📌 2. 공 물리 엔진 연산 실행
            ball.updatePhysics();

            if (Math.abs(ball.x - PITCH_WIDTH / 2) > 40 || ball.possessor !== null) {
                isKickOffPhase = false;
            }

            let closestPlayer = allPlayers[0];
            let minDescDist = Infinity;

            allPlayers.forEach(p => {
                if (!p.isRedCarded) {
                    let d = Math.hypot(ball.x - p.x, ball.y - p.y);
                    if (d < minDescDist) {
                        minDescDist = d;
                        closestPlayer = p;
                    }
                }
            });

            // 인터셉트 연산
            if (ball.vx !== 0 || ball.vy !== 0) {
                allPlayers.forEach(p => {
                    if (!p.isRedCarded && p !== ball.possessor) {
                        let distToBall = Math.hypot(ball.x - p.x, ball.y - p.y);
                        if (distToBall < 18 && Math.random() < 0.08) { 
                            ball.possessor = p;
                            ball.vx = 0; ball.vy = 0;
                            lastTouchIsHome = p.isHome;
                            
                            const logs = document.getElementById('match-logs');
                            if (logs) {
                                logs.innerHTML += `<div>[실시간] ⚡ ${p.name} 선수의 날카로운 인터셉트!</div>`;
                                logs.scrollTop = logs.scrollHeight;
                            }
                        }
                    }
                });
            }

            // 파울 및 카드 판정
            allPlayers.forEach(p1 => {
                if (p1.state === 'CHASING' && !p1.isRedCarded) {
                    allPlayers.forEach(p2 => {
                        if (p1.isHome !== p2.isHome && p2.state === 'POSSESSING') {
                            let d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
                            if (d < 15) {
                                let foulChance = 0.03 * (1 - p1.stamina / 100);
                                if (Math.random() < foulChance) {
                                    ball.possessor = p2;
                                    ball.vx = 0; ball.vy = 0;
                                    
                                    let cardRoll = Math.random();
                                    const logs = document.getElementById('match-logs');
                                    
                                    if (cardRoll < 0.15) {
                                        p1.yellowCards++;
                                        if (p1.yellowCards >= 2) {
                                            p1.isRedCarded = true;
                                            if (logs) logs.innerHTML += `<div style="color:#f44336">[파울] 🟨🟨 경고 누적으로 ${p1.name} 선수 퇴장!</div>`;
                                        } else {
                                            if (logs) logs.innerHTML += `<div style="color:#ffeb3b">[파울] 🟨 ${p1.name} 선수 거친 태클로 옐로 카드!</div>`;
                                        }
                                    } else {
                                        if (logs) logs.innerHTML += `<div>[파울] 📢 주심의 휘슬! ${p1.name} 선수의 파울 선언</div>`;
                                    }
                                }
                            }
                        }
                    });
                }
            });

            if (minDescDist < 30 && !ball.possessor && !isKickOffPhase) {
                ball.possessor = closestPlayer;
                lastTouchIsHome = closestPlayer.isHome;
            }

            if (ball.possessor) {
                let passer = ball.possessor;
                let targetGoalX = passer.isHome ? PITCH_WIDTH - 80 : 80;
                
                if (Math.hypot(targetGoalX - passer.x, (PITCH_HEIGHT / 2) - passer.y) < 160) {
                    let shootVx = passer.isHome ? 12 : -12;
                    let shootVy = (Math.random() - 0.5) * 5;
                    ball.kick(shootVx, shootVy, 2.5);
                }
            }
        }

        // 📌 3. 🌟 [수정 완료] animate() 내부에서 매 프레임 실시간 전술 지침(Context) 산출 및 선수 업데이트 연동
        const homeTactic = homeTacticSelect ? homeTacticSelect.value : '밸런스';
        const awayTactic = awayTacticSelect ? awayTacticSelect.value : '밸런스';

        const homeTacticalContext = tacticalEngine.evaluateContext(homeTactic, true, matchSeconds, homeGoalsTotal, awayGoalsTotal);
        const awayTacticalContext = tacticalEngine.evaluateContext(awayTactic, false, matchSeconds, homeGoalsTotal, awayGoalsTotal);

        homePlayers.forEach(player => {
            player.update(ball, allPlayers, PITCH_WIDTH, PITCH_HEIGHT, isPlaying, isKickOffPhase, homeTactic, homeTacticalContext);
        });
        awayPlayers.forEach(player => {
            player.update(ball, allPlayers, PITCH_WIDTH, PITCH_HEIGHT, isPlaying, isKickOffPhase, awayTactic, awayTacticalContext);
        });

        if (isPlaying) {
            // 📌 4. 룰 엔진 업데이트 및 득점/아웃 판정
            ball = ruleEngine.updateBallPhysics(ball);

            // 🌟 [수정 완료] PITCH_WIDTH와 PITCH_HEIGHT 인자를 정확히 전달합니다.
            const outcome = ruleEngine.checkBallOutAndOutcome(ball.x, ball.y, lastTouchIsHome, PITCH_WIDTH, PITCH_HEIGHT);
            
            if (outcome.status === 'GOAL') {
                let concedingTeamIsHome = true;

                if (outcome.team === 'HOME') {
                    homeGoalsTotal++;
                    if (homeScoreEl) homeScoreEl.textContent = homeGoalsTotal;
                    concedingTeamIsHome = false;
                } else {
                    awayGoalsTotal++;
                    if (awayScoreEl) awayScoreEl.textContent = awayGoalsTotal;
                    concedingTeamIsHome = true;
                }

                const logs = document.getElementById('match-logs');
                if (logs) {
                    logs.innerHTML += `<div>[${document.getElementById('match-timer').innerText}] ⚽ <strong>[공식 득점 성립!]</strong> ${outcome.team}팀 골 성공! (${homeGoalsTotal}:${awayGoalsTotal})</div>`;
                    logs.scrollTop = logs.scrollHeight;
                }

                ball.reset(PITCH_WIDTH / 2, PITCH_HEIGHT / 2);

                const targetTeamPlayers = concedingTeamIsHome ? homePlayers : awayPlayers;
                const restartPlayer = targetTeamPlayers.find(p => p.role === 'FW') || targetTeamPlayers[0];
                
                if (restartPlayer) {
                    restartPlayer.x = (PITCH_WIDTH / 2) + (concedingTeamIsHome ? -15 : 15);
                    restartPlayer.y = PITCH_HEIGHT / 2;
                    ball.possessor = restartPlayer;
                    lastTouchIsHome = concedingTeamIsHome;
                }

                isKickOffPhase = true; 
            } 
            else if (outcome.status === 'BALL_OUT_TOUCHLINE' || outcome.status === 'BALL_OUT_GOAL_LINE') {
                ball.reset(outcome.restartX, outcome.restartY);
            }
        }

        // 공 소유자 추적
        if (ball.possessor) {
            ball.x = ball.possessor.x + (ball.possessor.isHome ? 12 : -12);
            ball.y = ball.possessor.y;
            ball.z = 0;
            ball.vx = 0; ball.vy = 0;
        }

        // 📌 5. Y축 깊이에 따른 정렬 및 렌더링
        let renderList = [...allPlayers, ball];
        renderList.sort((a, b) => a.y - b.y);
        renderList.forEach(obj => {
            if (obj instanceof Ball || (obj.constructor && obj.constructor.name === 'Ball')) {
                obj.draw(ctx);
            } else {
                obj.draw(ctx, ball.possessor === obj);
            }
        });

        requestAnimationFrame(animate);
    }

    const btnStart = document.getElementById('btn-start');
    if (btnStart) {
        btnStart.addEventListener('click', () => {
            if (homePlayers.length !== 11 || awayPlayers.length !== 11) {
                const logs = document.getElementById('match-logs');
                if (logs) {
                    logs.textContent = '양 팀 선수 명단을 불러온 뒤 경기 시작을 눌러 주세요.';
                }
                return;
            }
            isPlaying = !isPlaying;
            btnStart.innerText = isPlaying ? '경기 일시정지' : '경기 시작';
            if (isPlaying) {
                if (!isTimerRunning) startMatchTimer();
                if (matchSeconds === 0) {
                    homeGoalsTotal = 0; awayGoalsTotal = 0;
                    if (homeScoreEl) homeScoreEl.textContent = '0';
                    if (awayScoreEl) awayScoreEl.textContent = '0';
                    initMatchStats(homePlayers, true);
                    initMatchStats(awayPlayers, false);
                    
                    // 📌 중앙 킥오프 재설정 (Ball.reset 활용)
                    ball.reset(PITCH_WIDTH / 2, PITCH_HEIGHT / 2);
                    
                    // ⚽ [축구룰] 시작은 항상 홈팀의 공격(센터 포워드)으로 설정
                    const kickoffPlayer = homePlayers.find(p => p.role === 'FW') || homePlayers[0];
                    if (kickoffPlayer) {
                        kickoffPlayer.x = (PITCH_WIDTH / 2) - 15;
                        kickoffPlayer.y = PITCH_HEIGHT / 2;
                        ball.possessor = kickoffPlayer; 
                        lastTouchIsHome = true;
                    }

                    isKickOffPhase = true;

                    const logs = document.getElementById('match-logs');
                    if (logs) logs.innerHTML += `<div>[00:00] 킥오프! 센터 공격수가 동료에게 백패스를 연결합니다.</div>`;
                }
            }
        });
    }

    const btnEnd = document.getElementById('btn-end');
    if (btnEnd) {
        btnEnd.addEventListener('click', async () => {
            isPlaying = false;
            if (btnStart) btnStart.innerText = '경기 시작';
            const finalPlayTime = stopMatchTimer();

            const homeLeague = homeLeagueSelect ? homeLeagueSelect.value : "1부리그";
            const awayLeague = awayLeagueSelect ? awayLeagueSelect.value : "2부리그";
            const homeTeamName = homeTeamSelect ? homeTeamSelect.value : "강원";
            const awayTeamName = awayTeamSelect ? awayTeamSelect.value : "광주";

            async function fetchTeamStatsJson(league, teamName) {
                try {
                    const res = await fetch(`${dataUrlBase}${league}/구단성적.json`);
                    if (res.ok) {
                        const data = await res.json();
                        const aliases = league === '2부리그'
                            ? {'아산': '충남아산', '청주': '충북청주'}
                            : {};
                        const recordName = aliases[teamName] || teamName;
                        return data.find(
                            item => item['구단_구단'] === recordName
                            && item['년도_년도'] === '2026'
                        ) || data.find(
                            item => item['구단_구단'] === recordName
                        ) || null;
                    }
                } catch (e) {
                    console.warn(`구단 성적 로드 실패`, e);
                }
                return null;
            }

            const homeRecord = await fetchTeamStatsJson(homeLeague, homeTeamName);
            const awayRecord = await fetchTeamStatsJson(awayLeague, awayTeamName);

            function getVal(rec, key, fallback) {
                if (!rec || rec[key] === undefined || rec[key] === null || rec[key] === '') {
                    return fallback;
                }
                const value = parseFloat(String(rec[key]).replace(/,/g, ''));
                return Number.isFinite(value) ? value : fallback;
            }

            const homeMetrics = {
                goals: homeGoalsTotal,
                shots: getVal(homeRecord, "슈팅_슈팅", 430),
                sog: getVal(homeRecord, "유효 슈팅_유효 슈팅", 148),
                passRate: getVal(homeRecord, "패스_성공%", 80.8),
                keyPass: getVal(homeRecord, "키패스_키패스", 310),
                crossRate: getVal(homeRecord, "크로스_성공%", 21.2),
                tackle: getVal(homeRecord, "태클_성공", 226),
                intercept: getVal(homeRecord, "인터셉트_인터셉트", 333)
            };

            const awayMetrics = {
                goals: awayGoalsTotal,
                shots: getVal(awayRecord, "슈팅_슈팅", 316),
                sog: getVal(awayRecord, "유효 슈팅_유효 슈팅", 113),
                passRate: getVal(awayRecord, "패스_성공%", 85.0),
                keyPass: getVal(awayRecord, "키패스_키패스", 237),
                crossRate: getVal(awayRecord, "크로스_성공%", 23.3),
                tackle: getVal(awayRecord, "태클_성공", 184),
                intercept: getVal(awayRecord, "인터셉트_인터셉트", 266)
            };

            function findMVP(playersArray, statsObj) {
                if (!playersArray || playersArray.length === 0) return { name: "미등록", number: "0" };
                let bestP = playersArray[0];
                let maxScore = -1;
                playersArray.forEach(p => {
                    const st = statsObj && statsObj[p.name] ? statsObj[p.name] : { goals: 0, shots: 1 };
                    const score = (st.goals * 50) + (st.shots * 10);
                    if (score > maxScore) { maxScore = score; bestP = p; }
                });
                return bestP;
            }

            const homeMVP = findMVP(homePlayers, matchStats.home);
            const awayMVP = findMVP(awayPlayers, matchStats.away);

            const hEmblem = document.getElementById('modal-home-emblem');
            if (hEmblem) { hEmblem.src = `${staticBaseUrl}${homeLeague}/구단마크/${homeTeamName}.png`; hEmblem.onerror = function() { this.style.display='none'; }; }
            const aEmblem = document.getElementById('modal-away-emblem');
            if (aEmblem) { aEmblem.src = `${staticBaseUrl}${awayLeague}/구단마크/${awayTeamName}.png`; aEmblem.onerror = function() { this.style.display='none'; }; }

            const hNameEl = document.getElementById('modal-home-name');
            if (hNameEl) hNameEl.textContent = homeTeamName;
            const aNameEl = document.getElementById('modal-away-name');
            if (aNameEl) aNameEl.textContent = awayTeamName;

            const hMvpName = document.getElementById('home-mvp-name');
            if (hMvpName) hMvpName.textContent = `${homeMVP.name} (No.${homeMVP.number})`;
            const aMvpName = document.getElementById('away-mvp-name');
            if (aMvpName) aMvpName.textContent = `${awayMVP.name} (No.${awayMVP.number})`;

            const hMvpThumb = document.getElementById('home-mvp-thumb');
            if (hMvpThumb) { hMvpThumb.src = `${staticBaseUrl}${homeLeague}/${homeTeamName}/${homeMVP.name}.png`; hMvpThumb.onerror = function() { this.onerror=null;this.src=placeholderUrl; }; }
            const aMvpThumb = document.getElementById('away-mvp-thumb');
            if (aMvpThumb) { aMvpThumb.src = `${staticBaseUrl}${awayLeague}/${awayTeamName}/${awayMVP.name}.png`; aMvpThumb.onerror = function() { this.onerror=null;this.src=placeholderUrl; }; }

            function updateCompareBar(key, hVal, aVal, isPct = false) {
                const max = Math.max(hVal, aVal, 1);
                const hPct = Math.round((hVal / max) * 100);
                const aPct = Math.round((aVal / max) * 100);

                const hVEl = document.getElementById(`home-val-${key}`);
                const aVEl = document.getElementById(`away-val-${key}`);
                const hBEl = document.getElementById(`home-bar-${key}`);
                const aBEl = document.getElementById(`away-bar-${key}`);

                if (hVEl) hVEl.textContent = hVal + (isPct ? '%' : '');
                if (aVEl) aVEl.textContent = aVal + (isPct ? '%' : '');
                if (hBEl) hBEl.style.width = hPct + '%';
                if (aBEl) aBEl.style.width = aPct + '%';
            }

            updateCompareBar('goal', homeMetrics.goals, awayMetrics.goals);
            updateCompareBar('shots', homeMetrics.shots, awayMetrics.shots);
            updateCompareBar('sog', homeMetrics.sog, awayMetrics.sog);
            updateCompareBar('pass', homeMetrics.passRate, awayMetrics.passRate, true);
            updateCompareBar('keypass', homeMetrics.keyPass, awayMetrics.keyPass);
            updateCompareBar('cross', homeMetrics.crossRate, awayMetrics.crossRate, true);
            updateCompareBar('tackle', homeMetrics.tackle, awayMetrics.tackle);
            updateCompareBar('intercept', homeMetrics.intercept, awayMetrics.intercept);

            const reportTime = document.getElementById('report-match-time');
            if (reportTime) reportTime.textContent = finalPlayTime;

            const logs = document.getElementById('match-logs');
            if (logs) {
                logs.innerHTML += `<div>[종료] 소요시간: ${finalPlayTime} | 스코어 (${homeGoalsTotal}:${awayGoalsTotal}) | 리포트 생성됨</div>`;
                logs.scrollTop = logs.scrollHeight;
            }

            if (statsModal) statsModal.style.display = 'flex';
        });
    }

    const btnNew = document.getElementById('btn-new');
    if (btnNew) {
        btnNew.addEventListener('click', () => {
            if (confirm("모든 구단 설정과 전술을 초기화하고 새로운 경기를 시작하시겠습니까?")) {
                location.reload();
            }
        });
    }

    const btnQuit = document.getElementById('btn-quit');
    if (btnQuit) {
        btnQuit.addEventListener('click', () => {
            if (confirm("게임을 종료하시겠습니까?")) {
                window.close();
                setTimeout(() => { alert("메인페이지로 이동합니다."); }, 100);
                location.href='/';
            }
        });
    }

    // 메인 애니메이션 루프 실행
    animate();
});
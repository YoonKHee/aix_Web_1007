/**
 * ==========================================
 * ⚽ 축구 매니저 시뮬레이터 - 메인 엔진 (script.js)
 * ==========================================
 * - Canvas 역할: 순수 축구 피치, 선수, 공, 파티클 렌더링 전담
 * - Arena 역할: 외곽 광고판, 전광판, 컨트롤러는 HTML/CSS 제어
 */

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const SCREEN_WIDTH = 1120;
const SCREEN_HEIGHT = 500;

// 색상 상수
const COLOR_GRASS_1 = "#228B22";
const COLOR_GRASS_2 = "#289628";
const COLOR_LINE = "#F0F0F0";
const COLOR_HOME = "#0077CC";
const COLOR_AWAY = "#DC143C";
const COLOR_BALL = "#FFFFFF";
const COLOR_GOAL = "#F0F0F0";
const COLOR_NET = "#B4B4B4";

// 축구장 규격 및 스케일링 상수 (1120x500 피치 뷰포트에 최적화)
const SCALE = 8.5;
const PITCH_WIDTH = 105 * SCALE;  // 892.5px
const PITCH_HEIGHT = 52 * SCALE;  // 442px
const PITCH_X = (SCREEN_WIDTH - PITCH_WIDTH) / 2;
const PITCH_Y = (SCREEN_HEIGHT - PITCH_HEIGHT) / 2;
const PITCH_CENTER_X = PITCH_X + PITCH_WIDTH / 2;
const PITCH_CENTER_Y = PITCH_Y + PITCH_HEIGHT / 2;

let gameTacticsData = null;

// JSON 데이터 비동기 로드
async function initGameData() {
    try {
        const response = await fetch('../static/data/t_data.json');
        gameTacticsData = await response.json();
        renderMenuDetails();
        document.getElementById('quickStatus').innerText = "전술판 대기 중 - 원하는 설정을 선택하세요.";
    } catch (e) {
        console.error("데이터 로드 실패:", e);
        gameTacticsData = {
            formations: ["4-4-2", "4-3-3", "3-5-2", "4-2-3-1"],
            tactics: [
                { code: "TIKI_TAKA", label: "티키타카" },
                { code: "GEGENPRESSING", label: "게겐프레싱" },
                { code: "COUNTER", label: "역습" },
                { code: "WING_PLAY", label: "측면돌파" }
            ]
        };
        renderMenuDetails();
    }
}

function getPositionActionRadius(name) {
    if (name.includes("GK")) return 110.0;
    if (name.includes("CB") || name.includes("LB") || name.includes("RB") || name.includes("WB")) return 160.0;
    if (name.includes("CM") || name.includes("DM") || name.includes("AM") || name.includes("LM") || name.includes("RM")) return 240.0;
    if (name.includes("ST") || name.includes("LW") || name.includes("RW")) return 220.0;
    return 180.0;
}

function playSound(type) {
    const statusEl = document.getElementById('quickStatus');
    if (type === "whistle" && statusEl) statusEl.innerText = "🔊 [Sound] 휘슬 울림!";
    else if (type === "goal" && statusEl) statusEl.innerText = "⚽ GOAL!!!! 환호 소리!";
    else if (type === "foul" && statusEl) statusEl.innerText = "🚨 파울 휘슬!";
}

// 1. 파티클 클래스
class Particle {
    constructor(x, y) {
        this.x = x; this.y = y;
        let angle = Math.random() * Math.PI * 2;
        let speed = Math.random() * 5 + 2;
        this.vx = Math.cos(angle) * speed;
        this.vy = Math.sin(angle) * speed;
        this.life = 50;
        this.radius = Math.floor(Math.random() * 4) + 3;
        const colors = ["#FFD700", "#FF4500", "#00FFFF", "#FF1493", "#32CD32", "#FFFFFF"];
        this.color = colors[Math.floor(Math.random() * colors.length)];
    }
    update() { this.x += this.vx; this.y += this.vy; this.vy += 0.15; this.life -= 1; }
    draw(context) {
        if (this.life > 0) {
            context.fillStyle = this.color;
            context.beginPath(); context.arc(this.x, this.y, this.radius, 0, Math.PI * 2); context.fill();
        }
    }
}

// 2. 순수 잔디 경기장 렌더링 클래스
class Pitch {
    constructor() {
        this.width = PITCH_WIDTH; this.height = PITCH_HEIGHT;
        this.x = PITCH_X; this.y = PITCH_Y;
        this.center_x = PITCH_CENTER_X; this.center_y = PITCH_CENTER_Y;
        let goal_w = 7.32 * SCALE; let goal_depth = 2.5 * SCALE;
        this.leftGoal = { x: this.x - goal_depth, y: this.center_y - goal_w / 2, width: goal_depth, height: goal_w };
        this.rightGoal = { x: this.x + this.width, y: this.center_y - goal_w / 2, width: goal_depth, height: goal_w };
    }
    draw(context) {
        // 잔디 그라운드 배경
        let num_stripes = 13; let stripe_width = this.width / num_stripes;
        for (let i = 0; i < num_stripes; i++) {
            context.fillStyle = (i % 2 === 0) ? COLOR_GRASS_1 : COLOR_GRASS_2;
            context.fillRect(this.x + i * stripe_width, this.y, stripe_width, this.height);
        }

        // 라인 드로잉
        context.strokeStyle = COLOR_LINE; context.lineWidth = 3; context.strokeRect(this.x, this.y, this.width, this.height);
        context.beginPath(); context.moveTo(this.center_x, this.y); context.lineTo(this.center_x, this.y + this.height); context.stroke();
        let center_circle_r = 9.15 * SCALE;
        context.beginPath(); context.arc(this.center_x, this.center_y, center_circle_r, 0, Math.PI * 2); context.stroke();
        context.beginPath(); context.arc(this.center_x, this.center_y, 4, 0, Math.PI * 2); context.fillStyle = COLOR_LINE; context.fill();
        
        let box_depth = 16.5 * SCALE; let box_width = 30.0 * SCALE;
        context.strokeRect(this.x, this.center_y - box_width / 2, box_depth, box_width);
        context.strokeRect(this.x + this.width - box_depth, this.center_y - box_width / 2, box_depth, box_width);
        
        this._drawGoalNet(context, this.leftGoal);
        this._drawGoalNet(context, this.rightGoal);
    }
    _drawGoalNet(context, goal) {
        context.strokeStyle = COLOR_GOAL; context.lineWidth = 3; context.strokeRect(goal.x, goal.y, goal.width, goal.height);
        context.strokeStyle = COLOR_NET; context.lineWidth = 1; let step = 8;
        for (let gx = goal.x + step; gx < goal.x + goal.width; gx += step) {
            context.beginPath(); context.moveTo(gx, goal.y); context.lineTo(gx, goal.y + goal.height); context.stroke();
        }
        for (let gy = goal.y + step; gy < goal.y + goal.height; gy += step) {
            context.beginPath(); context.moveTo(goal.x, gy); context.lineTo(goal.x + goal.width, gy); context.stroke();
        }
    }
}

// 3. 공 물리 클래스
class BallPhysics {
    constructor(x, y) {
        this.x = x; this.y = y; this.z = 0.0; this.vz = 0.0; this.vx = 0.0; this.vy = 0.0;
        this.possessor = null; this.kickType = "GROUND";
    }
    applyKick(vx, vy, vz, kickType = "GROUND") {
        this.vx = vx; this.vy = vy; this.vz = vz; this.kickType = kickType; this.possessor = null;
    }
    update(speedMultiplier) {
        if (this.possessor) {
            this.x = this.possessor.x + (this.possessor.team === 'home' ? 10 : -10);
            this.y = this.possessor.y; this.z = 0.0; this.vx = 0.0; this.vy = 0.0; this.vz = 0.0;
        } else {
            this.x += this.vx * speedMultiplier; this.y += this.vy * speedMultiplier; this.z += this.vz * speedMultiplier;
            if (this.z > 0) { this.vz -= 0.35 * speedMultiplier; }
            else { this.z = 0.0; if (this.vz < 0) this.vz = -this.vz * 0.3; }
            let friction = (this.kickType === "PASS") ? Math.pow(0.975, speedMultiplier) : Math.pow(0.96, speedMultiplier);
            this.vx *= friction; this.vy *= friction;
            if (this.x < PITCH_X || this.x > PITCH_X + PITCH_WIDTH) { this.vx *= -0.6; playSound("foul"); }
            if (this.y < PITCH_Y || this.y > PITCH_Y + PITCH_HEIGHT) { this.vy *= -0.6; }
        }
    }
    resetToCenter() {
        this.x = PITCH_CENTER_X; this.y = PITCH_CENTER_Y; this.z = 0.0; this.vx = 0.0; this.vy = 0.0; this.vz = 0.0; this.possessor = null;
    }
    draw(context) {
        let shadowScale = Math.max(3, Math.floor(12 - this.z * 0.15));
        context.fillStyle = "rgba(0, 0, 0, 0.3)";
        context.beginPath(); context.ellipse(this.x, this.y + 6, shadowScale, shadowScale / 2, 0, 0, Math.PI * 2); context.fill();
        let renderY = this.y - this.z;
        context.fillStyle = "#1E1E1E"; context.beginPath(); context.arc(this.x, renderY, 6, 0, Math.PI * 2); context.fill();
        context.fillStyle = COLOR_BALL; context.beginPath(); context.arc(this.x, renderY, 4, 0, Math.PI * 2); context.fill();
    }
}

// 4. 선수 클래스
class Player {
    constructor(x, y, team, name, speed = 2.2, passing = 70, shooting = 70) {
        this.original_base_x = x; this.original_base_y = y;
        this.current_base_y = y;
        this.x = x; this.y = y; this.vx = 0.0; this.vy = 0.0;
        this.team = team; this.name = name;
        this.stat_speed = speed; this.stat_passing = passing; this.stat_shooting = shooting;
        this.stamina = 100.0; this.goals = 0; this.passes_completed = 0; this.interceptions = 0;
        this.switchCooldown = 0;
    }
    calculateIntelligentTarget(ball, tactic, team, phase, opponents, teammates) {
        if (ball.possessor === null && ball.z > 2.0) {
            let timeToLand = ball.z / Math.max(0.1, Math.abs(ball.vz));
            return {
                x: Math.max(PITCH_X + 20, Math.min(PITCH_X + PITCH_WIDTH - 20, ball.x + ball.vx * timeToLand)),
                y: Math.max(PITCH_Y + 20, Math.min(PITCH_Y + PITCH_HEIGHT - 20, ball.y + ball.vy * timeToLand))
            };
        }
        return PositionBehaviorManager.getPositionTarget(this, ball, team, tactic, phase, opponents, teammates);
    }
    moveTowards(targetX, targetY, speedMultiplier, tactic) {
        let dx = targetX - this.x; let dy = targetY - this.y; let dist = Math.hypot(dx, dy);
        let drain = (tactic === "GEGENPRESSING") ? 0.009 : 0.005;
        this.stamina = Math.max(0.0, this.stamina - drain * speedMultiplier);
        let maxSpeed = this.stat_speed * speedMultiplier * (this.stamina < 30 ? 0.55 : 1.0);
        if (dist > 1.0) {
            this.vx += ((dx / dist) * maxSpeed - this.vx) * 0.12;
            this.vy += ((dy / dist) * maxSpeed - this.vy) * 0.12;
        } else { this.vx *= 0.8; this.vy *= 0.8; }
        this.x = Math.max(PITCH_X + 10, Math.min(PITCH_X + PITCH_WIDTH - 10, this.x + this.vx));
        this.y = Math.max(PITCH_Y + 10, Math.min(PITCH_Y + PITCH_HEIGHT - 10, this.y + this.vy));
        
        if (this.switchCooldown > 0) this.switchCooldown--;
    }
    draw(context, hasBall) {
        context.fillStyle = "rgba(0,0,0,0.35)"; context.beginPath(); context.ellipse(this.x, this.y + 3, 8, 4, 0, 0, Math.PI * 2); context.fill();
        context.fillStyle = hasBall ? "#FF8C00" : (this.team === 'home' ? COLOR_HOME : COLOR_AWAY);
        context.strokeStyle = "#141414"; context.lineWidth = 2;
        context.beginPath(); context.arc(this.x, this.y, hasBall ? 10 : 8, 0, Math.PI * 2); context.stroke(); context.fill();
        context.fillStyle = "#323232"; context.fillRect(this.x - 9, this.y - 24, 18, 3);
        context.fillStyle = this.stamina > 40 ? "#00FF00" : "#FF6400"; context.fillRect(this.x - 9, this.y - 24, 18 * (this.stamina / 100.0), 3);
        context.fillStyle = "#FFFFFF"; context.font = "10px 'Pretendard', sans-serif"; context.fillText(this.name, this.x - 12, this.y - 15);
    }
}

// 5. 전술 & 공간 탐색 AI 매니저
class PositionBehaviorManager {
    static getPositionTarget(player, ball, team, tactic, phase, opponents, teammates) {
        let base_x = player.original_base_x;
        let base_y = player.current_base_y;
        let dir_sign = team.isHome ? 1 : -1;
        let action_rad = getPositionActionRadius(player.name);

        if (player.name.includes("GK")) {
            return { x: base_x, y: Math.max(PITCH_CENTER_Y - 40, Math.min(PITCH_CENTER_Y + 40, ball.y)) };
        }

        if (phase === "FINAL_ATTACK" || phase === "CHANCE_CREATION") {
            this.applyPositionSwitching(player, teammates);
        }

        if (ball.possessor === null && ball.z <= 2.0) {
            let distToBall = Math.hypot(ball.x - player.x, ball.y - player.y);
            if (distToBall <= action_rad) {
                return { x: ball.x, y: ball.y };
            }
        }

        let ball_advance_offset = (ball.x - PITCH_CENTER_X) * 0.30 * dir_sign;
        let rawTargetX = base_x + ball_advance_offset;
        let rawTargetY = base_y;

        if (player.name.includes("CB") || player.name.includes("LB") || player.name.includes("RB") || player.name.includes("WB")) {
            let maxDefensiveLimit = team.isHome ? PITCH_CENTER_X + 25 : PITCH_CENTER_X - 25;
            rawTargetX = Math.min(team.isHome ? maxDefensiveLimit : PITCH_X + PITCH_WIDTH - 20, 
                         Math.max(PITCH_X + 20, dynamicLimit(base_x + ball_advance_offset * 0.6, team.isHome)));
            
            function dynamicLimit(val, isH) {
                return isH ? Math.min(val, PITCH_CENTER_X - 10) : Math.max(val, PITCH_CENTER_X + 10);
            }
        } else if (player.name.includes("CM") || player.name.includes("DM") || player.name.includes("AM") || player.name.includes("LM") || player.name.includes("RM")) {
            let shift_y = (ball.y - PITCH_CENTER_Y) * 0.22;
            rawTargetX = base_x + ball_advance_offset * 0.85;
            rawTargetY = base_y + shift_y;
        } else if (player.name.includes("ST") || player.name.includes("LW") || player.name.includes("RW")) {
            let attackPush = phase === "FINAL_ATTACK" ? 70 : 35;
            rawTargetX = base_x + ball_advance_offset + (dir_sign * attackPush);
            rawTargetY = base_y + (ball.y - PITCH_CENTER_Y) * 0.18;
        }

        let smartTarget = this.detectEmptySpace(player, rawTargetX, rawTargetY, opponents);
        
        return {
            x: rawTargetX * 0.70 + smartTarget.x * 0.30,
            y: rawTargetY * 0.70 + smartTarget.y * 0.30
        };
    }

    static applyPositionSwitching(player, teammates) {
        if (player.switchCooldown > 0 || !teammates) return;

        teammates.forEach(partner => {
            if (partner === player || partner.switchCooldown > 0 || partner.name.includes("GK")) return;
            
            let isWingCombination = (player.name.includes("LB") && partner.name.includes("LM")) || 
                                   (player.name.includes("RB") && partner.name.includes("RM")) ||
                                   (player.name.includes("ST1") && partner.name.includes("ST2"));

            if (isWingCombination) {
                let dist = Math.hypot(player.x - partner.x, player.y - partner.y);
                if (dist < 40 && Math.random() < 0.05) {
                    let tempY = player.current_base_y;
                    player.current_base_y = partner.current_base_y;
                    partner.current_base_y = tempY;

                    player.switchCooldown = 300;
                    partner.switchCooldown = 300;
                    document.getElementById('quickStatus').innerText = `🔄 [${player.name}] ↔ [${partner.name}] 전술적 포지션 스위칭!`;
                }
            }
        });
    }

    static detectEmptySpace(player, targetX, targetY, opponents) {
        if (!opponents || opponents.length === 0) return { x: targetX, y: targetY };

        let bestX = targetX;
        let bestY = targetY;
        let maxSpaceDist = 0;

        const angles = [0, 45, 90, 135, 180, 225, 270, 315];
        const searchRadius = 35.0;

        angles.forEach(deg => {
            let rad = (deg * Math.PI) / 180;
            let checkX = targetX + Math.cos(rad) * searchRadius;
            let checkY = targetY + Math.sin(rad) * searchRadius;

            let minOppDist = opponents.reduce((min, opp) => {
                let d = Math.hypot(opp.x - checkX, opp.y - checkY);
                return d < min ? d : min;
            }, 9999);

            if (minOppDist > maxSpaceDist) {
                maxSpaceDist = minOppDist;
                bestX = checkX;
                bestY = checkY;
            }
        });

        return {
            x: targetX * 0.5 + bestX * 0.5,
            y: targetY * 0.5 + bestY * 0.5
        };
    }
}

class DecisionEngine {
    static selectPassReceiver(passer, teammates, opponents) {
        if (!teammates || teammates.length === 0) return null;
        let action_rad = getPositionActionRadius(passer.name);
        let valid = teammates.filter(p => Math.hypot(p.x - passer.x, p.y - passer.y) <= action_rad);
        let pool = valid.length > 0 ? valid : teammates;
        return pool.reduce((prev, curr) => Math.hypot(curr.x - passer.x, curr.y - passer.y) < Math.hypot(prev.x - passer.x, prev.y - passer.y) ? curr : prev);
    }
    static evaluateShot(passer, distToGoal) {
        return distToGoal < 420 && Math.random() < (0.45 + passer.stat_shooting / 240.0);
    }
}

class Team {
    constructor(isHome = true, formation = "4-4-2", tactic = "TIKI_TAKA") {
        this.isHome = isHome; this.formation = formation; this.tactic = tactic;
        let px = isHome ? PITCH_X + 35 : PITCH_X + PITCH_WIDTH - 35;
        let dirSign = isHome ? 1 : -1;
        let teamStr = isHome ? 'home' : 'away';
        let prefix = isHome ? 'H' : 'A';
        this.starters = this._createStarters(px, dirSign, teamStr, prefix, formation);
        this.bench = [
            new Player(px, PITCH_CENTER_Y, teamStr, `${prefix}-SUB1`, 2.3, 75, 70),
            new Player(px, PITCH_CENTER_Y, teamStr, `${prefix}-SUB2`, 2.2, 72, 72),
            new Player(px, PITCH_CENTER_Y, teamStr, `${prefix}-SUB3`, 2.4, 70, 75),
        ];
        this.subsLeft = 3;
    }
    _createStarters(px, dirSign, teamStr, prefix, formation) {
        let gk = new Player(px + dirSign * 15, PITCH_CENTER_Y, teamStr, `${prefix}-GK`, 1.8, 60, 30);
        return [
            gk,
            new Player(px + dirSign * 80, PITCH_CENTER_Y - 140, teamStr, `${prefix}-LB`, 2.3, 72, 45),
            new Player(px + dirSign * 60, PITCH_CENTER_Y - 45, teamStr, `${prefix}-CB1`, 2.0, 68, 40),
            new Player(px + dirSign * 60, PITCH_CENTER_Y + 45, teamStr, `${prefix}-CB2`, 2.0, 68, 40),
            new Player(px + dirSign * 80, PITCH_CENTER_Y + 140, teamStr, `${prefix}-RB`, 2.3, 72, 45),
            new Player(px + dirSign * 180, PITCH_CENTER_Y - 150, teamStr, `${prefix}-LM`, 2.4, 78, 65),
            new Player(px + dirSign * 150, PITCH_CENTER_Y - 50, teamStr, `${prefix}-CM1`, 2.1, 85, 60),
            new Player(px + dirSign * 150, PITCH_CENTER_Y + 50, teamStr, `${prefix}-CM2`, 2.1, 85, 60),
            new Player(px + dirSign * 180, PITCH_CENTER_Y + 150, teamStr, `${prefix}-RM`, 2.4, 78, 65),
            new Player(px + dirSign * 300, PITCH_CENTER_Y - 35, teamStr, `${prefix}-ST1`, 2.3, 70, 88),
            new Player(px + dirSign * 300, PITCH_CENTER_Y + 35, teamStr, `${prefix}-ST2`, 2.3, 70, 88),
        ];
    }
}

let pitch = new Pitch();
let ball = new BallPhysics(PITCH_CENTER_X, PITCH_CENTER_Y);
let homeTeam = new Team(true, "4-4-2", "TIKI_TAKA");
let awayTeam = new Team(false, "4-4-2", "TIKI_TAKA");
let allPlayers = [...homeTeam.starters, ...awayTeam.starters];
let particles = [];

let gameState = "MENU";
let matchTime = 0.0; let homeScore = 0; let awayScore = 0;
let isPaused = false;
const speedLevels = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0];
let speedIdx = 1;
let matchDuration = 120.0;

function updateScreenState() {
    document.getElementById('menuScreen').classList.toggle('hidden', gameState !== "MENU");
    document.getElementById('lockerScreen').classList.toggle('hidden', gameState !== "LOCKER_ROOM");
    document.getElementById('summaryScreen').classList.toggle('hidden', gameState !== "SUMMARY");

    if (gameState === "MENU") {
        renderMenuDetails();
    } else if (gameState === "LOCKER_ROOM") {
        renderLockerDetails();
    } else if (gameState === "SUMMARY") {
        // 최종 스코어 표기
        document.getElementById('finalScoreText').innerText = `HOME ${homeScore} : ${awayScore} AWAY`;
        
        // 실제 진행된 경기 시간(초 -> 분/초 변환) 계산 및 표기
        let totalSeconds = Math.floor(matchTime);
        let minutes = Math.floor(totalSeconds / 60);
        let seconds = totalSeconds % 60;
        let formattedTime = `${String(minutes).padStart(2, '0')}분 ${String(seconds).padStart(2, '0')}초`;
        
        document.getElementById('finalPlayTimeText').innerText = `⏱️ 총 플레이 시간: ${formattedTime} (${totalSeconds}초 / 설정: ${Math.floor(matchDuration)}초)`;
    }
}

function renderMenuDetails() {
    document.getElementById('homeTitle').innerText = `🏠 홈 팀 선발 명단 (${homeTeam.formation})`;
    document.getElementById('awayTitle').innerText = `✈️ 원정 팀 선발 명단 (${awayTeam.formation})`;

    document.getElementById('homeStartersList').innerHTML = homeTeam.starters.map(p => 
        `<div>[${p.name}] 속도:${p.stat_speed} 패스:${p.stat_passing} 슛:${p.stat_shooting}</div>`
    ).join('');

    document.getElementById('awayStartersList').innerHTML = awayTeam.starters.map(p => 
        `<div>[${p.name}] 속도:${p.stat_speed} 패스:${p.stat_passing} 슛:${p.stat_shooting}</div>`
    ).join('');

    if (!gameTacticsData) return;

    document.getElementById('homeFormBtns').innerHTML = gameTacticsData.formations.map(f => 
        `<button onclick="changeHomeFormation('${f}')" class="px-2.5 py-1 rounded text-[10px] font-bold ${homeTeam.formation === f ? 'bg-sky-600 text-white' : 'bg-gray-800 text-gray-300'}">${f}</button>`
    ).join('');

    document.getElementById('homeTacticBtns').innerHTML = gameTacticsData.tactics.map(t => 
        `<button onclick="changeHomeTactic('${t.code}')" class="px-2.5 py-1 rounded text-[10px] font-bold ${homeTeam.tactic === t.code ? 'bg-sky-600 text-white' : 'bg-gray-800 text-gray-300'}">${t.label}</button>`
    ).join('');

    document.getElementById('awayFormBtns').innerHTML = gameTacticsData.formations.map(f => 
        `<button onclick="changeAwayFormation('${f}')" class="px-2.5 py-1 rounded text-[10px] font-bold ${awayTeam.formation === f ? 'bg-sky-600 text-white' : 'bg-gray-800 text-gray-300'}">${f}</button>`
    ).join('');

    document.getElementById('awayTacticBtns').innerHTML = gameTacticsData.tactics.map(t => 
        `<button onclick="changeAwayTactic('${t.code}')" class="px-2.5 py-1 rounded text-[10px] font-bold ${awayTeam.tactic === t.code ? 'bg-sky-600 text-white' : 'bg-gray-800 text-gray-300'}">${t.label}</button>`
    ).join('');
}

window.changeHomeFormation = (form) => {
    homeTeam = new Team(true, form, homeTeam.tactic);
    allPlayers = [...homeTeam.starters, ...awayTeam.starters];
    renderMenuDetails();
    document.getElementById('quickStatus').innerText = `홈 팀 포메이션 변경: [${form}]`;
};
window.changeHomeTactic = (tactic) => {
    homeTeam.tactic = tactic;
    renderMenuDetails();
    document.getElementById('quickStatus').innerText = `홈 팀 전술 변경: [${tactic}]`;
};
window.changeAwayFormation = (form) => {
    awayTeam = new Team(false, form, awayTeam.tactic);
    allPlayers = [...homeTeam.starters, ...awayTeam.starters];
    renderMenuDetails();
    document.getElementById('quickStatus').innerText = `원정 팀 포메이션 변경: [${form}]`;
};
window.changeAwayTactic = (tactic) => {
    awayTeam.tactic = tactic;
    renderMenuDetails();
    document.getElementById('quickStatus').innerText = `원정 팀 전술 변경: [${tactic}]`;
};

function renderLockerDetails() {
    const makeTableHTML = (starters) => starters.map(p => 
        `<div>${p.name.padEnd(8)} | 체력:${p.stamina.toFixed(0)}% | 패스:${p.passes_completed} | 득점:${p.goals}</div>`
    ).join('');

    document.getElementById('lockerHomeTable').innerHTML = makeTableHTML(homeTeam.starters);
    document.getElementById('lockerAwayTable').innerHTML = makeTableHTML(awayTeam.starters);
}

// 이벤트 리스너 바인딩
document.getElementById('btnStartMatch').addEventListener('click', () => {
    gameState = "MATCH";
    playSound("whistle");
    ball.x = PITCH_CENTER_X; ball.y = PITCH_CENTER_Y;
    ball.possessor = homeTeam.starters[homeTeam.starters.length - 1];
    document.getElementById('quickStatus').innerText = "⚽ 킥오프! Stadium Arena 엔진 가동.";
    updateScreenState();
});

document.getElementById('btnOpenLockerMenu').addEventListener('click', () => {
    gameState = "LOCKER_ROOM";
    updateScreenState();
});

document.getElementById('btnMatchPause').addEventListener('click', () => {
    isPaused = !isPaused;
    document.getElementById('btnMatchPause').innerText = isPaused ? "▶️ 재개" : "⏸️ 정지";
});

document.getElementById('btnSpeedDown').addEventListener('click', () => { if (speedIdx > 0) speedIdx--; });
document.getElementById('btnSpeedUp').addEventListener('click', () => { if (speedIdx < speedLevels.length - 1) speedIdx++; });

document.getElementById('btnMatchLocker').addEventListener('click', () => {
    gameState = "LOCKER_ROOM";
    updateScreenState();
});

document.getElementById('btnMatchSub').addEventListener('click', () => {
    if (homeTeam.subsLeft > 0 && homeTeam.bench.length > 0) {
        let fieldPlayers = homeTeam.starters.filter(p => !p.name.includes("GK"));
        if (fieldPlayers.length > 0) {
            let tiredPlayer = fieldPlayers.reduce((prev, curr) => curr.stamina < prev.stamina ? curr : prev);
            let subPlayer = homeTeam.bench.shift();
            subPlayer.x = tiredPlayer.x; subPlayer.y = tiredPlayer.y;
            subPlayer.original_base_x = tiredPlayer.original_base_x;
            subPlayer.original_base_y = tiredPlayer.original_base_y;
            subPlayer.current_base_y = tiredPlayer.current_base_y;
            let idx = homeTeam.starters.indexOf(tiredPlayer);
            homeTeam.starters[idx] = subPlayer;
            allPlayers = [...homeTeam.starters, ...awayTeam.starters];
            homeTeam.subsLeft--;
            document.getElementById('quickStatus').innerText = `🔄 감독 선수 교체: [${tiredPlayer.name}] OUT -> [${subPlayer.name}] IN`;
        }
    } else {
        document.getElementById('quickStatus').innerText = "❌ 교체 불가 (잔여 횟수 소진)";
    }
});

document.getElementById('btnMatchEnd').addEventListener('click', () => {
    gameState = "SUMMARY";
    playSound("whistle");
    document.getElementById('quickStatus').innerText = "🏁 감독 권한으로 경기가 종료되었습니다.";
    updateScreenState();
});

document.getElementById('btnCloseLocker').addEventListener('click', () => {
    gameState = (matchTime > 0) ? "MATCH" : "MENU";
    updateScreenState();
});

// 기존 btnRestart 버튼 이벤트: 전술판(메뉴)으로 복귀하여 새로운 게임 준비
document.getElementById('btnRestart').addEventListener('click', () => {
    pitch = new Pitch();
    ball = new BallPhysics(PITCH_CENTER_X, PITCH_CENTER_Y);
    homeTeam = new Team(true, "4-4-2", "TIKI_TAKA");
    awayTeam = new Team(false, "4-4-2", "TIKI_TAKA");
    allPlayers = [...homeTeam.starters, ...awayTeam.starters];
    particles = []; 
    matchTime = 0.0; 
    homeScore = 0; 
    awayScore = 0;
    isPaused = false; 
    gameState = "MENU";
    document.getElementById('quickStatus').innerText = "전술판 대기 중 - 새로운 게임 설정을 선택하세요.";
    updateScreenState();
});

// ❌ '게임 종료' 버튼 클릭 시 모든 창을 닫고 호출한 URL로 복귀
document.getElementById('btnExitGame').addEventListener('click', () => {
    // 1. 경기 데이터 및 전역 변수 초기화
    pitch = new Pitch();
    ball = new BallPhysics(PITCH_CENTER_X, PITCH_CENTER_Y);
    homeTeam = new Team(true, "4-4-2", "TIKI_TAKA");
    awayTeam = new Team(false, "4-4-2", "TIKI_TAKA");
    allPlayers = [...homeTeam.starters, ...awayTeam.starters];
    particles = []; 
    matchTime = 0.0; 
    homeScore = 0; 
    awayScore = 0;
    isPaused = false; 

    // 2. 브라우저 기록이나 부모 창을 통해 호출한 URL(이전 페이지)로 복귀 시도
    if (window.history.length > 1) {
        // 이전 페이지 기록이 있는 경우 뒤로 가기
        window.history.back();
    } else if (window.opener) {
        // 새 창(팝업)으로 열린 경우 창 닫기 시도
        window.close();
    } else {
        // 그 외의 경우 메인 도메인이나 루트 경로로 리다이렉트 복귀
        window.location.href = "../home/index.html";
    }
});

// 메인 게임 루프
function gameLoop() {
    let currentSpeed = speedLevels[speedIdx];

    if (gameState === "MATCH" && !isPaused) {
        matchTime += (1.0 / 60.0) * currentSpeed;

        if (matchTime >= matchDuration) {
            gameState = "SUMMARY";
            playSound("whistle");
            updateScreenState();
        }

        if (ball.x >= pitch.rightGoal.x && ball.y >= pitch.rightGoal.y && ball.y <= pitch.rightGoal.y + pitch.rightGoal.height) {
            homeScore++; if (ball.possessor) ball.possessor.goals++;
            playSound("goal");
            for (let i = 0; i < 60; i++) particles.push(new Particle(ball.x, ball.y));
            document.getElementById('quickStatus').innerText = `⚽ GOAL! 홈 팀 득점! (${homeScore} : ${awayScore})`;
            ball.resetToCenter(); ball.possessor = homeTeam.starters[homeTeam.starters.length - 1];
        } else if (ball.x <= pitch.leftGoal.x + pitch.leftGoal.width && ball.y >= pitch.leftGoal.y && ball.y <= pitch.leftGoal.y + pitch.leftGoal.height) {
            awayScore++; if (ball.possessor) ball.possessor.goals++;
            playSound("goal");
            for (let i = 0; i < 60; i++) particles.push(new Particle(ball.x, ball.y));
            document.getElementById('quickStatus').innerText = `⚽ GOAL! 원정 팀 득점! (${homeScore} : ${awayScore})`;
            ball.resetToCenter(); ball.possessor = awayTeam.starters[awayTeam.starters.length - 1];
        }

        if (ball.possessor) {
            let passer = ball.possessor;
            let targetGoalX = (passer.team === 'home') ? PITCH_X + PITCH_WIDTH : PITCH_X;
            passer.x += (passer.team === 'home' ? 1.8 : -1.8) * currentSpeed;

            if (Math.floor(matchTime * 60) % Math.floor(Math.max(10, 60 / currentSpeed)) === 0) {
                if (DecisionEngine.evaluateShot(passer, Math.abs(passer.x - targetGoalX))) {
                    let dx = targetGoalX - passer.x; let dy = PITCH_CENTER_Y - passer.y;
                    let dist = Math.hypot(dx, dy);
                    if (dist > 0) ball.applyKick((dx / dist) * 8.5, (dy / dist) * 8.5, 3.0, "SHOT");
                    document.getElementById('quickStatus').innerText = `🔥 [${passer.name}] 강력한 슈팅 발사!`;
                } else {
                    let teammates = (passer.team === 'home' ? homeTeam : awayTeam).starters.filter(p => p !== passer);
                    let opponents = (passer.team === 'home') ? awayTeam.starters : homeTeam.starters;
                    let receiver = DecisionEngine.selectPassReceiver(passer, teammates, opponents);
                    if (receiver) {
                        let dx = receiver.x - passer.x; let dy = receiver.y - passer.y; let dist = Math.hypot(dx, dy);
                        if (dist > 0) ball.applyKick((dx / dist) * 5.5, (dy / dist) * 5.5, 2.0, "PASS");
                        passer.passes_completed++;
                        document.getElementById('quickStatus').innerText = `[${passer.name}] -> [${receiver.name}] 지능형 패스 연결!`;
                    }
                }
            }
        }

        allPlayers.forEach(p => {
            if (ball.possessor === p) return;
            let currentTeam = (p.team === 'home') ? homeTeam : awayTeam;
            let opponents = (p.team === 'home') ? awayTeam.starters : homeTeam.starters;
            let phase = (Math.abs(ball.x - (p.team === 'home' ? PITCH_X + PITCH_WIDTH : PITCH_X)) > 600) ? "BUILD_UP" : "FINAL_ATTACK";

            let target = p.calculateIntelligentTarget(ball, currentTeam.tactic, currentTeam, phase, opponents, currentTeam.starters);
            p.moveTowards(target.x, target.y, currentSpeed, currentTeam.tactic);
        });

        ball.update(currentSpeed);

        // 상단 전광판 및 하단 요약 DOM 실시간 갱신
        document.getElementById('scoreText').innerText = `HOME ${homeScore} : ${awayScore} AWAY`;
        document.getElementById('timeText').innerText = `TIME ${Math.floor(matchTime)}/${Math.floor(matchDuration)}S | SPEED ${currentSpeed.toFixed(1)}x`;

        let homeStarters5 = homeTeam.starters.slice(0, 3).map(p => `${p.name}:${p.stamina.toFixed(0)}%(${p.goals}골)`).join(' ');
        let awayStarters5 = awayTeam.starters.slice(0, 3).map(p => `${p.name}:${p.stamina.toFixed(0)}%(${p.goals}골)`).join(' ');

        document.getElementById('homeStatsList').innerText = `🏠 ${homeStarters5}`;
        document.getElementById('awayStatsList').innerText = `✈️ ${awayStarters5}`;
    }

    for (let i = particles.length - 1; i >= 0; i--) {
        particles[i].update();
        if (particles[i].life <= 0) particles.splice(i, 1);
    }

    // Canvas 렌더링 (잔디, 선수, 공만 독립 처리)
    ctx.clearRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);
    pitch.draw(ctx);
    
    let renderList = [...allPlayers, ball];
    renderList.sort((a, b) => a.y - b.y);
    renderList.forEach(obj => {
        if (obj instanceof BallPhysics) obj.draw(ctx);
        else obj.draw(ctx, ball.possessor === obj);
    });
    particles.forEach(p => p.draw(ctx));

    requestAnimationFrame(gameLoop);
}

// 초기화
initGameData();
requestAnimationFrame(gameLoop);
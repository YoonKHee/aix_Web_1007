/**
 * ⚽ 팀 중심축(Centroid) 및 TacticalEngine 전술 지침이 완벽 반영된 PlayerController 클래스
 */
class PlayerController {
    constructor(x, y, color, number, name, role, photo, isHome, stat = {}) {
        this.id = Math.random().toString(36).substring(2, 9);
        this.x = x; 
        this.y = y;
        this.baseX = x; 
        this.baseY = y; 
        this.color = color;
        this.number = number;
        this.name = name;
        this.role = role; // 'GK', 'DF', 'LB', 'RB', 'MF', 'FW' 등
        this.photo = photo;
        this.isHome = isHome;
        this.radius = 12;

        const speedBonus = (stat.score ? (stat.score / 100) * 0.4 : Math.random() * 0.4);
        this.baseSpeed = 2.0 + speedBonus;
        this.speed = this.baseSpeed;

        this.vx = 0.0;
        this.vy = 0.0;
        this.state = 'IDLE'; 
        this.holdFrames = 0; 

        // 체력 및 카드 시스템
        this.maxStamina = 100;
        this.stamina = 100;
        this.yellowCards = 0;
        this.isRedCarded = false;

        this.stats = {
            pass: stat.pass || 75,
            tackle: stat.tackle || 70,
            intercept: stat.intercept || 72
        };
    }

    /**
     * 📌 선수의 두뇌 및 이동을 갱신하는 핵심 메서드
     */
    update(ball, allPlayers, PITCH_WIDTH, PITCH_HEIGHT, isPlaying, isKickOffPhase, tactic = '밸런스', context = {}) {
        if (!isPlaying || this.isRedCarded) return;

        // 1. TacticalEngine / evaluateTeamTactics로부터 전달받은 전술 지침 추출
        const press = context.pressIntensity !== undefined ? context.pressIntensity : (context.press || 1.0);
        const line = context.defensiveLine !== undefined ? context.defensiveLine : (context.line || 1.0);
        const width = context.fieldWidth !== undefined ? context.fieldWidth : (context.width || 1.0);

        // 2. 🌟 아군 팀 전체의 평균 위치(중심축 / Centroid) 실시간 계산
        const teammates = allPlayers.filter(p => p.isHome === this.isHome && !p.isRedCarded);
        let teamCentroidX = teammates.reduce((sum, p) => sum + p.baseX, 0) / (teammates.length || 1);
        let teamCentroidY = teammates.reduce((sum, p) => sum + p.baseY, 0) / (teammates.length || 1);

        // 공의 위치에 따라 팀의 중심축이 유기적으로 밀고 당겨짐 (블록 전진/후퇴)
        const ballInfluence = 0.25;
        let dynamicCenterX = teamCentroidX + (ball.x - PITCH_WIDTH / 2) * ballInfluence;
        let dynamicCenterY = teamCentroidY + (ball.y - PITCH_HEIGHT / 2) * ballInfluence;

        // 3. 전술적 성향 및 중심축을 반영한 대형 오프셋 계산
        let shiftedBaseX = this.baseX + (dynamicCenterX - teamCentroidX);
        let shiftedBaseY = this.baseY + (dynamicCenterY - teamCentroidY);

        const isFlankPlayer = (this.role === 'LB' || this.role === 'RB' || this.role === 'LW' || this.role === 'RW');

        if (this.role !== 'GK') {
            if (tactic === '하이프레스' || tactic === '공격형') {
                shiftedBaseX += this.isHome ? (75 * press) : (-75 * press);
            } else if (tactic === '로우블록' || tactic === '수비형') {
                shiftedBaseX += this.isHome ? (-65 * line) : (65 * line);
            } else if (tactic === '역습' && this.role === 'FW') {
                shiftedBaseX += this.isHome ? 100 : -100;
            } else {
                const forwardBias = this.isHome ? (shiftedBaseX - PITCH_WIDTH / 2) : (PITCH_WIDTH / 2 - shiftedBaseX);
                shiftedBaseX += (forwardBias * (line - 1.0));
            }

            // 측면 넓이(Width) 확보 및 조절
            if (isFlankPlayer || this.y < PITCH_HEIGHT * 0.25 || this.y > PITCH_HEIGHT * 0.75) {
                let sideExpand = (tactic === '측면 공략') ? (100 * width) : (70 * width);
                if (this.y < PITCH_HEIGHT / 2) {
                    shiftedBaseY -= sideExpand;
                } else {
                    shiftedBaseY += sideExpand;
                }
            }

            // 전후 간격(Compactness) 조절
            const centerDistanceY = shiftedBaseY - (PITCH_HEIGHT / 2);
            shiftedBaseY = (PITCH_HEIGHT / 2) + (centerDistanceY * width);
        }

        let targetX = shiftedBaseX;
        let targetY = shiftedBaseY;

        // 4. 체력 및 속도 소모/회복 연산
        if (this.state === 'CHASING' || this.state === 'POSSESSING') {
            let drainRate = (press > 1.4) ? 0.035 : 0.015;
            this.stamina = Math.max(0, this.stamina - drainRate);
        } else {
            this.stamina = Math.min(this.maxStamina, this.stamina + 0.006);
        }
        const staminaFactor = 0.6 + (this.stamina / this.maxStamina) * 0.4;
        this.speed = this.baseSpeed * staminaFactor;

        // 5. 골키퍼 행동 제어
        if (this.role === 'GK') {
            let gkX = this.isHome ? PITCH_WIDTH * 0.12 : PITCH_WIDTH * 0.88;
            targetX = gkX;

            if (ball.possessor === this) {
                this.state = 'POSSESSING';
                this.holdFrames++;
                targetX = gkX;
                targetY = PITCH_HEIGHT / 2;

                if (this.holdFrames > 90) {
                    ball.vx = this.isHome ? 14 : -14;
                    ball.vy = (Math.random() - 0.5) * 6;
                    ball.isAerial = true;
                    ball.z = 10;
                    ball.vz = 3.0;
                    ball.possessor = null;
                    this.holdFrames = 0;
                }
            } else {
                this.holdFrames = 0;
                targetY = Math.max(PITCH_HEIGHT * 0.38, Math.min(PITCH_HEIGHT * 0.62, ball.y));
            }
        } 
        // 6. 킥오프 백패스 처리
        else if (isKickOffPhase) {
            if (ball.possessor === this) {
                let backPassDir = this.isHome ? -1 : 1;
                ball.vx = backPassDir * 7;
                ball.vy = (Math.random() - 0.5) * 2;
                ball.isAerial = false;
                ball.possessor = null;
                this.state = 'CHASING';
            } else {
                targetX = shiftedBaseX;
                targetY = shiftedBaseY;
            }
        } 
        // 7. 필드 플레이어 전술적 공간 분산 및 압박 AI
        else {
            if (ball.possessor === this) {
                this.state = 'POSSESSING';
                let attackDir = this.isHome ? 1 : -1;
                let pushDist = (this.role === 'FW') ? 50 : (this.role === 'MF' ? 35 : 20);
                targetX = this.x + attackDir * pushDist;
                targetY = PITCH_HEIGHT / 2 + (shiftedBaseY - PITCH_HEIGHT / 2) * 0.5;
            } else {
                let distToBall = Math.hypot(ball.x - this.x, ball.y - this.y);

                let chaseThreshold = 180 * press;
                if (this.role === 'DF' || this.role === 'LB' || this.role === 'RB') {
                    chaseThreshold = this.isHome ? (ball.x < PITCH_WIDTH * 0.55 ? 190 * press : 110) 
                                                 : (ball.x > PITCH_WIDTH * 0.45 ? 190 * press : 110);
                } else if (this.role === 'FW') {
                    chaseThreshold = 230 * press;
                }

                if (distToBall < chaseThreshold) {
                    this.state = 'CHASING';
                    let ballPull = (this.role === 'FW') ? 0.8 : ((this.role === 'MF') ? 0.7 : 0.5);
                    targetX = shiftedBaseX * (1 - ballPull) + ball.x * ballPull;
                    targetY = shiftedBaseY * (1 - ballPull) + ball.y * ballPull;
                } else {
                    this.state = 'RETURNING';
                    targetX = shiftedBaseX;
                    targetY = shiftedBaseY;
                }
            }
        }

        // 8. 선수 간 충돌 및 밀집 방지 (Separation Force)
        let pushX = 0;
        let pushY = 0;
        allPlayers.forEach(other => {
            if (other !== this && !other.isRedCarded) {
                let d = Math.hypot(this.x - other.x, this.y - other.y);
                if (d < 30 && d > 0) {
                    let repelPower = (30 - d) / 30;
                    pushX += ((this.x - other.x) / d) * repelPower * 3.5;
                    pushY += ((this.y - other.y) / d) * repelPower * 3.5;
                }
            }
        });

        targetX += pushX;
        targetY += pushY;

        // 9. LERP 이동 처리
        let dx = targetX - this.x;
        let dy = targetY - this.y;
        let dist = Math.hypot(dx, dy);

        if (dist > 0.5) {
            let currentSpeed = this.state === 'CHASING' ? this.speed * 1.25 : this.speed;
            this.vx += ((dx / dist) * currentSpeed - this.vx) * 0.15;
            this.vy += ((dy / dist) * currentSpeed - this.vy) * 0.15;
        } else {
            this.vx *= 0.6;
            this.vy *= 0.6;
        }

        this.x += this.vx;
        this.y += this.vy;

        // 10. 경기장 경계 제한
        const minX = 70;
        const maxX = PITCH_WIDTH - 70;
        const minY = 70;
        const maxY = PITCH_HEIGHT - 70;

        this.x = Math.max(minX, Math.min(maxX, this.x));
        this.y = Math.max(minY, Math.min(maxY, this.y));
    }

    /**
     * 📌 선수 및 상태 UI 렌더링
     */
    draw(ctx, hasBall) {
        if (this.isRedCarded) return;

        // 발밑 그림자
        ctx.fillStyle = "rgba(0,0,0,0.35)";
        ctx.beginPath();
        ctx.ellipse(this.x, this.y + 4, 8, 4, 0, 0, Math.PI * 2);
        ctx.fill();

        // 선수 본체 원형
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = hasBall ? '#ff9800' : this.color;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#ffffff';
        ctx.stroke();

        // 등번호
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(this.number, this.x, this.y);

        // 체력 게이지 바
        const barW = 20;
        const barH = 3;
        const barX = this.x - barW / 2;
        const barY = this.y - this.radius - 8;

        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(barX, barY, barW, barH);

        const staminaPct = this.stamina / this.maxStamina;
        ctx.fillStyle = staminaPct > 0.5 ? '#4caf50' : (staminaPct > 0.25 ? '#ffeb3b' : '#f44336');
        ctx.fillRect(barX, barY, barW * staminaPct, barH);

        // 옐로카드 아이콘
        if (this.yellowCards === 1) {
            ctx.fillStyle = '#ffeb3b';
            ctx.fillRect(this.x + 8, this.y - 14, 5, 7);
        }
    }
}
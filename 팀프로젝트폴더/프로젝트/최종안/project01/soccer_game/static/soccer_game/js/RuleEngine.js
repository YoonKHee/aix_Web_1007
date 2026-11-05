/**
 * ⚖️ & ⚽ 통합 룰 및 물리 엔진 (RuleEngine)
 * - IFAB 규칙 (골인, 오프사이드, 반칙/카드, PK, 세트피스, 교체, VAR)
 * - 공의 동역학 (마찰력, 공중볼 포물선, 스루패스 예측) 완비
 */
class MatchRuleEngine {
    constructor(pitchGeometry = null, refereeStrictness = 0.5) {
        this.geo = pitchGeometry;
        this.refereeStrictness = refereeStrictness;
        
        this.matchState = {
            isLive: false,
            currentHalf: 1,
            matchTimeSeconds: 0,
            currentSetPiece: 'KICK_OFF', 
            restartingTeam: 'HOME',
            varActive: false,
            
            substitutions: {
                HOME: { usedCount: 0, stopCount: 0, substitutedOutPlayers: [] },
                AWAY: { usedCount: 0, stopCount: 0, substitutedOutPlayers: [] }
            }
        };
    }

    // ==========================================
    // ⚽ [공의 물리역학] 마찰력, 공중볼, 스루패스
    // ==========================================
    updateBallPhysics(ball, deltaTime = 1) {
        if (ball.isAerial && ball.z > 0) {
            ball.x += ball.vx * deltaTime;
            ball.y += ball.vy * deltaTime;
            ball.z += ball.vz * deltaTime;
            ball.vz -= 0.15 * deltaTime; // 중력

            if (ball.z <= 0) {
                ball.z = 0;
                ball.isAerial = false;
                ball.vx *= 0.7;
                ball.vy *= 0.7;
            }
        } else {
            const friction = 0.975; // 잔디 마찰 계수
            ball.vx *= friction;
            ball.vy *= friction;

            ball.x += ball.vx * deltaTime;
            ball.y += ball.vy * deltaTime;

            if (Math.hypot(ball.vx, ball.vy) < 0.1) {
                ball.vx = 0;
                ball.vy = 0;
            }
        }
        return ball;
    }

    calculateThroughPassTarget(passer, receiver, passPower) {
        const predictionFrames = 30;
        const predictedX = receiver.x + (receiver.vx || 0) * predictionFrames;
        const predictedY = receiver.y + (receiver.vy || 0) * predictionFrames;

        if (this.geo && typeof this.geo.getPerspectiveBounds === 'function') {
            const bounds = this.geo.getPerspectiveBounds(predictedX);
            return {
                targetX: Math.max(bounds.left, Math.min(bounds.right, predictedX)),
                targetY: Math.max(bounds.top, Math.min(bounds.bottom, predictedY)),
                isAerial: passPower > 15
            };
        }
        return { targetX: predictedX, targetY: predictedY, isAerial: passPower > 15 };
    }

    // ==========================================
    // 🛡️ 오프사이드 판정
    // ==========================================
    checkOffside(passer, receiver, defendingPlayers, isAttackingRight, halfwayX = 500) {
        if (this.geo && typeof this.geo.getCenterArea === 'function') {
            halfwayX = this.geo.getCenterArea().halfwayX;
        }
        if (isAttackingRight && receiver.x < halfwayX) return false;
        if (!isAttackingRight && receiver.x > halfwayX) return false;

        const outfieldDefenders = defendingPlayers.filter(p => p.role !== 'GK');
        if (outfieldDefenders.length === 0) return false;

        const sortedDefenders = [...outfieldDefenders].sort((a, b) => 
            isAttackingRight ? a.x - b.x : b.x - a.x
        );
        const secondLastDefenderX = sortedDefenders.length > 1 ? sortedDefenders[1].x : sortedDefenders[0].x;

        return isAttackingRight ? (receiver.x > secondLastDefenderX) : (receiver.x < secondLastDefenderX);
    }

    // ==========================================
    // ⚡ 반칙, 카드 및 페널티킥 판정
    // ==========================================
    evaluateFoulAndMisconduct(attacker, defender, isHomeAttacking) {
        const baseFoulChance = 0.12 + (this.refereeStrictness * 0.12);
        const isFoul = Math.random() < baseFoulChance;

        if (!isFoul) {
            return { isFoul: false, isYellow: false, isRed: false, isPenalty: false };
        }

        if (Math.random() < 0.20) {
            return { isFoul: true, isAdvantage: true, message: "어드밴티지 적용!" };
        }

        let isPenaltyBox = false;
        if (this.geo && typeof this.geo.isInsidePenaltyBox === 'function') {
            isPenaltyBox = this.geo.isInsidePenaltyBox(defender.x, defender.y, isHomeAttacking);
        }

        const cardRoll = Math.random();
        let isYellow = cardRoll < 0.30;
        let isRed = (cardRoll >= 0.30 && cardRoll < 0.35);

        return {
            isFoul: true,
            isAdvantage: false,
            isYellow: isYellow,
            isRed: isRed,
            isPenalty: isPenaltyBox,
            setPiece: isPenaltyBox ? 'PENALTY_KICK' : 'DIRECT_FREE_KICK',
            awardedTeam: isHomeAttacking ? 'HOME' : 'AWAY'
        };
    }

    // ==========================================
    // 👥 선수 교체 관리 시스템
    // ==========================================
    processSubstitution(teamKey, playerOut, playerIn) {
        const teamSubs = this.matchState.substitutions[teamKey];

        if (teamSubs.usedCount >= 5) {
            return { success: false, message: "❌ 교체 실패: 교체 인원을 모두 소모했습니다 (최대 5명)." };
        }
        if (teamSubs.stopCount >= 3 && this.matchState.currentHalf <= 2) {
            return { success: false, message: "❌ 교체 실패: 경기 중단 횟수를 모두 소모했습니다 (최대 3회)." };
        }
        if (teamSubs.substitutedOutPlayers.includes(playerOut.id)) {
            return { success: false, message: "❌ 교체 실패: 이미 그라운드를 떠난 선수는 재교체할 수 없습니다." };
        }

        teamSubs.usedCount++;
        teamSubs.stopCount++;
        teamSubs.substitutedOutPlayers.push(playerOut.id);

        return {
            success: true,
            message: `🔄 선수 교체 완료 [${teamKey}]: OUT #${playerOut.id} ➔ IN #${playerIn.id}`,
            remainingSubs: 5 - teamSubs.usedCount,
            remainingStops: 3 - teamSubs.stopCount
        };
    }

    // ==========================================
    // ⚽ [핵심] 골인, 코너킥, 골킥 및 터치라인 아웃 판정 (game.js 완벽 호환)
    // ==========================================
    checkBallOutAndOutcome(ballX, ballY, lastTouchIsHome, PITCH_WIDTH, PITCH_HEIGHT) {
        // 골문 Y축 범위 (중앙 기준 위아래로 45픽셀)
        const goalTop = (PITCH_HEIGHT / 2) - 45;
        const goalBottom = (PITCH_HEIGHT / 2) + 45;

        // 1. 좌측 골라인 아웃 (홈팀 골대 쪽)
        if (ballX <= 0) {
            if (ballY >= goalTop && ballY <= goalBottom) {
                this.matchState.currentSetPiece = 'KICK_OFF';
                this.matchState.restartingTeam = 'HOME';
                return { status: 'GOAL', team: 'AWAY' }; // 어웨이팀 득점 (골인)
            } else {
                if (lastTouchIsHome) {
                    this.matchState.currentSetPiece = 'CORNER_KICK';
                    this.matchState.restartingTeam = 'AWAY';
                    return { 
                        status: 'CORNER_KICK', 
                        team: 'AWAY', 
                        restartX: 40, 
                        restartY: ballY < PITCH_HEIGHT / 2 ? 40 : PITCH_HEIGHT - 40 
                    };
                } else {
                    this.matchState.currentSetPiece = 'GOAL_KICK';
                    this.matchState.restartingTeam = 'HOME';
                    return { 
                        status: 'GOAL_KICK', 
                        team: 'HOME', 
                        restartX: 100, 
                        restartY: PITCH_HEIGHT / 2 
                    };
                }
            }
        }

        // 2. 우측 골라인 아웃 (어웨이팀 골대 쪽)
        if (ballX >= PITCH_WIDTH) {
            if (ballY >= goalTop && ballY <= goalBottom) {
                this.matchState.currentSetPiece = 'KICK_OFF';
                this.matchState.restartingTeam = 'AWAY';
                return { status: 'GOAL', team: 'HOME' }; // 홈팀 득점 (골인)
            } else {
                if (!lastTouchIsHome) {
                    this.matchState.currentSetPiece = 'CORNER_KICK';
                    this.matchState.restartingTeam = 'HOME';
                    return { 
                        status: 'CORNER_KICK', 
                        team: 'HOME', 
                        restartX: PITCH_WIDTH - 40, 
                        restartY: ballY < PITCH_HEIGHT / 2 ? 40 : PITCH_HEIGHT - 40 
                    };
                } else {
                    this.matchState.currentSetPiece = 'GOAL_KICK';
                    this.matchState.restartingTeam = 'AWAY';
                    return { 
                        status: 'GOAL_KICK', 
                        team: 'AWAY', 
                        restartX: PITCH_WIDTH - 100, 
                        restartY: PITCH_HEIGHT / 2 
                    };
                }
            }
        }

        // 3. 사이드라인(터치라인) 아웃 판정
        const minX = 80;
        const maxX = PITCH_WIDTH - 80;
        const minY = 80;
        const maxY = PITCH_HEIGHT - 80;

        if (ballY <= minY || ballY >= maxY) {
            const throwingTeam = lastTouchIsHome ? 'AWAY' : 'HOME';
            this.matchState.currentSetPiece = 'THROW_IN';
            this.matchState.restartingTeam = throwingTeam;
            return {
                status: 'BALL_OUT_TOUCHLINE',
                restartBy: throwingTeam,
                restartX: Math.max(minX, Math.min(maxX, ballX)),
                restartY: ballY <= minY ? minY : maxY
            };
        }

        return { status: 'IN_PLAY' };
    }

    // ==========================================
    // 📺 VAR 판독 및 시간 관리
    // ==========================================
    triggerVARCheck() {
        this.matchState.varActive = true;
        const isOverturned = Math.random() < 0.20;
        return { checked: true, overturned: isOverturned, message: `📺 VAR 판독: ${isOverturned ? '판정 번복!' : '원심 유지'}` };
    }

    updateMatchTime() {
        this.matchState.matchTimeSeconds++;
        const totalSec = this.matchState.matchTimeSeconds;
        const halfTimeSec = 45 * 60;

        if (totalSec === halfTimeSec && this.matchState.currentHalf === 1) {
            this.matchState.currentHalf = 2;
            this.matchState.currentSetPiece = 'KICK_OFF';
            this.matchState.substitutions.HOME.stopCount = 0;
            this.matchState.substitutions.AWAY.stopCount = 0;
            return { halfEnded: true, message: "전반전 종료 휴식 시간" };
        } else if (totalSec >= halfTimeSec * 2) {
            return { matchEnded: true, message: "정규 시간 경기 종료" };
        }
        return { halfEnded: false, matchEnded: false };
    }
}
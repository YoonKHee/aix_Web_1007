/**
 * 🎯 TacticalEngine.js - 포메이션, 전술 가중치, 팀 중심축 및 동적 상황 판단 통합 매니저
 */
class TacticalEngine {
    constructor() {
        // 1. 포메이션 프리셋 좌표 데이터 정의
        this.formations = {
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

        // 2. 전술별 성향 가중치 프로필 매핑 (test_3.js와 TacticalEngine의 속성 완벽 통합)
        this.tacticProfiles = {
            "하이프레스": { pressIntensity: 1.8, buildUpSpeed: 1.2, fieldWidth: 1.0, defensiveLine: 1.4, timeWasting: false },
            "공격형":     { pressIntensity: 1.6, buildUpSpeed: 1.3, fieldWidth: 1.1, defensiveLine: 1.3, timeWasting: false },
            "수비형":     { pressIntensity: 0.5, buildUpSpeed: 0.8, fieldWidth: 0.9, defensiveLine: 0.6, timeWasting: false },
            "로우블록":   { pressIntensity: 0.4, buildUpSpeed: 0.7, fieldWidth: 0.8, defensiveLine: 0.5, timeWasting: false },
            "점유율":     { pressIntensity: 1.0, buildUpSpeed: 0.7, fieldWidth: 0.8, defensiveLine: 1.0, timeWasting: false },
            "측면 공략":  { pressIntensity: 1.2, buildUpSpeed: 1.1, fieldWidth: 1.6, defensiveLine: 1.1, timeWasting: false },
            "역습":       { pressIntensity: 0.8, buildUpSpeed: 1.8, fieldWidth: 1.3, defensiveLine: 0.7, timeWasting: false },
            "밸런스":     { pressIntensity: 1.0, buildUpSpeed: 1.0, fieldWidth: 1.0, defensiveLine: 1.0, timeWasting: false }
        };
    }

    /**
     * 포메이션 키에 따른 슬롯 배열 반환
     */
    getFormation(formationKey) {
        return this.formations[formationKey] || this.formations["4-4-2"];
    }

    /**
     * 📌 경기 상황(스코어, 시간) 및 전술에 따른 실시간 전술 지침(Context) 산출
     */
    evaluateContext(tacticName, isHome, matchSeconds, homeGoals, awayGoals) {
        let base = this.tacticProfiles[tacticName] || this.tacticProfiles["밸런스"];
        let strategy = { ...base };

        const isLeading = isHome ? (homeGoals > awayGoals) : (awayGoals > homeGoals);
        const isTrailing = isHome ? (homeGoals < awayGoals) : (awayGoals < homeGoals);
        const isLateGame = matchSeconds >= (40 * 60); // 후반 40분 이후

        // 조건 A: 지고 있고 경기 후반이면 '총력전(전방 압박 극대화)' 자동 전환
        if (isTrailing && isLateGame) {
            strategy.pressIntensity *= 1.5;
            strategy.buildUpSpeed *= 1.4;
            strategy.defensiveLine *= 1.2;
        }

        // 조건 B: 이기고 있고 경기 후반이면 '리드 시 시간 끌기 및 수비 강화' 자동 전환
        if (isLeading && isLateGame) {
            strategy.defensiveLine *= 0.7;
            strategy.pressIntensity *= 0.8;
            strategy.timeWasting = true;
        }

        // 🌟 PlayerController 호환성을 위한 단축 별칭 속성 동시 제공 (press, line, width)
        strategy.press = strategy.pressIntensity;
        strategy.line = strategy.defensiveLine;
        strategy.width = strategy.fieldWidth;

        return strategy;
    }

    /**
     * 📌 팀 전체의 중심축(Centroid) 계산
     */
    calculateCentroid(players) {
        const activePlayers = players.filter(p => !p.isRedCarded);
        if (activePlayers.length === 0) return { x: 0, y: 0 };
        
        let sumX = activePlayers.reduce((sum, p) => sum + p.baseX, 0);
        let sumY = activePlayers.reduce((sum, p) => sum + p.baseY, 0);
        
        return {
            x: sumX / activePlayers.length,
            y: sumY / activePlayers.length
        };
    }
}

/**
 * 외부 함수 호출 호환용 래퍼 함수 (test_3.js 연동 지원)
 */
function evaluateTeamTactics(tacticName, isHome, matchSeconds, homeGoals, awayGoals, ball, PITCH_WIDTH) {
    if (!window.tacticalEngineInstance) {
        window.tacticalEngineInstance = new TacticalEngine();
    }
    return window.tacticalEngineInstance.evaluateContext(tacticName, isHome, matchSeconds, homeGoals, awayGoals);
}
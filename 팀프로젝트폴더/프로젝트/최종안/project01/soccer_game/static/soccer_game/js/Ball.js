/**
 * ⚽ Ball.js
 * - 공의 물리 연산(마찰력, 공중 궤적, 바운스) 및 렌더링/소유권 관리 전담 클래스
 */
class Ball {
    constructor(x, y) {
        this.x = x;
        this.y = y;
        this.z = 0;          // 공중 높이 (픽셀 단위)
        
        this.vx = 0;         // X축 평면 속도
        this.vy = 0;         // Y축 평면 속도
        this.vz = 0;         // Z축 공중 수직 속도
        
        this.radius = 6;     // 공의 반지름
        this.friction = 0.98; // 지면 마찰 계수 (감속 비율)
        this.gravity = 0.38;  // 중력 가속도
        this.bounce = 0.55;   // 바운스 반발력 (0~1)
        
        this.isAerial = false; // 공중볼 여부
        this.possessor = null; // 공을 소유 중인 PlayerController 객체
    }

    /**
     * 📌 매 프레임 공의 물리(위치, 속도, 마찰력, 중력, 바운스) 업데이트
     */
    updatePhysics() {
        // 소유자가 있을 경우 소유자의 위치를 추적하므로 자체 속도 연산 비활성화
        if (this.possessor) {
            this.vx = 0;
            this.vy = 0;
            this.vz = 0;
            this.z = 0;
            this.isAerial = false;
            return;
        }

        // 1. X, Y축 지면 이동 및 마찰력 감속
        this.x += this.vx;
        this.y += this.vy;
        this.vx *= this.friction;
        this.vy *= this.friction;

        // 미세 속도 정지 처리
        if (Math.abs(this.vx) < 0.05) this.vx = 0;
        if (Math.abs(this.vy) < 0.05) this.vy = 0;

        // 2. Z축 공중 물리 (중력 및 바운스 연산)
        if (this.isAerial || this.z > 0 || this.vz !== 0) {
            this.z += this.vz;
            this.vz -= this.gravity; // 중력 적용

            // 지면 바운스 감지 (z <= 0)
            if (this.z <= 0) {
                this.z = 0;
                if (Math.abs(this.vz) > 1.2) {
                    this.vz = -this.vz * this.bounce; // 튀어오름
                    this.vx *= 0.85; // 바운스 시 감속
                    this.vy *= 0.85;
                } else {
                    // 바운스 정지
                    this.vz = 0;
                    this.isAerial = false;
                }
            }
        }
    }

    /**
     * 📌 공 킥/패스 정밀 발사 메서드
     * @param {number} targetVx - X축 발사 속도
     * @param {number} targetVy - Y축 발사 속도
     * @param {number} initialVz - Z축 뜬 공 초기 높이 속도 (0이면 땅볼)
     */
    kick(targetVx, targetVy, initialVz = 0) {
        this.possessor = null; // 소유권 해제
        this.vx = targetVx;
        this.vy = targetVy;
        
        if (initialVz > 0) {
            this.vz = initialVz;
            this.isAerial = true;
        } else {
            this.vz = 0;
            this.isAerial = false;
        }
    }

    /**
     * 📌 공 위치 재설정 (킥오프, 골 등)
     */
    reset(x, y) {
        this.x = x;
        this.y = y;
        this.z = 0;
        this.vx = 0;
        this.vy = 0;
        this.vz = 0;
        this.isAerial = false;
        this.possessor = null;
    }

    /**
     * 📌 캔버스 렌더링 (공중 높이에 따른 입체 그림자 및 원근감 반영)
     * @param {CanvasRenderingContext2D} ctx 
     */
    draw(ctx) {
        // 실제 화면에 그려질 Y 좌표 (높이 z만큼 위로 띄움)
        const renderY = this.y - this.z;

        // 1. 공중 높이에 따른 그림자 크기 및 투명도 동적 연산
        const shadowScale = Math.max(0.3, 1 - (this.z / 100));
        const shadowAlpha = Math.max(0.1, 0.4 - (this.z / 200));

        ctx.save();
        ctx.fillStyle = `rgba(0, 0, 0, ${shadowAlpha})`;
        ctx.beginPath();
        ctx.ellipse(this.x, this.y + 6, 6 * shadowScale, 3 * shadowScale, 0, 0, Math.PI * 2);
        ctx.fill();

        // 2. 공 본체 렌더링
        ctx.beginPath();
        ctx.arc(this.x, renderY, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.restore();
    }
}
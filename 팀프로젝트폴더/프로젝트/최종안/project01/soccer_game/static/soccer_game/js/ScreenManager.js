/**
 * 🖥️ ScreenManager.js
 * - 화면 해상도 변경 및 전체화면 대응 자동 스케일링/레이아웃 전담 클래스
 * - PitchGeometry나 Game Logic과의 결합도를 낮추어 코드 간섭 방지
 */
class ScreenManager {
    /**
     * @param {string} wrapperSelector - 화면 전체를 감싸는 메인 wrapper의 CSS 셀렉터
     * @param {number} baseWidth - 기준 디자인 가로 해상도 (기본: 1920)
     * @param {number} baseHeight - 기준 디자인 세로 해상도 (기본: 1080)
     */
    constructor(wrapperSelector = '.main-game-wrapper', baseWidth = 1920, baseHeight = 1080) {
        this.wrapper = document.querySelector(wrapperSelector);
        this.baseWidth = baseWidth;
        this.baseHeight = baseHeight;

        this.init();
    }

    /**
     * 📌 창 크기에 맞춰 레이아웃을 비율대로 정중앙에 스케일링
     */
    autoResize() {
        if (!this.wrapper) {
            this.wrapper = document.querySelector('.main-game-wrapper');
            if (!this.wrapper) return;
        }

        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;

        // 가로/세로 비율 중 작은 값을 선택해 화면 잘림 완전 방지
        const scaleX = windowWidth / this.baseWidth;
        const scaleY = windowHeight / this.baseHeight;
        const scale = Math.min(scaleX, scaleY);

        // 정중앙 고정 및 변형 적용
        this.wrapper.style.transform = `scale(${scale})`;
        this.wrapper.style.transformOrigin = 'center center';
        this.wrapper.style.position = 'absolute';
        this.wrapper.style.left = '50%';
        this.wrapper.style.top = '50%';
        this.wrapper.style.marginLeft = `-${this.baseWidth / 2}px`;
        this.wrapper.style.marginTop = `-${this.baseHeight / 2}px`;
    }

    /**
     * 📌 이벤트 리스너 등록 및 초기화
     */
    init() {
        // 리사이즈 이벤트 바인딩
        window.addEventListener('resize', () => this.autoResize());
        window.addEventListener('DOMContentLoaded', () => this.autoResize());
        
        // 전체화면(Full Screen) 전환 이벤트 대응
        document.addEventListener('fullscreenchange', () => this.autoResize());
        document.addEventListener('webkitfullscreenchange', () => this.autoResize());

        // 즉시 1회 실행
        this.autoResize();
    }
}
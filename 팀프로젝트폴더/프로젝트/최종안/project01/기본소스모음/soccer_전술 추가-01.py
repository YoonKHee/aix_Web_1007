import math
import random
import sys
import pygame

# 초기화
pygame.init()
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2)
except Exception:
    pass

# 화면 설정 (1280x720 표준 해상도)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("축구 모의 게임 - 포메이션 및 전술 시스템 고도화 버전")

# 색상 정의
COLOR_GRASS_1 = (34, 139, 34)
COLOR_GRASS_2 = (40, 150, 40)
COLOR_LINE = (240, 240, 240)
COLOR_HOME = (0, 119, 204)
COLOR_AWAY = (220, 20, 60)
COLOR_BALL = (255, 255, 255)
COLOR_GOAL = (240, 240, 240)
COLOR_NET = (180, 180, 180)
COLOR_STADIUM = (30, 30, 35)
COLOR_PANEL = (30, 30, 35)
COLOR_BUTTON = (50, 50, 65)
COLOR_BUTTON_HOVER = (70, 130, 180)
COLOR_BUTTON_ACTIVE = (0, 150, 200)

font = pygame.font.SysFont("malgungothic", 16)
font_bold = pygame.font.SysFont("malgungothic", 18, bold=True)
font_score = pygame.font.SysFont("malgungothic", 22, bold=True)
font_title = pygame.font.SysFont("malgungothic", 28, bold=True)

# FIFA 규격 스케일 및 기본 전역 좌표 변수 선언
SCALE = 9
METER_LENGTH = 105
METER_WIDTH = 68
PITCH_WIDTH = int(METER_LENGTH * SCALE)          # 945
PITCH_HEIGHT = int(METER_WIDTH * SCALE)        # 612
PITCH_X = (SCREEN_WIDTH - PITCH_WIDTH) // 2      # 167
PITCH_Y = 95
PITCH_CENTER_X = PITCH_X + PITCH_WIDTH / 2
PITCH_CENTER_Y = PITCH_Y + PITCH_HEIGHT / 2


def play_sound_effect(sound_type):
    if sound_type == "whistle":
        print("🔊 [Sound] 휘슬 삑-!")
    elif sound_type == "goal":
        print("🔊 [Sound] 골 함성 환호 ~~~ ⚽")
    elif sound_type == "foul":
        print("🔊 [Sound] 경고 휘슬 🚨")


class Particle:
    """[시각 효과] 골 득점 시 사방으로 퍼지는 폭죽 파티클 관리"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(2, 7)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 50
        self.radius = random.randint(3, 7)
        self.color = random.choice([
            (255, 215, 0), (255, 69, 0), (0, 255, 255), 
            (255, 20, 147), (50, 205, 50), (255, 255, 255)
        ])

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.life -= 1

    def draw(self, surface):
        if self.life > 0:
            pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)


class Pitch:
    """[경기장 클래스] 물리 좌표계와 렌더링 영역을 동기화하고 FIFA 규격을 준수하는 클래스 (고정 픽스)"""
    SCALE = 9
    METER_LENGTH = 105
    METER_WIDTH = 68

    def __init__(self):
        self.width = int(self.METER_LENGTH * self.SCALE)
        self.height = int(self.METER_WIDTH * self.SCALE)
        self.x = (SCREEN_WIDTH - self.width) // 2
        self.y = 95
        self.center_x = self.x + self.width / 2
        self.center_y = self.y + self.height / 2
        
        global PITCH_X, PITCH_Y, PITCH_WIDTH, PITCH_HEIGHT, PITCH_CENTER_X, PITCH_CENTER_Y
        PITCH_X = self.x
        PITCH_Y = self.y
        PITCH_WIDTH = self.width
        PITCH_HEIGHT = self.height
        PITCH_CENTER_X = self.center_x
        PITCH_CENTER_Y = self.center_y

        goal_w = int(7.32 * self.SCALE)
        goal_depth = int(2.5 * self.SCALE)
        
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)
        self.left_goal = pygame.Rect(self.x - goal_depth, self.center_y - goal_w/2, goal_depth, goal_w)
        self.right_goal = pygame.Rect(self.x + self.width, self.center_y - goal_w/2, goal_depth, goal_w)

    def draw(self, surface):
        surface.fill(COLOR_STADIUM)
        
        stripe_width = int(5 * self.SCALE)
        for x in range(self.x, self.x + self.width, stripe_width * 2):
            pygame.draw.rect(surface, COLOR_GRASS_1, (x, self.y, stripe_width, self.height))
            pygame.draw.rect(surface, COLOR_GRASS_2, (x + stripe_width, self.y, stripe_width, self.height))

        pygame.draw.rect(surface, COLOR_LINE, self.rect, 3)
        pygame.draw.line(surface, COLOR_LINE, (self.center_x, self.y), (self.center_x, self.y + self.height), 3)

        center_circle_r = int(9.15 * self.SCALE)
        pygame.draw.circle(surface, COLOR_LINE, (int(self.center_x), int(self.center_y)), center_circle_r, 3)
        pygame.draw.circle(surface, COLOR_LINE, (int(self.center_x), int(self.center_y)), 5)

        box_depth = int(16.5 * self.SCALE)
        box_width = int(40.32 * self.SCALE)
        pygame.draw.rect(surface, COLOR_LINE, (self.x, self.center_y - box_width/2, box_depth, box_width), 3)
        pygame.draw.rect(surface, COLOR_LINE, (self.x + self.width - box_depth, self.center_y - box_width/2, box_depth, box_width), 3)

        goal_area_depth = int(5.5 * self.SCALE)
        goal_area_width = int(18.32 * self.SCALE)
        pygame.draw.rect(surface, COLOR_LINE, (self.x, self.center_y - goal_area_width/2, goal_area_depth, goal_area_width), 3)
        pygame.draw.rect(surface, COLOR_LINE, (self.x + self.width - goal_area_depth, self.center_y - goal_area_width/2, goal_area_depth, goal_area_width), 3)

        spot_dist = int(11.0 * self.SCALE)
        left_spot_x = self.x + spot_dist
        right_spot_x = self.x + self.width - spot_dist
        
        pygame.draw.circle(surface, COLOR_LINE, (left_spot_x, int(self.center_y)), 4)
        pygame.draw.circle(surface, COLOR_LINE, (right_spot_x, int(self.center_y)), 4)

        arc_r = int(9.15 * self.SCALE)
        pygame.draw.arc(surface, COLOR_LINE, (left_spot_x - arc_r, int(self.center_y - arc_r), arc_r * 2, arc_r * 2), -math.pi/3, math.pi/3, 3)
        pygame.draw.arc(surface, COLOR_LINE, (right_spot_x - arc_r, int(self.center_y - arc_r), arc_r * 2, arc_r * 2), math.pi*2/3, math.pi*4/3, 3)

        corner_r = int(1.0 * self.SCALE)
        d = corner_r * 2
        pygame.draw.arc(surface, COLOR_LINE, (self.x, self.y, d, d), 3*math.pi/2, 2*math.pi, 2)
        pygame.draw.arc(surface, COLOR_LINE, (self.x + self.width - d, self.y, d, d), math.pi, 3*math.pi/2, 2)
        pygame.draw.arc(surface, COLOR_LINE, (self.x, self.y + self.height - d, d, d), 0, math.pi/2, 2)
        pygame.draw.arc(surface, COLOR_LINE, (self.x + self.width - d, self.y + self.height - d, d, d), math.pi/2, math.pi, 2)

        self._draw_goal_net(surface, self.left_goal)
        self._draw_goal_net(surface, self.right_goal)

    def _draw_goal_net(self, surface, goal_rect):
        pygame.draw.rect(surface, COLOR_GOAL, goal_rect, 3)
        step = 8
        for gx in range(goal_rect.left + step, goal_rect.right, step):
            pygame.draw.line(surface, COLOR_NET, (gx, goal_rect.top), (gx, goal_rect.bottom), 1)
        for gy in range(goal_rect.top + step, goal_rect.bottom, step):
            pygame.draw.line(surface, COLOR_NET, (goal_rect.left, gy), (goal_rect.right, gy), 1)


class Ball:
    """[공 클래스] 공의 물리 좌표, 속도, 마찰력, 소유권 및 리셋 관리"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.possessor = None

    def update(self, speed_multiplier):
        if self.possessor:
            self.x = self.possessor.x + 12
            self.y = self.possessor.y
            self.vx = 0
            self.vy = 0
        else:
            self.x += self.vx * speed_multiplier
            self.y += self.vy * speed_multiplier
            friction = 0.96 ** speed_multiplier
            self.vx *= friction
            self.vy *= friction

            if self.x < PITCH_X or self.x > PITCH_X + PITCH_WIDTH:
                self.vx *= -0.5
            if self.y < PITCH_Y or self.y > PITCH_Y + PITCH_HEIGHT:
                self.vy *= -0.5

    def reset_to_center(self):
        self.x = PITCH_CENTER_X
        self.y = PITCH_CENTER_Y
        self.vx = 0
        self.vy = 0
        self.possessor = None

    def draw(self, surface):
        shadow_surf = pygame.Surface((12, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 110), (0, 0, 12, 6))
        surface.blit(shadow_surf, (int(self.x) - 6, int(self.y) + 5))

        pygame.draw.circle(surface, (30, 30, 30), (int(self.x), int(self.y)), 7)
        pygame.draw.circle(surface, COLOR_BALL, (int(self.x), int(self.y)), 5)


class Player:
    """[선수 클래스] 개별 선수의 스탯, 스태미나, 포메이션 위치 및 전술별 이동 로직"""
    def __init__(self, x, y, team, name, speed=2.2, passing=70, shooting=70):
        self.original_base_x = x
        self.original_base_y = y
        self.base_x = x
        self.base_y = y
        self.x = x
        self.y = y
        self.team = team
        self.name = name
        
        self.stat_speed = speed
        self.stat_passing = passing
        self.stat_shooting = shooting
        self.stamina = 100.0
        self.goals = 0

    def calculate_dynamic_target(self, ball_x, ball_y, tactic):
        shift_offset = (ball_x - PITCH_CENTER_X) * 0.25
        tactic_offset = 0
        y_spread = 1.0

        # 4가지 핵심 전술 성향별 보정값 적용
        if self.team == 'home':
            if tactic == "TIKI_TAKA":
                # 짧은 간격, 점유율 유지 (중앙 밀집)
                shift_offset *= 0.15
                y_spread = 0.8
            elif tactic == "GEGENPRESSING":
                # 강력한 전방 압박 (전체적으로 앞쪽으로 전진)
                tactic_offset = 55
            elif tactic == "COUNTER":
                # 선수비 후역습 (수비 시 깊숙이, 역습 시 전방 대기)
                tactic_offset = -35 if ball_x < PITCH_CENTER_X else 60
            elif tactic == "WING_PLAY":
                # 측면 활용 극대화 (윙어/풀백들이 사이드로 넓게 벌림)
                if "LM" in self.name or "LW" in self.name or "LB" in self.name or "LWB" in self.name:
                    self.base_y = self.original_base_y - 45
                elif "RM" in self.name or "RW" in self.name or "RB" in self.name or "RWB" in self.name:
                    self.base_y = self.original_base_y + 45

        if "GK" in self.name:
            target_x = self.original_base_x
            target_y = max(PITCH_CENTER_Y - 50, min(PITCH_CENTER_Y + 50, ball_y))
        else:
            target_x = self.original_base_x + shift_offset + tactic_offset
            target_y = self.original_base_y * y_spread + (ball_y - PITCH_CENTER_Y) * 0.15

        return target_x, target_y

    def move_towards(self, target_x, target_y, speed_multiplier, tactic):
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.hypot(dx, dy)

        # 게겐프레싱 전술 사용 시 체력 소모 가중치 증가
        stamina_drain = 0.007 if tactic == "GEGENPRESSING" else 0.005
        fatigue_penalty = 0.6 if self.stamina < 30 else 1.0
        effective_speed = self.stat_speed * speed_multiplier * fatigue_penalty

        if distance > 2:
            self.x += (dx / distance) * effective_speed
            self.y += (dy / distance) * effective_speed
            self.stamina = max(0.0, self.stamina - stamina_drain * speed_multiplier)

        self.x = max(PITCH_X + 12, min(PITCH_X + PITCH_WIDTH - 12, self.x))
        self.y = max(PITCH_Y + 12, min(PITCH_Y + PITCH_HEIGHT - 12, self.y))

    def draw(self, surface, has_ball):
        shadow_surf = pygame.Surface((18, 9), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 90), (0, 0, 18, 9))
        surface.blit(shadow_surf, (int(self.x) - 9, int(self.y) + 3))

        color = (255, 140, 0) if has_ball else (COLOR_HOME if self.team == 'home' else COLOR_AWAY)
        radius = 11 if has_ball else 9

        pygame.draw.circle(surface, (20, 20, 20), (int(self.x), int(self.y)), radius + 1)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)

        bar_w = 20
        bar_h = 3
        fill_w = int(bar_w * (self.stamina / 100.0))
        bar_color = (0, 255, 0) if self.stamina > 40 else (255, 100, 0)
        pygame.draw.rect(surface, (50, 50, 50), (int(self.x) - bar_w/2, int(self.y) - 28, bar_w, bar_h))
        pygame.draw.rect(surface, bar_color, (int(self.x) - bar_w/2, int(self.y) - 28, fill_w, bar_h))

        name_surf = font.render(self.name, True, (255, 255, 255))
        surface.blit(name_surf, (int(self.x) - 12, int(self.y) - 22))


class Team:
    """[팀 관리 클래스] 포메이션별 선수 선발 명단 생성 지원"""
    def __init__(self, is_home=True, formation="4-4-2"):
        self.is_home = is_home
        self.formation = formation
        px = PITCH_X if is_home else PITCH_X + PITCH_WIDTH
        dir_sign = 1 if is_home else -1
        team_str = 'home' if is_home else 'away'
        prefix = 'H' if is_home else 'A'

        self.starters = self._create_formation_starters(px, dir_sign, team_str, prefix, formation)
        
        self.bench = [
            Player(px, PITCH_CENTER_Y, team_str, f'{prefix}-SUB1', speed=2.3, passing=75, shooting=70),
            Player(px, PITCH_CENTER_Y, team_str, f'{prefix}-SUB2', speed=2.2, passing=72, shooting=72),
            Player(px, PITCH_CENTER_Y, team_str, f'{prefix}-SUB3', speed=2.4, passing=70, shooting=75),
        ]
        self.tactic = "TIKI_TAKA"  # 기본 전술 설정
        self.subs_left = 3

    def _create_formation_starters(self, px, dir_sign, team_str, prefix, formation):
        gk = Player(px + dir_sign * 35, PITCH_CENTER_Y, team_str, f'{prefix}-GK', speed=1.8, passing=60, shooting=30)
        
        if formation == "4-4-2":
            return [
                gk,
                Player(px + dir_sign * 110, PITCH_CENTER_Y - 190, team_str, f'{prefix}-LB', speed=2.3, passing=72, shooting=45),
                Player(px + dir_sign * 90, PITCH_CENTER_Y - 65, team_str, f'{prefix}-CB1', speed=2.0, passing=68, shooting=40),
                Player(px + dir_sign * 90, PITCH_CENTER_Y + 65, team_str, f'{prefix}-CB2', speed=2.0, passing=68, shooting=40),
                Player(px + dir_sign * 110, PITCH_CENTER_Y + 190, team_str, f'{prefix}-RB', speed=2.3, passing=72, shooting=45),
                Player(px + dir_sign * 240, PITCH_CENTER_Y - 210, team_str, f'{prefix}-LM', speed=2.4, passing=78, shooting=65),
                Player(px + dir_sign * 220, PITCH_CENTER_Y - 70, team_str, f'{prefix}-CM1', speed=2.1, passing=85, shooting=60),
                Player(px + dir_sign * 220, PITCH_CENTER_Y + 70, team_str, f'{prefix}-CM2', speed=2.1, passing=85, shooting=60),
                Player(px + dir_sign * 240, PITCH_CENTER_Y + 210, team_str, f'{prefix}-RM', speed=2.4, passing=78, shooting=65),
                Player(px + dir_sign * 380, PITCH_CENTER_Y - 50, team_str, f'{prefix}-ST1', speed=2.3, passing=70, shooting=88),
                Player(px + dir_sign * 380, PITCH_CENTER_Y + 50, team_str, f'{prefix}-ST2', speed=2.3, passing=70, shooting=88),
            ]
        elif formation == "4-3-3":
            return [
                gk,
                Player(px + dir_sign * 110, PITCH_CENTER_Y - 190, team_str, f'{prefix}-LB', speed=2.3, passing=72, shooting=45),
                Player(px + dir_sign * 90, PITCH_CENTER_Y - 65, team_str, f'{prefix}-CB1', speed=2.0, passing=68, shooting=40),
                Player(px + dir_sign * 90, PITCH_CENTER_Y + 65, team_str, f'{prefix}-CB2', speed=2.0, passing=68, shooting=40),
                Player(px + dir_sign * 110, PITCH_CENTER_Y + 190, team_str, f'{prefix}-RB', speed=2.3, passing=72, shooting=45),
                Player(px + dir_sign * 200, PITCH_CENTER_Y, team_str, f'{prefix}-CDM', speed=2.1, passing=82, shooting=55),
                Player(px + dir_sign * 250, PITCH_CENTER_Y - 120, team_str, f'{prefix}-LCM', speed=2.2, passing=80, shooting=60),
                Player(px + dir_sign * 250, PITCH_CENTER_Y + 120, team_str, f'{prefix}-RCM', speed=2.2, passing=80, shooting=60),
                Player(px + dir_sign * 360, PITCH_CENTER_Y - 210, team_str, f'{prefix}-LW', speed=2.5, passing=75, shooting=80),
                Player(px + dir_sign * 380, PITCH_CENTER_Y, team_str, f'{prefix}-ST', speed=2.3, passing=70, shooting=90),
                Player(px + dir_sign * 360, PITCH_CENTER_Y + 210, team_str, f'{prefix}-RW', speed=2.5, passing=75, shooting=80),
            ]
        elif formation == "3-5-2":
            return [
                gk,
                Player(px + dir_sign * 90, PITCH_CENTER_Y - 130, team_str, f'{prefix}-LCB', speed=2.0, passing=70, shooting=40),
                Player(px + dir_sign * 80, PITCH_CENTER_Y, team_str, f'{prefix}-CB', speed=2.0, passing=68, shooting=35),
                Player(px + dir_sign * 90, PITCH_CENTER_Y + 130, team_str, f'{prefix}-RCB', speed=2.0, passing=70, shooting=40),
                Player(px + dir_sign * 180, PITCH_CENTER_Y - 230, team_str, f'{prefix}-LWB', speed=2.4, passing=75, shooting=60),
                Player(px + dir_sign * 220, PITCH_CENTER_Y - 80, team_str, f'{prefix}-LCM', speed=2.1, passing=84, shooting=60),
                Player(px + dir_sign * 200, PITCH_CENTER_Y, team_str, f'{prefix}-CM', speed=2.1, passing=86, shooting=60),
                Player(px + dir_sign * 220, PITCH_CENTER_Y + 80, team_str, f'{prefix}-RCM', speed=2.1, passing=84, shooting=60),
                Player(px + dir_sign * 180, PITCH_CENTER_Y + 230, team_str, f'{prefix}-RWB', speed=2.4, passing=75, shooting=60),
                Player(px + dir_sign * 370, PITCH_CENTER_Y - 60, team_str, f'{prefix}-ST1', speed=2.3, passing=70, shooting=88),
                Player(px + dir_sign * 370, PITCH_CENTER_Y + 60, team_str, f'{prefix}-ST2', speed=2.3, passing=70, shooting=88),
            ]
        elif formation == "4-2-3-1":
            return [
                gk,
                Player(px + dir_sign * 110, PITCH_CENTER_Y - 190, team_str, f'{prefix}-LB', speed=2.3, passing=72, shooting=45),
                Player(px + dir_sign * 90, PITCH_CENTER_Y - 65, team_str, f'{prefix}-CB1', speed=2.0, passing=68, shooting=40),
                Player(px + dir_sign * 90, PITCH_CENTER_Y + 65, team_str, f'{prefix}-CB2', speed=2.0, passing=68, shooting=40),
                Player(px + dir_sign * 110, PITCH_CENTER_Y + 190, team_str, f'{prefix}-RB', speed=2.3, passing=72, shooting=45),
                Player(px + dir_sign * 190, PITCH_CENTER_Y - 70, team_str, f'{prefix}-LDM', speed=2.1, passing=80, shooting=50),
                Player(px + dir_sign * 190, PITCH_CENTER_Y + 70, team_str, f'{prefix}-RDM', speed=2.1, passing=80, shooting=50),
                Player(px + dir_sign * 280, PITCH_CENTER_Y - 190, team_str, f'{prefix}-LAM', speed=2.3, passing=82, shooting=70),
                Player(px + dir_sign * 290, PITCH_CENTER_Y, team_str, f'{prefix}-CAM', speed=2.2, passing=88, shooting=75),
                Player(px + dir_sign * 280, PITCH_CENTER_Y + 190, team_str, f'{prefix}-RAM', speed=2.3, passing=82, shooting=70),
                Player(px + dir_sign * 380, PITCH_CENTER_Y, team_str, f'{prefix}-ST', speed=2.3, passing=70, shooting=90),
            ]
        return []


# --- [게임 컨트롤러 초기화] ---
pitch = Pitch()
ball = Ball(PITCH_CENTER_X, PITCH_CENTER_Y)
home_team = Team(is_home=True, formation="4-4-2")
away_team = Team(is_home=False, formation="4-4-2")
all_players = home_team.starters + away_team.starters
particles = []

clock = pygame.time.Clock()
game_state = "MENU"
game_status_text = "전술판 대기 중 ([ENTER] 키를 누르면 킥오프)"
match_time = 0.0
home_score = 0
away_score = 0
is_paused = False
SPEED_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0]
speed_idx = 1
match_duration = 120.0
kickoff_phase = True

# 메뉴 화면 포메이션 선택 버튼 영역 정의
formation_buttons = [
    (pygame.Rect(130, 570, 110, 40), "4-4-2"),
    (pygame.Rect(250, 570, 110, 40), "4-3-3"),
    (pygame.Rect(370, 570, 110, 40), "3-5-2"),
    (pygame.Rect(490, 570, 110, 40), "4-2-3-1"),
]

# 메인 게임 루프
while True:
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if game_state == "MENU":
                for rect, form_name in formation_buttons:
                    if rect.collidepoint(mouse_pos):
                        home_team = Team(is_home=True, formation=form_name)
                        all_players = home_team.starters + away_team.starters
                        game_status_text = f"홈 팀 포메이션 변경 완료: [{form_name}]"
        elif event.type == pygame.KEYDOWN:
            if game_state == "MENU":
                if event.key == pygame.K_RETURN:
                    game_state = "MATCH"
                    play_sound_effect("whistle")
                    st1 = home_team.starters[len(home_team.starters)-1]
                    ball.x, ball.y = PITCH_CENTER_X, PITCH_CENTER_Y
                    ball.possessor = st1
                    game_status_text = "⚽ 킥오프! 중앙에서 백패스로 경기를 시작합니다."
            elif game_state == "SUMMARY":
                if event.key == pygame.K_r:
                    pitch = Pitch()
                    ball = Ball(PITCH_CENTER_X, PITCH_CENTER_Y)
                    home_team = Team(is_home=True, formation="4-4-2")
                    away_team = Team(is_home=False, formation="4-4-2")
                    all_players = home_team.starters + away_team.starters
                    particles = []
                    match_time = 0.0
                    home_score = 0
                    away_score = 0
                    kickoff_phase = True
                    game_state = "MENU"
                    game_status_text = "전술판 대기 중 ([ENTER] 키를 누르면 킥오프)"
            else:
                if event.key == pygame.K_SPACE:
                    is_paused = not is_paused
                elif event.key == pygame.K_UP or event.key == pygame.K_EQUALS:
                    if speed_idx < len(SPEED_LEVELS) - 1:
                        speed_idx += 1
                elif event.key == pygame.K_DOWN or event.key == pygame.K_MINUS:
                    if speed_idx > 0:
                        speed_idx -= 1
                elif event.key == pygame.K_1:
                    home_team.tactic = "TIKI_TAKA"
                    game_status_text = "전술 변경: [1. 티키타카 (짧은 패스 & 점유율)]"
                elif event.key == pygame.K_2:
                    home_team.tactic = "GEGENPRESSING"
                    game_status_text = "전술 변경: [2. 게겐프레싱 (전방 압박 & 속공)]"
                elif event.key == pygame.K_3:
                    home_team.tactic = "COUNTER"
                    game_status_text = "전술 변경: [3. 선수비 후역습 (롱볼 역습)]"
                elif event.key == pygame.K_4:
                    home_team.tactic = "WING_PLAY"
                    game_status_text = "전술 변경: [4. 측면 돌파 및 크로스 (사이드 공략)]"
                elif event.key == pygame.K_s:
                    if home_team.subs_left > 0 and len(home_team.bench) > 0:
                        field_players = [p for p in home_team.starters if p.name != 'H-GK']
                        if field_players:
                            tired_player = min(field_players, key=lambda p: p.stamina)
                            sub_player = home_team.bench.pop(0)
                            
                            sub_player.x = tired_player.x
                            sub_player.y = tired_player.y
                            sub_player.original_base_x = tired_player.original_base_x
                            sub_player.original_base_y = tired_player.original_base_y
                            sub_player.base_x = tired_player.base_x
                            sub_player.base_y = tired_player.base_y
                            
                            idx = home_team.starters.index(tired_player)
                            home_team.starters[idx] = sub_player
                            all_players = home_team.starters + away_team.starters
                            
                            home_team.subs_left -= 1
                            game_status_text = f"🔄 선수 교체: [{tired_player.name}] OUT -> [{sub_player.name}] IN"
                    else:
                        game_status_text = "❌ 교체 불가 (잔여 횟수 소진)"

    current_speed = SPEED_LEVELS[speed_idx]

    if game_state == "MATCH" and not is_paused:
        match_time += (1.0 / 60.0) * current_speed

        if match_time >= match_duration:
            game_state = "SUMMARY"
            play_sound_effect("whistle")

        # 득점 판정
        if pitch.right_goal.collidepoint(ball.x, ball.y):
            home_score += 1
            if ball.possessor:
                ball.possessor.goals += 1
            play_sound_effect("goal")
            for _ in range(60):
                particles.append(Particle(ball.x, ball.y))
            game_status_text = f"⚽ GOAL! 홈 팀 득점! ({home_score} : {away_score})"
            ball.reset_to_center()
            st1 = home_team.starters[len(home_team.starters)-1]
            ball.possessor = st1
        elif pitch.left_goal.collidepoint(ball.x, ball.y):
            away_score += 1
            if ball.possessor:
                ball.possessor.goals += 1
            play_sound_effect("goal")
            for _ in range(60):
                particles.append(Particle(ball.x, ball.y))
            game_status_text = f"⚽ GOAL! 원정 팀 득점! ({home_score} : {away_score})"
            ball.reset_to_center()
            ast1 = away_team.starters[len(away_team.starters)-1]
            ball.possessor = ast1

        # 킥오프 백패스
        if kickoff_phase and ball.possessor:
            passer = ball.possessor
            cm_list = [p for p in (home_team.starters if passer.team == 'home' else away_team.starters) if "CM" in p.name or "CDM" in p.name or "CAM" in p.name]
            if not cm_list:
                cm_list = [p for p in (home_team.starters if passer.team == 'home' else away_team.starters) if p != passer]
            if cm_list:
                receiver = min(cm_list, key=lambda p: math.hypot(p.x - passer.x, p.y - passer.y))
                dx = receiver.x - passer.x
                dy = receiver.y - passer.y
                dist = math.hypot(dx, dy)
                if dist > 0:
                    ball.vx = (dx / dist) * 5.0
                    ball.vy = (dy / dist) * 5.0
                ball.possessor = None
                kickoff_phase = False
                game_status_text = f"[{passer.name}] 킥오프 백패스 -> [{receiver.name}]! 전진 공격 시작!"

        # 소유권 및 파울
        elif ball.possessor is None:
            closest_player = min(all_players, key=lambda p: math.hypot(p.x - ball.x, p.y - ball.y))
            if math.hypot(closest_player.x - ball.x, closest_player.y - ball.y) < 18:
                if random.random() < 0.003:
                    play_sound_effect("foul")
                    game_status_text = f"🚨 파울! [{closest_player.name}] 반칙 선언!"
                    ball.reset_to_center()
                    st1 = home_team.starters[len(home_team.starters)-1]
                    ball.possessor = st1
                else:
                    ball.possessor = closest_player
                    game_status_text = f"[{closest_player.name}] 공 소유!"

        # 패스/슈팅 (전술에 따른 패스 확률 및 성향 반영)
        elif int(match_time * 60) % int(max(10, 80 / current_speed)) == 0:
            passer = ball.possessor
            if passer:
                target_goal_x = PITCH_X + PITCH_WIDTH if passer.team == 'home' else PITCH_X
                dist_to_goal = abs(passer.x - target_goal_x)

                shot_threshold = 0.5 + (passer.stat_shooting / 300.0)
                if dist_to_goal < 480 and random.random() < shot_threshold:
                    goal_center_y = PITCH_CENTER_Y + random.uniform(-25, 25)
                    dx = target_goal_x - passer.x
                    dy = goal_center_y - passer.y
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        shot_speed = 8.0 + (passer.stat_shooting / 35.0)
                        ball.vx = (dx / dist) * shot_speed
                        ball.vy = (dy / dist) * shot_speed
                    ball.possessor = None
                    game_status_text = f"🔥 [{passer.name}] 상대 골대 향해 강력한 슈팅!"
                else:
                    teammates = [p for p in (home_team.starters if passer.team == 'home' else away_team.starters) if p != passer]
                    if teammates:
                        if passer.team == 'home':
                            forward_teammates = [p for p in teammates if p.x >= passer.x - 30]
                        else:
                            forward_teammates = [p for p in teammates if p.x <= passer.x + 30]
                        
                        receiver_pool = forward_teammates if forward_teammates else teammates
                        receiver = random.choice(receiver_pool)
                        
                        is_offside = False
                        if passer.team == 'home':
                            opp_defenders = sorted([p for p in away_team.starters if p.name != 'A-GK'], key=lambda p: p.x)
                            if len(opp_defenders) >= 2 and receiver.x > PITCH_CENTER_X:
                                if receiver.x > opp_defenders[1].x and receiver.x > passer.x:
                                    is_offside = True
                        else:
                            opp_defenders = sorted([p for p in home_team.starters if p.name != 'H-GK'], key=lambda p: p.x, reverse=True)
                            if len(opp_defenders) >= 2 and receiver.x < PITCH_CENTER_X:
                                if receiver.x < opp_defenders[1].x and receiver.x < passer.x:
                                    is_offside = True

                        if is_offside:
                            play_sound_effect("foul")
                            game_status_text = f"🚩 오프사이드! [{receiver.name}] 위치 반칙"
                            ball.reset_to_center()
                            st1 = home_team.starters[len(home_team.starters)-1]
                            ball.possessor = st1
                        else:
                            dx = receiver.x - passer.x
                            dy = receiver.y - passer.y
                            dist = math.hypot(dx, dy)
                            if dist > 0:
                                pass_speed = 5.0 + (passer.stat_passing / 40.0)
                                ball.vx = (dx / dist) * pass_speed
                                ball.vy = (dy / dist) * pass_speed
                            ball.possessor = None
                            game_status_text = f"[{passer.name}] -> [{receiver.name}] 전진 패스 연결!"

        # AI 이동
        for p in all_players:
            if ball.possessor == p:
                continue
            tactic_val = home_team.tactic if p.team == 'home' else "TIKI_TAKA"
            target_x, target_y = p.calculate_dynamic_target(ball.x, ball.y, tactic_val)
            if ball.possessor is None and math.hypot(p.x - ball.x, p.y - ball.y) < 180:
                target_x, target_y = ball.x, ball.y
            p.move_towards(target_x, target_y, current_speed, tactic_val)

        ball.update(current_speed)

    for p in particles[:]:
        p.update()
        if p.life <= 0:
            particles.remove(p)

    # 화면 렌더링
    if game_state == "MENU":
        screen.fill((20, 20, 25))
        title_surf = font_title.render("⚽ 축구 매니저 시뮬레이터 - 포메이션 및 전술 선택", True, (255, 255, 255))
        screen.blit(title_surf, (SCREEN_WIDTH / 2 - title_surf.get_width() / 2, 30))

        pygame.draw.rect(screen, COLOR_PANEL, (100, 90, 520, 520), border_radius=10)
        pygame.draw.rect(screen, COLOR_PANEL, (660, 90, 520, 520), border_radius=10)

        screen.blit(font_bold.render(f"🏠 홈 팀 선발 명단 ({home_team.formation} 포메이션)", True, COLOR_HOME), (130, 110))
        screen.blit(font_bold.render(f"✈️ 원정 팀 선발 명단 ({away_team.formation} 포메이션)", True, COLOR_AWAY), (690, 110))

        y_off = 150
        for p in home_team.starters:
            screen.blit(font.render(f"[{p.name}]  속도:{p.stat_speed} | 패스:{p.stat_passing} | 슛:{p.stat_shooting}", True, (220, 220, 220)), (130, y_off))
            y_off += 32

        y_off = 150
        for p in away_team.starters:
            screen.blit(font.render(f"[{p.name}]  속도:{p.stat_speed} | 패스:{p.stat_passing} | 슛:{p.stat_shooting}", True, (220, 220, 220)), (690, y_off))
            y_off += 32

        # 포메이션 선택 버튼 그리기
        label_surf = font.bold.render("마우스로 홈 팀 포메이션을 선택하세요:", True, (255, 255, 255))
        screen.blit(label_surf, (130, 535))

        for rect, form_name in formation_buttons:
            is_hover = rect.collidepoint(mouse_pos)
            is_selected = (home_team.formation == form_name)
            
            btn_color = COLOR_BUTTON_ACTIVE if is_selected else (COLOR_BUTTON_HOVER if is_hover else COLOR_BUTTON)
            pygame.draw.rect(screen, btn_color, rect, border_radius=6)
            pygame.draw.rect(screen, (200, 200, 200), rect, 2, border_radius=6)
            
            txt_surf = font_bold.render(form_name, True, (255, 255, 255))
            screen.blit(txt_surf, (rect.centerx - txt_surf.get_width() / 2, rect.centery - txt_surf.get_height() / 2))

        prompt_surf = font_title.render("▶ [ENTER] 키를 누르면 킥오프가 시작됩니다!", True, (0, 255, 255))
        screen.blit(prompt_surf, (SCREEN_WIDTH / 2 - prompt_surf.get_width() / 2, 635))

    elif game_state == "SUMMARY":
        screen.fill((15, 15, 20))
        summary_title = font_title.render("🏁 경기 종료 (FULL TIME)", True, (255, 200, 0))
        screen.blit(summary_title, (SCREEN_WIDTH / 2 - summary_title.get_width() / 2, 60))

        pygame.draw.rect(screen, COLOR_PANEL, (340, 140, 600, 420), border_radius=15)
        score_surf = font_title.render(f"{home_score}  :  {away_score}", True, (255, 255, 255))
        screen.blit(score_surf, (SCREEN_WIDTH / 2 - score_surf.get_width() / 2, 170))

        mvp_player = max(all_players, key=lambda p: p.goals * 10 + p.stat_shooting + p.stat_passing)
        mvp_text = f"⭐ MAN OF THE MATCH (MVP): [{mvp_player.name}] ({'홈' if mvp_player.team=='home' else '원정'}팀) - 득점: {mvp_player.goals}골"
        screen.blit(font_bold.render(mvp_text, True, (255, 215, 0)), (SCREEN_WIDTH / 2 - font_bold.size(mvp_text)[0] / 2, 320))

        restart_surf = font_bold.render("🔄 [R] 키를 누르면 전술판으로 돌아갑니다.", True, (0, 255, 255))
        screen.blit(restart_surf, (SCREEN_WIDTH / 2 - restart_surf.get_width() / 2, 460))

    else:
        pitch.draw(screen)
        render_list = all_players + [ball]
        render_list.sort(key=lambda obj: obj.y)

        for obj in render_list:
            if isinstance(obj, Ball):
                obj.draw(screen)
            else:
                obj.draw(screen, (ball.possessor == obj))

        for p in particles:
            p.draw(screen)

        pygame.draw.rect(screen, (15, 15, 15), (0, 0, SCREEN_WIDTH, 85))
        score_surf = font_score.render(f"HOME  {home_score} : {away_score}  AWAY", True, (255, 255, 255))
        screen.blit(score_surf, (SCREEN_WIDTH / 2 - score_surf.get_width() / 2, 10))

        time_text = f"시간: {int(match_time)}/{int(match_duration)}초"
        speed_text = f"배속: {current_speed:.1f}x (단계 {speed_idx + 1}/10)"
        
        tactic_korean = {
            "TIKI_TAKA": "1. 티키타카",
            "GEGENPRESSING": "2. 게겐프레싱",
            "COUNTER": "3. 선수비 후역습",
            "WING_PLAY": "4. 측면 돌파"
        }
        tactic_text = f"우리팀 전술: {tactic_korean[home_team.tactic]} ([1~4]키 변경) | 교체잔여: {home_team.subs_left}회 ([S]키)"

        screen.blit(font.render(time_text, True, (200, 200, 200)), (40, 12))
        screen.blit(font_bold.render(speed_text, True, (0, 255, 255) if not is_paused else (255, 100, 100)), (40, 35))
        screen.blit(font_bold.render(tactic_text, True, (255, 255, 100)), (40, 58))
        
        status_surf = font.render(f"상황: {game_status_text}" if not is_paused else "상황: [일시정지 중 - 스페이스바로 재개]", True, (255, 255, 0))
        screen.blit(status_surf, (SCREEN_WIDTH - status_surf.get_width() - 40, 58))

    pygame.display.flip()
    clock.tick(60)
import math
import random
import sys
import pygame

# 초기화
pygame.init()

# 화면 설정 (1280x720 표준 해상도)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("축구 모의 게임 - 선수 개별 능력치 및 매치 엔진")

# 색상 정의
COLOR_GRASS_1 = (34, 139, 34)
COLOR_GRASS_2 = (40, 150, 40)
COLOR_LINE = (240, 240, 240)
COLOR_HOME = (0, 119, 204)
COLOR_AWAY = (220, 20, 60)
COLOR_BALL = (255, 255, 255)
COLOR_GOAL = (200, 200, 200)
COLOR_STADIUM = (40, 40, 40)

font = pygame.font.SysFont("malgungothic", 16)
font_bold = pygame.font.SysFont("malgungothic", 18, bold=True)
font_score = pygame.font.SysFont("malgungothic", 22, bold=True)

# --- [FIFA 공식 규격 및 스케일 정의] ---
SCALE = 9
METER_LENGTH = 105
METER_WIDTH = 68

PITCH_WIDTH = int(METER_LENGTH * SCALE)   # 945픽셀
PITCH_HEIGHT = int(METER_WIDTH * SCALE)   # 612픽셀
PITCH_X = (SCREEN_WIDTH - PITCH_WIDTH) // 2  # 167
PITCH_Y = 95
PITCH_CENTER_X = PITCH_X + PITCH_WIDTH / 2
PITCH_CENTER_Y = PITCH_Y + PITCH_HEIGHT / 2


class Pitch:
    def __init__(self):
        self.rect = pygame.Rect(PITCH_X, PITCH_Y, PITCH_WIDTH, PITCH_HEIGHT)
        goal_w = int(7.32 * SCALE)
        goal_depth = int(2.0 * SCALE)
        self.left_goal = pygame.Rect(PITCH_X - goal_depth, PITCH_CENTER_Y - goal_w/2, goal_depth, goal_w)
        self.right_goal = pygame.Rect(PITCH_X + PITCH_WIDTH, PITCH_CENTER_Y - goal_w/2, goal_depth, goal_w)

    def draw(self, surface):
        surface.fill(COLOR_STADIUM)
        
        stripe_width = int(5 * SCALE)
        for x in range(PITCH_X, PITCH_X + PITCH_WIDTH, stripe_width * 2):
            stripe_rect = pygame.Rect(x, PITCH_Y, stripe_width, PITCH_HEIGHT)
            pygame.draw.rect(surface, COLOR_GRASS_1, stripe_rect)
            stripe_rect2 = pygame.Rect(x + stripe_width, PITCH_Y, stripe_width, PITCH_HEIGHT)
            pygame.draw.rect(surface, COLOR_GRASS_2, stripe_rect2)

        pygame.draw.rect(surface, COLOR_LINE, self.rect, 3)
        pygame.draw.line(surface, COLOR_LINE, (PITCH_CENTER_X, PITCH_Y), (PITCH_CENTER_X, PITCH_Y + PITCH_HEIGHT), 3)

        center_circle_r = int(9.15 * SCALE)
        pygame.draw.circle(surface, COLOR_LINE, (int(PITCH_CENTER_X), int(PITCH_CENTER_Y)), center_circle_r, 3)
        pygame.draw.circle(surface, COLOR_LINE, (int(PITCH_CENTER_X), int(PITCH_CENTER_Y)), 5)

        box_depth = int(16.5 * SCALE)
        box_width = int(40.32 * SCALE)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X, PITCH_CENTER_Y - box_width/2, box_depth, box_width), 3)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - box_depth, PITCH_CENTER_Y - box_width/2, box_depth, box_width), 3)

        goal_area_depth = int(5.5 * SCALE)
        goal_area_width = int(18.32 * SCALE)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X, PITCH_CENTER_Y - goal_area_width/2, goal_area_depth, goal_area_width), 3)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - goal_area_depth, PITCH_CENTER_Y - goal_area_width/2, goal_area_depth, goal_area_width), 3)

        spot_dist = int(11.0 * SCALE)
        pygame.draw.circle(surface, COLOR_LINE, (PITCH_X + spot_dist, int(PITCH_CENTER_Y)), 4)
        pygame.draw.circle(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - spot_dist, int(PITCH_CENTER_Y)), 4)

        pygame.draw.rect(surface, COLOR_GOAL, self.left_goal, 3)
        pygame.draw.rect(surface, COLOR_GOAL, self.right_goal, 3)


class Player:
    def __init__(self, x, y, team, name, speed=2.2, passing=70, shooting=70):
        self.original_base_x = x
        self.original_base_y = y
        self.base_x = x
        self.base_y = y
        self.x = x
        self.y = y
        self.team = team
        self.name = name
        
        # --- [개별 능력치 스탯] ---
        self.stat_speed = speed       # 이동 속도
        self.stat_passing = passing   # 패스 정확도 (0~100)
        self.stat_shooting = shooting # 슛 결정력 (0~100)

    def update_tactical_position(self, tactic):
        offset_x = 0
        if self.team == 'home':
            if tactic == "ATTACK":
                offset_x = 45
            elif tactic == "DEFENSE":
                offset_x = -45
        self.base_x = self.original_base_x + offset_x

    def move_towards(self, target_x, target_y, speed_multiplier):
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.hypot(dx, dy)

        # 능력치 기반 속도 반영
        effective_speed = self.stat_speed * speed_multiplier
        if distance > 2:
            self.x += (dx / distance) * effective_speed
            self.y += (dy / distance) * effective_speed

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

        name_surf = font.render(self.name, True, (255, 255, 255))
        surface.blit(name_surf, (int(self.x) - 12, int(self.y) - 22))


class Ball:
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

    def reset(self):
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


# --- [포지션별 개별 능력치를 가진 선수단 생성] ---
# (x, y, 팀, 이름, 속도, 패스스탯, 슛스탯)
def create_team_players(is_home=True):
    px = PITCH_X if is_home else PITCH_X + PITCH_WIDTH
    dir_sign = 1 if is_home else -1
    team_str = 'home' if is_home else 'away'
    prefix = 'H' if is_home else 'A'

    return [
        Player(px + dir_sign * 35, PITCH_CENTER_Y, team_str, f'{prefix}-GK', speed=1.8, passing=60, shooting=30),
        Player(px + dir_sign * 110, PITCH_CENTER_Y - 190 * dir_sign if not is_home else PITCH_CENTER_Y - 190, team_str, f'{prefix}-LB', speed=2.3, passing=72, shooting=45),
        Player(px + dir_sign * 90, PITCH_CENTER_Y - 65 * dir_sign if not is_home else PITCH_CENTER_Y - 65, team_str, f'{prefix}-CB1', speed=2.0, passing=68, shooting=40),
        Player(px + dir_sign * 90, PITCH_CENTER_Y + 65 * dir_sign if not is_home else PITCH_CENTER_Y + 65, team_str, f'{prefix}-CB2', speed=2.0, passing=68, shooting=40),
        Player(px + dir_sign * 110, PITCH_CENTER_Y + 190 * dir_sign if not is_home else PITCH_CENTER_Y + 190, team_str, f'{prefix}-RB', speed=2.3, passing=72, shooting=45),
        Player(px + dir_sign * 240, PITCH_CENTER_Y - 210 * dir_sign if not is_home else PITCH_CENTER_Y - 210, team_str, f'{prefix}-LM', speed=2.4, passing=78, shooting=65),
        Player(px + dir_sign * 220, PITCH_CENTER_Y - 70 * dir_sign if not is_home else PITCH_CENTER_Y - 70, team_str, f'{prefix}-CM1', speed=2.1, passing=85, shooting=60),
        Player(px + dir_sign * 220, PITCH_CENTER_Y + 70 * dir_sign if not is_home else PITCH_CENTER_Y + 70, team_str, f'{prefix}-CM2', speed=2.1, passing=85, shooting=60),
        Player(px + dir_sign * 240, PITCH_CENTER_Y + 210 * dir_sign if not is_home else PITCH_CENTER_Y + 210, team_str, f'{prefix}-RM', speed=2.4, passing=78, shooting=65),
        Player(px + dir_sign * 380, PITCH_CENTER_Y - 50 * dir_sign if not is_home else PITCH_CENTER_Y - 50, team_str, f'{prefix}-ST1', speed=2.3, passing=70, shooting=88),
        Player(px + dir_sign * 380, PITCH_CENTER_Y + 50 * dir_sign if not is_home else PITCH_CENTER_Y + 50, team_str, f'{prefix}-ST2', speed=2.3, passing=70, shooting=88),
    ]

pitch = Pitch()
ball = Ball(PITCH_CENTER_X, PITCH_CENTER_Y)

home_players = create_team_players(is_home=True)
away_players = create_team_players(is_home=False)
all_players = home_players + away_players

clock = pygame.time.Clock()
match_time = 0.0
game_status_text = "개별 능력치 스탯 시스템 적용 완료!"

home_score = 0
away_score = 0
is_paused = False

SPEED_LEVELS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.5, 10.0]
speed_idx = 1
home_tactic = "BALANCED"

# 메인 게임 루프
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                is_paused = not is_paused
            elif event.key == pygame.K_UP or event.key == pygame.K_EQUALS:
                if speed_idx < len(SPEED_LEVELS) - 1:
                    speed_idx += 1
            elif event.key == pygame.K_DOWN or event.key == pygame.K_MINUS:
                if speed_idx > 0:
                    speed_idx -= 1
            elif event.key == pygame.K_1:
                home_tactic = "ATTACK"
                game_status_text = "전술 변경: [공격형]"
            elif event.key == pygame.K_2:
                home_tactic = "BALANCED"
                game_status_text = "전술 변경: [균형형]"
            elif event.key == pygame.K_3:
                home_tactic = "DEFENSE"
                game_status_text = "전술 변경: [수비형]"

    current_speed = SPEED_LEVELS[speed_idx]

    if not is_paused:
        match_time += (1.0 / 60.0) * current_speed

        for p in home_players:
            p.update_tactical_position(home_tactic)

        # 1. 득점 판정
        if pitch.right_goal.collidepoint(ball.x, ball.y):
            home_score += 1
            game_status_text = f"⚽ GOAL! 홈 팀 득점! ({home_score} : {away_score})"
            ball.reset()
            for p in all_players:
                p.x, p.y = p.base_x, p.base_y
        elif pitch.left_goal.collidepoint(ball.x, ball.y):
            away_score += 1
            game_status_text = f"⚽ GOAL! 원정 팀 득점! ({home_score} : {away_score})"
            ball.reset()
            for p in all_players:
                p.x, p.y = p.base_x, p.base_y

        # 2. 소유권 판정
        if ball.possessor is None:
            closest_player = min(all_players, key=lambda p: math.hypot(p.x - ball.x, p.y - ball.y))
            dist_to_ball = math.hypot(closest_player.x - ball.x, closest_player.y - ball.y)

            if dist_to_ball < 18:
                ball.possessor = closest_player
                game_status_text = f"[{closest_player.name}] 공 소유!"

        # 3. 능력치 반영 패스/슈팅 판단
        elif int(match_time * 60) % int(max(10, 80 / current_speed)) == 0:
            passer = ball.possessor
            target_goal_x = PITCH_X + PITCH_WIDTH if passer.team == 'home' else PITCH_X
            dist_to_goal = abs(passer.x - target_goal_x)

            # 슈팅 스탯(stat_shooting)이 높을수록 슛을 시도할 확률 증가
            shot_threshold = 0.5 + (passer.stat_shooting / 300.0)
            if dist_to_goal < 480 and random.random() < shot_threshold:
                goal_center_y = PITCH_CENTER_Y + random.uniform(-25, 25)
                dx = target_goal_x - passer.x
                dy = goal_center_y - passer.y
                dist = math.hypot(dx, dy)
                
                if dist > 0:
                    # 슈팅 스탯에 따라 슛 속도와 정확도 보정
                    shot_speed = 8.0 + (passer.stat_shooting / 35.0)
                    ball.vx = (dx / dist) * shot_speed
                    ball.vy = (dy / dist) * shot_speed
                    
                ball.possessor = None
                game_status_text = f"🔥 [{passer.name}] (결정력:{passer.stat_shooting}) 슈팅!"
            else:
                teammates = [p for p in home_players if p != passer] if passer.team == 'home' else [p for p in away_players if p != passer]
                if teammates:
                    receiver = random.choice(teammates)
                    dx = receiver.x - passer.x
                    dy = receiver.y - passer.y
                    dist = math.hypot(dx, dy)
                    
                    if dist > 0:
                        # 패스 스탯(stat_passing)이 높을수록 패스 속도가 정교함
                        pass_speed = 5.0 + (passer.stat_passing / 40.0)
                        ball.vx = (dx / dist) * pass_speed
                        ball.vy = (dy / dist) * pass_speed
                        
                    ball.possessor = None
                    game_status_text = f"[{passer.name}] (패스:{passer.stat_passing}) -> [{receiver.name}]"

        # 4. AI 이동 로직
        for p in all_players:
            if ball.possessor == p:
                continue
            elif ball.possessor is None:
                p.move_towards(ball.x, ball.y, current_speed)
            else:
                p.move_towards(p.base_x, p.base_y, current_speed)

        ball.update(current_speed)

    # 5. 화면 렌더링
    pitch.draw(screen)

    render_list = all_players + [ball]
    render_list.sort(key=lambda obj: obj.y)

    for obj in render_list:
        if isinstance(obj, Ball):
            obj.draw(screen)
        else:
            has_ball = (ball.possessor == obj)
            obj.draw(screen, has_ball)

    # UI 영역
    pygame.draw.rect(screen, (15, 15, 15), (0, 0, SCREEN_WIDTH, 85))
    
    score_str = f"HOME  {home_score} : {away_score}  AWAY"
    score_surf = font_score.render(score_str, True, (255, 255, 255))
    screen.blit(score_surf, (SCREEN_WIDTH / 2 - score_surf.get_width() / 2, 10))

    time_text = f"시간: {int(match_time)}초"
    speed_text = f"배속: {current_speed:.1f}x (단계 {speed_idx + 1}/10)"
    tactic_korean = {"ATTACK": "공격형 (1)", "BALANCED": "균형형 (2)", "DEFENSE": "수비형 (3)"}
    tactic_text = f"우리팀 전술: {tactic_korean[home_tactic]}"

    time_surf = font.render(time_text, True, (200, 200, 200))
    speed_surf = font_bold.render(speed_text, True, (0, 255, 255) if not is_paused else (255, 100, 100))
    tactic_surf = font_bold.render(tactic_text, True, (255, 100, 100) if home_tactic == "ATTACK" else ((100, 255, 100) if home_tactic == "BALANCED" else (100, 150, 255)))
    
    status_text = f"상황: {game_status_text}"
    if is_paused:
        status_text = "상황: [일시정지 중 - 스페이스바로 재개]"
    status_surf = font.render(status_text, True, (255, 255, 0))

    screen.blit(time_surf, (40, 12))
    screen.blit(speed_surf, (40, 35))
    screen.blit(tactic_surf, (40, 58))
    screen.blit(status_surf, (SCREEN_WIDTH - status_surf.get_width() - 40, 58))

    pygame.display.flip()
    clock.tick(60)
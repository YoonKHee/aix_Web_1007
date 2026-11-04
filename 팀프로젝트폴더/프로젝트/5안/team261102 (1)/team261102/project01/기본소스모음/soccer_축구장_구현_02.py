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
pygame.display.set_caption("축구 모의 게임 - 4-4-2 포메이션 (11 vs 11)")

# 색상 정의
COLOR_GRASS_1 = (34, 139, 34)    # 기본 잔디
COLOR_GRASS_2 = (40, 150, 40)    # 밝은 잔디 (줄무늬용)
COLOR_LINE = (240, 240, 240)     # 규격 라인
COLOR_HOME = (0, 119, 204)       # 홈 팀 (파란색)
COLOR_AWAY = (220, 20, 60)       # 원정 팀 (크림슨 레드)
COLOR_BALL = (255, 255, 255)     # 공
COLOR_GOAL = (200, 200, 200)     # 골대
COLOR_STADIUM = (40, 40, 40)     # 관중석 외곽 배경

font = pygame.font.SysFont("malgungothic", 16)

# --- [FIFA 공식 규격 및 스케일 정의] ---
SCALE = 9
METER_LENGTH = 105
METER_WIDTH = 68

PITCH_WIDTH = int(METER_LENGTH * SCALE)   # 945픽셀
PITCH_HEIGHT = int(METER_WIDTH * SCALE)   # 612픽셀
PITCH_X = (SCREEN_WIDTH - PITCH_WIDTH) // 2  # 167
PITCH_Y = 85
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
        
        # 잔디 줄무늬 패턴
        stripe_width = int(5 * SCALE)
        for x in range(PITCH_X, PITCH_X + PITCH_WIDTH, stripe_width * 2):
            stripe_rect = pygame.Rect(x, PITCH_Y, stripe_width, PITCH_HEIGHT)
            pygame.draw.rect(surface, COLOR_GRASS_1, stripe_rect)
            stripe_rect2 = pygame.Rect(x + stripe_width, PITCH_Y, stripe_width, PITCH_HEIGHT)
            pygame.draw.rect(surface, COLOR_GRASS_2, stripe_rect2)

        # 외곽 터치라인 및 골라인
        pygame.draw.rect(surface, COLOR_LINE, self.rect, 3)

        # 하프라인
        pygame.draw.line(surface, COLOR_LINE, (PITCH_CENTER_X, PITCH_Y), (PITCH_CENTER_X, PITCH_Y + PITCH_HEIGHT), 3)

        # 센터 서클 (반지름 9.15m)
        center_circle_r = int(9.15 * SCALE)
        pygame.draw.circle(surface, COLOR_LINE, (int(PITCH_CENTER_X), int(PITCH_CENTER_Y)), center_circle_r, 3)
        pygame.draw.circle(surface, COLOR_LINE, (int(PITCH_CENTER_X), int(PITCH_CENTER_Y)), 5)

        # 페널티 박스 & 골 에어리어
        box_depth = int(16.5 * SCALE)
        box_width = int(40.32 * SCALE)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X, PITCH_CENTER_Y - box_width/2, box_depth, box_width), 3)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - box_depth, PITCH_CENTER_Y - box_width/2, box_depth, box_width), 3)

        goal_area_depth = int(5.5 * SCALE)
        goal_area_width = int(18.32 * SCALE)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X, PITCH_CENTER_Y - goal_area_width/2, goal_area_depth, goal_area_width), 3)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - goal_area_depth, PITCH_CENTER_Y - goal_area_width/2, goal_area_depth, goal_area_width), 3)

        # 페널티 스팟
        spot_dist = int(11.0 * SCALE)
        pygame.draw.circle(surface, COLOR_LINE, (PITCH_X + spot_dist, int(PITCH_CENTER_Y)), 4)
        pygame.draw.circle(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - spot_dist, int(PITCH_CENTER_Y)), 4)

        # 골대
        pygame.draw.rect(surface, COLOR_GOAL, self.left_goal, 3)
        pygame.draw.rect(surface, COLOR_GOAL, self.right_goal, 3)


class Player:
    def __init__(self, x, y, team, name):
        self.base_x = x
        self.base_y = y
        self.x = x
        self.y = y
        self.team = team
        self.name = name
        self.speed = 2.2  # 11명이 뛰므로 속도를 약간 조절하여 균형 유지

    def move_towards(self, target_x, target_y):
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.hypot(dx, dy)

        if distance > 2:
            self.x += (dx / distance) * self.speed
            self.y += (dy / distance) * self.speed

        self.x = max(PITCH_X + 12, min(PITCH_X + PITCH_WIDTH - 12, self.x))
        self.y = max(PITCH_Y + 12, min(PITCH_Y + PITCH_HEIGHT - 12, self.y))

    def draw(self, surface, has_ball):
        # 그림자
        shadow_surf = pygame.Surface((18, 9), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 90), (0, 0, 18, 9))
        surface.blit(shadow_surf, (int(self.x) - 9, int(self.y) + 3))

        color = (255, 140, 0) if has_ball else (COLOR_HOME if self.team == 'home' else COLOR_AWAY)
        radius = 11 if has_ball else 9

        pygame.draw.circle(surface, (20, 20, 20), (int(self.x), int(self.y)), radius + 1)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)

        # 이름 (글자가 너무 겹치지 않게 크기 최소화)
        name_surf = font.render(self.name, True, (255, 255, 255))
        surface.blit(name_surf, (int(self.x) - 12, int(self.y) - 22))


class Ball:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.possessor = None

    def update(self):
        if self.possessor:
            self.x = self.possessor.x + 12
            self.y = self.possessor.y
            self.vx = 0
            self.vy = 0
        else:
            self.x += self.vx
            self.y += self.vy
            self.vx *= 0.96
            self.vy *= 0.96

            if self.x < PITCH_X or self.x > PITCH_X + PITCH_WIDTH:
                self.vx *= -0.5
            if self.y < PITCH_Y or self.y > PITCH_Y + PITCH_HEIGHT:
                self.vy *= -0.5

    def draw(self, surface):
        shadow_surf = pygame.Surface((12, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 110), (0, 0, 12, 6))
        surface.blit(shadow_surf, (int(self.x) - 6, int(self.y) + 5))

        pygame.draw.circle(surface, (30, 30, 30), (int(self.x), int(self.y)), 7)
        pygame.draw.circle(surface, COLOR_BALL, (int(self.x), int(self.y)), 5)


# 필드 및 공 생성
pitch = Pitch()
ball = Ball(PITCH_CENTER_X, PITCH_CENTER_Y)

# --- [4-4-2 포메이션 11명 배치 좌표계 설정] ---
# 홈 팀 (왼쪽 진영 공격 방향)
home_players = [
    Player(PITCH_X + 35, PITCH_CENTER_Y, 'home', 'H-GK'),               # 골키퍼
    Player(PITCH_X + 110, PITCH_CENTER_Y - 190, 'home', 'H-LB'),        # 레프트백
    Player(PITCH_X + 90, PITCH_CENTER_Y - 65, 'home', 'H-CB1'),         # 센터백 1
    Player(PITCH_X + 90, PITCH_CENTER_Y + 65, 'home', 'H-CB2'),         # 센터백 2
    Player(PITCH_X + 110, PITCH_CENTER_Y + 190, 'home', 'H-RB'),        # 라이트백
    Player(PITCH_X + 240, PITCH_CENTER_Y - 210, 'home', 'H-LM'),        # 레프트 미드필더
    Player(PITCH_X + 220, PITCH_CENTER_Y - 70, 'home', 'H-CM1'),        # 중앙 미드필더 1
    Player(PITCH_X + 220, PITCH_CENTER_Y + 70, 'home', 'H-CM2'),        # 중앙 미드필더 2
    Player(PITCH_X + 240, PITCH_CENTER_Y + 210, 'home', 'H-RM'),        # 라이트 미드필더
    Player(PITCH_X + 380, PITCH_CENTER_Y - 50, 'home', 'H-ST1'),        # 공격수 1
    Player(PITCH_X + 380, PITCH_CENTER_Y + 50, 'home', 'H-ST2'),        # 공격수 2
]

# 원정 팀 (오른쪽 진영 공격 방향 - 대칭 배치)
away_players = [
    Player(PITCH_X + PITCH_WIDTH - 35, PITCH_CENTER_Y, 'away', 'A-GK'),
    Player(PITCH_X + PITCH_WIDTH - 110, PITCH_CENTER_Y + 190, 'away', 'A-LB'),
    Player(PITCH_X + PITCH_WIDTH - 90, PITCH_CENTER_Y + 65, 'away', 'A-CB1'),
    Player(PITCH_X + PITCH_WIDTH - 90, PITCH_CENTER_Y - 65, 'away', 'A-CB2'),
    Player(PITCH_X + PITCH_WIDTH - 110, PITCH_CENTER_Y - 190, 'away', 'A-RB'),
    Player(PITCH_X + PITCH_WIDTH - 240, PITCH_CENTER_Y + 210, 'away', 'A-LM'),
    Player(PITCH_X + PITCH_WIDTH - 220, PITCH_CENTER_Y + 70, 'away', 'A-CM1'),
    Player(PITCH_X + PITCH_WIDTH - 220, PITCH_CENTER_Y - 70, 'away', 'A-CM2'),
    Player(PITCH_X + PITCH_WIDTH - 240, PITCH_CENTER_Y - 210, 'away', 'A-RM'),
    Player(PITCH_X + PITCH_WIDTH - 380, PITCH_CENTER_Y + 50, 'away', 'A-ST1'),
    Player(PITCH_X + PITCH_WIDTH - 380, PITCH_CENTER_Y - 50, 'away', 'A-ST2'),
]

all_players = home_players + away_players

clock = pygame.time.Clock()
match_time = 0
game_status_text = "4-4-2 포메이션 22명 선수 배치 완료!"

# 메인 게임 루프
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    match_time += 1

    # 1. 소유권 판정 (가장 가까운 선수)
    if ball.possessor is None:
        closest_player = min(all_players, key=lambda p: math.hypot(p.x - ball.x, p.y - ball.y))
        dist_to_ball = math.hypot(closest_player.x - ball.x, closest_player.y - ball.y)

        if dist_to_ball < 18:
            ball.possessor = closest_player
            game_status_text = f"[{closest_player.name}] 공 소유!"

    elif match_time % 90 == 0:
        passer = ball.possessor
        teammates = [p for p in home_players if p != passer] if passer.team == 'home' else [p for p in away_players if p != passer]
        
        if teammates:
            receiver = random.choice(teammates)
            dx = receiver.x - passer.x
            dy = receiver.y - passer.y
            dist = math.hypot(dx, dy)
            
            if dist > 0:
                pass_speed = 6.0
                ball.vx = (dx / dist) * pass_speed
                ball.vy = (dy / dist) * pass_speed
                
            ball.possessor = None
            game_status_text = f"[{passer.name}] -> [{receiver.name}] 패스 성공!"

    # 2. AI 이동 로직
    for p in all_players:
        if ball.possessor == p:
            continue
        elif ball.possessor is None:
            # 공이 비어있으면 가까운 선수들이 공을 향해 압박
            p.move_towards(ball.x, ball.y)
        else:
            # 공이 소유된 상태면 각자 자기 포메이션 위치(base_x, base_y)로 복귀 정렬
            p.move_towards(p.base_x, p.base_y)

    ball.update()

    # 3. 화면 렌더링
    pitch.draw(screen)

    # Y축 깊이 정렬 (Depth Sorting)
    render_list = all_players + [ball]
    render_list.sort(key=lambda obj: obj.y)

    for obj in render_list:
        if isinstance(obj, Ball):
            obj.draw(screen)
        else:
            has_ball = (ball.possessor == obj)
            obj.draw(screen, has_ball)

    # 상단 UI
    pygame.draw.rect(screen, (15, 15, 15), (0, 0, SCREEN_WIDTH, 75))
    time_surf = font.render(f"경기 시간: {match_time // 60}초", True, (255, 255, 255))
    status_surf = font.render(f"상황: {game_status_text}", True, (255, 255, 0))
    screen.blit(time_surf, (40, 15))
    screen.blit(status_surf, (40, 42))

    pygame.display.flip()
    clock.tick(60)
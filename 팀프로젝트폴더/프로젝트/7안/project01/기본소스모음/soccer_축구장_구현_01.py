import math
import random
import sys
import pygame

# 초기화
pygame.init()

# 화면 설정 (1280x720)
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("축구 모의 게임 - 2.5D 입체 필드 및 그림자")

# 색상 정의
COLOR_GRASS_1 = (34, 139, 34)    # 기본 잔디
COLOR_GRASS_2 = (40, 150, 40)    # 밝은 잔디 (줄무늬용)
COLOR_LINE = (240, 240, 240)     # 라인 (살짝 아이보리빛 흰색)
COLOR_HOME = (0, 119, 204)       # 홈 팀 (파란색)
COLOR_AWAY = (220, 20, 60)       # 원정 팀 (크림슨 레드)
COLOR_BALL = (255, 255, 255)     # 공 (흰색 축구공 느낌)
COLOR_SHADOW = (0, 0, 0, 80)     # 그림자 색상
COLOR_GOAL = (200, 200, 200)     # 골대
COLOR_STADIUM = (40, 40, 40)     # 경기장 주변 (관중석/바깥 영역)

font = pygame.font.SysFont("malgungothic", 18)

# --- [축구장 규격 정의] ---
PITCH_X = 80
PITCH_Y = 90
PITCH_WIDTH = 1120
PITCH_HEIGHT = 560
PITCH_CENTER_X = PITCH_X + PITCH_WIDTH / 2
PITCH_CENTER_Y = PITCH_Y + PITCH_HEIGHT / 2


class Pitch:
    def __init__(self):
        self.rect = pygame.Rect(PITCH_X, PITCH_Y, PITCH_WIDTH, PITCH_HEIGHT)
        self.left_goal = pygame.Rect(PITCH_X - 40, PITCH_CENTER_Y - 50, 40, 100)
        self.right_goal = pygame.Rect(PITCH_X + PITCH_WIDTH, PITCH_CENTER_Y - 50, 40, 100)

    def draw(self, surface):
        # 1. 경기장 바깥 배경 (스타디움 관중석 느낌)
        surface.fill(COLOR_STADIUM)
        
        # 2. 잔디 줄무늬 패턴 (입체감 부여)----------------------------------------------------------------
        stripe_width = 37
        for x in range(PITCH_X, PITCH_X + PITCH_WIDTH, stripe_width * 2):
            stripe_rect = pygame.Rect(x, PITCH_Y, stripe_width, PITCH_HEIGHT)
            pygame.draw.rect(surface, COLOR_GRASS_1, stripe_rect)
            stripe_rect2 = pygame.Rect(x + stripe_width, PITCH_Y, stripe_width, PITCH_HEIGHT)
            pygame.draw.rect(surface, COLOR_GRASS_2, stripe_rect2)

        # 3. 외곽선 (터치라인 및 골라인)
        pygame.draw.rect(surface, COLOR_LINE, self.rect, 4)

        # 4. 하프라인 (중앙선)
        pygame.draw.line(surface, COLOR_LINE, (PITCH_CENTER_X, PITCH_Y), (PITCH_CENTER_X, PITCH_Y + PITCH_HEIGHT), 4)

        # 5. 센터 서클 & 센터 스팟
        pygame.draw.circle(surface, COLOR_LINE, (int(PITCH_CENTER_X), int(PITCH_CENTER_Y)), 70, 4)
        pygame.draw.circle(surface, COLOR_LINE, (int(PITCH_CENTER_X), int(PITCH_CENTER_Y)), 6)

        # 6. 페널티 박스 & 골 에어리어
        box_w, box_h = 140, 320
        goal_area_w, goal_area_h = 50, 140

        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X, PITCH_CENTER_Y - box_h/2, box_w, box_h), 4)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - box_w, PITCH_CENTER_Y - box_h/2, box_w, box_h), 4)

        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X, PITCH_CENTER_Y - goal_area_h/2, goal_area_w, goal_area_h), 4)
        pygame.draw.rect(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - goal_area_w, PITCH_CENTER_Y - goal_area_h/2, goal_area_w, goal_area_h), 4)

        # 7. 페널티 스팟
        pygame.draw.circle(surface, COLOR_LINE, (PITCH_X + 100, int(PITCH_CENTER_Y)), 5)
        pygame.draw.circle(surface, COLOR_LINE, (PITCH_X + PITCH_WIDTH - 100, int(PITCH_CENTER_Y)), 5)

        # 8. 골대
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
        self.speed = 2.5

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
        # 입체감을 주는 그림자 (선수 발 아래 타원형)
        shadow_surf = pygame.Surface((20, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 100), (0, 0, 20, 10))
        surface.blit(shadow_surf, (int(self.x) - 10, int(self.y) + 4))

        # 선수 몸체
        color = (255, 140, 0) if has_ball else (COLOR_HOME if self.team == 'home' else COLOR_AWAY)
        radius = 13 if has_ball else 11

        # 외곽선과 입체감을 위한 테두리 효과
        pygame.draw.circle(surface, (20, 20, 20), (int(self.x), int(self.y)), radius + 1)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), radius)

        # 선수 이름 텍스트
        name_surf = font.render(self.name, True, (255, 255, 255))
        surface.blit(name_surf, (int(self.x) - 15, int(self.y) - 28))


class Ball:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0
        self.vy = 0
        self.possessor = None

    def update(self):
        if self.possessor:
            self.x = self.possessor.x + 15
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
        # 공 그림자
        shadow_surf = pygame.Surface((14, 7), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 120), (0, 0, 14, 7))
        surface.blit(shadow_surf, (int(self.x) - 7, int(self.y) + 6))

        # 공 본체 (외곽선 + 흰색)
        pygame.draw.circle(surface, (30, 30, 30), (int(self.x), int(self.y)), 8)
        pygame.draw.circle(surface, COLOR_BALL, (int(self.x), int(self.y)), 6)


# 경기장 및 객체 생성
pitch = Pitch()
ball = Ball(PITCH_CENTER_X, PITCH_CENTER_Y)

home_players = [
    Player(PITCH_CENTER_X - 150, PITCH_CENTER_Y, 'home', 'H-FW'),
    Player(PITCH_CENTER_X - 300, PITCH_CENTER_Y - 120, 'home', 'H-MF1'),
    Player(PITCH_CENTER_X - 300, PITCH_CENTER_Y + 120, 'home', 'H-MF2'),
    Player(PITCH_CENTER_X - 450, PITCH_CENTER_Y, 'home', 'H-DF'),
]

away_players = [
    Player(PITCH_CENTER_X + 150, PITCH_CENTER_Y, 'away', 'A-FW'),
    Player(PITCH_CENTER_X + 300, PITCH_CENTER_Y - 120, 'away', 'A-MF1'),
    Player(PITCH_CENTER_X + 300, PITCH_CENTER_Y + 120, 'away', 'A-MF2'),
    Player(PITCH_CENTER_X + 450, PITCH_CENTER_Y, 'away', 'A-DF'),
]

all_players = home_players + away_players

clock = pygame.time.Clock()
match_time = 0
game_status_text = "입체 필드와 그림자 효과가 적용되었습니다!"

# 메인 게임 루프
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

    match_time += 1

    # 1. 공 소유권 판정
    if ball.possessor is None:
        closest_player = min(all_players, key=lambda p: math.hypot(p.x - ball.x, p.y - ball.y))
        dist_to_ball = math.hypot(closest_player.x - ball.x, closest_player.y - ball.y)

        if dist_to_ball < 20:
            ball.possessor = closest_player
            game_status_text = f"[{closest_player.name}] 선수가 공을 잡았습니다!"

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
            game_status_text = f"[{passer.name}] -> [{receiver.name}] 패스 연결!"

    # 2. 선수 이동 AI
    for p in all_players:
        if ball.possessor == p:
            continue
        elif ball.possessor is None:
            p.move_towards(ball.x, ball.y)
        else:
            p.move_towards(p.base_x, p.base_y)

    # 3. 공 업데이트
    ball.update()

    # 4. 화면 렌더링
    pitch.draw(screen)

    # --- [중요] Y축 깊이 정렬 (Depth Sorting) ---
    # 화면 아래(Y가 큰 값)에 있는 객체가 화면 위(Y가 작은 값)에 있는 객체를 가리도록 정렬
    render_list = all_players + [ball]
    render_list.sort(key=lambda obj: obj.y)

    for obj in render_list:
        if isinstance(obj, Ball):
            obj.draw(screen)
        else:
            has_ball = (ball.possessor == obj)
            obj.draw(screen, has_ball)

    # 상단 UI 영역
    pygame.draw.rect(screen, (15, 15, 15), (0, 0, SCREEN_WIDTH, 75))
    time_surf = font.render(f"경기 시간: {match_time // 60}초", True, (255, 255, 255))
    status_surf = font.render(f"상황: {game_status_text}", True, (255, 255, 0))
    screen.blit(time_surf, (40, 15))
    screen.blit(status_surf, (40, 42))

    pygame.display.flip()
    clock.tick(60)
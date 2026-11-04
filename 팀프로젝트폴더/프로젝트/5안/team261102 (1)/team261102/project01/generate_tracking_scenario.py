import json
import math
import shutil
from datetime import datetime
from pathlib import Path


DURATION = 60
STEP = 0.2

# 시간별 위치를 연결하는 기준 시점입니다.
TIMES = [0, 8, 16, 26, 32, 40, 50, 60]

# 역할, 시작 x, 시작 y
FORMATION = [
    ('GK', 8, 34),
    ('LB', 28, 10),
    ('LCB', 25, 26),
    ('RCB', 25, 42),
    ('RB', 28, 58),
    ('DM', 43, 34),
    ('LCM', 55, 23),
    ('RCM', 55, 45),
    ('LW', 75, 12),
    ('ST', 80, 34),
    ('RW', 75, 56),
]

players = []

for team, prefix in [('HOME', 'H'), ('AWAY', 'A')]:
    for number, (role, x, y) in enumerate(FORMATION, start=1):
        players.append({
            'player_id': f'{prefix}{number:02d}',
            'name': f'가상 {team} 선수 {number}',
            'team_id': team,
            'number': number,
            'role': role,
            'base_x': x if team == 'HOME' else 105 - x,
            'base_y': y,
        })


# 기본 움직임:
# 홈팀은 전진했다가 공을 잃은 뒤 수비 위치로 복귀합니다.
# 원정팀은 수비하다가 공을 얻은 뒤 왼쪽으로 전진합니다.
home_shift = [0, 3, 6, 9, 7, -2, -9, -5]
away_shift = [0, 3, 6, 8, 4, -5, -13, -17]

paths = {}

for player in players:
    shifts = (
        home_shift
        if player['team_id'] == 'HOME'
        else away_shift
    )

    # 골키퍼는 필드 선수보다 적게 움직입니다.
    multiplier = 0.15 if player['role'] == 'GK' else 1.0

    paths[player['player_id']] = [
        (
            player['base_x'] + shift * multiplier,
            player['base_y'],
        )
        for shift in shifts
    ]


# 주요 선수들의 역할별 움직임입니다.
# 각 좌표는 TIMES의 8개 시점과 순서대로 대응합니다.
paths.update({
    # 홈 오른쪽 풀백: 공격 지원 후 수비 복귀
    'H05': [
        (28, 58), (36, 57), (47, 56), (61, 55),
        (59, 54), (43, 56), (30, 57), (28, 58),
    ],

    # 홈 중앙 미드필더: 패스 연결과 전진 지원
    'H08': [
        (50, 44), (53, 43), (61, 43), (70, 42),
        (68, 41), (54, 40), (43, 42), (46, 44),
    ],

    # 홈 오른쪽 윙어: 측면으로 전진
    'H11': [
        (66, 56), (71, 56), (79, 55), (91, 53),
        (90, 50), (76, 52), (61, 54), (65, 56),
    ],

    # 홈 중앙 공격수: 골문 방향 침투 후 복귀
    'H10': [
        (74, 34), (78, 34), (83, 35), (89, 35),
        (90, 34), (78, 34), (65, 33), (69, 34),
    ],

    # 원정 센터백: 수비 후 공을 가로챕니다.
    'A03': [
        (80, 26), (83, 27), (87, 28), (90, 30),
        (86, 32), (75, 30), (66, 27), (63, 26),
    ],

    # 원정 중앙 미드필더: 공을 받아 역습 연결
    'A08': [
        (50, 44), (55, 43), (62, 42), (72, 40),
        (75, 39), (60, 39), (46, 40), (40, 42),
    ],

    # 원정 오른쪽 윙어: 왼쪽 골문 방향으로 역습
    'A11': [
        (31, 12), (36, 13), (43, 14), (52, 15),
        (57, 16), (47, 15), (29, 16), (19, 18),
    ],

    # 원정 중앙 공격수: 역습 시 전방 침투
    'A10': [
        (26, 34), (31, 34), (38, 33), (47, 33),
        (50, 33), (39, 34), (22, 34), (14, 35),
    ],
})


def position(player_id, time):
    """기준 좌표 사이를 직선으로 연결합니다."""
    points = paths[player_id]

    for index in range(len(TIMES) - 1):
        start_time = TIMES[index]
        end_time = TIMES[index + 1]

        if time <= end_time:
            ratio = (time - start_time) / (end_time - start_time)
            ratio = max(0, min(1, ratio))

            start = points[index]
            end = points[index + 1]

            return {
                'x': round(
                    start[0] + (end[0] - start[0]) * ratio, 3
                ),
                'y': round(
                    start[1] + (end[1] - start[1]) * ratio, 3
                ),
            }

    return {
        'x': points[-1][0],
        'y': points[-1][1],
    }


# 시작, 도착, 패서, 의도한 수신자, 실제 수신자, 결과
PASSES = [
    (8, 10, 'H05', 'H08', 'H08', 'complete'),
    (16, 18, 'H08', 'H11', 'H11', 'complete'),
    (26, 28, 'H11', 'H10', 'H10', 'complete'),

    # H10이 H09에게 보내려던 패스를 A03이 가로챕니다.
    (30, 32, 'H10', 'H09', 'A03', 'incomplete'),

    (36, 38, 'A03', 'A08', 'A08', 'complete'),
    (44, 46, 'A08', 'A11', 'A11', 'complete'),
    (54, 56, 'A11', 'A10', 'A10', 'complete'),
]


def ball_position(time):
    holder = 'H05'

    for start, end, passer, intended, actual, outcome in PASSES:
        if time < start:
            return position(holder, time)

        if time < end:
            source = position(passer, start)
            target = position(actual, end)
            ratio = (time - start) / (end - start)

            return {
                'x': round(
                    source['x'] + (target['x'] - source['x']) * ratio,
                    3,
                ),
                'y': round(
                    source['y'] + (target['y'] - source['y']) * ratio,
                    3,
                ),
            }

        holder = actual

    return position(holder, time)


events = []

for index, (
    start, end, passer, intended, actual, outcome
) in enumerate(PASSES, start=1):

    events.append({
        'event_id': f'PASS{index}',
        'type': 'pass',
        'time_sec': start,
        'end_time_sec': end,
        'player_id': passer,
        'receiver_id': intended,
        'actual_receiver_id': actual,
        'start': position(passer, start),

        # 실패 패스의 끝점은 의도한 위치가 아니라
        # 실제로 공을 빼앗긴 위치입니다.
        'end': position(actual, end),
        'outcome': outcome,
    })

    events.append({
        'event_id': f'RECEIVE{index}',
        'type': 'reception',
        'time_sec': end,
        'player_id': actual,
        'position': position(actual, end),
        'acquisition': (
            'interception'
            if outcome == 'incomplete'
            else 'pass'
        ),
    })


frames = []

for index in range(round(DURATION / STEP) + 1):
    time = round(index * STEP, 1)

    frames.append({
        'time_sec': time,
        'players': [
            {
                'player_id': player['player_id'],
                **position(player['player_id'], time),
            }
            for player in players
        ],
        'ball': ball_position(time),
    })


# 저장 전에 좌표 범위와 이동 속도를 검사합니다.
maximum_speed = 0

for index, frame in enumerate(frames):
    for point in frame['players'] + [frame['ball']]:
        if not (
            0 <= point['x'] <= 105
            and 0 <= point['y'] <= 68
        ):
            raise ValueError('경기장 밖 좌표가 있습니다.')

    if index == 0:
        continue

    previous = frames[index - 1]

    for before, after in zip(
        previous['players'],
        frame['players'],
    ):
        speed = math.hypot(
            after['x'] - before['x'],
            after['y'] - before['y'],
        ) / STEP

        maximum_speed = max(maximum_speed, speed)

        if speed > 9:
            raise ValueError('선수 이동 속도가 설정 범위를 넘었습니다.')


document = {
    'schema_version': 1,
    'match_id': 'DEMO002',
    'is_synthetic': True,
    'notice': '가상 공격·역습 시나리오입니다. 실제 경기 기록이 아닙니다.',
    'pitch': {
        'length': 105,
        'width': 68,
        'unit': 'metres',
        'origin': 'bottom_left',
    },
    'home_attacking_direction': 'positive_x',
    'duration_sec': DURATION,
    'sample_interval_sec': STEP,
    'players': players,
    'events': events,
    'frames': frames,
}

target = (
    Path(__file__).resolve().parent
    / 'data'
    / 'demo'
    / 'tracking_demo.json'
)

target.parent.mkdir(parents=True, exist_ok=True)

# 기존 데모 파일을 먼저 백업합니다.
if target.exists():
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = target.with_name(f'tracking_demo_backup_{stamp}.json')
    shutil.copy2(target, backup)
    print(f'백업 위치: {backup}')

temporary = target.with_suffix('.tmp')

temporary.write_text(
    json.dumps(document, ensure_ascii=False, indent=2),
    encoding='utf-8',
)

temporary.replace(target)

print(f'저장 위치: {target}')
print(f'선수: {len(players)}명')
print(f'위치 기록: {len(frames)}개 시점')
print(f'이벤트: {len(events)}개')
print(f'선수 최고 이동 속도: {maximum_speed:.2f}m/s')
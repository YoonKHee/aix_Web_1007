import json
import math
from pathlib import Path


# 경기장 좌표는 미터 단위입니다.
PITCH_LENGTH = 105
PITCH_WIDTH = 68

DURATION = 60
STEP = 0.2

# 4-3-3 기본 위치: 역할, x, y
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


def position(player_id, time):
    """기본 위치 주변을 천천히 움직이는 가상 좌표."""
    player = next(
        item for item in players
        if item['player_id'] == player_id
    )

    phase = player['number'] * 0.4

    x = player['base_x'] + 2 * math.sin(time / 6 + phase)
    y = player['base_y'] + 2 * math.sin(time / 8 + phase)

    return {
        'x': round(x, 3),
        'y': round(y, 3),
    }


# 패스 시작 시각, 도착 시각, 패서, 수신자
PASSES = [
    (10, 12, 'H05', 'H08'),
    (25, 27, 'H08', 'H11'),
    (40, 42, 'H11', 'H10'),
]


def ball_position(time):
    """패스 전후에는 소유 선수를 따르고, 패스 중에는 이동."""
    holder = 'H05'

    for start, end, passer, receiver in PASSES:
        if time < start:
            return position(holder, time)

        if time < end:
            source = position(passer, start)
            target = position(receiver, end)
            ratio = (time - start) / (end - start)

            return {
                'x': round(
                    source['x']
                    + (target['x'] - source['x']) * ratio,
                    3,
                ),
                'y': round(
                    source['y']
                    + (target['y'] - source['y']) * ratio,
                    3,
                ),
            }

        holder = receiver

    return position(holder, time)


events = []

for index, (start, end, passer, receiver) in enumerate(
    PASSES, start=1
):
    source = position(passer, start)
    target = position(receiver, end)

    events.append({
        'event_id': f'PASS{index}',
        'type': 'pass',
        'time_sec': start,
        'end_time_sec': end,
        'player_id': passer,
        'receiver_id': receiver,
        'start': source,
        'end': target,
        'outcome': 'complete',
    })

    events.append({
        'event_id': f'RECEIVE{index}',
        'type': 'reception',
        'time_sec': end,
        'player_id': receiver,
        'position': target,
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


document = {
    'schema_version': 1,
    'match_id': 'DEMO001',
    'is_synthetic': True,
    'notice': '가상 데이터입니다. 실제 선수 평가에 사용하지 않습니다.',
    'pitch': {
        'length': PITCH_LENGTH,
        'width': PITCH_WIDTH,
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

# 기존 파일은 실수로 덮어쓰지 않습니다.
with target.open('x', encoding='utf-8') as file:
    json.dump(document, file, ensure_ascii=False, indent=2)

print(f'저장 위치: {target}')
print(f'선수: {len(players)}명')
print(f'위치 기록: {len(frames)}개 시점')
print(f'이벤트: {len(events)}개')
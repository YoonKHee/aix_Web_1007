"""기존 가상 장면을 변형합니다. 실제 선수 능력이나 전술을 재현하지 않습니다."""

import copy
import hashlib
import json
import random

from player.tracking_demo_views import connect_roster
from validate_tracking_demo import validate


VERSION = 'scenario-transform-v1'


# 기존 참조 장면을 변형하는 10개 조건입니다.
# width: 활동 구역의 좌우 폭
# tempo: 경기 시간 배수
# mirror: 경기장 위아래 반전
# swap: 홈팀과 원정팀의 행동 교환
SCENARIOS = [
    {
        'code': 'base',
        'name': '기본 공격·역습',
        'width': 1.0,
        'tempo': 1.0,
    },
    {
        'code': 'mirror',
        'name': '좌우 반전 공격·역습',
        'width': 1.0,
        'tempo': 1.0,
        'mirror': True,
    },
    {
        'code': 'compact',
        'name': '중앙 밀집 전개',
        'width': 0.65,
        'tempo': 1.0,
    },
    {
        'code': 'compact_mirror',
        'name': '중앙 밀집·좌우 반전',
        'width': 0.65,
        'tempo': 1.0,
        'mirror': True,
    },
    {
        'code': 'wide',
        'name': '측면 공간 확장',
        'width': 1.12,
        'tempo': 1.0,
    },
    {
        'code': 'wide_mirror',
        'name': '측면 확장·좌우 반전',
        'width': 1.12,
        'tempo': 1.0,
        'mirror': True,
    },
    {
        'code': 'slow',
        'name': '느린 템포 전개',
        'width': 1.0,
        'tempo': 1.25,
    },
    {
        'code': 'fast',
        'name': '빠른 템포 전개',
        'width': 1.0,
        'tempo': 0.8,
    },
    {
        'code': 'away_first',
        'name': '원정팀 선공 전개',
        'width': 1.0,
        'tempo': 1.0,
        'swap': True,
    },
    {
        'code': 'away_slow',
        'name': '원정팀 선공·느린 전개',
        'width': 1.0,
        'tempo': 1.25,
        'swap': True,
    },
]


def digest(value):
    """데이터 내용을 일정한 문자열로 바꿔 중복 검사값을 만듭니다."""
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    )

    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def check_document(document):
    """기존 검사 함수로 선수·시간·패스 위치 연결을 확인합니다."""
    errors, maximum_speed = validate(document)

    if errors:
        raise ValueError(
            '데이터 연결 검사 실패: ' + '; '.join(errors[:5])
        )

    if maximum_speed > 9:
        raise ValueError(
            f'가상 선수 속도 제한 초과: {maximum_speed:.2f}m/s'
        )

    return {
        'passed': True,
        'maximum_speed_mps': round(maximum_speed, 3),
        'validator': 'validate_tracking_demo',
    }


def generate(source, scenario, home, away, seed, source_hash):
    """참조 장면을 복사해서 한 개의 가상 경기 문서를 만듭니다."""
    document = copy.deepcopy(source)

    swap = bool(scenario.get('swap'))
    mirror = bool(scenario.get('mirror'))

    tempo = scenario['tempo']
    width_scale = scenario['width']

    # 같은 조건과 시드라면 같은 위치 변형이 만들어집니다.
    rng = random.Random(
        f"{VERSION}:{scenario['code']}:{seed}"
    )
    shift_y = round(rng.uniform(-0.35, 0.35), 6)

    def change_player_id(value):
        if value is None or not swap:
            return value

        prefix = 'A' if value.startswith('H') else 'H'
        return prefix + value[1:]

    def change_point(value):
        x = 105 - value['x'] if swap else value['x']

        # 경기장 중앙선을 기준으로 좌우 폭을 조절합니다.
        y = 34 + (value['y'] - 34) * width_scale

        if mirror:
            y = 68 - y

        y += shift_y

        if not (0 <= x <= 105 and 0 <= y <= 68):
            raise ValueError(
                '공간 변환이 경기장 범위를 벗어났습니다.'
            )

        return {
            'x': round(x, 3),
            'y': round(y, 3),
        }

    def change_time(value):
        return round(value * tempo, 6)

    # 1. 선수 기본 위치와 가상 ID 변환
    for player in document['players']:
        player['player_id'] = change_player_id(
            player['player_id']
        )

        if swap:
            player['team_id'] = (
                'AWAY'
                if player['team_id'] == 'HOME'
                else 'HOME'
            )

        if 'base_x' in player:
            point = change_point({
                'x': player['base_x'],
                'y': player['base_y'],
            })

            player['base_x'] = point['x']
            player['base_y'] = point['y']

        player['name'] = (
            f"가상 {player['team_id']} 선수 {player['number']}"
        )

    # 2. 시간별 선수와 공 위치 변환
    for frame in document['frames']:
        frame['time_sec'] = change_time(frame['time_sec'])

        for player in frame['players']:
            player['player_id'] = change_player_id(
                player['player_id']
            )
            player.update(change_point(player))

        frame['ball'].update(change_point(frame['ball']))

    # 3. 패스·수신 이벤트도 같은 규칙으로 변환
    for event in document['events']:
        event['time_sec'] = change_time(event['time_sec'])

        if 'end_time_sec' in event:
            event['end_time_sec'] = change_time(
                event['end_time_sec']
            )

        for key in (
            'player_id',
            'receiver_id',
            'actual_receiver_id',
        ):
            if key in event:
                event[key] = change_player_id(event[key])

        for key in ('start', 'end', 'position'):
            if key in event:
                event[key] = change_point(event[key])

    document['duration_sec'] = change_time(
        source['duration_sec']
    )
    document['sample_interval_sec'] = change_time(
        source['sample_interval_sec']
    )

    document['players'].sort(
        key=lambda player: (
            player['team_id'] != 'HOME',
            player['number'],
        )
    )

    # 4. 선택한 구단의 기본 BEST11을 연결
    for team, prefix in ((home, 'H'), (away, 'A')):
        roster, warning = connect_roster(
            document,
            team,
            prefix,
        )

        if warning or len(roster) != 11:
            raise ValueError(
                f'{team}: '
                f'{warning or "BEST11 11명이 필요합니다."}'
            )

    # 5. 재현과 추적에 필요한 조건 보관
    document['match_id'] = (
        f"SYNTH-{scenario['code']}-{seed}"
    )
    document['is_synthetic'] = True
    document['notice'] = (
        '실제 명단과 연결한 가상 좌표 변형입니다. '
        '실제 선수 기록이나 승무패 정답이 아닙니다.'
    )

    document['simulation'] = {
        'generator_version': VERSION,
        'seed': seed,
        'scenario_code': scenario['code'],
        'scenario_name': scenario['name'],
        'home_team': {
            'id': home.pk,
            'name': home.team_name,
        },
        'away_team': {
            'id': away.pk,
            'name': away.team_name,
        },
        'source_sha256': source_hash,
        'parameters': {
            **scenario,
            'shift_y': shift_y,
        },
        'lineup_method': (
            'get_filtered_best11 / 4-3-3 / 기본 기준'
        ),
        'score_label': None,
    }

    validation = check_document(document)

    return document, validation
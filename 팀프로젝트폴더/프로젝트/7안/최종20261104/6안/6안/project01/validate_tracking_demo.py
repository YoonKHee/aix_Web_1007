import json
import math
from pathlib import Path


def validate(data):
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    players = data['players']
    frames = data['frames']
    events = data['events']

    length = data['pitch']['length']
    width = data['pitch']['width']
    duration = data['duration_sec']

    ids = [player['player_id'] for player in players]
    player_ids = set(ids)

    check(len(ids) == len(player_ids), '선수 ID가 중복되었습니다.')
    check(len(players) == 22, '선수가 22명이 아닙니다.')

    for team in ('HOME', 'AWAY'):
        count = sum(
            player['team_id'] == team
            for player in players
        )
        check(count == 11, f'{team} 선수가 11명이 아닙니다.')

    check(len(frames) >= 2, '위치 기록이 부족합니다.')

    if len(frames) < 2:
        return errors, 0

    check(frames[0]['time_sec'] == 0, '시작 시간이 0초가 아닙니다.')
    check(
        frames[-1]['time_sec'] == duration,
        '마지막 시간이 경기 길이와 다릅니다.',
    )

    frame_lookup = {}
    maximum_speed = 0

    def in_pitch(point):
        x = point['x']
        y = point['y']

        return (
            math.isfinite(x)
            and math.isfinite(y)
            and 0 <= x <= length
            and 0 <= y <= width
        )

    for index, frame in enumerate(frames):
        time = frame['time_sec']
        rows = frame['players']
        positions = {
            player['player_id']: player
            for player in rows
        }

        check(
            len(rows) == len(positions),
            f'{time}초: 선수 위치가 중복되었습니다.',
        )
        check(
            set(positions) == player_ids,
            f'{time}초: 누락되거나 알 수 없는 선수가 있습니다.',
        )

        for player in rows:
            check(
                in_pitch(player),
                f"{time}초: {player['player_id']} 좌표 오류",
            )

        check(in_pitch(frame['ball']), f'{time}초: 공 좌표 오류')

        frame_lookup[round(time, 6)] = {
            'players': positions,
            'ball': frame['ball'],
        }

        if index == 0:
            continue

        previous = frames[index - 1]
        elapsed = time - previous['time_sec']

        check(elapsed > 0, f'{time}초: 시간 순서가 잘못됐습니다.')

        if elapsed <= 0:
            continue

        previous_positions = {
            player['player_id']: player
            for player in previous['players']
        }

        for player_id, current in positions.items():
            before = previous_positions.get(player_id)

            if before is None:
                continue

            speed = math.hypot(
                current['x'] - before['x'],
                current['y'] - before['y'],
            ) / elapsed

            maximum_speed = max(maximum_speed, speed)

    def close(first, second):
        return math.hypot(
            first['x'] - second['x'],
            first['y'] - second['y'],
        ) <= 0.02

    event_ids = [event['event_id'] for event in events]

    check(
        len(event_ids) == len(set(event_ids)),
        '이벤트 ID가 중복되었습니다.',
    )

    for event in events:
        label = event['event_id']
        time = event['time_sec']
        player_id = event['player_id']

        check(player_id in player_ids, f'{label}: 선수 ID 오류')
        check(0 <= time <= duration, f'{label}: 이벤트 시간 오류')

        frame = frame_lookup.get(round(time, 6))

        check(
            frame is not None,
            f'{label}: 이벤트 시각에 해당하는 위치 기록이 없습니다.',
        )

        if frame is None or player_id not in frame['players']:
            continue

        if event['type'] == 'pass':
            end_time = event['end_time_sec']
            actual = event.get(
                'actual_receiver_id',
                event['receiver_id'],
            )

            check(
                time < end_time <= duration,
                f'{label}: 패스 도착 시간 오류',
            )
            check(
                event['receiver_id'] in player_ids,
                f'{label}: 의도한 수신 선수 ID 오류',
            )
            check(actual in player_ids, f'{label}: 실제 수신 선수 ID 오류')

            check(
                close(event['start'], frame['players'][player_id]),
                f'{label}: 패스 시작점과 선수 위치가 다릅니다.',
            )
            check(
                close(event['start'], frame['ball']),
                f'{label}: 패스 시작점과 공 위치가 다릅니다.',
            )

            arrival = frame_lookup.get(round(end_time, 6))

            check(
                arrival is not None,
                f'{label}: 도착 시각의 위치 기록이 없습니다.',
            )

            if arrival and actual in arrival['players']:
                check(
                    close(event['end'], arrival['players'][actual]),
                    f'{label}: 도착점과 실제 수신 선수 위치가 다릅니다.',
                )
                check(
                    close(event['end'], arrival['ball']),
                    f'{label}: 도착점과 공 위치가 다릅니다.',
                )

            receptions = [
                item for item in events
                if item['type'] == 'reception'
                and item['player_id'] == actual
                and abs(item['time_sec'] - end_time) < 0.000001
            ]

            check(
                len(receptions) == 1,
                f'{label}: 연결된 수신 이벤트가 정확히 1개여야 합니다.',
            )

        elif event['type'] == 'reception':
            check(
                close(event['position'], frame['players'][player_id]),
                f'{label}: 수신 위치와 선수 위치가 다릅니다.',
            )
            check(
                close(event['position'], frame['ball']),
                f'{label}: 수신 위치와 공 위치가 다릅니다.',
            )

    return errors, maximum_speed


def main():
    target = (
        Path(__file__).resolve().parent
        / 'data'
        / 'demo'
        / 'tracking_demo.json'
    )

    try:
        data = json.loads(target.read_text(encoding='utf-8'))
        errors, maximum_speed = validate(data)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'검사를 진행할 수 없습니다: {exc}')
        return 1

    if errors:
        print(f'검사 실패: {len(errors)}개 문제')

        for message in errors:
            print(f'- {message}')

        return 1

    print('검사 통과')
    print(f"선수: {len(data['players'])}명")
    print(f"위치 기록: {len(data['frames'])}개 시점")
    print(f"이벤트: {len(data['events'])}개")
    print(f'선수 최고 이동 속도: {maximum_speed:.2f}m/s')
    print('선수 ID·좌표·시간·패스 위치 연결을 확인했습니다.')
    print('가상 데이터의 연결 검사이며 실제 전술의 타당성 검증은 아닙니다.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
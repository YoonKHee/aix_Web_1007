import math

from .generator import check_document


METRICS_VERSION = "team-summary-v1"


def summarize(document):
    check_document(document)

    players = document["players"]
    frames = document["frames"]

    team_of = {
        player["player_id"]: player["team_id"]
        for player in players
    }

    result = {
        side: {
            "distance_m": 0.0,
            "pass_attempts": 0,
            "successful_passes": 0,
            "interceptions": 0,
            "possession_seconds": 0.0,
        }
        for side in ("HOME", "AWAY")
    }

    # 연속된 좌표 사이의 거리를 선수별로 더합니다.
    for before, after in zip(frames, frames[1:]):
        previous = {
            player["player_id"]: player
            for player in before["players"]
        }

        for player in after["players"]:
            pid = player["player_id"]
            old = previous[pid]

            distance = math.hypot(
                player["x"] - old["x"],
                player["y"] - old["y"],
            )

            result[team_of[pid]]["distance_m"] += distance

    # 시작 시점에 공과 같은 위치에 있는 선수를 찾습니다.
    first = frames[0]

    owner = min(
        first["players"],
        key=lambda player: math.hypot(
            player["x"] - first["ball"]["x"],
            player["y"] - first["ball"]["y"],
        ),
    )

    initial_distance = math.hypot(
        owner["x"] - first["ball"]["x"],
        owner["y"] - first["ball"]["y"],
    )

    if initial_distance > 0.02:
        raise ValueError(
            "시작 시점의 공 소유자를 확인할 수 없습니다."
        )

    owner = owner["player_id"]
    cursor = 0.0

    passes = sorted(
        (
            event
            for event in document["events"]
            if event["type"] == "pass"
        ),
        key=lambda event: event["time_sec"],
    )

    for event in passes:
        start = event["time_sec"]
        end = event["end_time_sec"]

        if start < cursor or event["player_id"] != owner:
            raise ValueError(
                "패스 시간 또는 공 소유 연결을 확인해야 합니다."
            )

        side = team_of[owner]
        row = result[side]

        # 공을 받은 뒤 다음 패스를 시작할 때까지의 시간입니다.
        row["possession_seconds"] += start - cursor
        row["pass_attempts"] += 1

        actual = event.get(
            "actual_receiver_id",
            event["receiver_id"],
        )

        if event["outcome"] == "complete":
            if (
                team_of[actual] != side
                or actual != event["receiver_id"]
            ):
                raise ValueError(
                    "성공 패스의 수신 선수를 확인해야 합니다."
                )

            row["successful_passes"] += 1

        elif (
            event["outcome"] == "incomplete"
            and team_of[actual] != side
        ):
            result[team_of[actual]]["interceptions"] += 1

        else:
            raise ValueError(
                "현재 집계기는 성공 패스와 가로채기만 지원합니다."
            )

        # 공이 날아가는 시간은 팀 보유 시간에서 제외합니다.
        owner = actual
        cursor = end

    # 마지막 패스 이후 경기 종료까지의 보유 시간을 더합니다.
    result[team_of[owner]]["possession_seconds"] += (
        document["duration_sec"] - cursor
    )

    for row in result.values():
        row["distance_m"] = round(
            row["distance_m"],
            3,
        )

        row["possession_seconds"] = round(
            row["possession_seconds"],
            3,
        )

    return result
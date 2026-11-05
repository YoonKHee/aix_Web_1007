import math

from .generator import check_document


EVENT_VERSION = "player-events-v1"

EVENT_PARAMETERS = {
    "forward_minimum_m": 5.0,
    "possession_excludes_ball_flight": True,
}


def extract_player_events(document):
    if document.get("is_synthetic") is not True:
        raise ValueError(
            "더미데이터만 집계할 수 있습니다."
        )

    check_document(document)

    direction = document.get("home_attacking_direction")

    if direction not in ("positive_x", "negative_x"):
        raise ValueError("공격 방향을 확인해야 합니다.")

    sides = {
        player["player_id"]: player["team_id"]
        for player in document["players"]
    }

    result = {
        pid: {
            "pass_attempts": 0,
            "successful_passes": 0,
            "failed_passes": 0,
            "passes_received": 0,
            "forward_pass_attempts": 0,
            "successful_forward_passes": 0,
            "interceptions": 0,
            "possession_seconds": 0.0,
        }
        for pid in sides
    }

    frames = {
        round(frame["time_sec"], 6): {
            player["player_id"]: player
            for player in frame["players"]
        }
        for frame in document["frames"]
    }

    first = document["frames"][0]

    owners = [
        player["player_id"]
        for player in first["players"]
        if math.hypot(
            player["x"] - first["ball"]["x"],
            player["y"] - first["ball"]["y"],
        ) <= 0.02
    ]

    if len(owners) != 1:
        raise ValueError(
            "시작 시점의 공 소유자가 명확하지 않습니다."
        )

    owner = owners[0]
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

        intended = event["receiver_id"]
        actual = event.get(
            "actual_receiver_id",
            intended,
        )

        if sides[intended] != sides[owner]:
            raise ValueError(
                "패스 대상이 같은 팀 선수가 아닙니다."
            )

        row = result[owner]

        row["possession_seconds"] += start - cursor
        row["pass_attempts"] += 1

        target = frames[round(start, 6)][intended]

        positive = (
            (sides[owner] == "HOME")
            == (direction == "positive_x")
        )

        sign = 1 if positive else -1

        forward = (
            (target["x"] - event["start"]["x"]) * sign
            >= EVENT_PARAMETERS["forward_minimum_m"]
        )

        row["forward_pass_attempts"] += int(forward)

        if (
            event["outcome"] == "complete"
            and actual == intended
        ):
            row["successful_passes"] += 1
            row["successful_forward_passes"] += int(forward)

            result[actual]["passes_received"] += 1

        elif (
            event["outcome"] == "incomplete"
            and sides[actual] != sides[owner]
        ):
            row["failed_passes"] += 1
            result[actual]["interceptions"] += 1

        else:
            raise ValueError(
                "현재 집계기는 성공 패스와 가로채기만 지원합니다."
            )

        # 패스 비행 시간은 보유 시간에 포함하지 않습니다.
        owner = actual
        cursor = end

    result[owner]["possession_seconds"] += (
        document["duration_sec"] - cursor
    )

    for row in result.values():
        row["possession_seconds"] = round(
            row["possession_seconds"],
            3,
        )

    return result
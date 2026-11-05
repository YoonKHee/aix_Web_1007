SPATIAL_PARAMETERS = {
    "spatial_version": "activity-v1",
    "position_method": "time_weighted_segment_midpoint",
    "coordinate_convention": "own_goal_left_rotated_180_if_needed",
    "penalty_area_depth_m": 16.5,
    "penalty_area_width_m": 40.32,
}


def extract_spatial(document):
    length = document["pitch"]["length"]
    width = document["pitch"]["width"]
    direction = document.get("home_attacking_direction")

    if direction not in ("positive_x", "negative_x"):
        raise ValueError(
            "홈팀 공격 방향을 확인해야 합니다."
        )

    frames = document["frames"]

    sides = {
        player["player_id"]: player["team_id"]
        for player in document["players"]
    }

    totals = {
        pid: {
            "x": 0.0,
            "y": 0.0,
            "defensive": 0.0,
            "middle": 0.0,
            "attacking": 0.0,
            "entries": 0,
        }
        for pid in sides
    }

    duration = (
        frames[-1]["time_sec"] - frames[0]["time_sec"]
    )

    if duration <= 0:
        raise ValueError("위치 기록 시간이 부족합니다.")

    def normalized(pid, point):
        positive = (
            (sides[pid] == "HOME")
            == (direction == "positive_x")
        )

        if positive:
            return point["x"], point["y"]

        return (
            length - point["x"],
            width - point["y"],
        )

    def in_box(x, y):
        return (
            x >= length - SPATIAL_PARAMETERS["penalty_area_depth_m"]
            and abs(y - width / 2)
            <= SPATIAL_PARAMETERS["penalty_area_width_m"] / 2
        )

    for before, after in zip(frames, frames[1:]):
        elapsed = (
            after["time_sec"] - before["time_sec"]
        )

        previous = {
            player["player_id"]: player
            for player in before["players"]
        }

        for player in after["players"]:
            pid = player["player_id"]

            x0, y0 = normalized(pid, previous[pid])
            x1, y1 = normalized(pid, player)

            # 두 기록 사이의 중간 위치로 구간을 판정합니다.
            x = (x0 + x1) / 2
            y = (y0 + y1) / 2

            row = totals[pid]

            row["x"] += x * elapsed
            row["y"] += y * elapsed

            if x < length / 3:
                zone = "defensive"

            elif x < length * 2 / 3:
                zone = "middle"

            else:
                zone = "attacking"

            row[zone] += elapsed

            # 밖에서 안으로 이동한 경우에만 진입으로 셉니다.
            if not in_box(x0, y0) and in_box(x1, y1):
                row["entries"] += 1

    return {
        pid: {
            "average_x": round(row["x"] / duration, 3),
            "average_y": round(row["y"] / duration, 3),
            "defensive_third_seconds": round(
                row["defensive"], 3
            ),
            "middle_third_seconds": round(
                row["middle"], 3
            ),
            "attacking_third_seconds": round(
                row["attacking"], 3
            ),
            "opponent_box_entries": row["entries"],
        }
        for pid, row in totals.items()
    }
import math
from itertools import groupby
from .tracking_spatial import SPATIAL_PARAMETERS, extract_spatial
from .generator import check_document


TRACKING_VERSION = "player-tracking-v1"

PARAMETERS = {
    
    "high_speed_kmh": 19.8,
    "sprint_speed_kmh": 25.2,
    "minimum_sprint_seconds": 1.0,
}
PARAMETERS.update(SPATIAL_PARAMETERS)

def measure_segments(segments):
    # 각 항목: 이동 거리(m), 경과 시간(초), 속도(km/h)
    duration = sum(
        dt
        for distance, dt, speed in segments
    )

    if duration <= 0:
        raise ValueError("위치 기록 시간이 부족합니다.")

    total = sum(
        distance
        for distance, dt, speed in segments
    )

    sprint_count = 0
    sprint_distance = 0.0
    sprint_seconds = 0.0

    # 연속으로 스프린트 기준을 넘은 구간을 묶습니다.
    groups = groupby(
        segments,
        key=lambda item: (
            item[2] >= PARAMETERS["sprint_speed_kmh"]
        ),
    )

    for is_sprint, group in groups:
        items = list(group)

        seconds = sum(
            item[1]
            for item in items
        )

        if (
            is_sprint
            and seconds + 1e-9
            >= PARAMETERS["minimum_sprint_seconds"]
        ):
            sprint_count += 1

            sprint_distance += sum(
                item[0]
                for item in items
            )

            sprint_seconds += seconds

    high_speed_distance = sum(
        distance
        for distance, dt, speed in segments
        if speed >= PARAMETERS["high_speed_kmh"]
    )

    return {
        "tracked_seconds": round(duration, 3),
        "total_distance_m": round(total, 3),
        "distance_per_minute": round(
            total / duration * 60,
            3,
        ),
        "avg_speed_kmh": round(
            total / duration * 3.6,
            3,
        ),
        "max_speed_kmh": round(
            max(item[2] for item in segments),
            3,
        ),
        "high_speed_distance_m": round(
            high_speed_distance,
            3,
        ),
        "sprint_count": sprint_count,
        "sprint_distance_m": round(sprint_distance, 3),
        "sprint_seconds": round(sprint_seconds, 3),
    }


def extract_player_tracking(document):
    if document.get("is_synthetic") is not True:
        raise ValueError(
            "이 명령어는 더미데이터 전용입니다."
        )

    check_document(document)

    segments = {
        player["player_id"]: []
        for player in document["players"]
    }

    frames = document["frames"]

    for before, after in zip(frames, frames[1:]):
        elapsed = (
            after["time_sec"] - before["time_sec"]
        )

        if abs(
            elapsed - document["sample_interval_sec"]
        ) > 1e-6:
            raise ValueError(
                "위치 기록 간격에 누락 또는 변경이 있습니다."
            )

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

            speed = distance / elapsed * 3.6

            segments[pid].append(
                (distance, elapsed, speed)
            )

    spatial = extract_spatial(document)

    return {
        pid: {
            **measure_segments(items),
            **spatial[pid],
        }
        for pid, items in segments.items()
    }
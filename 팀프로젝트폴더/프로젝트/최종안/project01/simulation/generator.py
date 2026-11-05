"""공 소유와 전술 규칙으로 만드는 가상 경기입니다."""
import copy
import hashlib
import json
import math
import random

from player.tracking_demo_views import connect_roster
from validate_tracking_demo import validate


VERSION = "possession-engine-v2"

SCENARIOS = [
    dict(
        code="possession", name="짧은 패스",
        hold=1.2, reach=14, forward=0.2,
        width=1.0, press=1, line=0, speed=4,
    ),
    dict(
        code="counter", name="빠른 전진",
        hold=1.0, reach=25, forward=1.3,
        width=1.0, press=1, line=-4, speed=6,
    ),
    dict(
        code="wide", name="측면 전개",
        hold=1.8, reach=23, forward=0.6,
        width=1.3, press=1, line=0, speed=5,
    ),
    dict(
        code="central", name="중앙 전개",
        hold=1.4, reach=18, forward=0.8,
        width=0.6, press=1, line=0, speed=4.5,
    ),
    dict(
        code="press", name="강한 압박",
        hold=1.2, reach=18, forward=0.6,
        width=1.0, press=3, line=7, speed=5.5,
    ),
    dict(
        code="low", name="낮은 수비",
        hold=2.4, reach=20, forward=0.3,
        width=0.8, press=1, line=-9, speed=4,
    ),
    dict(
        code="long", name="긴 패스",
        hold=1.4, reach=38, forward=1.1,
        width=1.1, press=1, line=-3, speed=4.5,
    ),
    dict(
        code="target", name="공격수 중심",
        hold=1.8, reach=28, forward=0.8,
        width=0.9, press=1, line=0, speed=4.5,
    ),
    dict(
        code="safe", name="안전한 전개",
        hold=3.0, reach=12, forward=-0.3,
        width=1.0, press=1, line=-5, speed=3.5,
    ),
    dict(
        code="urgent", name="공격적인 전개",
        hold=0.8, reach=26, forward=1.5,
        width=1.2, press=2, line=9, speed=6,
    ),
]


def digest(value):
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_document(document):
    errors, speed = validate(document)

    if errors or speed > 9:
        raise ValueError(
            "가상 경기 검사 실패: "
            + "; ".join(errors[:5])
            + f" / 최고 속도 {speed:.2f}m/s"
        )

    return {
        "passed": True,
        "maximum_speed_mps": round(speed, 3),
        "validator": "validate_tracking_demo",
    }


def generate(source, scenario, home, away, seed, source_hash):
    data = copy.deepcopy(source)

    rng = random.Random(
        f"{VERSION}:{home.pk}:{away.pk}:{scenario['code']}:{seed}"
    )

    # 0.2초 간격으로 60초 분량을 생성합니다.
    dt = 0.2
    total = 300

    players = data["players"]
    ids = [p["player_id"] for p in players]

    groups = {
        side: [
            p["player_id"]
            for p in players
            if p["team_id"] == side
        ]
        for side in ("HOME", "AWAY")
    }

    team_of = {
        pid: side
        for side, rows in groups.items()
        for pid in rows
    }

    profiles = {
        "HOME": scenario,
        "AWAY": SCENARIOS[0],
    }

    # 4-3-3 기본 위치입니다.
    bases = [
        (8, 34),
        (28, 10),
        (25, 26),
        (25, 42),
        (28, 58),
        (43, 34),
        (53, 23),
        (53, 45),
        (73, 12),
        (76, 34),
        (73, 56),
    ]

    pos = {}
    base = {}

    for player in players:
        pid = player["player_id"]
        x, y = bases[int(pid[1:]) - 1]

        if team_of[pid] == "AWAY":
            x = 105 - x

        base[pid] = (x, y)
        pos[pid] = [x, y]

        player.update(base_x=x, base_y=y)

    # 실제 BEST11 명단을 생성 시점에 연결합니다.
    for team, prefix in ((home, "H"), (away, "A")):
        roster, warning = connect_roster(data, team, prefix)

        if warning or len(roster) != 11:
            raise ValueError(
                f'{team}: {warning or "BEST11 11명이 필요합니다."}'
            )

    step = 0

    # 시작 팀과 최초 공 소유자를 시드에 따라 선택합니다.
    first_team = rng.choice(["HOME", "AWAY"])
    owner = rng.choice(groups[first_team][5:])

    ball = list(pos[owner])
    frames = []
    events = []

    def point(xy):
        return {
            "x": round(xy[0], 3),
            "y": round(xy[1], 3),
        }

    def distance(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def record():
        frames.append({
            "time_sec": round(step * dt, 6),
            "players": [
                {
                    "player_id": pid,
                    **point(pos[pid]),
                }
                for pid in ids
            ],
            "ball": point(ball),
        })

    def targets():
        """공 위치와 전술에 따라 다음 이동 목표를 정합니다."""
        result = {}
        attacking = team_of[owner]

        for side, rows in groups.items():
            cfg = profiles[side]
            direction = 1 if side == "HOME" else -1

            for pid in rows:
                x, y = base[pid]

                if pid.endswith("01"):
                    result[pid] = [x, y]
                    continue

                # 팀 전체가 공 위치에 따라 움직입니다.
                shift = (ball[0] - 52.5) * 0.25
                x += direction * cfg["line"] + shift
                y = 34 + (y - 34) * cfg["width"]

                result[pid] = [
                    max(3, min(102, x + rng.uniform(-4, 4))),
                    max(3, min(65, y + rng.uniform(-3, 3))),
                ]

            # 수비팀은 가까운 선수부터 공 주변을 압박합니다.
            if side != attacking:
                nearest = sorted(
                    rows[1:],
                    key=lambda pid: distance(pos[pid], ball),
                )

                for pid in nearest[:cfg["press"]]:
                    result[pid] = list(ball)

        # 공 소유자는 공을 가지고 전진합니다.
        cfg = profiles[attacking]
        direction = 1 if attacking == "HOME" else -1

        result[owner] = [
            max(
                4,
                min(
                    101,
                    pos[owner][0]
                    + direction * (4 + 5 * cfg["forward"]),
                ),
            ),
            max(
                3,
                min(65, pos[owner][1] + rng.uniform(-5, 5)),
            ),
        ]

        return result

    def advance(count, goals, flight=None):
        """속도 제한을 지키며 선수와 공을 이동시킵니다."""
        nonlocal step, ball

        for index in range(1, count + 1):
            for pid in ids:
                length = distance(pos[pid], goals[pid])
                speed = profiles[team_of[pid]]["speed"]

                ratio = min(
                    1,
                    speed * dt / max(length, 0.001),
                )

                pos[pid] = [
                    a + (b - a) * ratio
                    for a, b in zip(pos[pid], goals[pid])
                ]

            if flight:
                start, end = flight

                ball = [
                    a + (b - a) * index / count
                    for a, b in zip(start, end)
                ]
            else:
                ball = list(pos[owner])

            step += 1
            record()

    record()

    while step < total:
        side = team_of[owner]
        cfg = profiles[side]

        # 전술에 따라 공을 보유하는 시간이 달라집니다.
        hold = max(
            1,
            round(cfg["hold"] * rng.uniform(0.7, 1.3) / dt),
        )

        advance(
            min(hold, total - step),
            targets(),
        )

        # 이번 버전의 패스 비행 시간은 2초입니다.
        flight_steps = 10

        if total - step < flight_steps:
            advance(total - step, targets())
            break

        candidates = [
            pid
            for pid in groups[side]
            if pid != owner
        ]

        direction = 1 if side == "HOME" else -1
        weights = []

        # 선호 거리와 전진 성향으로 패스 대상을 선택합니다.
        for pid in candidates:
            length = distance(pos[owner], pos[pid])
            forward = direction * (
                pos[pid][0] - pos[owner][0]
            )

            weight = math.exp(
                -abs(length - cfg["reach"]) / 12
                + cfg["forward"] * forward / 30
            )

            if (
                scenario["code"] == "target"
                and side == "HOME"
                and pid == "H10"
            ):
                weight *= 5

            if scenario["code"] == "wide" and side == "HOME":
                weight *= 1 + abs(pos[pid][1] - 34) / 10

            weights.append(weight)

        intended = rng.choices(
            candidates,
            weights=weights,
            k=1,
        )[0]

        start = list(pos[owner])
        destination = list(pos[intended])

        opponents = groups[
            "AWAY" if side == "HOME" else "HOME"
        ]

        def lane_distance(pid):
            """상대 선수와 패스 경로 사이의 거리입니다."""
            dx = destination[0] - start[0]
            dy = destination[1] - start[1]

            fraction = max(
                0,
                min(
                    1,
                    (
                        (pos[pid][0] - start[0]) * dx
                        + (pos[pid][1] - start[1]) * dy
                    )
                    / max(dx * dx + dy * dy, 0.001),
                ),
            )

            closest = [
                start[0] + dx * fraction,
                start[1] + dy * fraction,
            ]

            return distance(pos[pid], closest)

        interceptor = min(
            opponents,
            key=lane_distance,
        )

        # 긴 패스이거나 상대가 경로에 가까우면 위험이 커집니다.
        risk = min(
            0.7,
            0.05
            + max(0, 6 - lane_distance(interceptor)) * 0.07
            + distance(start, destination) / 250,
        )

        actual = (
            interceptor
            if rng.random() < risk
            else intended
        )

        end = list(pos[actual])

        events.append({
            "event_id": f"PASS{len(events) + 1}",
            "type": "pass",
            "time_sec": round(step * dt, 6),
            "end_time_sec": round(
                (step + flight_steps) * dt,
                6,
            ),
            "player_id": owner,
            "receiver_id": intended,
            "actual_receiver_id": actual,
            "start": point(start),
            "end": point(end),
            "outcome": (
                "complete"
                if actual == intended
                else "incomplete"
            ),
        })

        goals = targets()

        # 수신 선수는 도착 위치에서 기다리도록 단순화했습니다.
        goals[actual] = list(end)

        advance(
            flight_steps,
            goals,
            flight=(start, end),
        )

        owner = actual

        events.append({
            "event_id": f"RECEIVE{len(events) + 1}",
            "type": "reception",
            "time_sec": round(step * dt, 6),
            "player_id": owner,
            "position": point(end),
            "acquisition": (
                "pass"
                if actual == intended
                else "interception"
            ),
        })

    data.update(
        match_id=f"SYNTH-{scenario['code']}-{seed}",
        is_synthetic=True,
        duration_sec=60,
        sample_interval_sec=dt,
        frames=frames,
        events=events,
        notice=(
            "공 소유와 전술 규칙으로 생성한 가상 경기이며 "
            "실제 선수 기록이나 승무패 정답이 아닙니다."
        ),
    )

    data["simulation"] = {
        "generator_version": VERSION,
        "seed": seed,
        "scenario_code": scenario["code"],
        "scenario_name": scenario["name"],
        "home_team": {
            "id": home.pk,
            "name": home.team_name,
        },
        "away_team": {
            "id": away.pk,
            "name": away.team_name,
        },
        "source_sha256": source_hash,
        "parameters": {
            "home_tactics": scenario,
            "away_tactics": SCENARIOS[0],
            "duration_sec": 60,
            "sample_interval_sec": dt,
        },
        "lineup_method": (
            "get_filtered_best11 / 4-3-3 / 기본 기준"
        ),
        "score_label": None,
    }

    return data, check_document(data)
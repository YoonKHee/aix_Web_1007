from team.player_prediction_features import find_team
from simulation.models import SimulationRun
from simulation.generator import VERSION
from simulation.management.commands.export_match_features import build_row


DISPLAY_FIELDS = [
    (
        "distance_per_minute_mean",
        "선수당 분당 이동 거리",
        "m/분",
    ),
    (
        "high_speed_m_per_minute_mean",
        "선수당 분당 고속 이동 거리",
        "m/분",
    ),
    ("max_speed_kmh", "팀 최고 속도", "km/h"),
    ("attacking_time_pct", "공격 지역 활동 비율", "%"),
    ("pass_success_pct", "패스 성공률", "%"),
    ("forward_pass_success_pct", "전진 패스 성공률", "%"),
    ("interceptions_per_minute", "팀 분당 가로채기", "회/분"),
    ("possession_pct", "공 보유 비율", "%"),
]


def build_gps_features(home_name, away_name):
    try:
        home = find_team(home_name)
        away = find_team(away_name)

        if home.pk == away.pk:
            raise ValueError(
                "서로 다른 팀을 선택해야 합니다."
            )

        runs = (
            SimulationRun.objects
            .filter(
                generator_version=VERSION,
                home_team=home,
                away_team=away,
            )
            .order_by("created_at", "pk")
        )

        samples = []
        scenarios = set()

        for run in runs.iterator(chunk_size=10):
            samples.append(build_row(run))
            scenarios.add(run.scenario_code)

    except (ValueError, KeyError, TypeError) as exc:
        return {
            "available": False,
            "message": f"더미 집계를 확인해 주세요: {exc}",
        }

    if not samples:
        return {
            "available": False,
            "message": (
                "이 홈·원정 조합으로 저장한 현재 버전의 "
                "더미 경기가 없습니다. 반대 대진이나 "
                "다른 팀의 기록으로 대신 계산하지 않습니다."
            ),
        }

    rows = []
    values = {}

    for key, label, unit in DISPLAY_FIELDS:
        valid = [
            sample
            for sample in samples
            if sample["home_" + key] is not None
            and sample["away_" + key] is not None
        ]

        if valid:
            home_value = sum(
                sample["home_" + key]
                for sample in valid
            ) / len(valid)

            away_value = sum(
                sample["away_" + key]
                for sample in valid
            ) / len(valid)

            difference = home_value - away_value

        else:
            home_value = None
            away_value = None
            difference = None

        values[key + "_diff"] = difference

        rows.append({
            "label": label,
            "home": home_value,
            "away": away_value,
            "difference": difference,
            "unit": unit,
            "difference_unit": (
                "%p" if unit == "%" else unit
            ),
            "count": len(valid),
        })

    return {
        "available": True,
        "data_source": "synthetic",
        "run_count": len(samples),
        "scenario_count": len(scenarios),
        "home_name": home.team_name,
        "away_name": away.team_name,
        "rows": rows,
        "values": values,
    }
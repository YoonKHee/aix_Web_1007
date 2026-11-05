import csv
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from simulation.models import SimulationRun
from simulation.generator import VERSION
from simulation.tracking_models import SimulationPlayerTracking
from simulation.tracking_metrics import TRACKING_VERSION
from simulation.event_models import SimulationPlayerEventStats
from simulation.event_metrics import EVENT_VERSION


FEATURE_VERSION = "match-features-v1"

FEATURES = [
    "distance_per_minute_mean",
    "high_speed_m_per_minute_mean",
    "max_speed_kmh",
    "attacking_time_pct",
    "pass_success_pct",
    "forward_pass_success_pct",
    "interceptions_per_minute",
    "possession_pct",
]

META = [
    "run_id",
    "scenario_code",
    "scenario_name",
    "seed",
    "data_source",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "generator_version",
    "tracking_version",
    "event_version",
    "feature_version",
    "source_fingerprint",
    "outcome_label",
]


def percentage(numerator, denominator):
    if not denominator:
        return None

    return numerator / denominator * 100


def build_row(run):
    document = run.document

    if document.get("is_synthetic") is not True:
        raise ValueError("더미데이터만 내보낼 수 있습니다.")

    players = document["players"]
    ids = [p.get("real_player_id") for p in players]

    if len(ids) != 22 or None in ids or len(set(ids)) != 22:
        raise ValueError("선수 22명의 연결을 확인해야 합니다.")

    gps = {
        g.player_id: g
        for g in SimulationPlayerTracking.objects.filter(
            run=run,
            metrics_version=TRACKING_VERSION,
        )
    }

    events = {
        e.player_id: e
        for e in SimulationPlayerEventStats.objects.filter(
            run=run,
            metrics_version=EVENT_VERSION,
        )
    }

    if set(gps) != set(ids) or set(events) != set(ids):
        raise ValueError(
            "선수 GPS 또는 이벤트 집계가 누락됐습니다."
        )

    grouped = {}

    for side in ("HOME", "AWAY"):
        selected = [
            p for p in players
            if p["team_id"] == side
        ]

        if len(selected) != 11:
            raise ValueError("팀별 선수가 11명이 아닙니다.")

        gs = [gps[p["real_player_id"]] for p in selected]
        es = [events[p["real_player_id"]] for p in selected]

        if any(
            r.team_side != side
            or r.data_source != "synthetic"
            for r in gs + es
        ):
            raise ValueError(
                "팀 구분 또는 데이터 출처가 일치하지 않습니다."
            )

        if any(
            g.attacking_third_seconds is None
            or abs(
                g.tracked_seconds - document["duration_sec"]
            ) > 0.01
            for g in gs
        ):
            raise ValueError(
                "활동 위치 집계 또는 전체 위치 기록이 부족합니다."
            )

        grouped[side] = gs, es

    controlled_seconds = sum(
        e.possession_seconds
        for _, es in grouped.values()
        for e in es
    )

    minutes = document["duration_sec"] / 60

    if minutes <= 0:
        raise ValueError("경기 시간이 올바르지 않습니다.")

    metrics = {}

    for side, (gs, es) in grouped.items():
        metrics[side] = {
            "distance_per_minute_mean": (
                sum(g.distance_per_minute for g in gs) / 11
            ),
            "high_speed_m_per_minute_mean": (
                sum(g.high_speed_distance_m for g in gs)
                / minutes / 11
            ),
            "max_speed_kmh": max(
                g.max_speed_kmh for g in gs
            ),
            "attacking_time_pct": percentage(
                sum(g.attacking_third_seconds for g in gs),
                sum(g.tracked_seconds for g in gs),
            ),
            "pass_success_pct": percentage(
                sum(e.successful_passes for e in es),
                sum(e.pass_attempts for e in es),
            ),
            "forward_pass_success_pct": percentage(
                sum(e.successful_forward_passes for e in es),
                sum(e.forward_pass_attempts for e in es),
            ),
            "interceptions_per_minute": (
                sum(e.interceptions for e in es) / minutes
            ),
            "possession_pct": percentage(
                sum(e.possession_seconds for e in es),
                controlled_seconds,
            ),
        }

    snapshot = document.get("simulation", {})

    row = {
        "run_id": str(run.pk),
        "scenario_code": run.scenario_code,
        "scenario_name": run.scenario_name,
        "seed": run.seed,
        "data_source": "synthetic",
        "home_team_id": run.home_team_id,
        "home_team_name": snapshot.get(
            "home_team", {}
        ).get("name", ""),
        "away_team_id": run.away_team_id,
        "away_team_name": snapshot.get(
            "away_team", {}
        ).get("name", ""),
        "generator_version": run.generator_version,
        "tracking_version": TRACKING_VERSION,
        "event_version": EVENT_VERSION,
        "feature_version": FEATURE_VERSION,
        "source_fingerprint": run.fingerprint,
        "outcome_label": None,
    }

    for key in FEATURES:
        home = metrics["HOME"][key]
        away = metrics["AWAY"][key]

        row["home_" + key] = (
            round(home, 4) if home is not None else None
        )

        row["away_" + key] = (
            round(away, 4) if away is not None else None
        )

        row[key + "_diff"] = (
            round(home - away, 4)
            if home is not None and away is not None
            else None
        )

    return row


class Command(BaseCommand):
    help = "선수 기록을 홈·원정 경기 비교 컬럼으로 내보냅니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="data/prediction/match_features_synthetic.csv",
        )

    def handle(self, *args, **options):
        output = Path(options["output"])

        if not output.is_absolute():
            output = Path(settings.BASE_DIR) / output

        if output.suffix.lower() != ".csv":
            raise CommandError(
                "출력 파일 확장자는 .csv여야 합니다."
            )

        columns = META + [
            name
            for key in FEATURES
            for name in (
                "home_" + key,
                "away_" + key,
                key + "_diff",
            )
        ]

        temporary = None
        count = 0

        try:
            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8-sig",
                newline="",
                dir=output.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)

                writer = csv.DictWriter(
                    stream,
                    fieldnames=columns,
                )

                writer.writeheader()

                runs = (
                    SimulationRun.objects
                    .filter(generator_version=VERSION)
                    .order_by("created_at", "pk")
                )

                for run in runs.iterator(chunk_size=10):
                    try:
                        row = build_row(run)

                    except (ValueError, KeyError, TypeError) as exc:
                        raise CommandError(
                            f"{run.pk} 내보내기 중단: {exc}"
                        ) from exc

                    writer.writerow(row)
                    count += 1

            os.replace(temporary, output)

        except OSError as exc:
            raise CommandError(
                f"CSV 저장 실패: {exc}. "
                "엑셀에서 파일을 열었다면 닫아 주세요."
            ) from exc

        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 경기 비교 데이터 {count}행 저장."
            )
        )

        self.stdout.write(str(output))
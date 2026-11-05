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


GPS_FIELDS = [
    "tracked_seconds",
    "total_distance_m",
    "distance_per_minute",
    "avg_speed_kmh",
    "max_speed_kmh",
    "high_speed_distance_m",
    "sprint_count",
    "sprint_distance_m",
    "sprint_seconds",
    "average_x",
    "average_y",
    "defensive_third_seconds",
    "middle_third_seconds",
    "attacking_third_seconds",
    "opponent_box_entries",
]

EVENT_FIELDS = [
    "pass_attempts",
    "successful_passes",
    "failed_passes",
    "passes_received",
    "forward_pass_attempts",
    "successful_forward_passes",
    "interceptions",
    "possession_seconds",
]

META_FIELDS = [
    "run_id",
    "scenario_code",
    "scenario_name",
    "seed",
    "generator_version",
    "data_source",
    "team_side",
    "team_name",
    "player_id",
    "player_name",
    "position",
    "slot_id",
    "gps_available",
    "events_available",
    "spatial_available",
    "tracking_version",
    "event_version",
    "pass_success_rate",
    "outcome_label",
]


class Command(BaseCommand):
    help = "더미 경기의 선수별 GPS와 이벤트를 CSV 한 행으로 합칩니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="data/prediction/player_features_synthetic.csv",
        )

    def rows(self):
        runs = (
            SimulationRun.objects
            .filter(generator_version=VERSION)
            .order_by("created_at", "pk")
        )

        for run in runs.iterator(chunk_size=10):
            document = run.document

            if document.get("is_synthetic") is not True:
                raise CommandError(
                    f"{run.pk}: 더미데이터가 아닙니다."
                )

            players = document["players"]

            real_ids = [
                player.get("real_player_id")
                for player in players
            ]

            if (
                len(players) != 22
                or None in real_ids
                or len(set(real_ids)) != 22
            ):
                raise CommandError(
                    f"{run.pk}: 선수 22명의 연결을 확인하세요."
                )

            gps = {
                row.player_id: row
                for row in SimulationPlayerTracking.objects.filter(
                    run=run,
                    metrics_version=TRACKING_VERSION,
                )
            }

            events = {
                row.player_id: row
                for row in SimulationPlayerEventStats.objects.filter(
                    run=run,
                    metrics_version=EVENT_VERSION,
                )
            }

            for player in players:
                pid = player["real_player_id"]

                g = gps.get(pid)
                e = events.get(pid)

                spatial_available = (
                    g is not None
                    and all(
                        getattr(g, key) is not None
                        for key in GPS_FIELDS[9:]
                    )
                )

                row = {
                    "run_id": str(run.pk),
                    "scenario_code": run.scenario_code,
                    "scenario_name": run.scenario_name,
                    "seed": run.seed,
                    "generator_version": run.generator_version,
                    "data_source": "synthetic",
                    "team_side": player["team_id"],
                    "team_name": player.get("real_team_name", ""),
                    "player_id": pid,
                    "player_name": player.get("name", ""),
                    "position": player.get("real_position", ""),
                    "slot_id": player["player_id"],
                    "gps_available": int(g is not None),
                    "events_available": int(e is not None),
                    "spatial_available": int(spatial_available),
                    "tracking_version": (
                        g.metrics_version if g else ""
                    ),
                    "event_version": (
                        e.metrics_version if e else ""
                    ),
                    "pass_success_rate": (
                        e.pass_success_rate if e else None
                    ),
                    "outcome_label": None,
                }

                for fields, record in (
                    (GPS_FIELDS, g),
                    (EVENT_FIELDS, e),
                ):
                    row.update({
                        key: (
                            getattr(record, key)
                            if record else None
                        )
                        for key in fields
                    })

                yield row

    def handle(self, *args, **options):
        output = Path(options["output"])

        if not output.is_absolute():
            output = Path(settings.BASE_DIR) / output

        if output.suffix.lower() != ".csv":
            raise CommandError(
                "출력 파일 확장자는 .csv여야 합니다."
            )

        temporary = None
        count = 0
        missing = 0

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
                    fieldnames=(
                        META_FIELDS + GPS_FIELDS + EVENT_FIELDS
                    ),
                )

                writer.writeheader()

                for row in self.rows():
                    writer.writerow(row)
                    count += 1

                    complete = (
                        row["gps_available"]
                        and row["events_available"]
                        and row["spatial_available"]
                    )

                    missing += int(not complete)

            # 내보내기가 끝난 뒤에만 최종 파일을 교체합니다.
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
                f"완료: 선수 기록 {count}행 저장."
            )
        )

        self.stdout.write(str(output))

        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"일부 집계가 없는 {missing}행은 "
                    "해당 값을 빈칸으로 저장했습니다."
                )
            )
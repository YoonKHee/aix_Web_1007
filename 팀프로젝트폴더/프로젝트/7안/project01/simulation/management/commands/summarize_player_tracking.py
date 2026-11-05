from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from player.models import Player
from simulation.generator import VERSION
from simulation.models import SimulationRun
from simulation.tracking_models import SimulationPlayerTracking
from simulation.tracking_metrics import (
    TRACKING_VERSION,
    PARAMETERS,
    extract_player_tracking,
)


class Command(BaseCommand):
    help = "가상 경기 GPS를 선수별로 계산해 저장합니다."

    def handle(self, *args, **options):
        count = 0

        runs = SimulationRun.objects.filter(
            generator_version=VERSION,
        )

        for run in runs.iterator(chunk_size=10):
            try:
                values = extract_player_tracking(
                    run.document,
                )

                players = run.document["players"]

                real_ids = [
                    player.get("real_player_id")
                    for player in players
                ]

                existing = Player.objects.in_bulk(
                    real_ids,
                )

                if (
                    None in real_ids
                    or len(set(real_ids)) != 22
                    or len(existing) != 22
                ):
                    raise ValueError(
                        "실제 선수 22명의 연결을 확인해야 합니다."
                    )

                # 한 경기의 선수 22명 기록을 함께 저장합니다.
                with transaction.atomic():
                    for player in players:
                        pid = player["player_id"]

                        SimulationPlayerTracking.objects.update_or_create(
                            run=run,
                            player_id=player["real_player_id"],
                            metrics_version=TRACKING_VERSION,
                            defaults={
                                **values[pid],
                                "slot_id": pid,
                                "team_side": player["team_id"],
                                "data_source": "synthetic",
                                "parameters": PARAMETERS,
                            },
                        )

                count += 1

            except (ValueError, KeyError, TypeError) as exc:
                raise CommandError(
                    f"{run.pk} 계산 중단: {exc}"
                ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: {count}경기, "
                f"{count * 22}개 선수 GPS 기록 저장."
            )
        )
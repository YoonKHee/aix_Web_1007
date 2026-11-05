from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from player.models import Player
from simulation.models import SimulationRun
from simulation.generator import VERSION
from simulation.event_models import SimulationPlayerEventStats
from simulation.event_metrics import (
    EVENT_VERSION,
    EVENT_PARAMETERS,
    extract_player_events,
)


class Command(BaseCommand):
    help = "더미 경기의 선수별 패스와 공 보유 기록을 집계합니다."

    def handle(self, *args, **options):
        count = 0

        runs = SimulationRun.objects.filter(
            generator_version=VERSION,
        )

        for run in runs.iterator(chunk_size=10):
            try:
                values = extract_player_events(run.document)
                players = run.document["players"]

                real_ids = [
                    player.get("real_player_id")
                    for player in players
                ]

                if (
                    None in real_ids
                    or len(set(real_ids)) != 22
                    or Player.objects.filter(
                        pk__in=real_ids
                    ).count() != 22
                ):
                    raise ValueError(
                        "실제 선수 22명의 연결을 확인해야 합니다."
                    )

                with transaction.atomic():
                    for player in players:
                        pid = player["player_id"]

                        SimulationPlayerEventStats.objects.update_or_create(
                            run=run,
                            player_id=player["real_player_id"],
                            metrics_version=EVENT_VERSION,
                            defaults={
                                **values[pid],
                                "slot_id": pid,
                                "team_side": player["team_id"],
                                "data_source": "synthetic",
                                "parameters": EVENT_PARAMETERS,
                            },
                        )

                count += 1

            except (ValueError, KeyError, TypeError) as exc:
                raise CommandError(
                    f"{run.pk} 집계 중단: {exc}"
                ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: {count}경기, "
                f"{count * 22}개 선수 이벤트 기록 저장."
            )
        )
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from simulation.generator import VERSION
from simulation.metrics import METRICS_VERSION, summarize
from simulation.models import SimulationRun, SimulationTeamSummary


class Command(BaseCommand):
    help = "현재 생성기 버전의 가상 경기를 팀별로 집계합니다."

    def handle(self, *args, **options):
        runs = SimulationRun.objects.filter(
            generator_version=VERSION,
        )

        count = 0

        for run in runs.iterator(chunk_size=20):
            try:
                result = summarize(run.document)

            except (ValueError, KeyError, TypeError) as exc:
                raise CommandError(
                    f"{run.pk} 집계 중단: {exc}"
                ) from exc

            # 홈팀과 원정팀 통계를 함께 저장합니다.
            with transaction.atomic():
                for side, values in result.items():
                    SimulationTeamSummary.objects.update_or_create(
                        run=run,
                        side=side,
                        metrics_version=METRICS_VERSION,
                        defaults=values,
                    )

            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: {count}경기, "
                f"{count * 2}개 팀 통계 집계. "
                f"생성기 버전: {VERSION}"
            )
        )
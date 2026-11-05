import hashlib
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from team.models import Team

from simulation.generator import (
    SCENARIOS,
    VERSION,
    check_document,
    digest,
    generate,
)
from simulation.models import SimulationRun


class Command(BaseCommand):
    help = '가상 시나리오 10개를 생성하고 별도 테이블에 저장합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--home',
            type=int,
            required=True,
            help='홈팀 DB 번호',
        )

        parser.add_argument(
            '--away',
            type=int,
            required=True,
            help='원정팀 DB 번호',
        )

        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='같은 데이터를 재현하기 위한 난수 시드',
        )

    def handle(self, *args, **options):
        home_id = options['home']
        away_id = options['away']
        seed = options['seed']

        if home_id == away_id:
            raise CommandError(
                '홈팀과 원정팀은 달라야 합니다.'
            )

        if not 0 <= seed <= 2147483647:
            raise CommandError(
                '시드는 0~2147483647 범위로 입력하세요.'
            )

        # 저장 전에 원본과 생성 결과 전체를 검사합니다.
        try:
            home = Team.objects.get(pk=home_id)
            away = Team.objects.get(pk=away_id)

            source_path = (
                settings.BASE_DIR
                / 'data'
                / 'demo'
                / 'tracking_demo.json'
            )

            raw = source_path.read_bytes()
            source = json.loads(raw.decode('utf-8'))

            if source.get('is_synthetic') is not True:
                raise ValueError(
                    '가상 데이터만 사용할 수 있습니다.'
                )

            check_document(source)

            source_hash = hashlib.sha256(raw).hexdigest()

            prepared = []

            for scenario in SCENARIOS:
                document, validation = generate(
                    source=source,
                    scenario=scenario,
                    home=home,
                    away=away,
                    seed=seed,
                    source_hash=source_hash,
                )

                prepared.append(
                    (scenario, document, validation)
                )

        except (
            Team.DoesNotExist,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            ValidationError,
        ) as exc:
            raise CommandError(
                f'저장 전 검사 중단: {exc}'
            ) from exc

        created_count = 0
        results = []

        # 도중에 오류가 발생하면 이번 저장 전체를 취소합니다.
        try:
            with transaction.atomic():
                for scenario, document, validation in prepared:
                    fingerprint = digest(document)

                    saved_run, created = (
                        SimulationRun.objects.get_or_create(
                            fingerprint=fingerprint,
                            defaults={
                                'home_team': home,
                                'away_team': away,
                                'scenario_code': scenario['code'],
                                'scenario_name': scenario['name'],
                                'generator_version': VERSION,
                                'seed': seed,
                                'duration_sec': document['duration_sec'],
                                'frame_count': len(document['frames']),
                                'event_count': len(document['events']),
                                'source_sha256': source_hash,
                                'document': document,
                                'parameters': (
                                    document['simulation']['parameters']
                                ),
                                'validation': validation,
                            },
                        )
                    )

                    created_count += int(created)

                    results.append({
                        'name': scenario['name'],
                        'created': created,
                        'duration': saved_run.duration_sec,
                    })

        except IntegrityError as exc:
            raise CommandError(
                f'DB 저장 실패. 이번 저장은 취소했습니다: {exc}'
            ) from exc

        # 저장이 모두 끝난 뒤 결과를 출력합니다.
        for result in results:
            status = (
                '새로 저장'
                if result['created']
                else '기존 유지'
            )

            self.stdout.write(
                f"{status}: {result['name']}"
                f" / {result['duration']}초"
            )

        duplicate_count = len(prepared) - created_count

        self.stdout.write(
            self.style.SUCCESS(
                f'완료: 새 경기 {created_count}개, '
                f'중복 {duplicate_count}개.'
            )
        )

        self.stdout.write(
            '기존 데모 JSON·실제 선수 기록·예측 모델은 '
            '변경하지 않았습니다.'
        )
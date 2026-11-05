import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import Player


class Command(BaseCommand):

    help = '광주FC 선수의 JSON 포지션과 DB 포지션을 비교합니다.'

    def handle(self, *args, **options):

        # =====================================================
        # 광주 선수정보 JSON 찾기
        # =====================================================

        json_dir = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
        )

        json_file = (
            json_dir
            / '광주_선수정보.json'
        )

        if not json_file.exists():

            self.stdout.write(
                self.style.ERROR(
                    f'파일을 찾을 수 없습니다: {json_file}'
                )
            )

            return

        # =====================================================
        # JSON 읽기
        # =====================================================

        with open(
            json_file,
            'r',
            encoding='utf-8-sig'
        ) as f:

            rows = json.load(f)

        # =====================================================
        # 기본 정보
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '광주FC 포지션 원인 검사'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write('')

        self.stdout.write(
            f'광주 선수정보 JSON : {len(rows)}명'
        )

        # =====================================================
        # 첫 번째 JSON의 실제 key 확인
        # =====================================================

        if rows:

            self.stdout.write('')

            self.stdout.write(
                '========== JSON 실제 컬럼 =========='
            )

            first_row = rows[0]

            for key in first_row.keys():

                self.stdout.write(
                    f'- {repr(key)}'
                )

            self.stdout.write('')

            self.stdout.write(
                '========== JSON 첫 번째 선수 원본 =========='
            )

            self.stdout.write(
                json.dumps(
                    first_row,
                    ensure_ascii=False,
                    indent=2
                )
            )

        # =====================================================
        # JSON 선수별 포지션 확인
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== JSON 선수별 포지션 =========='
        )

        json_position_empty = 0
        json_position_exists = 0

        for row in rows:

            name = str(
                row.get(
                    '성명',
                    ''
                )
            ).strip()

            position = str(
                row.get(
                    '포지션',
                    ''
                )
                or ''
            ).strip()

            if position:

                json_position_exists += 1

                status = 'OK'

            else:

                json_position_empty += 1

                status = 'EMPTY'

            self.stdout.write(
                f'{status:<5} / '
                f'{name:<15} / '
                f'포지션={repr(position)}'
            )

        # =====================================================
        # DB 광주 선수
        # =====================================================

        players = (
            Player.objects
            .filter(
                team__team_name='광주FC'
            )
            .order_by(
                'name'
            )
        )

        self.stdout.write('')

        self.stdout.write(
            '========== DB 광주FC 선수 =========='
        )

        db_position_empty = 0
        db_position_exists = 0

        for player in players:

            position = (
                player.position
                or ''
            ).strip()

            if position:

                db_position_exists += 1

                status = 'OK'

            else:

                db_position_empty += 1

                status = 'EMPTY'

            self.stdout.write(
                f'{status:<5} / '
                f'ID {player.id:<4} / '
                f'{player.name:<15} / '
                f'{player.number}번 / '
                f'포지션={repr(position)}'
            )

        # =====================================================
        # JSON ↔ DB 비교
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== JSON ↔ DB 비교 =========='
        )

        mismatch_count = 0

        for row in rows:

            name = str(
                row.get(
                    '성명',
                    ''
                )
            ).strip()

            json_position = str(
                row.get(
                    '포지션',
                    ''
                )
                or ''
            ).strip()

            player = (
                Player.objects
                .filter(
                    team__team_name='광주FC',
                    name=name
                )
                .first()
            )

            if player is None:

                self.stdout.write(
                    self.style.WARNING(
                        f'DB 선수 없음 / {name}'
                    )
                )

                continue

            db_position = (
                player.position
                or ''
            ).strip()

            if json_position != db_position:

                mismatch_count += 1

                self.stdout.write(
                    f'DIFF / '
                    f'{name} / '
                    f'JSON={repr(json_position)} / '
                    f'DB={repr(db_position)}'
                )

        # =====================================================
        # 최종 요약
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '검사 결과'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            f'JSON 포지션 있음 : '
            f'{json_position_exists}명'
        )

        self.stdout.write(
            f'JSON 포지션 없음 : '
            f'{json_position_empty}명'
        )

        self.stdout.write('')

        self.stdout.write(
            f'DB 포지션 있음   : '
            f'{db_position_exists}명'
        )

        self.stdout.write(
            f'DB 포지션 없음   : '
            f'{db_position_empty}명'
        )

        self.stdout.write('')

        self.stdout.write(
            f'JSON ↔ DB 불일치 : '
            f'{mismatch_count}명'
        )

        self.stdout.write('')

        # =====================================================
        # 원인 판정
        # =====================================================

        if json_position_empty > 0:

            self.stdout.write(
                self.style.WARNING(
                    '광주 선수정보 JSON 자체에 '
                    '포지션이 비어 있는 선수가 있습니다.'
                )
            )

        elif (
            json_position_empty == 0
            and
            db_position_empty > 0
        ):

            self.stdout.write(
                self.style.ERROR(
                    'JSON에는 포지션이 있지만 '
                    'DB 저장 과정에서 누락되었습니다.'
                )
            )

        else:

            self.stdout.write(
                self.style.SUCCESS(
                    '광주 포지션 데이터는 정상입니다.'
                )
            )

        self.stdout.write('')

        self.stdout.write(
            '※ 검사 전용 프로그램입니다.'
        )

        self.stdout.write(
            '※ DB를 수정하지 않았습니다.'
        )
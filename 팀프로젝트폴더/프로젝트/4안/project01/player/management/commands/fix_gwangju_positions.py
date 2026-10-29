import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from player.models import Player


class Command(BaseCommand):

    help = '광주 선수정보 JSON의 포자션 오타를 이용해 DB 포지션을 복구합니다.'

    # =========================================================
    # 옵션
    #
    # --check
    # 실제 수정하지 않고 검사만
    # =========================================================
    def add_arguments(self, parser):

        parser.add_argument(
            '--check',
            action='store_true',
            help='DB를 수정하지 않고 결과만 검사합니다.'
        )

    # =========================================================
    # 실행
    # =========================================================
    def handle(self, *args, **options):

        check_only = options['check']

        # =====================================================
        # 광주 JSON 파일
        # =====================================================

        json_file = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
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
        # 결과 저장용
        # =====================================================

        success_list = []
        fail_list = []
        empty_position_list = []

        # =====================================================
        # 먼저 전체 검사
        # =====================================================

        for row in rows:

            name = str(
                row.get(
                    '성명',
                    ''
                )
            ).strip()

            number = str(
                row.get(
                    '등번',
                    ''
                )
            ).strip()

            # =================================================
            # 중요!
            #
            # 정상 키:
            # 포지션
            #
            # 광주 JSON 오타:
            # 포자션
            #
            # 둘 다 대응
            # =================================================

            position = str(
                row.get('포지션')
                or
                row.get('포자션')
                or
                ''
            ).strip()

            # -------------------------------------------------
            # 포지션 자체가 비어 있음
            # -------------------------------------------------

            if not position:

                empty_position_list.append(
                    (
                        name,
                        number
                    )
                )

                continue

            # -------------------------------------------------
            # DB 광주 선수 찾기
            # -------------------------------------------------

            player = (
                Player.objects
                .filter(
                    team__team_name='광주FC',
                    name=name
                )
                .first()
            )

            if player is None:

                fail_list.append(
                    (
                        name,
                        number,
                        position
                    )
                )

                continue

            success_list.append(
                (
                    player,
                    position
                )
            )

        # =====================================================
        # 검사 결과 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '광주FC 포지션 복구'
        )

        self.stdout.write(
            '=========================================='
        )

        if check_only:

            self.stdout.write(
                '실행 방식 : 검사만 (--check)'
            )

        else:

            self.stdout.write(
                '실행 방식 : 실제 DB 수정'
            )

        self.stdout.write('')

        self.stdout.write(
            f'광주 JSON 선수 : {len(rows)}명'
        )

        self.stdout.write(
            f'DB 매칭 성공   : {len(success_list)}명'
        )

        self.stdout.write(
            f'DB 매칭 실패   : {len(fail_list)}명'
        )

        self.stdout.write(
            f'포지션 없음    : {len(empty_position_list)}명'
        )

        # =====================================================
        # 변경 예정 선수 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 포지션 변경 예정 =========='
        )

        for player, position in success_list:

            old_position = (
                player.position
                or ''
            )

            self.stdout.write(
                f'{player.name:<15} / '
                f'{player.number}번 / '
                f'{repr(old_position)} '
                f'→ '
                f'{repr(position)}'
            )

        # =====================================================
        # 실패
        # =====================================================

        if fail_list:

            self.stdout.write('')

            self.stdout.write(
                '========== DB 매칭 실패 =========='
            )

            for (
                name,
                number,
                position
            ) in fail_list:

                self.stdout.write(
                    f'{name} / '
                    f'{number}번 / '
                    f'{position}'
                )

        # =====================================================
        # 포지션 없음
        # =====================================================

        if empty_position_list:

            self.stdout.write('')

            self.stdout.write(
                '========== 포지션 값 없음 =========='
            )

            for (
                name,
                number
            ) in empty_position_list:

                self.stdout.write(
                    f'{name} / '
                    f'{number}번'
                )

        # =====================================================
        # 검사 모드 종료
        # =====================================================

        if check_only:

            self.stdout.write('')

            if (
                len(success_list) == 36
                and
                len(fail_list) == 0
                and
                len(empty_position_list) == 0
            ):

                self.stdout.write(
                    self.style.SUCCESS(
                        '최종 판정 : 36명 모두 복구 가능 ✅'
                    )
                )

            else:

                self.stdout.write(
                    self.style.ERROR(
                        '최종 판정 : 실제 수정 전 확인 필요 ❌'
                    )
                )

            self.stdout.write('')

            self.stdout.write(
                '※ DB는 수정하지 않았습니다.'
            )

            return

        # =====================================================
        # 실제 수정 전 안전검사
        # =====================================================

        if fail_list:

            raise RuntimeError(
                'DB에 매칭되지 않는 광주 선수가 있습니다.'
            )

        if empty_position_list:

            raise RuntimeError(
                '포지션 값이 없는 광주 선수가 있습니다.'
            )

        if len(success_list) != 36:

            raise RuntimeError(
                f'광주 선수 수가 예상과 다릅니다. '
                f'현재 {len(success_list)}명'
            )

        # =====================================================
        # 실제 DB 수정
        #
        # position만 수정
        # 다른 데이터는 절대 건드리지 않음
        # =====================================================

        with transaction.atomic():

            update_count = 0

            for player, position in success_list:

                player.position = position

                player.save(
                    update_fields=[
                        'position'
                    ]
                )

                update_count += 1

        # =====================================================
        # 완료
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            self.style.SUCCESS(
                '광주FC 포지션 복구 완료'
            )
        )

        self.stdout.write(
            f'수정 선수 : {update_count}명'
        )

        self.stdout.write(
            '=========================================='
        )
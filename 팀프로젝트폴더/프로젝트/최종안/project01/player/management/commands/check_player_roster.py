import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import Player


class Command(BaseCommand):

    help = '기존 DB 선수와 새로운 K리그 선수정보 JSON 명단을 비교합니다.'

    # =========================================================
    # 문자열 정리
    #
    # 예:
    # "후안 이비자" -> "후안이비자"
    # =========================================================
    def normalize(self, value):

        if value is None:
            return ''

        return re.sub(
            r'\s+',
            '',
            str(value).strip()
        )

    # =========================================================
    # JSON 팀 이름과 DB 팀 이름 비교
    #
    # 강원 ↔ 강원FC
    # 서울 ↔ FC서울
    # 전북 ↔ 전북현대
    # =========================================================
    def same_team(self, json_team, db_team):

        json_team = self.normalize(json_team)
        db_team = self.normalize(db_team)

        if not json_team or not db_team:
            return False

        return (
            json_team in db_team
            or
            db_team in json_team
        )

    # =========================================================
    # 값이 없을 때 보기 좋게 표시
    # =========================================================
    def show_value(self, value):

        if value is None:
            return '-'

        value = str(value).strip()

        if value == '':
            return '-'

        return value

    # =========================================================
    # 실행
    # =========================================================
    def handle(self, *args, **options):

        json_dir = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
        )

        if not json_dir.exists():

            self.stdout.write(
                self.style.ERROR(
                    'JSON 데이터 폴더를 찾을 수 없습니다.'
                )
            )

            self.stdout.write(
                str(json_dir)
            )

            return

        # =====================================================
        # 1. JSON 선수정보 읽기
        # =====================================================

        json_players = []

        info_files = sorted(
            json_dir.glob('*_선수정보.json')
        )

        for json_file in info_files:

            team_name = (
                json_file.name.split('_')[0]
            )

            with open(
                json_file,
                'r',
                encoding='utf-8-sig'
            ) as f:

                rows = json.load(f)

            for row in rows:

                player_name = str(
                    row.get(
                        '성명',
                        ''
                    )
                ).strip()

                if not player_name:
                    continue

                json_players.append(
                    {
                        'team': team_name,
                        'name': player_name,

                        # -------------------------------------
                        # 동명이인 비교에 사용할 상세정보
                        # -------------------------------------
                        'number': row.get('등번'),
                        'position': row.get('포지션'),
                        'height': row.get('키'),
                        'weight': row.get('몸무게'),
                        'birth_date': row.get('생년월일'),
                    }
                )

        # =====================================================
        # 2. 기존 DB 선수 읽기
        # =====================================================

        db_players = list(
            Player.objects
            .select_related('team')
            .all()
        )

        # =====================================================
        # 3. 결과 저장용
        # =====================================================

        exact_matches = []

        new_players = []

        moved_players = []

        duplicate_players = []

        matched_db_ids = set()

        # =====================================================
        # 4. JSON 선수 한 명씩 검사
        # =====================================================

        for item in json_players:

            json_team = item['team']
            json_name = item['name']

            # -------------------------------------------------
            # 이름이 같은 DB 선수 찾기
            # -------------------------------------------------

            same_name_players = []

            for player in db_players:

                if (
                    self.normalize(player.name)
                    ==
                    self.normalize(json_name)
                ):

                    same_name_players.append(
                        player
                    )

            # -------------------------------------------------
            # 이름 자체가 DB에 없음
            #
            # → 신규 선수 후보
            # -------------------------------------------------

            if len(same_name_players) == 0:

                new_players.append(
                    item
                )

                continue

            # -------------------------------------------------
            # 같은 이름 + 같은 팀 찾기
            # -------------------------------------------------

            same_team_players = []

            for player in same_name_players:

                if self.same_team(
                    json_team,
                    player.team.team_name
                ):

                    same_team_players.append(
                        player
                    )

            # -------------------------------------------------
            # 같은 이름 + 같은 팀 정확히 1명
            #
            # → 정상 매칭
            # -------------------------------------------------

            if len(same_team_players) == 1:

                player = same_team_players[0]

                exact_matches.append(
                    (
                        item,
                        player
                    )
                )

                matched_db_ids.add(
                    player.pk
                )

                continue

            # -------------------------------------------------
            # DB에 같은 이름이 딱 1명
            # 그런데 팀은 다름
            #
            # → 팀 이동 후보
            # -------------------------------------------------

            if len(same_name_players) == 1:

                player = same_name_players[0]

                moved_players.append(
                    (
                        item,
                        player
                    )
                )

                matched_db_ids.add(
                    player.pk
                )

                continue

            # -------------------------------------------------
            # 이름 같은 DB 선수가 여러 명
            # 현재 팀에도 정확히 일치하지 않음
            #
            # → 동명이인
            # -------------------------------------------------

            duplicate_players.append(
                (
                    item,
                    same_name_players
                )
            )

        # =====================================================
        # 5. 기존 DB에만 있는 선수 찾기
        # =====================================================

        duplicate_candidate_ids = set()

        for item, candidates in duplicate_players:

            for player in candidates:

                duplicate_candidate_ids.add(
                    player.pk
                )

        old_only_players = []

        for player in db_players:

            if player.pk in matched_db_ids:
                continue

            if player.pk in duplicate_candidate_ids:
                continue

            old_only_players.append(
                player
            )

        # =====================================================
        # 6. 전체 결과 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            'K리그 선수 명단 비교 결과'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            f'기존 DB 선수           : '
            f'{len(db_players)}명'
        )

        self.stdout.write(
            f'새 JSON 선수정보       : '
            f'{len(json_players)}명'
        )

        self.stdout.write('')

        self.stdout.write(
            self.style.SUCCESS(
                f'같은 팀 + 같은 이름    : '
                f'{len(exact_matches)}명'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'신규 선수 후보         : '
                f'{len(new_players)}명'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'팀 이동 후보           : '
                f'{len(moved_players)}명'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'동명이인 확인 필요     : '
                f'{len(duplicate_players)}명'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'기존 DB에만 있는 선수  : '
                f'{len(old_only_players)}명'
            )
        )

        # =====================================================
        # 7. 신규 선수 출력
        # =====================================================

        if new_players:

            self.stdout.write('')

            self.stdout.write(
                '========== 신규 선수 후보 =========='
            )

            for item in new_players:

                self.stdout.write(
                    f"{item['team']} / "
                    f"{item['name']}"
                )

        # =====================================================
        # 8. 팀 이동 후보 출력
        # =====================================================

        if moved_players:

            self.stdout.write('')

            self.stdout.write(
                '========== 팀 이동 후보 =========='
            )

            for item, player in moved_players:

                self.stdout.write(
                    f'{player.team.team_name} / '
                    f'{player.name}'
                    f'  →  '
                    f"{item['team']}"
                )

        # =====================================================
        # 9. 동명이인 상세 비교
        #
        # 이번 단계에서 가장 중요한 부분
        # =====================================================

        if duplicate_players:

            self.stdout.write('')

            self.stdout.write(
                '=========================================='
            )

            self.stdout.write(
                '동명이인 상세 비교'
            )

            self.stdout.write(
                '=========================================='
            )

            for item, candidates in duplicate_players:

                self.stdout.write('')

                self.stdout.write(
                    '------------------------------------------'
                )

                self.stdout.write(
                    f"JSON 선수 : "
                    f"{item['team']} / "
                    f"{item['name']}"
                )

                self.stdout.write(
                    '------------------------------------------'
                )

                self.stdout.write(
                    f"등번호     : "
                    f"{self.show_value(item['number'])}"
                )

                self.stdout.write(
                    f"포지션     : "
                    f"{self.show_value(item['position'])}"
                )

                self.stdout.write(
                    f"키         : "
                    f"{self.show_value(item['height'])}"
                )

                self.stdout.write(
                    f"몸무게     : "
                    f"{self.show_value(item['weight'])}"
                )

                self.stdout.write(
                    f"생년월일   : "
                    f"{self.show_value(item['birth_date'])}"
                )

                # =============================================
                # DB 후보들
                # =============================================

                for index, player in enumerate(
                    candidates,
                    start=1
                ):

                    self.stdout.write('')

                    self.stdout.write(
                        f'  [DB 후보 {index}]'
                    )

                    self.stdout.write(
                        f'  DB ID      : '
                        f'{player.pk}'
                    )

                    self.stdout.write(
                        f'  현재 팀    : '
                        f'{player.team.team_name}'
                    )

                    self.stdout.write(
                        f'  이름       : '
                        f'{player.name}'
                    )

                    self.stdout.write(
                        f'  등번호     : '
                        f'{self.show_value(player.number)}'
                    )

                    self.stdout.write(
                        f'  포지션     : '
                        f'{self.show_value(player.position)}'
                    )

                    self.stdout.write(
                        f'  키         : '
                        f'{self.show_value(player.height)}'
                    )

                    self.stdout.write(
                        f'  몸무게     : '
                        f'{self.show_value(player.weight)}'
                    )

                    self.stdout.write(
                        f'  생년월일   : '
                        f'{self.show_value(player.birth_date)}'
                    )

        # =====================================================
        # 10. 기존 DB에만 있는 선수
        # =====================================================

        if old_only_players:

            self.stdout.write('')

            self.stdout.write(
                '=========================================='
            )

            self.stdout.write(
                '기존 DB에만 있는 선수'
            )

            self.stdout.write(
                '=========================================='
            )

            for player in old_only_players:

                self.stdout.write(
                    f'{player.team.team_name} / '
                    f'{player.name}'
                )

        # =====================================================
        # 11. 마지막 안내
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '※ 검사 전용 명령어입니다.'
        )

        self.stdout.write(
            '※ DB 추가/수정/삭제는 하지 않았습니다.'
        )
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import PlayerStats


class Command(BaseCommand):

    help = '2026 현재 JSON 성적 기준 BEST11 후보군을 검사합니다.'

    # =========================================================
    # 문자열 정리
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
    # JSON 읽기
    # =========================================================
    def read_json(self, path):

        with open(
            path,
            'r',
            encoding='utf-8-sig'
        ) as f:

            return json.load(f)

    # =========================================================
    # 팀 이름 비교
    # =========================================================
    def same_team(
        self,
        json_team,
        db_team
    ):

        json_team = self.normalize(
            json_team
        )

        db_team = self.normalize(
            db_team
        )

        if not json_team or not db_team:
            return False

        return (
            json_team in db_team
            or
            db_team in json_team
        )

    # =========================================================
    # JSON 성적에 해당 선수가 있는지 확인
    # =========================================================
    def is_current_stats_player(
        self,
        player,
        json_stats
    ):

        player_name = self.normalize(
            player.name
        )

        db_team = (
            player.team.team_name
        )

        for (
            json_team,
            ranking_text
        ) in json_stats:

            # ---------------------------------------------
            # 같은 팀 확인
            # ---------------------------------------------
            if not self.same_team(
                json_team,
                db_team
            ):

                continue

            # ---------------------------------------------
            # 성적 문자열에 선수 이름이 있는지 확인
            # ---------------------------------------------
            ranking_text = self.normalize(
                ranking_text
            )

            if (
                player_name
                and
                player_name in ranking_text
            ):

                return True

        return False

    # =========================================================
    # 실행
    # =========================================================
    def handle(
        self,
        *args,
        **options
    ):

        # =====================================================
        # JSON 위치
        # =====================================================

        json_dir = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
        )

        # =====================================================
        # 선수성적 JSON 읽기
        # =====================================================

        json_stats = []

        stats_files = sorted(
            json_dir.glob(
                '*_선수성적.json'
            )
        )

        for json_file in stats_files:

            team_name = (
                json_file.name
                .split('_')[0]
            )

            rows = self.read_json(
                json_file
            )

            for row in rows:

                ranking_text = str(
                    row.get(
                        '순위',
                        ''
                    )
                ).strip()

                json_stats.append(
                    (
                        team_name,
                        ranking_text
                    )
                )

        # =====================================================
        # DB 2026 성적
        # =====================================================

        stats_2026 = (
            PlayerStats.objects
            .filter(
                season=2026
            )
            .select_related(
                'player',
                'player__team'
            )
        )

        # =====================================================
        # 결과 저장
        # =====================================================

        current_stats = []

        candidates = []

        excluded_old = []

        excluded_minutes = []

        # =====================================================
        # DB 성적 하나씩 검사
        # =====================================================

        for stats in stats_2026:

            player = stats.player

            # =================================================
            # 1. 현재 JSON 420명인지 확인
            # =================================================

            is_current = (
                self.is_current_stats_player(
                    player,
                    json_stats
                )
            )

            # -------------------------------------------------
            # 현재 JSON 성적에 없는 기존 DB 선수
            # -------------------------------------------------

            if not is_current:

                excluded_old.append(
                    stats
                )

                continue

            # -------------------------------------------------
            # 현재 JSON 성적 선수
            # -------------------------------------------------

            current_stats.append(
                stats
            )

            # =================================================
            # 2. 출전시간 600분 확인
            # =================================================

            if stats.minutes < 600:

                excluded_minutes.append(
                    stats
                )

                continue

            # =================================================
            # BEST11 최종 후보
            # =================================================

            candidates.append(
                stats
            )

        # =====================================================
        # 포지션 분리
        # =====================================================

        gk_list = []
        df_list = []
        mf_list = []
        fw_list = []
        etc_list = []

        for stats in candidates:

            position = self.normalize(
                stats.player.position
            ).upper()

            if position == 'GK':

                gk_list.append(
                    stats
                )

            elif position == 'DF':

                df_list.append(
                    stats
                )

            elif position == 'MF':

                mf_list.append(
                    stats
                )

            elif position == 'FW':

                fw_list.append(
                    stats
                )

            else:

                etc_list.append(
                    stats
                )

        # =====================================================
        # 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '2026 BEST11 후보군 검사'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write('')

        self.stdout.write(
            f'DB 2026 PlayerStats     : '
            f'{stats_2026.count()}명'
        )

        self.stdout.write(
            f'현재 JSON 성적 선수     : '
            f'{len(current_stats)}명'
        )

        self.stdout.write(
            f'기존 DB 전용 제외       : '
            f'{len(excluded_old)}명'
        )

        self.stdout.write(
            f'600분 미만 제외         : '
            f'{len(excluded_minutes)}명'
        )

        self.stdout.write('')

        self.stdout.write(
            self.style.SUCCESS(
                f'BEST11 후보             : '
                f'{len(candidates)}명'
            )
        )

        # =====================================================
        # 포지션별 후보
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 포지션별 후보 =========='
        )

        self.stdout.write(
            f'GK : {len(gk_list)}명'
        )

        self.stdout.write(
            f'DF : {len(df_list)}명'
        )

        self.stdout.write(
            f'MF : {len(mf_list)}명'
        )

        self.stdout.write(
            f'FW : {len(fw_list)}명'
        )

        self.stdout.write(
            f'기타 : {len(etc_list)}명'
        )

        # =====================================================
        # 제외된 기존 DB 선수
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 기존 DB 전용 제외 =========='
        )

        for stats in excluded_old:

            player = stats.player

            self.stdout.write(
                f'{player.team.team_name} / '
                f'{player.name} / '
                f'{player.position} / '
                f'{stats.minutes}분'
            )

        # =====================================================
        # 600분 이상인데 포지션 이상
        # =====================================================

        if etc_list:

            self.stdout.write('')

            self.stdout.write(
                '========== 포지션 확인 필요 =========='
            )

            for stats in etc_list:

                player = stats.player

                self.stdout.write(
                    f'{player.team.team_name} / '
                    f'{player.name} / '
                    f'position={player.position} / '
                    f'{stats.minutes}분'
                )

        # =====================================================
        # BEST11 계산 가능 여부
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            'BEST11 계산 준비 상태'
        )

        self.stdout.write(
            '=========================================='
        )

        enough_position = (
            len(gk_list) >= 1
            and
            len(df_list) >= 4
            and
            len(mf_list) >= 3
            and
            len(fw_list) >= 3
        )

        if (
            len(current_stats) == 420
            and
            len(excluded_old) == 9
            and
            enough_position
        ):

            self.stdout.write(
                self.style.SUCCESS(
                    'BEST11 점수 계산 준비 완료 ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.WARNING(
                    'BEST11 후보군을 추가 확인해야 합니다.'
                )
            )

        self.stdout.write('')

        self.stdout.write(
            '※ DB를 수정하지 않았습니다.'
        )
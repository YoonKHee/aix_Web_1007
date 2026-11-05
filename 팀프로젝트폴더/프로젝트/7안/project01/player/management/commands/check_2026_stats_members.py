import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import PlayerStats


class Command(BaseCommand):

    help = '2026 PlayerStats와 JSON 선수성적 420건의 포함 관계를 검사합니다.'

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
    # JSON 파일 읽기
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
    #
    # 강원 ↔ 강원FC
    # 서울 ↔ FC서울
    # 전북 ↔ 전북현대
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
    # 순위 문자열에서 선수 이름 찾기
    #
    # 예:
    # 15조현태강원
    #
    # DB 선수:
    # 조현태
    #
    # → 성공
    # =========================================================
    def ranking_contains_player(
        self,
        ranking_text,
        player_name
    ):

        ranking_text = self.normalize(
            ranking_text
        )

        player_name = self.normalize(
            player_name
        )

        if not player_name:
            return False

        return (
            player_name
            in ranking_text
        )

    # =========================================================
    # 실행
    # =========================================================
    def handle(
        self,
        *args,
        **options
    ):

        # =====================================================
        # JSON 폴더
        # =====================================================

        json_dir = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
        )

        if not json_dir.exists():

            self.stdout.write(
                self.style.ERROR(
                    'JSON 폴더를 찾을 수 없습니다.'
                )
            )

            return

        # =====================================================
        # 선수성적 JSON 파일
        # =====================================================

        stats_files = sorted(
            json_dir.glob(
                '*_선수성적.json'
            )
        )

        # =====================================================
        # JSON 성적 전체 저장
        #
        # [
        #   ('강원', '15조현태강원'),
        #   ...
        # ]
        # =====================================================

        json_stats = []

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
        # DB의 2026 PlayerStats
        # =====================================================

        db_stats = (
            PlayerStats.objects
            .filter(
                season=2026
            )
            .select_related(
                'player',
                'player__team'
            )
            .order_by(
                'player__team__team_name',
                'player__name'
            )
        )

        # =====================================================
        # 결과 저장
        # =====================================================

        matched = []

        db_only = []

        # =====================================================
        # DB PlayerStats 1개씩 검사
        # =====================================================

        for stats in db_stats:

            player = stats.player

            db_team = (
                player.team.team_name
            )

            db_name = (
                player.name
            )

            found = False

            matched_json_team = None
            matched_ranking = None

            # -------------------------------------------------
            # JSON 420건 중에서
            # 같은 팀 + 같은 이름 찾기
            # -------------------------------------------------

            for (
                json_team,
                ranking_text
            ) in json_stats:

                # 같은 팀인지
                if not self.same_team(
                    json_team,
                    db_team
                ):

                    continue

                # 순위 문자열에 이름이 있는지
                if not self.ranking_contains_player(
                    ranking_text,
                    db_name
                ):

                    continue

                found = True

                matched_json_team = (
                    json_team
                )

                matched_ranking = (
                    ranking_text
                )

                break

            # -------------------------------------------------
            # JSON에도 존재
            # -------------------------------------------------

            if found:

                matched.append(
                    (
                        stats,
                        matched_json_team,
                        matched_ranking
                    )
                )

            # -------------------------------------------------
            # DB에만 존재
            # -------------------------------------------------

            else:

                db_only.append(
                    stats
                )

        # =====================================================
        # JSON 쪽에서도 DB에 없는 성적이 있는지 검사
        # =====================================================

        json_not_found = []

        for (
            json_team,
            ranking_text
        ) in json_stats:

            found = False

            for stats in db_stats:

                player = stats.player

                if not self.same_team(
                    json_team,
                    player.team.team_name
                ):

                    continue

                if not self.ranking_contains_player(
                    ranking_text,
                    player.name
                ):

                    continue

                found = True
                break

            if not found:

                json_not_found.append(
                    (
                        json_team,
                        ranking_text
                    )
                )

        # =====================================================
        # 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '2026 PlayerStats 구성 검사'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write('')

        self.stdout.write(
            f'JSON 선수성적       : '
            f'{len(json_stats)}건'
        )

        self.stdout.write(
            f'DB PlayerStats      : '
            f'{db_stats.count()}건'
        )

        self.stdout.write('')

        self.stdout.write(
            f'JSON ↔ DB 매칭      : '
            f'{len(matched)}건'
        )

        self.stdout.write(
            f'DB에만 있는 성적    : '
            f'{len(db_only)}건'
        )

        self.stdout.write(
            f'JSON만 있고 DB 없음 : '
            f'{len(json_not_found)}건'
        )

        # =====================================================
        # DB에만 있는 선수 출력
        # =====================================================

        if db_only:

            self.stdout.write('')

            self.stdout.write(
                '========== DB에만 있는 2026 성적 =========='
            )

            for stats in db_only:

                player = stats.player

                self.stdout.write(
                    f'ID {player.id} / '
                    f'{player.team.team_name} / '
                    f'{player.name} / '
                    f'{player.number}번 / '
                    f'{player.position} / '
                    f'출전시간 {stats.minutes}분'
                )

        # =====================================================
        # JSON에만 있는 성적 출력
        # =====================================================

        if json_not_found:

            self.stdout.write('')

            self.stdout.write(
                '========== JSON에만 있는 성적 =========='
            )

            for (
                team_name,
                ranking_text
            ) in json_not_found:

                self.stdout.write(
                    f'{team_name} / '
                    f'{ranking_text}'
                )

        # =====================================================
        # BEST11 관점 검사
        # =====================================================

        db_only_600 = []

        for stats in db_only:

            if stats.minutes >= 600:

                db_only_600.append(
                    stats
                )

        self.stdout.write('')

        self.stdout.write(
            '========== BEST11 영향 검사 =========='
        )

        self.stdout.write(
            f'DB 전용 성적 중 '
            f'600분 이상 : '
            f'{len(db_only_600)}명'
        )

        if db_only_600:

            self.stdout.write('')

            self.stdout.write(
                '※ 현재 BEST11 후보에 들어갈 수 있는 '
                'DB 전용 선수'
            )

            for stats in db_only_600:

                player = stats.player

                self.stdout.write(
                    f'{player.team.team_name} / '
                    f'{player.name} / '
                    f'{player.position} / '
                    f'{stats.minutes}분'
                )

        # =====================================================
        # 최종 판정
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '최종 판정'
        )

        self.stdout.write(
            '=========================================='
        )

        if len(json_not_found) == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    'JSON 성적은 모두 DB에 저장되어 있습니다. ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    'DB에 없는 JSON 성적이 있습니다. ❌'
                )
            )

        if db_only:

            self.stdout.write(
                self.style.WARNING(
                    f'DB 전용 2026 성적 '
                    f'{len(db_only)}건이 존재합니다.'
                )
            )

            self.stdout.write(
                'BEST11 계산 전에 포함 여부를 '
                '결정해야 합니다.'
            )

        else:

            self.stdout.write(
                self.style.SUCCESS(
                    'DB 전용 2026 성적 없음 ✅'
                )
            )

        self.stdout.write('')

        self.stdout.write(
            '※ 검사 전용 프로그램입니다.'
        )

        self.stdout.write(
            '※ DB를 수정하지 않았습니다.'
        )
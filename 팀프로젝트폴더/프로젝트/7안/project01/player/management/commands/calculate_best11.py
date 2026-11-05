import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import PlayerStats


class Command(BaseCommand):

    help = '2026 K리그 BEST11 후보의 포지션별 점수를 계산합니다.'

    MIN_MINUTES = 600

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
    # 현재 JSON 성적 선수인지 확인
    # =========================================================
    def is_current_stats_player(
        self,
        player,
        json_stats
    ):

        player_name = self.normalize(
            player.name
        )

        db_team = player.team.team_name

        for json_team, ranking_text in json_stats:

            if not self.same_team(
                json_team,
                db_team
            ):
                continue

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
    # 숫자 안전 변환
    # =========================================================
    def number(self, value):

        if value is None:
            return 0.0

        try:
            return float(value)

        except (TypeError, ValueError):
            return 0.0

    # =========================================================
    # 90분당 기록
    #
    # 예:
    # 1800분 출전 + 10골
    #
    # 10 / 1800 * 90
    # = 0.5골 / 90분
    # =========================================================
    def per90(self, value, minutes):

        value = self.number(value)
        minutes = self.number(minutes)

        if minutes <= 0:
            return 0.0

        return (
            value
            / minutes
            * 90
        )

    # =========================================================
    # 성공률
    #
    # 성공 / 시도 × 100
    # =========================================================
    def success_rate(
        self,
        success,
        attempt
    ):

        success = self.number(success)
        attempt = self.number(attempt)

        if attempt <= 0:
            return 0.0

        return (
            success
            / attempt
            * 100
        )

    # =========================================================
    # 최고값 기준 0~100 정규화
    #
    # 해당 지표 최고 선수 = 100점
    # =========================================================
    def normalize_score(
        self,
        value,
        max_value
    ):

        value = self.number(value)
        max_value = self.number(max_value)

        if max_value <= 0:
            return 0.0

        return (
            value
            / max_value
            * 100
        )

    # =========================================================
    # FW 지표
    # =========================================================
    def fw_metrics(self, stats):

        return {
            'goals': self.per90(
                stats.goals,
                stats.minutes
            ),

            'assists': self.per90(
                stats.assists,
                stats.minutes
            ),

            'shots_on_target': self.per90(
                stats.shots_on_target,
                stats.minutes
            ),

            'shots': self.per90(
                stats.shots,
                stats.minutes
            ),

            'key_passes': self.per90(
                stats.key_passes,
                stats.minutes
            ),

            'dribble': self.per90(
                stats.dribble_success,
                stats.minutes
            ),
        }

    # =========================================================
    # MF 지표
    # =========================================================
    def mf_metrics(self, stats):

        return {
            'assists': self.per90(
                stats.assists,
                stats.minutes
            ),

            'key_passes': self.per90(
                stats.key_passes,
                stats.minutes
            ),

            'pass_rate': self.success_rate(
                stats.pass_success,
                stats.pass_attempt
            ),

            'goals': self.per90(
                stats.goals,
                stats.minutes
            ),

            'recoveries': self.per90(
                stats.recoveries,
                stats.minutes
            ),

            'interceptions': self.per90(
                stats.interceptions,
                stats.minutes
            ),

            'dribble': self.per90(
                stats.dribble_success,
                stats.minutes
            ),
        }

    # =========================================================
    # DF 지표
    # =========================================================
    def df_metrics(self, stats):

        return {
            'clearances': self.per90(
                stats.clearances,
                stats.minutes
            ),

            'interceptions': self.per90(
                stats.interceptions,
                stats.minutes
            ),

            'recoveries': self.per90(
                stats.recoveries,
                stats.minutes
            ),

            'tackle': self.per90(
                stats.tackle_success,
                stats.minutes
            ),

            'aerial_duel': self.per90(
                stats.aerial_duel_success,
                stats.minutes
            ),

            'ground_duel': self.per90(
                stats.ground_duel_success,
                stats.minutes
            ),

            'defensive_blocks': self.per90(
                stats.defensive_blocks,
                stats.minutes
            ),

            'blocks': self.per90(
                stats.blocks,
                stats.minutes
            ),
        }

    # =========================================================
    # GK 지표
    #
    # 현재 DB에는
    # 선방 / 실점 / 클린시트가 없으므로
    #
    # 평균평점
    # MOM
    # BEST11 선정
    # 출전시간
    #
    # 네 가지를 임시 기준으로 사용
    # =========================================================
    def gk_metrics(self, stats):

        return {
            'rating': self.number(
                stats.average_rating
            ),

            'mom': self.per90(
                stats.mom,
                stats.minutes
            ),

            'best11': self.per90(
                stats.best11_count,
                stats.minutes
            ),

            'minutes': self.number(
                stats.minutes
            ),
        }

    # =========================================================
    # 포지션별 점수 계산
    # =========================================================
    def calculate_position_scores(
        self,
        stats_list,
        metric_function,
        weights
    ):

        rows = []

        # -----------------------------------------------------
        # 선수별 실제 지표 계산
        # -----------------------------------------------------

        for stats in stats_list:

            metrics = metric_function(
                stats
            )

            rows.append({
                'stats': stats,
                'metrics': metrics,
            })

        # -----------------------------------------------------
        # 각 지표 최고값 찾기
        # -----------------------------------------------------

        max_values = {}

        for metric_name in weights.keys():

            values = [
                row['metrics'][metric_name]
                for row in rows
            ]

            if values:
                max_values[metric_name] = max(
                    values
                )
            else:
                max_values[metric_name] = 0

        # -----------------------------------------------------
        # 정규화 + 가중치
        # -----------------------------------------------------

        for row in rows:

            total_score = 0.0
            normalized = {}

            for (
                metric_name,
                weight
            ) in weights.items():

                raw_value = (
                    row['metrics'][
                        metric_name
                    ]
                )

                max_value = (
                    max_values[
                        metric_name
                    ]
                )

                score = self.normalize_score(
                    raw_value,
                    max_value
                )

                normalized[
                    metric_name
                ] = score

                total_score += (
                    score
                    * weight
                    / 100
                )

            row['normalized'] = normalized
            row['score'] = total_score

        # -----------------------------------------------------
        # 높은 점수 순
        # -----------------------------------------------------

        rows.sort(
            key=lambda x: x['score'],
            reverse=True
        )

        return rows

    # =========================================================
    # TOP 선수 출력
    # =========================================================
    def print_ranking(
        self,
        title,
        rows,
        top_n=10
    ):

        self.stdout.write('')

        self.stdout.write(
            f'========== {title} =========='
        )

        for rank, row in enumerate(
            rows[:top_n],
            start=1
        ):

            stats = row['stats']
            player = stats.player

            self.stdout.write(
                f'{rank:>2}위 / '
                f'{player.name:<15} / '
                f'{player.team.team_name:<12} / '
                f'{stats.minutes:>4}분 / '
                f'{row["score"]:.2f}점'
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
        # 현재 JSON 성적 420건 읽기
        # =====================================================

        json_dir = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
        )

        json_stats = []

        for json_file in sorted(
            json_dir.glob(
                '*_선수성적.json'
            )
        ):

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
                season=2026,
                minutes__gte=self.MIN_MINUTES
            )
            .select_related(
                'player',
                'player__team'
            )
        )

        # =====================================================
        # 현재 JSON + 600분 이상 선수만
        # =====================================================

        candidates = []

        for stats in stats_2026:

            if self.is_current_stats_player(
                stats.player,
                json_stats
            ):

                candidates.append(
                    stats
                )

        # =====================================================
        # 포지션별 분리
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
                gk_list.append(stats)

            elif position == 'DF':
                df_list.append(stats)

            elif position == 'MF':
                mf_list.append(stats)

            elif position == 'FW':
                fw_list.append(stats)

            else:
                etc_list.append(stats)

        # =====================================================
        # 가중치
        #
        # 합계는 각각 100
        # =====================================================

        fw_weights = {
            'goals': 35,
            'assists': 20,
            'shots_on_target': 15,
            'shots': 10,
            'key_passes': 10,
            'dribble': 10,
        }

        mf_weights = {
            'assists': 20,
            'key_passes': 20,
            'pass_rate': 20,
            'goals': 15,
            'recoveries': 10,
            'interceptions': 10,
            'dribble': 5,
        }

        df_weights = {
            'clearances': 20,
            'interceptions': 20,
            'recoveries': 15,
            'tackle': 15,
            'aerial_duel': 10,
            'ground_duel': 10,
            'defensive_blocks': 5,
            'blocks': 5,
        }

        # =====================================================
        # GK 임시 가중치
        #
        # 선방/실점/클린시트 데이터가 없기 때문에
        # 추후 변경 가능
        # =====================================================

        gk_weights = {
            'rating': 50,
            'mom': 15,
            'best11': 25,
            'minutes': 10,
        }

        # =====================================================
        # 점수 계산
        # =====================================================

        fw_rows = self.calculate_position_scores(
            fw_list,
            self.fw_metrics,
            fw_weights
        )

        mf_rows = self.calculate_position_scores(
            mf_list,
            self.mf_metrics,
            mf_weights
        )

        df_rows = self.calculate_position_scores(
            df_list,
            self.df_metrics,
            df_weights
        )

        gk_rows = self.calculate_position_scores(
            gk_list,
            self.gk_metrics,
            gk_weights
        )

        # =====================================================
        # 기본 정보 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '2026 K리그 BEST11 점수 계산'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write('')

        self.stdout.write(
            f'최소 출전시간 : '
            f'{self.MIN_MINUTES}분'
        )

        self.stdout.write(
            f'전체 후보     : '
            f'{len(candidates)}명'
        )

        self.stdout.write('')

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
        # TOP10 출력
        # =====================================================

        self.print_ranking(
            'FW TOP 10',
            fw_rows
        )

        self.print_ranking(
            'MF TOP 10',
            mf_rows
        )

        self.print_ranking(
            'DF TOP 10',
            df_rows
        )

        self.print_ranking(
            'GK TOP 10',
            gk_rows
        )

        # =====================================================
        # 4-3-3 기준 BEST11
        # =====================================================

        best_fw = fw_rows[:3]
        best_mf = mf_rows[:3]
        best_df = df_rows[:4]
        best_gk = gk_rows[:1]

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '4-3-3 BEST11'
        )

        self.stdout.write(
            '=========================================='
        )

        # FW
        self.stdout.write('')

        self.stdout.write(
            'FW'
        )

        for row in best_fw:

            player = row['stats'].player

            self.stdout.write(
                f'- {player.name} / '
                f'{player.team.team_name} / '
                f'{row["score"]:.2f}점'
            )

        # MF
        self.stdout.write('')

        self.stdout.write(
            'MF'
        )

        for row in best_mf:

            player = row['stats'].player

            self.stdout.write(
                f'- {player.name} / '
                f'{player.team.team_name} / '
                f'{row["score"]:.2f}점'
            )

        # DF
        self.stdout.write('')

        self.stdout.write(
            'DF'
        )

        for row in best_df:

            player = row['stats'].player

            self.stdout.write(
                f'- {player.name} / '
                f'{player.team.team_name} / '
                f'{row["score"]:.2f}점'
            )

        # GK
        self.stdout.write('')

        self.stdout.write(
            'GK'
        )

        for row in best_gk:

            player = row['stats'].player

            self.stdout.write(
                f'- {player.name} / '
                f'{player.team.team_name} / '
                f'{row["score"]:.2f}점'
            )

        # =====================================================
        # 종료
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            self.style.SUCCESS(
                'BEST11 1차 계산 완료 ✅'
            )
        )

        self.stdout.write(
            '※ DB를 수정하지 않았습니다.'
        )

        self.stdout.write(
            '※ GK 점수 기준은 임시 기준입니다.'
        )
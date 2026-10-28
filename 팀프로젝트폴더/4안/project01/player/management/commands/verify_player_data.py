from django.core.management.base import BaseCommand
from django.db.models import Count

from team.models import Team
from player.models import Player, PlayerStats


class Command(BaseCommand):

    help = '2026 K리그 선수 데이터 통합 결과를 검증합니다.'

    # =========================================================
    # 출력용 구분선
    # =========================================================
    def line(self):

        self.stdout.write(
            '=========================================='
        )

    # =========================================================
    # 실행
    # =========================================================
    def handle(self, *args, **options):

        self.stdout.write('')

        self.line()

        self.stdout.write(
            '2026 K리그 선수 데이터 최종 검증'
        )

        self.line()

        # =====================================================
        # 1. 전체 Player 수
        # =====================================================

        player_count = (
            Player.objects.count()
        )

        self.stdout.write('')

        self.stdout.write(
            '========== 1. 전체 선수 =========='
        )

        self.stdout.write(
            f'전체 Player : {player_count}명'
        )

        if player_count == 496:

            self.stdout.write(
                self.style.SUCCESS(
                    '전체 선수 수 정상 ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    '전체 선수 수 확인 필요 ❌'
                )
            )

        # =====================================================
        # 2. 구단별 선수 수
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 2. 구단별 선수 수 =========='
        )

        teams = (
            Team.objects
            .annotate(
                player_count=Count('player')
            )
            .order_by('team_name')
        )

        team_total = 0

        for team in teams:

            count = team.player_count

            team_total += count

            self.stdout.write(
                f'{team.team_name:<15} : '
                f'{count}명'
            )

        self.stdout.write(
            f'구단별 합계           : '
            f'{team_total}명'
        )

        # =====================================================
        # 3. 2026 PlayerStats
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 3. 2026 PlayerStats =========='
        )

        stats_2026 = (
            PlayerStats.objects
            .filter(season=2026)
        )

        stats_count = (
            stats_2026.count()
        )

        self.stdout.write(
            f'2026 PlayerStats : '
            f'{stats_count}건'
        )

        # -----------------------------------------------------
        # PlayerStats가 존재하는 서로 다른 선수 수
        # -----------------------------------------------------

        stats_player_count = (
            stats_2026
            .values('player_id')
            .distinct()
            .count()
        )

        self.stdout.write(
            f'성적 보유 선수    : '
            f'{stats_player_count}명'
        )

        # =====================================================
        # 4. 동일 선수 + 동일 시즌 중복 PlayerStats 검사
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 4. 성적 중복 검사 =========='
        )

        duplicate_stats = (
            PlayerStats.objects
            .values(
                'player_id',
                'season'
            )
            .annotate(
                count=Count('id')
            )
            .filter(
                count__gt=1
            )
        )

        duplicate_stats_count = (
            duplicate_stats.count()
        )

        if duplicate_stats_count == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    'PlayerStats 중복 없음 ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    f'PlayerStats 중복 발견 : '
                    f'{duplicate_stats_count}건 ❌'
                )
            )

            for item in duplicate_stats:

                player = (
                    Player.objects
                    .filter(
                        id=item['player_id']
                    )
                    .select_related('team')
                    .first()
                )

                if player:

                    self.stdout.write(
                        f"  {player.team.team_name} / "
                        f"{player.name} / "
                        f"{item['season']} / "
                        f"{item['count']}개"
                    )

        # =====================================================
        # 5. 선수 중복 검사
        #
        # 같은 팀 + 같은 이름이 2명 이상인지 검사
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 5. 선수 중복 검사 =========='
        )

        duplicate_players = (
            Player.objects
            .values(
                'team_id',
                'name'
            )
            .annotate(
                count=Count('id')
            )
            .filter(
                count__gt=1
            )
        )

        duplicate_player_count = (
            duplicate_players.count()
        )

        if duplicate_player_count == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    '같은 팀 + 같은 이름 중복 없음 ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    f'같은 팀 + 같은 이름 중복 : '
                    f'{duplicate_player_count}건 ❌'
                )
            )

            for item in duplicate_players:

                team = (
                    Team.objects
                    .filter(
                        id=item['team_id']
                    )
                    .first()
                )

                team_name = (
                    team.team_name
                    if team
                    else '알 수 없음'
                )

                self.stdout.write(
                    f"  {team_name} / "
                    f"{item['name']} / "
                    f"{item['count']}명"
                )

        # =====================================================
        # 6. 사진 연결 상태
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 6. 사진 연결 =========='
        )

        photo_count = (
            Player.objects
            .exclude(photo='')
            .exclude(photo__isnull=True)
            .count()
        )

        no_photo_count = (
            player_count
            -
            photo_count
        )

        self.stdout.write(
            f'사진 연결 선수 : '
            f'{photo_count}명'
        )

        self.stdout.write(
            f'사진 없는 선수 : '
            f'{no_photo_count}명'
        )

        # =====================================================
        # 7. 프로필 확인
        #
        # height / weight / birth_date
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 7. 선수 프로필 =========='
        )

        height_count = (
            Player.objects
            .filter(
                height__gt=0
            )
            .count()
        )

        weight_count = (
            Player.objects
            .filter(
                weight__gt=0
            )
            .count()
        )

        birth_count = (
            Player.objects
            .exclude(
                birth_date__isnull=True
            )
            .count()
        )

        self.stdout.write(
            f'키 정보 있음       : '
            f'{height_count}명'
        )

        self.stdout.write(
            f'몸무게 정보 있음   : '
            f'{weight_count}명'
        )

        self.stdout.write(
            f'생년월일 정보 있음 : '
            f'{birth_count}명'
        )

        # =====================================================
        # 8. 팀 이동 선수 확인
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 8. 주요 팀 이동 확인 =========='
        )

        move_checks = [

            ('강원FC', '김이석'),

            ('김천상무', '안찬기'),
            ('김천상무', '강영훈'),
            ('김천상무', '김진호'),
            ('김천상무', '송준석'),
            ('김천상무', '이상혁'),
            ('김천상무', '김준하'),
            ('김천상무', '최규현'),
            ('김천상무', '허율'),

            ('대전하나시티즌', '이정택'),

            ('울산HD', '문현호'),

            ('전북현대', '이수빈'),
            ('전북현대', '전병관'),

            ('제주SK FC', '김태환'),
        ]

        move_success = 0

        for team_name, player_name in move_checks:

            exists = (
                Player.objects
                .filter(
                    team__team_name=team_name,
                    name=player_name
                )
                .exists()
            )

            if exists:

                move_success += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f'OK  {team_name} / '
                        f'{player_name}'
                    )
                )

            else:

                self.stdout.write(
                    self.style.ERROR(
                        f'FAIL {team_name} / '
                        f'{player_name}'
                    )
                )

        self.stdout.write(
            f'팀 이동 확인 : '
            f'{move_success}'
            f'/'
            f'{len(move_checks)}명'
        )

        # =====================================================
        # 9. 신규 특수 선수 확인
        #
        # 전북 이건희
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 9. 신규 선수 확인 =========='
        )

        new_lee = (
            Player.objects
            .filter(
                team__team_name='전북현대',
                name='이건희',
                number=47,
                position='MF'
            )
            .first()
        )

        if new_lee:

            self.stdout.write(
                self.style.SUCCESS(
                    '전북현대 / 이건희 / '
                    '47번 / MF 생성 확인 ✅'
                )
            )

            self.stdout.write(
                f'Player ID : '
                f'{new_lee.id}'
            )

            self.stdout.write(
                f'생년월일  : '
                f'{new_lee.birth_date}'
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    '전북현대 이건희 확인 실패 ❌'
                )
            )

        # =====================================================
        # 10. 기존 상세 통계 보존 확인
        #
        # 2026 데이터에서 상세 통계 값이
        # 실제로 남아 있는지 검사
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 10. 기존 상세 통계 보존 =========='
        )

        detailed_stats_count = (
            stats_2026
            .filter(
                minutes__gt=0
            )
            .count()
        )

        self.stdout.write(
            f'출전시간 보유 성적 : '
            f'{detailed_stats_count}건'
        )

        # -----------------------------------------------------
        # 상세 통계 필드 중 하나라도 값이 있는 선수
        #
        # 기존 XLS 데이터가 남아 있는지 보기 위한 검사
        # -----------------------------------------------------

        detailed_field_count = (
            stats_2026
            .filter(
                pass_attempt__gt=0
            )
            .count()
        )

        self.stdout.write(
            f'패스 시도 데이터 있음 : '
            f'{detailed_field_count}건'
        )

        if detailed_field_count > 0:

            self.stdout.write(
                self.style.SUCCESS(
                    '기존 상세 통계 데이터 존재 확인 ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.WARNING(
                    '상세 통계 필드 확인 필요 ⚠'
                )
            )

        # =====================================================
        # 11. BEST11용 핵심 데이터 확인
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 11. BEST11 데이터 =========='
        )

        enough_minutes = (
            stats_2026
            .filter(
                minutes__gte=600
            )
            .count()
        )

        self.stdout.write(
            f'600분 이상 선수 : '
            f'{enough_minutes}명'
        )

        goals_count = (
            stats_2026
            .filter(
                goals__gt=0
            )
            .count()
        )

        assists_count = (
            stats_2026
            .filter(
                assists__gt=0
            )
            .count()
        )

        self.stdout.write(
            f'득점 기록 선수   : '
            f'{goals_count}명'
        )

        self.stdout.write(
            f'도움 기록 선수   : '
            f'{assists_count}명'
        )

        # =====================================================
        # 12. 최종 판정
        # =====================================================

        self.stdout.write('')

        self.line()

        self.stdout.write(
            '최종 검증 결과'
        )

        self.line()

        problems = []

        if player_count != 496:

            problems.append(
                'Player 전체 수'
            )

        if duplicate_player_count > 0:

            problems.append(
                'Player 중복'
            )

        if duplicate_stats_count > 0:

            problems.append(
                'PlayerStats 중복'
            )

        if move_success != len(move_checks):

            problems.append(
                '팀 이동'
            )

        if new_lee is None:

            problems.append(
                '전북 이건희'
            )

        if len(problems) == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    '기본 DB 검증 통과 ✅'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    '확인이 필요한 항목이 있습니다.'
                )
            )

            for problem in problems:

                self.stdout.write(
                    f'- {problem}'
                )

        self.stdout.write('')

        self.stdout.write(
            '※ 검증 전용 명령어입니다.'
        )

        self.stdout.write(
            '※ DB를 수정하지 않았습니다.'
        )
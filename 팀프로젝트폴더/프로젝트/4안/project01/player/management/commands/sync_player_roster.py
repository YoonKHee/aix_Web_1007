import json
import re
import shutil
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from team.models import Team
from player.models import Player, PlayerStats


class Command(BaseCommand):

    help = '2026 K리그 선수명단, 프로필, 사진, 성적을 최종 통합합니다.'

    # =========================================================
    # 명령어 옵션
    # =========================================================
    def add_arguments(self, parser):

        parser.add_argument(
            '--check',
            action='store_true',
            help='DB를 수정하지 않고 최종 결과만 검사합니다.'
        )

    # =========================================================
    # 문자열 정리
    #
    # "김 태 환" -> "김태환"
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
    # 정수 변환
    # =========================================================
    def to_int(self, value):

        if value is None:
            return 0

        value = (
            str(value)
            .strip()
            .replace(',', '')
        )

        if value == '':
            return 0

        try:
            return int(float(value))

        except (ValueError, TypeError):
            return 0

    # =========================================================
    # 실수 변환
    # =========================================================
    def to_float(self, value):

        if value is None:
            return 0.0

        value = (
            str(value)
            .strip()
            .replace(',', '')
        )

        if value == '':
            return 0.0

        try:
            return float(value)

        except (ValueError, TypeError):
            return 0.0

    # =========================================================
    # Cm / Kg 같은 문자열에서 숫자만 가져오기
    #
    # 177Cm -> 177
    # 67Kg  -> 67
    # =========================================================
    def only_number(self, value):

        if value is None:
            return 0

        result = re.search(
            r'\d+',
            str(value)
        )

        if result:
            return int(result.group())

        return 0

    # =========================================================
    # 날짜 변환
    # =========================================================
    def to_date(self, value):

        if not value:
            return None

        value = str(value).strip()

        formats = [
            '%Y/%m/%d',
            '%Y-%m-%d',
            '%Y.%m.%d',
        ]

        for fmt in formats:

            try:
                return datetime.strptime(
                    value,
                    fmt
                ).date()

            except ValueError:
                pass

        return None

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
    # JSON 팀 이름 → DB Team
    # =========================================================
    def find_team(self, json_team):

        teams = Team.objects.all()

        for team in teams:

            if self.same_team(
                json_team,
                team.team_name
            ):

                return team

        return None

    # =========================================================
    # 같은 이름 DB 선수 전부 찾기
    # =========================================================
    def find_same_name_players(
        self,
        player_name
    ):

        target_name = self.normalize(
            player_name
        )

        result = []

        players = (
            Player.objects
            .select_related('team')
            .all()
        )

        for player in players:

            if (
                self.normalize(player.name)
                ==
                target_name
            ):

                result.append(
                    player
                )

        return result

    # =========================================================
    # JSON 선수와 기존 DB 선수 연결
    # =========================================================
    def match_player(
        self,
        team_name,
        player_name,
        number,
        position
    ):

        candidates = (
            self.find_same_name_players(
                player_name
            )
        )

        # -----------------------------------------------------
        # 이름 자체가 DB에 없음
        #
        # → 신규
        # -----------------------------------------------------

        if len(candidates) == 0:

            return None, 'new'

        # -----------------------------------------------------
        # 같은 이름 + 같은 팀
        #
        # → 기존 동일 선수
        # -----------------------------------------------------

        same_team_candidates = []

        for player in candidates:

            if self.same_team(
                team_name,
                player.team.team_name
            ):

                same_team_candidates.append(
                    player
                )

        if len(same_team_candidates) == 1:

            return (
                same_team_candidates[0],
                'same'
            )

        # -----------------------------------------------------
        # 이름이 DB 전체에서 딱 1명인데
        # 팀이 다름
        #
        # → 팀 이동
        # -----------------------------------------------------

        if len(candidates) == 1:

            return (
                candidates[0],
                'move'
            )

        # =====================================================
        # 김태환 특별 판별
        #
        # JSON
        # 제주 / 71 / DF
        #
        # DB
        # 김천상무 / 71 / DF
        #
        # → 김천 → 제주 이동
        # =====================================================

        if (
            self.normalize(player_name)
            == '김태환'
            and
            self.normalize(team_name)
            == '제주'
            and
            self.to_int(number) == 71
            and
            self.normalize(position) == 'DF'
        ):

            for player in candidates:

                if (
                    self.normalize(
                        player.team.team_name
                    )
                    == '김천상무'
                    and
                    player.number == 71
                    and
                    self.normalize(
                        player.position
                    )
                    == 'DF'
                ):

                    return (
                        player,
                        'move'
                    )

        # =====================================================
        # 전북 이건희 특별 판별
        #
        # JSON
        # 전북 / 47 / MF
        #
        # 기존 DB 이건희
        # 10 / FW
        #
        # → 다른 선수이므로 신규
        # =====================================================

        if (
            self.normalize(player_name)
            == '이건희'
            and
            self.normalize(team_name)
            == '전북'
            and
            self.to_int(number) == 47
            and
            self.normalize(position) == 'MF'
        ):

            return None, 'new'

        # -----------------------------------------------------
        # 자동 판단 불가
        # -----------------------------------------------------

        return None, 'ambiguous'

    # =========================================================
    # 프로필 값 적용
    # =========================================================
    def apply_profile(
        self,
        player,
        row
    ):

        player.number = self.to_int(
            row.get('등번')
        )

        position = str(
            row.get('포지션')
            or row.get('포자션')
            or ''
        ).strip()

        player.height = self.only_number(
            row.get('키')
        )

        player.weight = self.only_number(
            row.get('몸무게')
        )

        player.birth_date = self.to_date(
            row.get('생년월일')
        )

    # =========================================================
    # 사진 찾기
    # =========================================================
    def find_photo(
        self,
        source_dir,
        team_name,
        player_name
    ):

        team_dir = (
            source_dir
            / team_name
        )

        if not team_dir.exists():
            return None

        extensions = [
            '.png',
            '.jpg',
            '.jpeg',
            '.webp',
        ]

        for ext in extensions:

            photo_path = (
                team_dir
                / f'{player_name}{ext}'
            )

            if photo_path.exists():

                return photo_path

        return None

    # =========================================================
    # 실제 사진 복사
    # =========================================================
    def save_photo(
        self,
        player,
        source_dir,
        team_name,
        player_name
    ):

        photo_path = self.find_photo(
            source_dir,
            team_name,
            player_name
        )

        if photo_path is None:

            return False

        media_root = Path(
            settings.MEDIA_ROOT
        )

        destination_dir = (
            media_root
            / 'players'
            / team_name
        )

        destination_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        destination_file = (
            destination_dir
            / photo_path.name
        )

        shutil.copy2(
            photo_path,
            destination_file
        )

        player.photo.name = (
            f'players/'
            f'{team_name}/'
            f'{photo_path.name}'
        )

        return True

    # =========================================================
    # 선수정보 JSON에서
    # 성적 순위 문자열의 선수 찾기
    # =========================================================
    def find_info_player_from_ranking(
        self,
        ranking_text,
        team_players
    ):

        ranking_text = self.normalize(
            ranking_text
        )

        candidates = []

        for info_player in team_players:

            player_name = self.normalize(
                info_player['name']
            )

            if (
                player_name
                and
                player_name in ranking_text
            ):

                candidates.append(
                    info_player
                )

        if len(candidates) == 0:

            return None

        candidates.sort(
            key=lambda p: len(
                self.normalize(
                    p['name']
                )
            ),
            reverse=True
        )

        return candidates[0]

    # =========================================================
    # DB에서
    # 같은 팀 + 성적 선수 찾기
    # =========================================================
    def find_db_stats_player(
        self,
        team_name,
        ranking_text
    ):

        ranking_text = self.normalize(
            ranking_text
        )

        candidates = []

        players = (
            Player.objects
            .select_related('team')
            .all()
        )

        for player in players:

            if not self.same_team(
                team_name,
                player.team.team_name
            ):

                continue

            player_name = self.normalize(
                player.name
            )

            if (
                player_name
                and
                player_name in ranking_text
            ):

                candidates.append(
                    player
                )

        if len(candidates) == 0:

            return None

        candidates.sort(
            key=lambda p: len(
                self.normalize(
                    p.name
                )
            ),
            reverse=True
        )

        return candidates[0]

    # =========================================================
    # 현재 DB에서 이름으로 선수 찾기
    #
    # 선수정보 JSON에서 이미 이름을 확인한 뒤
    # 실제 Player 객체를 찾는 용도
    # =========================================================
    def find_current_player(
        self,
        team_name,
        player_name
    ):

        candidates = (
            self.find_same_name_players(
                player_name
            )
        )

        same_team_candidates = []

        for player in candidates:

            if self.same_team(
                team_name,
                player.team.team_name
            ):

                same_team_candidates.append(
                    player
                )

        if len(same_team_candidates) == 1:

            return same_team_candidates[0]

        return None

    # =========================================================
    # PlayerStats에 JSON 성적 적용
    #
    # 중요:
    # 여기 적힌 컬럼만 최신 JSON 값으로 수정
    #
    # 기존 XLS의 상세 패스/태클/드리블 등의
    # 다른 컬럼은 건드리지 않음
    # =========================================================
    def apply_stats(
        self,
        stats,
        row
    ):

        stats.games = self.to_int(
            row.get('경기')
        )

        stats.goals = self.to_int(
            row.get('득점')
        )

        stats.assists = self.to_int(
            row.get('도움')
        )

        stats.attack_points = self.to_int(
            row.get('공격포인트')
        )

        stats.pk_goals = self.to_int(
            row.get('PK골')
        )

        stats.mom = self.to_int(
            row.get('MOM')
        )

        stats.average_rating = (
            self.to_float(
                row.get('평균평점')
            )
        )

        stats.best11_count = (
            self.to_int(
                row.get('BEST11')
            )
        )

        stats.shots = self.to_int(
            row.get('슈팅')
        )

        stats.shots_on_target = (
            self.to_int(
                row.get('유효슈팅')
            )
        )

        stats.minutes = self.to_int(
            row.get('출전시간(분)')
        )

        stats.fouls = self.to_int(
            row.get('파울')
        )

        stats.fouls_won = self.to_int(
            row.get('피파울')
        )

        stats.yellow_cards = (
            self.to_int(
                row.get('경고')
            )
        )

        stats.red_cards = self.to_int(
            row.get('퇴장')
        )

        stats.corner_kicks = (
            self.to_int(
                row.get('코너킥')
            )
        )

        stats.pk_attempts = self.to_int(
            row.get('PK')
        )

        stats.offsides = self.to_int(
            row.get('오프사이드')
        )

    # =========================================================
    # 실행
    # =========================================================
    def handle(
        self,
        *args,
        **options
    ):

        check_only = options['check']

        source_dir = (
            Path(settings.BASE_DIR)
            / 'data'
        )

        json_dir = (
            source_dir
            / 'k_1부 리그'
            / 'json_data'
        )

        if not json_dir.exists():

            self.stdout.write(
                self.style.ERROR(
                    'JSON 데이터 폴더를 찾을 수 없습니다.'
                )
            )

            return

        info_files = sorted(
            json_dir.glob(
                '*_선수정보.json'
            )
        )

        stats_files = sorted(
            json_dir.glob(
                '*_선수성적.json'
            )
        )

        # =====================================================
        # 먼저 선수정보 JSON 전체를 메모리에 저장
        # =====================================================

        team_player_dict = {}

        total_info = 0

        for json_file in info_files:

            team_name = (
                json_file.name
                .split('_')[0]
            )

            rows = self.read_json(
                json_file
            )

            team_player_dict[
                team_name
            ] = []

            for row in rows:

                player_name = str(
                    row.get(
                        '성명',
                        ''
                    )
                ).strip()

                if not player_name:
                    continue

                team_player_dict[
                    team_name
                ].append(
                    {
                        'name': player_name,
                        'row': row,
                    }
                )

                total_info += 1

        # =====================================================
        # 선수명단 검사
        # =====================================================

        same_count = 0
        move_count = 0
        new_count = 0
        ambiguous_count = 0

        photo_found = 0
        photo_missing = 0

        move_list = []
        new_list = []
        ambiguous_list = []

        # -----------------------------------------------------
        # 검사 단계에서는 DB 수정하지 않음
        # -----------------------------------------------------

        for team_name, players in (
            team_player_dict.items()
        ):

            for info_player in players:

                player_name = (
                    info_player['name']
                )

                row = info_player['row']

                player, status = (
                    self.match_player(
                        team_name,
                        player_name,
                        row.get('등번'),
                        row.get('포지션')
                    )
                )

                if status == 'same':

                    same_count += 1

                elif status == 'move':

                    move_count += 1

                    move_list.append(
                        (
                            player.team.team_name,
                            player.name,
                            team_name
                        )
                    )

                elif status == 'new':

                    new_count += 1

                    new_list.append(
                        (
                            team_name,
                            player_name
                        )
                    )

                else:

                    ambiguous_count += 1

                    ambiguous_list.append(
                        (
                            team_name,
                            player_name
                        )
                    )

                photo_path = self.find_photo(
                    source_dir,
                    team_name,
                    player_name
                )

                if photo_path:

                    photo_found += 1

                else:

                    photo_missing += 1

        # =====================================================
        # 성적 420건 사전 검사
        #
        # 여기서는 DB 수정 전에 검사하므로
        # JSON 선수정보 우선
        # +
        # 기존 DB 보완
        # =====================================================

        stats_total = 0
        stats_success = 0
        stats_fail = 0

        stats_json_match = 0
        stats_db_match = 0

        stats_fail_list = []

        for json_file in stats_files:

            team_name = (
                json_file.name
                .split('_')[0]
            )

            rows = self.read_json(
                json_file
            )

            team_players = (
                team_player_dict.get(
                    team_name,
                    []
                )
            )

            for row in rows:

                stats_total += 1

                ranking_text = str(
                    row.get(
                        '순위',
                        ''
                    )
                ).strip()

                # ---------------------------------------------
                # 1차
                # 선수정보 JSON에서 검색
                # ---------------------------------------------

                info_player = (
                    self.find_info_player_from_ranking(
                        ranking_text,
                        team_players
                    )
                )

                if info_player is not None:

                    stats_success += 1
                    stats_json_match += 1

                    continue

                # ---------------------------------------------
                # 2차
                # 기존 DB 보완
                # ---------------------------------------------

                db_player = (
                    self.find_db_stats_player(
                        team_name,
                        ranking_text
                    )
                )

                if db_player is not None:

                    stats_success += 1
                    stats_db_match += 1

                    continue

                # ---------------------------------------------
                # 둘 다 실패
                # ---------------------------------------------

                stats_fail += 1

                stats_fail_list.append(
                    (
                        team_name,
                        ranking_text
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
            '2026 K리그 최종 통합 검사'
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
                '실행 방식 : 실제 저장'
            )

        self.stdout.write('')

        self.stdout.write(
            f'선수정보 JSON        : '
            f'{total_info}명'
        )

        self.stdout.write('')

        self.stdout.write(
            f'기존 동일 선수       : '
            f'{same_count}명'
        )

        self.stdout.write(
            f'팀 이동              : '
            f'{move_count}명'
        )

        self.stdout.write(
            f'신규 선수            : '
            f'{new_count}명'
        )

        self.stdout.write(
            f'판단 불가            : '
            f'{ambiguous_count}명'
        )

        self.stdout.write('')

        self.stdout.write(
            f'사진 발견            : '
            f'{photo_found}장'
        )

        self.stdout.write(
            f'사진 없음            : '
            f'{photo_missing}명'
        )

        self.stdout.write('')

        self.stdout.write(
            '========== 성적 검사 =========='
        )

        self.stdout.write(
            f'선수성적 JSON        : '
            f'{stats_total}건'
        )

        self.stdout.write(
            f'성적 매칭 성공       : '
            f'{stats_success}건'
        )

        self.stdout.write(
            f'성적 매칭 실패       : '
            f'{stats_fail}건'
        )

        self.stdout.write(
            f'JSON 명단 매칭       : '
            f'{stats_json_match}건'
        )

        self.stdout.write(
            f'기존 DB 보완 매칭    : '
            f'{stats_db_match}건'
        )

        # =====================================================
        # 실패 목록
        # =====================================================

        if stats_fail_list:

            self.stdout.write('')

            self.stdout.write(
                '========== 성적 매칭 실패 =========='
            )

            for (
                team_name,
                ranking_text
            ) in stats_fail_list:

                self.stdout.write(
                    f'{team_name} / '
                    f'{ranking_text}'
                )

        # =====================================================
        # 검사 모드
        # =====================================================

        if check_only:

            self.stdout.write('')

            self.stdout.write(
                '=========================================='
            )

            if (
                total_info == 454
                and
                same_count == 372
                and
                move_count == 14
                and
                new_count == 68
                and
                ambiguous_count == 0
                and
                stats_total == 420
                and
                stats_success == 420
                and
                stats_fail == 0
            ):

                self.stdout.write(
                    self.style.SUCCESS(
                        '최종 판정 : 저장 준비 완료'
                    )
                )

            else:

                self.stdout.write(
                    self.style.ERROR(
                        '최종 판정 : 아직 실제 저장하면 안 됩니다.'
                    )
                )

            self.stdout.write('')

            self.stdout.write(
                '※ DB는 수정하지 않았습니다.'
            )

            return

        # =====================================================
        # 실제 저장 전 안전검사
        # =====================================================

        if ambiguous_count > 0:

            raise RuntimeError(
                '판단 불가 선수가 있습니다. '
                '실제 저장을 중단합니다.'
            )

        if stats_fail > 0:

            raise RuntimeError(
                '성적 매칭 실패가 있습니다. '
                '실제 저장을 중단합니다.'
            )

        # =====================================================
        # 실제 DB 저장
        #
        # 중간에 오류가 발생하면
        # DB 변경은 transaction.atomic으로 롤백
        # =====================================================

        with transaction.atomic():

            # =================================================
            # 1. 선수정보 저장
            # =================================================

            saved_same = 0
            saved_move = 0
            saved_new = 0

            saved_photo = 0
            saved_photo_missing = 0

            for team_name, players in (
                team_player_dict.items()
            ):

                team = self.find_team(
                    team_name
                )

                if team is None:

                    raise RuntimeError(
                        f'팀을 찾을 수 없습니다: '
                        f'{team_name}'
                    )

                for info_player in players:

                    player_name = (
                        info_player['name']
                    )

                    row = (
                        info_player['row']
                    )

                    player, status = (
                        self.match_player(
                            team_name,
                            player_name,
                            row.get('등번'),
                            row.get('포지션')
                        )
                    )

                    # -----------------------------------------
                    # 신규
                    # -----------------------------------------

                    if status == 'new':

                        player = Player(
                            team=team,
                            name=player_name
                        )

                        saved_new += 1

                    # -----------------------------------------
                    # 기존 동일
                    # -----------------------------------------

                    elif status == 'same':

                        player.team = team

                        saved_same += 1

                    # -----------------------------------------
                    # 팀 이동
                    # -----------------------------------------

                    elif status == 'move':

                        player.team = team

                        saved_move += 1

                    else:

                        raise RuntimeError(
                            f'선수 판별 실패: '
                            f'{team_name} / '
                            f'{player_name}'
                        )

                    # -----------------------------------------
                    # 프로필 최신화
                    # -----------------------------------------

                    self.apply_profile(
                        player,
                        row
                    )

                    # -----------------------------------------
                    # 사진
                    # -----------------------------------------

                    photo_saved = (
                        self.save_photo(
                            player,
                            source_dir,
                            team_name,
                            player_name
                        )
                    )

                    if photo_saved:

                        saved_photo += 1

                    else:

                        saved_photo_missing += 1

                    player.save()

            # =================================================
            # 2. 선수성적 저장
            # =================================================

            saved_stats = 0
            failed_stats = []

            for json_file in stats_files:

                team_name = (
                    json_file.name
                    .split('_')[0]
                )

                rows = self.read_json(
                    json_file
                )

                team_players = (
                    team_player_dict.get(
                        team_name,
                        []
                    )
                )

                for row in rows:

                    ranking_text = str(
                        row.get(
                            '순위',
                            ''
                        )
                    ).strip()

                    player = None

                    # =========================================
                    # 1차
                    # 선수정보 JSON 명단에서 이름 확인
                    # =========================================

                    info_player = (
                        self.find_info_player_from_ranking(
                            ranking_text,
                            team_players
                        )
                    )

                    if info_player is not None:

                        player = (
                            self.find_current_player(
                                team_name,
                                info_player['name']
                            )
                        )

                    # =========================================
                    # 2차
                    # 기존 DB 보완
                    # =========================================

                    if player is None:

                        player = (
                            self.find_db_stats_player(
                                team_name,
                                ranking_text
                            )
                        )

                    # =========================================
                    # 그래도 못 찾음
                    # =========================================

                    if player is None:

                        failed_stats.append(
                            (
                                team_name,
                                ranking_text
                            )
                        )

                        continue

                    # =========================================
                    # PlayerStats
                    # =========================================

                    stats, created = (
                        PlayerStats.objects
                        .get_or_create(
                            player=player,
                            season=2026
                        )
                    )

                    # JSON에 있는 컬럼만 수정
                    self.apply_stats(
                        stats,
                        row
                    )

                    stats.save()

                    saved_stats += 1

            # =================================================
            # 성적이 하나라도 실패하면 전체 DB 롤백
            # =================================================

            if failed_stats:

                message = (
                    '실제 저장 중 성적 매칭 실패: '
                    + str(failed_stats)
                )

                raise RuntimeError(
                    message
                )

            # =================================================
            # 420건 확인
            # =================================================

            if saved_stats != 420:

                raise RuntimeError(
                    f'성적 저장 건수가 '
                    f'420건이 아닙니다. '
                    f'현재: {saved_stats}건'
                )

        # =====================================================
        # transaction 정상 완료
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '최종 저장 완료'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            f'기존 선수 업데이트   : '
            f'{saved_same}명'
        )

        self.stdout.write(
            f'팀 이동 처리         : '
            f'{saved_move}명'
        )

        self.stdout.write(
            f'신규 선수 생성       : '
            f'{saved_new}명'
        )

        self.stdout.write(
            f'사진 저장            : '
            f'{saved_photo}장'
        )

        self.stdout.write(
            f'사진 없음            : '
            f'{saved_photo_missing}명'
        )

        self.stdout.write(
            f'성적 저장            : '
            f'{saved_stats}건'
        )

        self.stdout.write(
            f'현재 전체 Player     : '
            f'{Player.objects.count()}명'
        )

        self.stdout.write('')

        self.stdout.write(
            self.style.SUCCESS(
                '2026 K리그 데이터 통합이 완료되었습니다.'
            )
        )
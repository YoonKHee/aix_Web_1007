import json
import re
import shutil
from pathlib import Path
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import Player, PlayerStats


class Command(BaseCommand):

    help = 'K리그 JSON 선수정보/선수성적/선수사진을 기존 DB와 합칩니다.'

    # =========================================================
    # 명령어 옵션
    # =========================================================
    def add_arguments(self, parser):

        parser.add_argument(
            '--check',
            action='store_true',
            help='DB를 수정하지 않고 매칭 결과만 확인합니다.'
        )

        parser.add_argument(
            '--source',
            type=str,
            default='',
            help='data 폴더 경로'
        )

    # =========================================================
    # 정수 변환
    # "3,028" -> 3028
    # =========================================================
    def to_int(self, value):

        if value is None:
            return 0

        value = str(value).strip().replace(',', '')

        if value == '':
            return 0

        try:
            return int(float(value))

        except (ValueError, TypeError):
            return 0

    # =========================================================
    # 실수 변환
    # "7.1" -> 7.1
    # =========================================================
    def to_float(self, value):

        if value is None:
            return 0

        value = str(value).strip().replace(',', '')

        if value == '':
            return 0

        try:
            return float(value)

        except (ValueError, TypeError):
            return 0

    # =========================================================
    # 키 / 몸무게에서 숫자만 가져오기
    #
    # "187Cm" -> 187
    # "72Kg"  -> 72
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
    # 생년월일 변환
    # =========================================================
    def to_date(self, value):

        if not value:
            return None

        value = str(value).strip()

        date_formats = [
            '%Y/%m/%d',
            '%Y-%m-%d',
            '%Y.%m.%d',
        ]

        for fmt in date_formats:

            try:
                return datetime.strptime(
                    value,
                    fmt
                ).date()

            except ValueError:
                pass

        return None

    # =========================================================
    # 문자열 비교용
    #
    # 공백을 제거
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
    # JSON 팀 이름과 DB 팀 이름이 같은 팀인지 확인
    #
    # 강원 ↔ 강원FC
    # 서울 ↔ FC서울
    # 전북 ↔ 전북현대
    # =========================================================
    def same_team(self, json_team, db_team):

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
    # DB에서 선수 찾기
    # =========================================================
    def find_player(
        self,
        team_name,
        player_name
    ):

        normalized_name = self.normalize(
            player_name
        )

        # -----------------------------------------------------
        # DB 전체 선수 중 이름 비교
        #
        # filter(name=...)만 사용하지 않고 normalize해서 비교
        # 공백 차이도 처리
        # -----------------------------------------------------
        candidates = []

        players = (
            Player.objects
            .select_related('team')
            .all()
        )

        for player in players:

            if (
                self.normalize(player.name)
                == normalized_name
            ):
                candidates.append(
                    player
                )

        # 이름 같은 선수가 없음
        if len(candidates) == 0:

            return (
                None,
                'not_found'
            )

        # -----------------------------------------------------
        # 같은 이름 중 현재 팀까지 일치하는 선수 우선
        # -----------------------------------------------------
        for player in candidates:

            if self.same_team(
                team_name,
                player.team.team_name
            ):

                return (
                    player,
                    'team_name'
                )

        # -----------------------------------------------------
        # 이름이 같은 선수가 딱 한 명뿐이라면
        # 팀이 달라도 이름으로 연결
        #
        # 팀 이동 선수 가능성 때문
        # -----------------------------------------------------
        if len(candidates) == 1:

            return (
                candidates[0],
                'name_only'
            )

        # 동명이인인데 팀도 다르면 자동 연결하지 않음
        return (
            None,
            'duplicate_name'
        )

    # =========================================================
    # 선수성적 JSON에서
    # 선수정보 JSON의 이름을 이용해 이름 찾기
    #
    # 예:
    # "1김대원강원"
    # -> 김대원
    # =========================================================
    def find_stats_player_name(
        self,
        ranking_text,
        team_player_names
    ):

        ranking_text = self.normalize(
            ranking_text
        )

        sorted_names = sorted(
            team_player_names,
            key=lambda name: len(
                self.normalize(name)
            ),
            reverse=True
        )

        for name in sorted_names:

            if (
                self.normalize(name)
                in ranking_text
            ):

                return name

        return None

    # =========================================================
    # ★ 새로 추가된 핵심 함수
    #
    # 선수성적 JSON에서 DB 선수를 직접 찾음
    #
    # 예:
    #
    # "15조현태강원"
    #       ↓
    # DB 강원FC / 조현태
    #
    # "4송민규서울"
    #       ↓
    # DB FC서울 / 송민규
    # =========================================================
    def find_stats_player_from_db(
        self,
        team_name,
        ranking_text
    ):

        ranking_text = self.normalize(
            ranking_text
        )

        matched_players = []

        players = (
            Player.objects
            .select_related('team')
            .all()
        )

        for player in players:

            # -------------------------------------------------
            # 현재 팀 선수만 검사
            # -------------------------------------------------
            if not self.same_team(
                team_name,
                player.team.team_name
            ):
                continue

            player_name = self.normalize(
                player.name
            )

            # 이름이 비어있으면 제외
            if not player_name:
                continue

            # -------------------------------------------------
            # 순위 문자열 안에 선수 이름이 있는지 확인
            #
            # 15조현태강원
            # 안에
            # 조현태
            # 가 있음
            # -------------------------------------------------
            if player_name in ranking_text:

                matched_players.append(
                    player
                )

        # 후보가 없음
        if len(matched_players) == 0:

            return None

        # 후보가 1명
        if len(matched_players) == 1:

            return matched_players[0]

        # -----------------------------------------------------
        # 후보가 여러 명이면
        # 이름이 가장 긴 선수를 우선
        #
        # 짧은 이름이 긴 이름에 포함되는 문제 방지
        # -----------------------------------------------------
        matched_players.sort(
            key=lambda player: len(
                self.normalize(
                    player.name
                )
            ),
            reverse=True
        )

        return matched_players[0]

    # =========================================================
    # 선수 사진 찾기
    #
    # 예:
    # data\강원\김대원.png
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

            photo = (
                team_dir
                / f'{player_name}{ext}'
            )

            if photo.exists():
                return photo

        return None

    # =========================================================
    # 실제 실행
    # =========================================================
    def handle(
        self,
        *args,
        **options
    ):

        check_only = options['check']

        # =====================================================
        # 데이터 폴더
        # =====================================================

        if options['source']:

            source_dir = Path(
                options['source']
            )

        else:

            # ---------------------------------------------
            # project01\data
            # ---------------------------------------------
            source_dir = (
                Path(settings.BASE_DIR)
                / 'data'
            )

        # -----------------------------------------------------
        # 실제 JSON 위치
        #
        # project01
        # └─ data
        #    └─ k_1부 리그
        #       └─ json_data
        # -----------------------------------------------------
        json_dir = (
            source_dir
            / 'k_1부 리그'
            / 'json_data'
        )

        # =====================================================
        # 폴더 존재 확인
        # =====================================================

        if not source_dir.exists():

            self.stdout.write(
                self.style.ERROR(
                    'data 폴더가 없습니다.'
                )
            )

            self.stdout.write(
                str(source_dir)
            )

            return

        if not json_dir.exists():

            self.stdout.write(
                self.style.ERROR(
                    'JSON 데이터 폴더가 없습니다.'
                )
            )

            self.stdout.write(
                str(json_dir)
            )

            return

        # =====================================================
        # 시작 메시지
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            'K리그 선수 프로필 통합 시작'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            f'사진 데이터 폴더 : '
            f'{source_dir}'
        )

        self.stdout.write(
            f'JSON 데이터 폴더 : '
            f'{json_dir}'
        )

        if check_only:

            self.stdout.write(
                '실행 방식 : 검사만 (--check)'
            )

        else:

            self.stdout.write(
                '실행 방식 : 실제 DB 저장'
            )

        self.stdout.write('')

        # =====================================================
        # JSON 파일 분류
        # =====================================================

        info_files = []
        stats_files = []

        for json_file in json_dir.glob(
            '*.json'
        ):

            try:

                data = self.read_json(
                    json_file
                )

            except Exception as e:

                self.stdout.write(
                    self.style.WARNING(
                        f'JSON 읽기 실패 : '
                        f'{json_file.name} / {e}'
                    )
                )

                continue

            if not isinstance(
                data,
                list
            ):
                continue

            if len(data) == 0:
                continue

            first = data[0]

            # 선수정보
            if '성명' in first:

                info_files.append(
                    (
                        json_file,
                        data
                    )
                )

            # 선수성적
            elif '평균평점' in first:

                stats_files.append(
                    (
                        json_file,
                        data
                    )
                )

        self.stdout.write(
            f'선수정보 JSON 파일 : '
            f'{len(info_files)}개'
        )

        self.stdout.write(
            f'선수성적 JSON 파일 : '
            f'{len(stats_files)}개'
        )

        self.stdout.write('')

        # =====================================================
        # 통계 변수
        # =====================================================

        db_count = (
            Player.objects.count()
        )

        info_total = 0
        info_match = 0
        info_fail = 0

        stats_total = 0
        stats_match = 0
        stats_fail = 0

        # -----------------------------------------------------
        # 성적 매칭 방법을 따로 계산
        # -----------------------------------------------------
        stats_json_name_match = 0
        stats_db_direct_match = 0

        photo_found = 0
        photo_missing = 0

        failed_info = []
        failed_stats = []

        # 팀별 JSON 선수 이름
        team_player_names = {}

        # =====================================================
        # 1. 선수정보 JSON 처리
        # =====================================================

        for json_file, rows in info_files:

            team_name = (
                json_file.name
                .split('_')[0]
            )

            team_player_names[
                team_name
            ] = []

            for row in rows:

                info_total += 1

                player_name = str(
                    row.get(
                        '성명',
                        ''
                    )
                ).strip()

                if not player_name:
                    continue

                # ---------------------------------------------
                # 성적 데이터 이름 찾기에 사용할 수 있도록
                # 성공/실패 여부와 상관없이 이름 저장
                # ---------------------------------------------
                team_player_names[
                    team_name
                ].append(
                    player_name
                )

                player, match_type = (
                    self.find_player(
                        team_name,
                        player_name
                    )
                )

                # ---------------------------------------------
                # 기존 DB에서 못 찾음
                #
                # 현재 단계에서는 신규 추가하지 않음
                # ---------------------------------------------
                if player is None:

                    info_fail += 1

                    failed_info.append(
                        f'{team_name} / '
                        f'{player_name}'
                    )

                    continue

                info_match += 1

                # ---------------------------------------------
                # 사진 확인
                # ---------------------------------------------
                photo_path = self.find_photo(
                    source_dir,
                    team_name,
                    player_name
                )

                if photo_path:

                    photo_found += 1

                else:

                    photo_missing += 1

                # ---------------------------------------------
                # 검사 모드면 저장하지 않음
                # ---------------------------------------------
                if check_only:
                    continue

                # =============================================
                # 선수 기본정보 업데이트
                # =============================================

                player.number = self.to_int(
                    row.get('등번')
                )

                player.position = str(
                    row.get(
                        '포지션',
                        player.position
                    )
                ).strip()

                player.height = self.only_number(
                    row.get('키')
                )

                player.weight = self.only_number(
                    row.get('몸무게')
                )

                player.birth_date = (
                    self.to_date(
                        row.get('생년월일')
                    )
                )

                # =============================================
                # 선수 사진 복사
                # =============================================

                if photo_path:

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

                player.save()

        # =====================================================
        # 2. 선수성적 JSON 처리
        # =====================================================

        for json_file, rows in stats_files:

            team_name = (
                json_file.name
                .split('_')[0]
            )

            names = (
                team_player_names.get(
                    team_name,
                    []
                )
            )

            for row in rows:

                stats_total += 1

                ranking_text = row.get(
                    '순위',
                    ''
                )

                # =============================================
                # 1차 검색
                #
                # 선수정보 JSON의 이름으로 찾기
                # =============================================

                player_name = (
                    self.find_stats_player_name(
                        ranking_text,
                        names
                    )
                )

                player = None
                match_method = None

                if player_name:

                    player, match_type = (
                        self.find_player(
                            team_name,
                            player_name
                        )
                    )

                    if player is not None:

                        match_method = (
                            'json_name'
                        )

                # =============================================
                # 2차 검색
                #
                # 1차에서 실패하면
                # DB 선수 이름으로 직접 검색
                #
                # 예:
                # 15조현태강원
                # 4송민규서울
                # 12남태희제주
                # =============================================

                if player is None:

                    player = (
                        self.find_stats_player_from_db(
                            team_name,
                            ranking_text
                        )
                    )

                    if player is not None:

                        match_method = (
                            'db_direct'
                        )

                # =============================================
                # 둘 다 실패
                # =============================================

                if player is None:

                    stats_fail += 1

                    failed_stats.append(
                        f'{team_name} / '
                        f'{ranking_text}'
                    )

                    continue

                # =============================================
                # 매칭 성공
                # =============================================

                stats_match += 1

                if (
                    match_method
                    == 'json_name'
                ):

                    stats_json_name_match += 1

                elif (
                    match_method
                    == 'db_direct'
                ):

                    stats_db_direct_match += 1

                # ---------------------------------------------
                # --check이면 DB 저장 안 함
                # ---------------------------------------------
                if check_only:
                    continue

                # =============================================
                # 2026 PlayerStats 찾기
                # =============================================

                stats = (
                    PlayerStats.objects
                    .filter(
                        player=player,
                        season=2026
                    )
                    .first()
                )

                # 없으면 생성
                if stats is None:

                    stats = (
                        PlayerStats.objects
                        .create(
                            player=player,
                            season=2026
                        )
                    )

                # =============================================
                # 새 JSON 데이터
                # =============================================

                stats.games = self.to_int(
                    row.get('경기')
                )

                stats.attack_points = (
                    self.to_int(
                        row.get(
                            '공격포인트'
                        )
                    )
                )

                stats.pk_goals = self.to_int(
                    row.get('PK골')
                )

                stats.mom = self.to_int(
                    row.get('MOM')
                )

                stats.average_rating = (
                    self.to_float(
                        row.get(
                            '평균평점'
                        )
                    )
                )

                stats.best11_count = (
                    self.to_int(
                        row.get('BEST11')
                    )
                )

                stats.pk_attempts = (
                    self.to_int(
                        row.get('PK')
                    )
                )

                # =============================================
                # 기존 PlayerStats에도 있는 데이터
                # =============================================

                stats.goals = self.to_int(
                    row.get('득점')
                )

                stats.assists = self.to_int(
                    row.get('도움')
                )

                stats.shots = self.to_int(
                    row.get('슈팅')
                )

                stats.shots_on_target = (
                    self.to_int(
                        row.get(
                            '유효슈팅'
                        )
                    )
                )

                stats.minutes = self.to_int(
                    row.get(
                        '출전시간(분)'
                    )
                )

                stats.fouls = self.to_int(
                    row.get('파울')
                )

                stats.fouls_won = (
                    self.to_int(
                        row.get('피파울')
                    )
                )

                stats.yellow_cards = (
                    self.to_int(
                        row.get('경고')
                    )
                )

                stats.red_cards = (
                    self.to_int(
                        row.get('퇴장')
                    )
                )

                stats.corner_kicks = (
                    self.to_int(
                        row.get('코너킥')
                    )
                )

                stats.offsides = (
                    self.to_int(
                        row.get(
                            '오프사이드'
                        )
                    )
                )

                stats.save()

        # =====================================================
        # 3. 결과 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        if check_only:

            self.stdout.write(
                '검사 결과'
            )

        else:

            self.stdout.write(
                '저장 결과'
            )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            f'DB 선수             : '
            f'{db_count}명'
        )

        self.stdout.write('')

        # -----------------------------------------------------
        # 선수정보
        # -----------------------------------------------------

        self.stdout.write(
            f'선수정보 JSON        : '
            f'{info_total}명'
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'선수정보 매칭 성공   : '
                f'{info_match}명'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'선수정보 매칭 실패   : '
                f'{info_fail}명'
            )
        )

        self.stdout.write('')

        # -----------------------------------------------------
        # 선수성적
        # -----------------------------------------------------

        self.stdout.write(
            f'선수성적 JSON        : '
            f'{stats_total}건'
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'선수성적 매칭 성공   : '
                f'{stats_match}건'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'선수성적 매칭 실패   : '
                f'{stats_fail}건'
            )
        )

        self.stdout.write(
            f'  ├─ JSON 이름 매칭  : '
            f'{stats_json_name_match}건'
        )

        self.stdout.write(
            f'  └─ DB 직접 매칭    : '
            f'{stats_db_direct_match}건'
        )

        self.stdout.write('')

        # -----------------------------------------------------
        # 사진
        # -----------------------------------------------------

        self.stdout.write(
            self.style.SUCCESS(
                f'선수사진 발견        : '
                f'{photo_found}장'
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f'선수사진 없음        : '
                f'{photo_missing}명'
            )
        )

        # =====================================================
        # 선수정보 실패 목록
        # =====================================================

        if failed_info:

            self.stdout.write('')

            self.stdout.write(
                '----- 선수정보 매칭 실패 -----'
            )

            for item in failed_info:

                self.stdout.write(
                    f'  {item}'
                )

        # =====================================================
        # 선수성적 실패 목록
        # =====================================================

        if failed_stats:

            self.stdout.write('')

            self.stdout.write(
                '----- 선수성적 매칭 실패 -----'
            )

            for item in failed_stats:

                self.stdout.write(
                    f'  {item}'
                )

        self.stdout.write('')

        # =====================================================
        # 마지막 안내
        # =====================================================

        if check_only:

            self.stdout.write(
                self.style.SUCCESS(
                    '※ --check 모드이므로 '
                    'DB는 수정하지 않았습니다.'
                )
            )

        else:

            self.stdout.write(
                self.style.SUCCESS(
                    '선수정보/성적/사진 '
                    'DB 저장이 완료되었습니다.'
                )
            )
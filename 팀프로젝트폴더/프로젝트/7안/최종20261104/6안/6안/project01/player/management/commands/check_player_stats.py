import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from player.models import Player


class Command(BaseCommand):

    help = '2026 K리그 선수정보 JSON + 기존 DB를 이용해서 선수성적 JSON 연결 상태를 검사합니다.'

    # =========================================================
    # 문자열 정리
    #
    # 예:
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
    # 팀 이름 비교
    #
    # 예:
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
    # 1차 검색
    #
    # 선수정보 JSON 안에서
    # 성적 선수 이름 찾기
    #
    # 예:
    # ranking_text
    # "23이은호강원"
    #
    # 선수정보 JSON에
    # "이은호"가 있으면 성공
    # =========================================================
    def find_player_from_ranking(
        self,
        ranking_text,
        team_players
    ):

        ranking_text = self.normalize(
            ranking_text
        )

        candidates = []

        for player in team_players:

            player_name = self.normalize(
                player['name']
            )

            if (
                player_name
                and
                player_name in ranking_text
            ):

                candidates.append(
                    player
                )

        # 아무도 못 찾음
        if len(candidates) == 0:

            return None, []

        # -----------------------------------------------------
        # 이름이 긴 선수를 먼저 사용
        #
        # 혹시 이름 일부가 겹치는 상황을
        # 최대한 방지
        # -----------------------------------------------------

        candidates.sort(
            key=lambda p: len(
                self.normalize(
                    p['name']
                )
            ),
            reverse=True
        )

        return (
            candidates[0],
            candidates
        )

    # =========================================================
    # 2차 검색
    #
    # 선수정보 JSON에서 못 찾았다면
    # 기존 Django DB에서 검색
    #
    # 예:
    #
    # 성적 JSON
    # 강원 / 15조현태강원
    #
    # 선수정보 JSON
    # 조현태 없음
    #
    # 기존 DB
    # 강원FC / 조현태 있음
    #
    # → 성공
    # =========================================================
    def find_player_from_db(
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

            # -------------------------------------------------
            # 같은 팀인지 먼저 확인
            # -------------------------------------------------

            if not self.same_team(
                team_name,
                player.team.team_name
            ):

                continue

            # -------------------------------------------------
            # 선수 이름 확인
            # -------------------------------------------------

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

        # 아무도 못 찾음
        if len(candidates) == 0:

            return None, []

        # 이름이 긴 선수 우선
        candidates.sort(
            key=lambda p: len(
                self.normalize(
                    p.name
                )
            ),
            reverse=True
        )

        return (
            candidates[0],
            candidates
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
        # JSON 폴더 위치
        # =====================================================

        json_dir = (
            Path(settings.BASE_DIR)
            / 'data'
            / 'k_1부 리그'
            / 'json_data'
        )

        # =====================================================
        # 폴더 존재 확인
        # =====================================================

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
        # 선수정보 JSON 파일
        # =====================================================

        info_files = sorted(
            json_dir.glob(
                '*_선수정보.json'
            )
        )

        # =====================================================
        # 선수성적 JSON 파일
        # =====================================================

        stats_files = sorted(
            json_dir.glob(
                '*_선수성적.json'
            )
        )

        # =====================================================
        # 1. 선수정보 JSON 읽기
        # =====================================================

        team_player_dict = {}

        total_info = 0

        for json_file in info_files:

            # -------------------------------------------------
            # 파일명에서 팀 이름 가져오기
            #
            # 예:
            # 강원_선수정보.json
            #
            # → 강원
            # -------------------------------------------------

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

                # 이름이 없으면 건너뜀
                if not player_name:
                    continue

                player_data = {

                    'team': team_name,

                    'name': player_name,

                    'number': row.get(
                        '등번'
                    ),

                    'position': row.get(
                        '포지션'
                    ),

                    'birth_date': row.get(
                        '생년월일'
                    ),
                }

                team_player_dict[
                    team_name
                ].append(
                    player_data
                )

                total_info += 1

        # =====================================================
        # 2. 선수성적 검사 준비
        # =====================================================

        total_stats = 0

        # 전체 성공
        success_count = 0

        # 전체 실패
        fail_count = 0

        # -----------------------------------------------------
        # 어디에서 찾았는지도 따로 계산
        # -----------------------------------------------------

        # 선수정보 JSON에서 바로 찾음
        json_match_count = 0

        # 선수정보 JSON에는 없었지만
        # 기존 DB에서 찾음
        db_match_count = 0

        # -----------------------------------------------------
        # 복수 후보
        # -----------------------------------------------------

        multiple_count = 0

        # -----------------------------------------------------
        # 목록 저장
        # -----------------------------------------------------

        fail_list = []

        db_match_list = []

        multiple_list = []

        # -----------------------------------------------------
        # 팀별 결과
        # -----------------------------------------------------

        team_result = {}

        # =====================================================
        # 3. 선수성적 JSON 검사
        # =====================================================

        for json_file in stats_files:

            team_name = (
                json_file.name
                .split('_')[0]
            )

            rows = self.read_json(
                json_file
            )

            # -------------------------------------------------
            # 해당 팀의 선수정보 JSON 선수들
            # -------------------------------------------------

            team_players = (
                team_player_dict.get(
                    team_name,
                    []
                )
            )

            # -------------------------------------------------
            # 팀별 결과 초기값
            # -------------------------------------------------

            team_result[
                team_name
            ] = {

                'total': 0,

                'success': 0,

                'fail': 0,

                'json': 0,

                'db': 0,
            }

            # =================================================
            # 성적 한 줄씩 검사
            # =================================================

            for row in rows:

                total_stats += 1

                team_result[
                    team_name
                ]['total'] += 1

                ranking_text = str(
                    row.get(
                        '순위',
                        ''
                    )
                ).strip()

                # =============================================
                # 1차 검색
                #
                # 선수정보 JSON에서 검색
                # =============================================

                player, candidates = (
                    self.find_player_from_ranking(
                        ranking_text,
                        team_players
                    )
                )

                # =============================================
                # 1차 검색 성공
                # =============================================

                if player is not None:

                    success_count += 1

                    json_match_count += 1

                    team_result[
                        team_name
                    ]['success'] += 1

                    team_result[
                        team_name
                    ]['json'] += 1

                    # -----------------------------------------
                    # 후보가 여러 명 잡혔는지 확인
                    # -----------------------------------------

                    if len(candidates) > 1:

                        multiple_count += 1

                        multiple_list.append(
                            (
                                team_name,
                                ranking_text,
                                [
                                    p['name']
                                    for p
                                    in candidates
                                ]
                            )
                        )

                    # 성공했으므로 다음 성적으로 이동
                    continue

                # =============================================
                # 2차 검색
                #
                # 선수정보 JSON에서 못 찾았으므로
                # 기존 DB에서 검색
                # =============================================

                db_player, db_candidates = (
                    self.find_player_from_db(
                        team_name,
                        ranking_text
                    )
                )

                # =============================================
                # 2차 DB 검색 성공
                # =============================================

                if db_player is not None:

                    success_count += 1

                    db_match_count += 1

                    team_result[
                        team_name
                    ]['success'] += 1

                    team_result[
                        team_name
                    ]['db'] += 1

                    # -----------------------------------------
                    # DB에서 찾아낸 선수 목록 저장
                    # -----------------------------------------

                    db_match_list.append(
                        (
                            team_name,
                            ranking_text,
                            db_player.team.team_name,
                            db_player.name,
                            db_player.number,
                            db_player.position
                        )
                    )

                    # -----------------------------------------
                    # DB 후보가 여러 명 잡혔는지 확인
                    # -----------------------------------------

                    if len(db_candidates) > 1:

                        multiple_count += 1

                        multiple_list.append(
                            (
                                team_name,
                                ranking_text,
                                [
                                    p.name
                                    for p
                                    in db_candidates
                                ]
                            )
                        )

                    continue

                # =============================================
                # 1차 JSON 검색 실패
                # +
                # 2차 DB 검색 실패
                #
                # → 최종 실패
                # =============================================

                fail_count += 1

                team_result[
                    team_name
                ]['fail'] += 1

                fail_list.append(
                    (
                        team_name,
                        ranking_text
                    )
                )

        # =====================================================
        # 4. 전체 결과 출력
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            '2026 K리그 선수성적 최종 검사'
        )

        self.stdout.write(
            '=========================================='
        )

        self.stdout.write(
            f'선수정보 JSON       : '
            f'{total_info}명'
        )

        self.stdout.write(
            f'선수성적 JSON       : '
            f'{total_stats}건'
        )

        self.stdout.write('')

        # =====================================================
        # 성공
        # =====================================================

        self.stdout.write(
            self.style.SUCCESS(
                f'성적 매칭 성공      : '
                f'{success_count}건'
            )
        )

        # =====================================================
        # 실패
        # =====================================================

        if fail_count == 0:

            self.stdout.write(
                self.style.SUCCESS(
                    f'성적 매칭 실패      : '
                    f'{fail_count}건'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    f'성적 매칭 실패      : '
                    f'{fail_count}건'
                )
            )

        self.stdout.write('')

        # =====================================================
        # 어디에서 찾았는지
        # =====================================================

        self.stdout.write(
            f'선수정보 JSON 매칭  : '
            f'{json_match_count}건'
        )

        self.stdout.write(
            f'기존 DB 보완 매칭   : '
            f'{db_match_count}건'
        )

        self.stdout.write(
            f'복수 후보 발견      : '
            f'{multiple_count}건'
        )

        # =====================================================
        # 5. 팀별 결과
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '========== 팀별 검사 =========='
        )

        for team_name, result in (
            team_result.items()
        ):

            self.stdout.write(
                f"{team_name:<4} : "
                f"{result['success']}"
                f"/"
                f"{result['total']}"
                f" 성공"
                f"  "
                f"(JSON {result['json']} / "
                f"DB {result['db']})"
            )

        # =====================================================
        # 6. DB 보완으로 찾아낸 선수
        # =====================================================

        if db_match_list:

            self.stdout.write('')

            self.stdout.write(
                '========== 기존 DB 보완 매칭 =========='
            )

            for (
                json_team,
                ranking_text,
                db_team,
                db_name,
                db_number,
                db_position
            ) in db_match_list:

                self.stdout.write(
                    f'{json_team} / '
                    f'{ranking_text}'
                    f'  →  '
                    f'{db_team} / '
                    f'{db_name}'
                    f' / {db_number}번'
                    f' / {db_position}'
                )

        # =====================================================
        # 7. 실패 목록
        # =====================================================

        if fail_list:

            self.stdout.write('')

            self.stdout.write(
                '========== 최종 매칭 실패 =========='
            )

            for (
                team_name,
                ranking_text
            ) in fail_list:

                self.stdout.write(
                    f'{team_name} / '
                    f'{ranking_text}'
                )

        # =====================================================
        # 8. 복수 후보
        # =====================================================

        if multiple_list:

            self.stdout.write('')

            self.stdout.write(
                '========== 복수 후보 확인 =========='
            )

            for (
                team_name,
                ranking_text,
                candidates
            ) in multiple_list:

                self.stdout.write(
                    f'{team_name} / '
                    f'{ranking_text}'
                )

                self.stdout.write(
                    '  후보 : '
                    + ', '.join(
                        candidates
                    )
                )

        # =====================================================
        # 9. 최종 판정
        # =====================================================

        self.stdout.write('')

        self.stdout.write(
            '=========================================='
        )

        if (
            total_stats == success_count
            and
            fail_count == 0
        ):

            self.stdout.write(
                self.style.SUCCESS(
                    '최종 판정 : 전체 성적 매칭 성공'
                )
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f'{success_count}'
                    f'/'
                    f'{total_stats}'
                    f'건 매칭되었습니다.'
                )
            )

        else:

            self.stdout.write(
                self.style.ERROR(
                    '최종 판정 : 추가 확인 필요'
                )
            )

            self.stdout.write(
                self.style.ERROR(
                    f'{fail_count}건을 '
                    f'추가 확인해야 합니다.'
                )
            )

        self.stdout.write('')

        self.stdout.write(
            '※ 검사 전용 프로그램입니다.'
        )

        self.stdout.write(
            '※ DB 추가/수정/삭제는 하지 않았습니다.'
        )
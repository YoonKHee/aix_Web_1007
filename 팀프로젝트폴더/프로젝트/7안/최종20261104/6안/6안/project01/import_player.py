import os
import glob
import django
import pandas as pd


# =========================================================
# 1. Django 설정
# =========================================================

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project01.settings')
django.setup()


# Django 모델 불러오기
from team.models import Team
from player.models import Player, PlayerStats


# =========================================================
# 2. 기본 폴더 위치
# =========================================================

# 현재 import_player.py가 있는 위치
base_dir = os.path.dirname(os.path.abspath(__file__))

# 선수 XLS 파일들이 들어있는 폴더
player_dir = os.path.join(
    base_dir,
    'data',
    'player'
)


# =========================================================
# 3. 파일명 → 실제 팀명 연결
# =========================================================

team_name_map = {
    '강원': '강원FC',
    '광주': '광주FC',
    '김천': '김천상무',
    '대전': '대전하나시티즌',
    '부천': '부천FC1995',
    '서울': 'FC서울',
    '안양': 'FC안양',
    '울산': '울산HD',
    '인천': '인천유나이티드',
    '전북': '전북현대',
    '제주': '제주SK FC',
    '포항': '포항스틸러스',
}


# =========================================================
# 4. 숫자 변환 함수
# =========================================================

def to_int(value):

    # NaN이면 0
    if pd.isna(value):
        return 0

    try:
        return int(float(value))

    except:
        return 0


# =========================================================
# 5. player 폴더 안의 모든 xls 파일 찾기
# =========================================================

file_list = glob.glob(
    os.path.join(player_dir, '*.xls')
)

# 파일명 순서대로 정렬
file_list.sort()


print('==========================================')
print('K리그 전체 선수 데이터 등록 시작')
print('==========================================')

print('선수 데이터 폴더 :', player_dir)
print('발견한 XLS 파일 수 :', len(file_list))

print()


# =========================================================
# 6. 전체 결과를 저장할 변수
# =========================================================

total_success = 0
total_error = 0
total_skip = 0


# =========================================================
# 7. XLS 파일을 하나씩 처리
# =========================================================

for file_path in file_list:

    print()
    print('==========================================')

    # 파일명만 가져오기
    # 예 : 2026_강원.xls
    file_name = os.path.basename(file_path)

    # 확장자 제거
    # 예 : 2026_강원
    file_name_without_ext = os.path.splitext(file_name)[0]

    # _ 기준으로 나누기
    # ['2026', '강원']
    file_parts = file_name_without_ext.split('_')

    # 두 번째 값이 팀 코드
    team_code = file_parts[1]

    print('파일 :', file_name)
    print('팀 코드 :', team_code)


    # -----------------------------------------------------
    # 팀명 확인
    # -----------------------------------------------------

    if team_code not in team_name_map:

        print('등록되지 않은 팀명입니다.')
        print('이 파일은 건너뜁니다.')

        total_skip += 1

        continue


    # 실제 팀명 가져오기
    team_name = team_name_map[team_code]

    print('실제 팀명 :', team_name)


    # -----------------------------------------------------
    # Team 생성 또는 가져오기
    # -----------------------------------------------------

    team, team_created = Team.objects.get_or_create(

        team_name=team_name,

        defaults={
            'league': 'K리그1',
            'stadium': ''
        }
    )


    if team_created:
        print('Team 생성 완료 :', team_name)

    else:
        print('기존 Team 사용 :', team_name)


    # -----------------------------------------------------
    # XLS 읽기
    # -----------------------------------------------------

    try:

        tables = pd.read_html(file_path)

        # 첫 번째 테이블이 선수기록
        df = tables[0]

        print('원본 데이터 크기 :', df.shape)

    except Exception as e:

        print('파일 읽기 실패 :', e)

        total_error += 1

        continue


    # -----------------------------------------------------
    # 현재 팀의 결과
    # -----------------------------------------------------

    team_success = 0
    team_error = 0
    team_skip = 0


    # =====================================================
    # 8. 선수 한 명씩 처리
    # =====================================================

    for index, row in df.iterrows():

        try:

            # -------------------------------------------------
            # 선수 기본정보
            # -------------------------------------------------

            season = to_int(
                row[('년도', '년도')]
            )

            name = str(
                row[('선수명', '선수명')]
            ).strip()

            position = str(
                row[('포지션', '포지션')]
            ).strip()

            number = to_int(
                row[('등번호', '등번호')]
            )


            # -------------------------------------------------
            # 선수 데이터가 아닌 행 제외
            # -------------------------------------------------

            if (
                name == ''
                or name == 'nan'
                or season == 0
                or position == 'nan'
            ):

                team_skip += 1
                total_skip += 1

                continue


            # -------------------------------------------------
            # Player 저장
            # -------------------------------------------------

            player, player_created = Player.objects.update_or_create(

                team=team,
                name=name,

                defaults={
                    'number': number,
                    'position': position,
                }
            )


            # -------------------------------------------------
            # PlayerStats 저장
            # -------------------------------------------------

            stats, stats_created = PlayerStats.objects.update_or_create(

                player=player,
                season=season,

                defaults={

                    # =========================================
                    # 기본 기록
                    # =========================================

                    'minutes': to_int(
                        row[('출전시간(분)', '출전시간(분)')]
                    ),

                    'goals': to_int(
                        row[('득점', '득점')]
                    ),

                    'assists': to_int(
                        row[('도움', '도움')]
                    ),


                    # =========================================
                    # 슈팅
                    # =========================================

                    'shots': to_int(
                        row[('슈팅', '슈팅')]
                    ),

                    'shots_on_target': to_int(
                        row[('유효 슈팅', '유효 슈팅')]
                    ),

                    'shots_blocked': to_int(
                        row[('차단된슈팅', '차단된슈팅')]
                    ),

                    'shots_off_target': to_int(
                        row[('벗어난슈팅', '벗어난슈팅')]
                    ),

                    'shots_inside_box': to_int(
                        row[('PA내 슈팅', 'PA내 슈팅')]
                    ),

                    'shots_outside_box': to_int(
                        row[('PA외 슈팅', 'PA외 슈팅')]
                    ),


                    # =========================================
                    # 공격 기타
                    # =========================================

                    'offsides': to_int(
                        row[('오프사이드', '오프사이드')]
                    ),

                    'free_kicks': to_int(
                        row[('프리킥', '프리킥')]
                    ),

                    'corner_kicks': to_int(
                        row[('코너킥', '코너킥')]
                    ),

                    'throw_ins': to_int(
                        row[('스로인', '스로인')]
                    ),


                    # =========================================
                    # 드리블
                    # =========================================

                    'dribble_attempt': to_int(
                        row[('드리블', '시도')]
                    ),

                    'dribble_success': to_int(
                        row[('드리블', '성공')]
                    ),


                    # =========================================
                    # 전체 패스
                    # =========================================

                    'pass_attempt': to_int(
                        row[('패스', '시도')]
                    ),

                    'pass_success': to_int(
                        row[('패스', '성공')]
                    ),

                    'key_passes': to_int(
                        row[('키패스', '키패스')]
                    ),


                    # =========================================
                    # 전방 패스
                    # =========================================

                    'forward_pass_attempt': to_int(
                        row[('전방 패스', '시도')]
                    ),

                    'forward_pass_success': to_int(
                        row[('전방 패스', '성공')]
                    ),


                    # =========================================
                    # 후방 패스
                    # =========================================

                    'backward_pass_attempt': to_int(
                        row[('후방 패스', '시도')]
                    ),

                    'backward_pass_success': to_int(
                        row[('후방 패스', '성공')]
                    ),


                    # =========================================
                    # 횡패스
                    # =========================================

                    'lateral_pass_attempt': to_int(
                        row[('횡패스', '시도')]
                    ),

                    'lateral_pass_success': to_int(
                        row[('횡패스', '성공')]
                    ),


                    # =========================================
                    # 공격지역패스
                    # =========================================

                    'attacking_third_pass_attempt': to_int(
                        row[('공격지역패스', '시도')]
                    ),

                    'attacking_third_pass_success': to_int(
                        row[('공격지역패스', '성공')]
                    ),


                    # =========================================
                    # 수비지역패스
                    # =========================================

                    'defensive_third_pass_attempt': to_int(
                        row[('수비지역패스', '시도')]
                    ),

                    'defensive_third_pass_success': to_int(
                        row[('수비지역패스', '성공')]
                    ),


                    # =========================================
                    # 중앙지역패스
                    # =========================================

                    'middle_third_pass_attempt': to_int(
                        row[('중앙지역패스', '시도')]
                    ),

                    'middle_third_pass_success': to_int(
                        row[('중앙지역패스', '성공')]
                    ),


                    # =========================================
                    # 롱패스
                    # =========================================

                    'long_pass_attempt': to_int(
                        row[('롱패스', '시도')]
                    ),

                    'long_pass_success': to_int(
                        row[('롱패스', '성공')]
                    ),


                    # =========================================
                    # 중거리패스
                    # =========================================

                    'medium_pass_attempt': to_int(
                        row[('중거리패스', '시도')]
                    ),

                    'medium_pass_success': to_int(
                        row[('중거리패스', '성공')]
                    ),


                    # =========================================
                    # 숏패스
                    # =========================================

                    'short_pass_attempt': to_int(
                        row[('숏패스', '시도')]
                    ),

                    'short_pass_success': to_int(
                        row[('숏패스', '성공')]
                    ),


                    # =========================================
                    # 크로스
                    # =========================================

                    'cross_attempt': to_int(
                        row[('크로스', '시도')]
                    ),

                    'cross_success': to_int(
                        row[('크로스', '성공')]
                    ),


                    # =========================================
                    # 탈압박
                    # =========================================

                    'escape_pressure': to_int(
                        row[('탈압박', '탈압박')]
                    ),


                    # =========================================
                    # 지상 경합
                    # =========================================

                    'ground_duel_attempt': to_int(
                        row[('경합 지상', '시도')]
                    ),

                    'ground_duel_success': to_int(
                        row[('경합 지상', '성공')]
                    ),


                    # =========================================
                    # 공중 경합
                    # =========================================

                    'aerial_duel_attempt': to_int(
                        row[('경합 공중', '시도')]
                    ),

                    'aerial_duel_success': to_int(
                        row[('경합 공중', '성공')]
                    ),


                    # =========================================
                    # 태클
                    # =========================================

                    'tackle_attempt': to_int(
                        row[('태클', '시도')]
                    ),

                    'tackle_success': to_int(
                        row[('태클', '성공')]
                    ),


                    # =========================================
                    # 수비
                    # =========================================

                    'clearances': to_int(
                        row[('클리어링', '클리어링')]
                    ),

                    'interceptions': to_int(
                        row[('인터셉트', '인터셉트')]
                    ),

                    'defensive_blocks': to_int(
                        row[('차단', '차단')]
                    ),

                    'recoveries': to_int(
                        row[('획득', '획득')]
                    ),

                    'blocks': to_int(
                        row[('블락', '블락')]
                    ),


                    # =========================================
                    # 볼미스
                    # =========================================

                    'ball_misses': to_int(
                        row[('볼미스', '볼미스')]
                    ),


                    # =========================================
                    # 파울
                    # =========================================

                    'fouls': to_int(
                        row[('파울', '파울')]
                    ),

                    'fouls_won': to_int(
                        row[('피파울', '피파울')]
                    ),


                    # =========================================
                    # 카드
                    # =========================================

                    'yellow_cards': to_int(
                        row[('경고', '경고')]
                    ),

                    'red_cards': to_int(
                        row[('퇴장', '퇴장')]
                    ),
                }
            )


            team_success += 1
            total_success += 1


        except Exception as e:

            team_error += 1
            total_error += 1

            print()
            print('선수 저장 실패')
            print('행 번호 :', index)
            print('선수명 :', row.get(('선수명', '선수명'), '확인불가'))
            print('오류 :', e)


    # =====================================================
    # 9. 한 팀 처리 결과
    # =====================================================

    print()
    print('------------------------------------------')
    print(team_name, '등록 결과')
    print('------------------------------------------')
    print('저장 성공 :', team_success)
    print('제외 행 :', team_skip)
    print('오류 :', team_error)

    print(
        'DB 선수 수 :',
        Player.objects.filter(team=team).count()
    )

    print(
        'DB 기록 수 :',
        PlayerStats.objects.filter(
            player__team=team,
            season=2026
        ).count()
    )

    print('==========================================')


# =========================================================
# 10. 12팀 전체 결과
# =========================================================

print()
print()
print('==========================================')
print('K리그 전체 선수 데이터 등록 완료')
print('==========================================')

print('처리한 XLS 파일 수 :', len(file_list))
print('선수 저장 성공 :', total_success)
print('제외된 행 :', total_skip)
print('오류 :', total_error)

print('전체 Team 수 :', Team.objects.count())
print('전체 Player 수 :', Player.objects.count())
print('전체 PlayerStats 수 :', PlayerStats.objects.count())

print('==========================================')
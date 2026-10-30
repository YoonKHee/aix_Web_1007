from django.shortcuts import render
from django.http import JsonResponse

from player.models import Player, PlayerStats
from team.models import Team

from player.services import (
    get_best11,
    get_player_radar,
    get_filtered_best11,
    get_formations,
)


# =========================================================
# 선수 목록
# =========================================================
def plist(request):

    team_id = request.GET.get(
        'team',
        ''
    )

    position = request.GET.get(
        'position',
        ''
    )

    search_word = request.GET.get(
        'search_word',
        ''
    )


    qs = Player.objects.all()


    # -----------------------------------------------------
    # 구단 검색
    # -----------------------------------------------------
    if team_id:

        qs = qs.filter(
            team_id=team_id
        )


    # -----------------------------------------------------
    # 포지션 검색
    # -----------------------------------------------------
    if position:

        qs = qs.filter(
            position=position
        )


    # -----------------------------------------------------
    # 선수명 검색
    # -----------------------------------------------------
    if search_word:

        qs = qs.filter(
            name__contains=search_word
        )


    qs = qs.order_by(
        'team__team_name',
        'position',
        'number'
    )


    teams = Team.objects.all().order_by(
        'team_name'
    )


    context = {

        'list':
            qs,

        'teams':
            teams,

        'team_id':
            team_id,

        'position':
            position,

        'search_word':
            search_word,
    }


    return render(
        request,
        'plist.html',
        context
    )


# =========================================================
# 선수 상세정보
# =========================================================
def pview(request, id):

    # -----------------------------------------------------
    # 선수 1명
    # -----------------------------------------------------
    qs = Player.objects.get(
        id=id
    )


    # -----------------------------------------------------
    # 해당 선수 시즌 기록
    # -----------------------------------------------------
    stats = (

        PlayerStats.objects

        .filter(
            player=qs
        )

        .order_by(
            '-season'
        )
    )


    context = {

        'player':
            qs,

        'stats':
            stats,
    }


    return render(
        request,
        'pview.html',
        context
    )


# =========================================================
# 2026 K리그 BEST11
#
# GET 예시
#
# 전체 K리그 / 4-3-3
# /player/best11/
#
# 전북현대 / 4-2-3-1
# /player/best11/?team=10&formation=4-2-3-1
#
# 구단과 포메이션을 GET 방식으로 받는다.
# =========================================================
def best11(request):


    # =====================================================
    # 1. 사용자가 선택한 구단
    #
    # 선택하지 않으면 ''
    # =====================================================
    team_id = request.GET.get(
        'team',
        ''
    )


    # =====================================================
    # 2. 사용자가 선택한 포메이션
    #
    # 기본값 = 4-3-3
    # =====================================================
    formation = request.GET.get(
        'formation',
        '4-3-3'
    )


    # =====================================================
    # 3. 구단 + 포메이션 BEST11 계산
    # =====================================================
    result = get_filtered_best11(

        team_id=team_id,

        formation=formation
    )


    # =====================================================
    # 4. 모든 구단
    #
    # HTML의 구단 선택창에서 사용
    # =====================================================
    teams = (

        Team.objects

        .all()

        .order_by(
            'team_name'
        )
    )


    # =====================================================
    # 5. 사용 가능한 포메이션
    # =====================================================
    formations = (
        get_formations()
    )


    # =====================================================
    # 6. 선택된 구단 객체
    # =====================================================
    selected_team = None


    if result['team_id']:

        selected_team = (

            Team.objects

            .filter(
                id=result['team_id']
            )

            .first()
        )


    # =====================================================
    # 7. HTML로 전달
    # =====================================================
    context = {


        # -------------------------------------------------
        # BEST11
        # -------------------------------------------------
        'best11':
            result['best11'],


        # -------------------------------------------------
        # 포지션별 전체 순위
        # -------------------------------------------------
        'rankings':
            result['rankings'],


        # -------------------------------------------------
        # 후보 선수 숫자
        # -------------------------------------------------
        'candidate_count':
            result['candidate_count'],


        # -------------------------------------------------
        # 포지션별 후보 숫자
        # -------------------------------------------------
        'position_count':
            result['position_count'],


        # -------------------------------------------------
        # 구단 목록
        # -------------------------------------------------
        'teams':
            teams,


        # -------------------------------------------------
        # 포메이션 목록
        # -------------------------------------------------
        'formations':
            formations,


        # -------------------------------------------------
        # 현재 선택된 구단 ID
        # -------------------------------------------------
        'team_id':
            result['team_id'],


        # -------------------------------------------------
        # 현재 선택된 구단 객체
        # -------------------------------------------------
        'selected_team':
            selected_team,


        # -------------------------------------------------
        # 현재 선택된 포메이션
        # -------------------------------------------------
        'formation':
            result['formation'],


        # -------------------------------------------------
        # 포메이션별 선수 숫자
        # -------------------------------------------------
        'formation_count':
            result['formation_count'],


        # -------------------------------------------------
        # 실제 선발 숫자
        # -------------------------------------------------
        'selected_count':
            result['selected_count'],


        # -------------------------------------------------
        # 해당 포메이션 구성 가능 여부
        # -------------------------------------------------
        'formation_available':
            result['formation_available'],
    }


    return render(
        request,
        'player/best11.html',
        context
    )


# =========================================================
# 선수 팝업 JSON
# =========================================================
def player_info(request, id):


    # =====================================================
    # 1. services.py에서 육각형 계산
    # =====================================================
    result = get_player_radar(
        id
    )


    # =====================================================
    # 2. 2026 기록이 없는 경우
    # =====================================================
    if result is None:

        return JsonResponse(
            {
                'success': False,
                'message': '2026 시즌 기록이 없습니다.'
            }
        )


    player = result[
        'player'
    ]


    stats = result[
        'stats'
    ]


    # =====================================================
    # 3. 선수 사진
    # =====================================================
    photo_url = ''


    if player.photo:

        try:

            photo_url = (
                player.photo.url
            )

        except ValueError:

            photo_url = ''


    # =====================================================
    # 4. JSON
    # =====================================================
    data = {


        'success': True,


        # =================================================
        # 선수정보
        # =================================================
        'player': {

            'id':
                player.id,

            'name':
                player.name,

            'team':
                player.team.team_name,

            'number':
                player.number,

            'position':
                player.position,

            'height':
                player.height,

            'weight':
                player.weight,

            'photo':
                photo_url,
        },


        # =================================================
        # 시즌 기록
        # =================================================
        'stats': {

            'season':
                stats.season,

            'minutes':
                stats.minutes,

            'games':
                stats.games,

            'goals':
                stats.goals,

            'assists':
                stats.assists,

            'attack_points':
                stats.attack_points,

            'shots':
                stats.shots,

            'shots_on_target':
                stats.shots_on_target,

            'key_passes':
                stats.key_passes,

            'dribble_success':
                stats.dribble_success,

            'interceptions':
                stats.interceptions,

            'clearances':
                stats.clearances,

            'recoveries':
                stats.recoveries,
        },


        # =================================================
        # BEST11
        # =================================================
        'best11': {

            'score':
                result[
                    'best11_score'
                ],

            'rank':
                result[
                    'position_rank'
                ],

            'candidate_count':
                result[
                    'position_candidate_count'
                ],
        },


        # =================================================
        # 포지션별 육각형 제목
        # =================================================
        'radar_labels':

            result[
                'radar_labels'
            ],


        # =================================================
        # 포지션별 육각형 점수
        # =================================================
        'radar_scores':

            result[
                'radar_scores'
            ],


        # =================================================
        # 기존 호환용 radar
        # =================================================
        'radar': {

            'attack':
                result[
                    'radar'
                ][
                    'attack'
                ],

            'shooting':
                result[
                    'radar'
                ][
                    'shooting'
                ],

            'passing':
                result[
                    'radar'
                ][
                    'passing'
                ],

            'dribbling':
                result[
                    'radar'
                ][
                    'dribbling'
                ],

            'defense':
                result[
                    'radar'
                ][
                    'defense'
                ],

            'duel':
                result[
                    'radar'
                ][
                    'duel'
                ],
        },


        # =================================================
        # 90분당 기록
        # =================================================
        'per90': {

            'goals':
                result[
                    'raw'
                ][
                    'goals_per90'
                ],

            'assists':
                result[
                    'raw'
                ][
                    'assists_per90'
                ],

            'shots':
                result[
                    'raw'
                ][
                    'shots_per90'
                ],

            'shots_on_target':
                result[
                    'raw'
                ][
                    'shots_on_target_per90'
                ],

            'key_passes':
                result[
                    'raw'
                ][
                    'key_passes_per90'
                ],

            'pass_rate':
                result[
                    'raw'
                ][
                    'pass_rate'
                ],

            'dribble':
                result[
                    'raw'
                ][
                    'dribble_per90'
                ],

            'interceptions':
                result[
                    'raw'
                ][
                    'interceptions_per90'
                ],

            'clearances':
                result[
                    'raw'
                ][
                    'clearances_per90'
                ],

            'recoveries':
                result[
                    'raw'
                ][
                    'recoveries_per90'
                ],
        },
    }


    return JsonResponse(
        data
    )
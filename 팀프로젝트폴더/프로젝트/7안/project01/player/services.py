from player.models import PlayerStats


# =========================================================
# 출전시간 기준
# =========================================================

# 공식 BEST11 점수 / 순위 / TOP10 기준
BEST11_MIN_MINUTES = 600

# 팀별 포메이션 구성 후보 기준
FORMATION_MIN_MINUTES = 450


# =========================================================
# 숫자 안전 변환
# =========================================================

def number(value):

    if value is None:
        return 0.0

    try:
        return float(value)

    except (TypeError, ValueError):
        return 0.0


# =========================================================
# 90분당 기록 계산
# =========================================================

def per90(value, minutes):

    value = number(value)
    minutes = number(minutes)

    if minutes <= 0:
        return 0.0

    return value / minutes * 90


# =========================================================
# 성공률 계산
# =========================================================

def success_rate(success, attempt):

    success = number(success)
    attempt = number(attempt)

    if attempt <= 0:
        return 0.0

    return success / attempt * 100


# =========================================================
# 최고값 기준 점수 변환
#
# BEST11 V1 계산에서 계속 사용
# =========================================================

def normalize_score(value, max_value):

    value = number(value)
    max_value = number(max_value)

    if max_value <= 0:
        return 0.0

    return value / max_value * 100


# =========================================================
# BEST11 평가 지표 (통합 선수 점수)
#
# 컬럼·범주·기본 비율은 player/scoring.py 에 있다.
# BEST11 · 감독 연구실 · 승부예측이 같은 점수를 쓴다.
# 범주 비율은 관리자 > 점수 기준에서 바꿀 수 있다.
# =========================================================

from player import scoring as SC


def get_fw_metrics(stats):
    return SC.metric_values(stats, 'FW')


def get_mf_metrics(stats):
    return SC.metric_values(stats, 'MF')


def get_df_metrics(stats):
    return SC.metric_values(stats, 'DF')


# GK 는 MOM·베스트11을 90분당이 아니라 시즌 누적 횟수로 본다
# (90분당으로 바꾸면 5경기 뛴 선수가 1~2번만 뽑혀도 주전보다 높아짐)
def get_gk_metrics(stats):
    return SC.metric_values(stats, 'GK')


# =========================================================
# BEST11 포지션별 가중치 (컬럼별 = 범주 비율 ÷ 범주 안 컬럼 수)
#
# 아래 상수는 '기본' 범주 비율로 만든 값이다.
# 실제 계산은 position_weights() 로 관리자 설정까지 반영한다.
# =========================================================

FW_WEIGHTS = SC.metric_weights('FW', SC.default_group_weights('FW'))
MF_WEIGHTS = SC.metric_weights('MF', SC.default_group_weights('MF'))
DF_WEIGHTS = SC.metric_weights('DF', SC.default_group_weights('DF'))
GK_WEIGHTS = SC.metric_weights('GK', SC.default_group_weights('GK'))


def position_weights(position):
    """관리자 > 점수 기준의 범주 비율을 반영한 컬럼별 가중치."""
    return SC.metric_weights(position)


# =========================================================
# 한 포지션의 BEST11 점수 계산
# =========================================================

def calculate_position_scores(
    stats_list,
    metric_function,
    weights
):

    rows = []


    # -----------------------------------------------------
    # 1. 선수별 실제 기록 계산
    # -----------------------------------------------------

    for stats in stats_list:

        metrics = metric_function(
            stats
        )

        rows.append({

            'stats': stats,

            'player': stats.player,

            'metrics': metrics,
        })


    # -----------------------------------------------------
    # 2. 컬럼별 분포 (최저·최고·평균) — 적을수록 좋은 컬럼은 뒤집는다
    # -----------------------------------------------------

    normalizer = SC.Normalizer(
        [row['metrics'] for row in rows],
        weights.keys()
    )


    # -----------------------------------------------------
    # 3. 가중치 점수 계산 (0~100)
    # -----------------------------------------------------

    for row in rows:

        total_score = 0.0

        normalized = {}

        contributions = {}


        for metric_name, weight in weights.items():

            score = normalizer.unit(
                metric_name,
                row['metrics'].get(metric_name)
            ) * 100


            contribution = (
                score
                * weight
                / 100
            )


            normalized[metric_name] = score

            contributions[metric_name] = (
                contribution
            )

            total_score += contribution


        row['normalized'] = normalized

        row['contributions'] = contributions

        row['score'] = round(
            total_score,
            2
        )


    # -----------------------------------------------------
    # 4. 높은 점수 순 정렬
    # -----------------------------------------------------

    rows.sort(
        key=lambda row: row['score'],
        reverse=True
    )


    return rows


# =========================================================
# 현재 로스터에서 제외할 선수
# =========================================================

EXCLUDED_PLAYER_IDS = [
    232,  # FC안양 토마스
    222,  # FC안양 황병근
    72,   # 광주FC 박정인
    82,   # 김천상무 백종범
    111,  # 김천상무 이건희
    276,  # 울산HD 이민혁
    290,  # 인천유나이티드 이상현
    383,  # 제주SK FC 기티스
    380,  # 제주SK FC 오재혁
]


# =========================================================
# 2026 BEST11 후보
# =========================================================

def get_best11_candidates():

    stats_list = (
        PlayerStats.objects

        .filter(
            season=2026,
            minutes__gte=BEST11_MIN_MINUTES
        )

        .exclude(
            player_id__in=EXCLUDED_PLAYER_IDS
        )

        .select_related(
            'player',
            'player__team'
        )
    )

    return list(
        stats_list
    )


# =========================================================
# 2026 팀별 포메이션 구성 후보
#
# 공식 BEST11 / TOP10 자격은 600분 이상
# 팀별 포메이션 구성 후보는 450분 이상
# =========================================================

def get_formation_candidates():

    stats_list = (
        PlayerStats.objects

        .filter(
            season=2026,
            minutes__gte=FORMATION_MIN_MINUTES
        )

        .exclude(
            player_id__in=EXCLUDED_PLAYER_IDS
        )

        .select_related(
            'player',
            'player__team'
        )
    )

    return list(
        stats_list
    )


# =========================================================
# 2026 BEST11 계산
# =========================================================

def get_best11():

    # =====================================================
    # 1. BEST11 점수 계산 기준
    #
    # 모든 화면에서 같은 선수는 같은 점수를 사용해야 한다.
    # 따라서 점수 자체는 포메이션 후보와 동일하게
    # 450분 이상 선수 전체를 기준으로 계산한다.
    # =====================================================

    score_candidates = (
        get_formation_candidates()
    )


    fw_list = []
    mf_list = []
    df_list = []
    gk_list = []

    for stats in score_candidates:

        position = (
            stats.player.position
            or ''
        ).strip().upper()

        if position == 'FW':
            fw_list.append(stats)

        elif position == 'MF':
            mf_list.append(stats)

        elif position == 'DF':
            df_list.append(stats)

        elif position == 'GK':
            gk_list.append(stats)


    # =====================================================
    # 2. 450분 이상 리그 전체 기준으로 점수 계산
    # =====================================================

    fw_score_ranking = calculate_position_scores(
        fw_list,
        get_fw_metrics,
        position_weights('FW')
    )

    mf_score_ranking = calculate_position_scores(
        mf_list,
        get_mf_metrics,
        position_weights('MF')
    )

    df_score_ranking = calculate_position_scores(
        df_list,
        get_df_metrics,
        position_weights('DF')
    )

    gk_score_ranking = calculate_position_scores(
        gk_list,
        get_gk_metrics,
        position_weights('GK')
    )


    # =====================================================
    # 3. 공식 BEST11 / TOP10 참가 자격
    #
    # 점수는 450분 전체 기준으로 이미 계산되었다.
    # 공식 랭킹에는 600분 이상 선수만 남긴다.
    #
    # 즉:
    # 450~599분 -> 점수는 존재하지만 공식 랭킹 자격 X
    # 600분 이상 -> 공식 BEST11 / TOP10 자격 O
    # =====================================================

    def official_only(ranking):

        return [
            row
            for row in ranking
            if row['stats'].minutes >= BEST11_MIN_MINUTES
        ]


    fw_ranking = official_only(
        fw_score_ranking
    )

    mf_ranking = official_only(
        mf_score_ranking
    )

    df_ranking = official_only(
        df_score_ranking
    )

    gk_ranking = official_only(
        gk_score_ranking
    )


    # =====================================================
    # 4. 공식 BEST11
    # 4-3-3 기준
    # =====================================================

    best11 = {

        'FW':
            fw_ranking[:3],

        'MF':
            mf_ranking[:3],

        'DF':
            df_ranking[:4],

        'GK':
            gk_ranking[:1],
    }


    # =====================================================
    # 5. 공식 포지션별 전체 랭킹
    # =====================================================

    rankings = {

        'FW':
            fw_ranking,

        'MF':
            mf_ranking,

        'DF':
            df_ranking,

        'GK':
            gk_ranking,
    }


    # =====================================================
    # 6. 결과 반환
    # =====================================================

    return {

        'best11':
            best11,

        'rankings':
            rankings,

        'candidate_count':
            (
                len(fw_ranking)
                +
                len(mf_ranking)
                +
                len(df_ranking)
                +
                len(gk_ranking)
            ),

        'position_count': {

            'FW':
                len(fw_ranking),

            'MF':
                len(mf_ranking),

            'DF':
                len(df_ranking),

            'GK':
                len(gk_ranking),
        },
    }


# =========================================================
# =========================================================
#
# 육각형 그래프 전용 기능
#
# BEST11 점수 계산과는 별개
#
# =========================================================
# =========================================================


# =========================================================
# 백분위 점수
#
# 같은 포지션에서
# 해당 선수보다 낮은 기록을 가진 선수가 얼마나 있는지 계산
#
# 0 ~ 100점
# =========================================================

def percentile_score(value, values):

    if not values:

        return 0.0


    value = number(
        value
    )


    clean_values = [

        number(v)

        for v in values
    ]


    lower_count = sum(

        1

        for v in clean_values

        if v < value
    )


    equal_count = sum(

        1

        for v in clean_values

        if v == value
    )


    # -----------------------------------------------------
    # 동점자는 중간 위치로 계산
    # -----------------------------------------------------

    rank_value = (

        lower_count

        +

        (equal_count * 0.5)
    )


    score = (

        rank_value

        /

        len(clean_values)

        *

        100
    )


    return round(
        score,
        1
    )


# =========================================================
# FW 육각형 원본 기록
# =========================================================

def get_fw_radar_metrics(stats):

    minutes = stats.minutes


    # -----------------------------------------------------
    # 1. 득점력
    # -----------------------------------------------------

    scoring = per90(
        stats.goals,
        minutes
    )


    # -----------------------------------------------------
    # 2. 슈팅
    #
    # 유효슈팅 70%
    # 전체슈팅 30%
    # -----------------------------------------------------

    shooting = (

        per90(
            stats.shots_on_target,
            minutes
        ) * 0.7

        +

        per90(
            stats.shots,
            minutes
        ) * 0.3
    )


    # -----------------------------------------------------
    # 3. 찬스메이킹
    #
    # 도움 60%
    # 키패스 40%
    # -----------------------------------------------------

    chance = (

        per90(
            stats.assists,
            minutes
        ) * 0.6

        +

        per90(
            stats.key_passes,
            minutes
        ) * 0.4
    )


    # -----------------------------------------------------
    # 4. 드리블
    # -----------------------------------------------------

    dribbling = per90(
        stats.dribble_success,
        minutes
    )


    # -----------------------------------------------------
    # 5. 패스
    # -----------------------------------------------------

    passing = success_rate(
        stats.pass_success,
        stats.pass_attempt
    )


    # -----------------------------------------------------
    # 6. 경합
    # -----------------------------------------------------

    duel = (

        per90(
            stats.aerial_duel_success,
            minutes
        ) * 0.5

        +

        per90(
            stats.ground_duel_success,
            minutes
        ) * 0.5
    )


    return {

        'scoring': scoring,

        'shooting': shooting,

        'chance': chance,

        'dribbling': dribbling,

        'passing': passing,

        'duel': duel,
    }


# =========================================================
# MF 육각형 원본 기록
# =========================================================

def get_mf_radar_metrics(stats):

    minutes = stats.minutes


    # -----------------------------------------------------
    # 1. 공격포인트
    # -----------------------------------------------------

    attack = (

        per90(
            stats.goals,
            minutes
        )

        +

        per90(
            stats.assists,
            minutes
        )
    )


    # -----------------------------------------------------
    # 2. 찬스메이킹
    # -----------------------------------------------------

    chance = (

        per90(
            stats.key_passes,
            minutes
        ) * 0.7

        +

        per90(
            stats.assists,
            minutes
        ) * 0.3
    )


    # -----------------------------------------------------
    # 3. 패스
    # -----------------------------------------------------

    passing = success_rate(
        stats.pass_success,
        stats.pass_attempt
    )


    # -----------------------------------------------------
    # 4. 드리블
    # -----------------------------------------------------

    dribbling = per90(
        stats.dribble_success,
        minutes
    )


    # -----------------------------------------------------
    # 5. 볼회수
    # -----------------------------------------------------

    recovery = (

        per90(
            stats.recoveries,
            minutes
        ) * 0.7

        +

        per90(
            stats.interceptions,
            minutes
        ) * 0.3
    )


    # -----------------------------------------------------
    # 6. 경합
    # -----------------------------------------------------

    duel = (

        per90(
            stats.aerial_duel_success,
            minutes
        ) * 0.5

        +

        per90(
            stats.ground_duel_success,
            minutes
        ) * 0.5
    )


    return {

        'attack': attack,

        'chance': chance,

        'passing': passing,

        'dribbling': dribbling,

        'recovery': recovery,

        'duel': duel,
    }


# =========================================================
# DF 육각형 원본 기록
# =========================================================

def get_df_radar_metrics(stats):

    minutes = stats.minutes


    # -----------------------------------------------------
    # 1. 수비
    # -----------------------------------------------------

    defense = (

        per90(
            stats.clearances,
            minutes
        ) * 0.45

        +

        per90(
            stats.interceptions,
            minutes
        ) * 0.35

        +

        per90(
            stats.defensive_blocks,
            minutes
        ) * 0.20
    )


    # -----------------------------------------------------
    # 2. 태클
    # -----------------------------------------------------

    tackle = per90(
        stats.tackle_success,
        minutes
    )


    # -----------------------------------------------------
    # 3. 인터셉트
    # -----------------------------------------------------

    interception = per90(
        stats.interceptions,
        minutes
    )


    # -----------------------------------------------------
    # 4. 경합
    # -----------------------------------------------------

    duel = (

        per90(
            stats.aerial_duel_success,
            minutes
        ) * 0.5

        +

        per90(
            stats.ground_duel_success,
            minutes
        ) * 0.5
    )


    # -----------------------------------------------------
    # 5. 빌드업
    # -----------------------------------------------------

    buildup = success_rate(
        stats.pass_success,
        stats.pass_attempt
    )


    # -----------------------------------------------------
    # 6. 활동량
    # -----------------------------------------------------

    activity = per90(
        stats.recoveries,
        minutes
    )


    return {

        'defense': defense,

        'tackle': tackle,

        'interception': interception,

        'duel': duel,

        'buildup': buildup,

        'activity': activity,
    }


# =========================================================
# GK 육각형 원본 기록
#
# 주의:
# 선방 / 실점 / 클린시트 자료가 없기 때문에
# 현재 DB에서 사용 가능한 데이터로 만든 임시 평가
# =========================================================

def get_gk_radar_metrics(stats):

    minutes = stats.minutes


    # -----------------------------------------------------
    # 1. 패스
    # -----------------------------------------------------

    passing = success_rate(
        stats.pass_success,
        stats.pass_attempt
    )


    # -----------------------------------------------------
    # 2. 롱패스
    # -----------------------------------------------------

    long_pass = per90(
        stats.long_pass_success,
        minutes
    )


    # -----------------------------------------------------
    # 3. 볼회수
    # -----------------------------------------------------

    recovery = per90(
        stats.recoveries,
        minutes
    )


    # -----------------------------------------------------
    # 4. 클리어링
    # -----------------------------------------------------

    clearance = per90(
        stats.clearances,
        minutes
    )


    # -----------------------------------------------------
    # 5. 출전시간
    # -----------------------------------------------------

    playing_time = number(
        stats.minutes
    )


    # -----------------------------------------------------
    # 6. 평균평점
    # -----------------------------------------------------

    rating = number(
        stats.average_rating
    )


    return {

        'passing': passing,

        'long_pass': long_pass,

        'recovery': recovery,

        'clearance': clearance,

        'playing_time': playing_time,

        'rating': rating,
    }


# =========================================================
# 포지션별 육각형 설정
# =========================================================

def get_position_radar_config(position):


    # -----------------------------------------------------
    # FW
    # -----------------------------------------------------

    if position == 'FW':

        return {

            'function':
                get_fw_radar_metrics,

            'labels': [

                '득점력',

                '슈팅',

                '찬스메이킹',

                '드리블',

                '패스',

                '경합',
            ]
        }


    # -----------------------------------------------------
    # MF
    # -----------------------------------------------------

    elif position == 'MF':

        return {

            'function':
                get_mf_radar_metrics,

            'labels': [

                '공격포인트',

                '찬스메이킹',

                '패스',

                '드리블',

                '볼회수',

                '경합',
            ]
        }


    # -----------------------------------------------------
    # DF
    # -----------------------------------------------------

    elif position == 'DF':

        return {

            'function':
                get_df_radar_metrics,

            'labels': [

                '수비',

                '태클',

                '인터셉트',

                '경합',

                '빌드업',

                '활동량',
            ]
        }


    # -----------------------------------------------------
    # GK
    # -----------------------------------------------------

    elif position == 'GK':

        return {

            'function':
                get_gk_radar_metrics,

            'labels': [

                '패스',

                '롱패스',

                '볼회수',

                '클리어링',

                '출전시간',

                '평점',
            ]
        }


    return None


# =========================================================
# 선수 1명의 육각형 점수
# =========================================================

def get_player_radar(player_id):


    # =====================================================
    # 1. 선수의 2026 기록
    # =====================================================

    stats = (

        PlayerStats.objects

        .filter(
            player_id=player_id,
            season=2026
        )

        .select_related(
            'player',
            'player__team'
        )

        .first()
    )


    if stats is None:

        return None


    player = stats.player


    position = (
        player.position
        or ''
    ).strip().upper()


    # =====================================================
    # 2. 통합 점수 범주 (BEST11 점수·관리자 범주와 같은 기준)
    #
    # 그래프 꼭짓점 = 포지션별 범주 4~6개 (FW·DF·GK 5개, MF 6개)
    # 범주 점수 = 범주 안 컬럼들의 0~100 점수 평균
    # BEST11 점수 = 범주 점수 × 범주 비율 의 합 → 그래프와 점수가 같은 기준
    # =====================================================

    if position not in SC.POSITIONS:

        return None


    groups = SC.GROUPS[position]

    labels = [
        group_label
        for _key, group_label, _weight, _keys in groups
    ]


    # =====================================================
    # 3. 비교 대상: BEST11 점수와 같은 450분 이상 같은 포지션 선수
    # =====================================================

    same_position_stats = [

        candidate

        for candidate in get_formation_candidates()

        if (
            candidate.player.position
            or ''
        ).strip().upper() == position
    ]


    if not same_position_stats:

        return None


    keys = SC.metric_keys(position)

    normalizer = SC.Normalizer(
        [
            SC.metric_values(candidate, position)
            for candidate in same_position_stats
        ],
        keys,
    )


    # =====================================================
    # 4. 이 선수의 범주 점수 (0~100)
    # =====================================================

    player_values = SC.metric_values(
        stats,
        position
    )

    radar_scores = []

    radar_virtual = []

    for _key, _label, _weight, group_keys in groups:

        unit_scores = [
            normalizer.unit(
                key,
                player_values.get(key)
            ) * 100
            for key in group_keys
        ]

        radar_scores.append(
            round(
                sum(unit_scores) / len(unit_scores),
                1
            )
        )

        # 가상 데이터 컬럼이 들어 있는 범주 표시
        radar_virtual.append(
            any(
                SC.METRIC_DEFS[key][5]
                for key in group_keys
            )
        )


    # 현재 범주 비율 (관리자 > 점수 기준, 합계 100으로 환산)
    current_weights = SC.group_weights(position)

    weight_total = sum(current_weights.values()) or 1

    radar_weights = [
        round(
            current_weights.get(key, 0) / weight_total * 100,
            1
        )
        for key, _label, _weight, _keys in groups
    ]


    # =====================================================
    # 5. BEST11 점수 / 순위 (600분 이상 공식 순위)
    # =====================================================

    best11_result = (
        get_best11()
    )

    ranking = (
        best11_result[
            'rankings'
        ]
        .get(
            position,
            []
        )
    )

    best11_score = None

    position_rank = None

    for index, row in enumerate(
        ranking,
        start=1
    ):

        if row['player'].id == player.id:

            best11_score = (
                row['score']
            )

            position_rank = (
                index
            )

            break


    # 기존 views.py 호환용: 범주 키 → 점수
    radar = {
        key: score
        for (key, _label, _weight, _keys), score in zip(groups, radar_scores)
    }


    # =====================================================
    # 9. 반환
    # =====================================================

    return {

        'player':
            player,

        'stats':
            stats,

        'position':
            position,


        # -------------------------------------------------
        # BEST11
        # -------------------------------------------------

        'best11_score':
            best11_score,

        'position_rank':
            position_rank,

        'position_candidate_count':
            len(
                ranking
            ),


        # -------------------------------------------------
        # 새로운 포지션별 육각형
        # -------------------------------------------------

        'radar_labels':
            labels,

        'radar_scores':
            radar_scores,

        'radar_weights':
            radar_weights,

        'radar_virtual':
            radar_virtual,


        # -------------------------------------------------
        # 기존 views.py 호환용
        # -------------------------------------------------

        'radar':
            radar,


        # -------------------------------------------------
        # 실제 90분당 기록
        # -------------------------------------------------

        'raw': {


            'goals_per90': round(

                per90(
                    stats.goals,
                    stats.minutes
                ),

                2
            ),


            'assists_per90': round(

                per90(
                    stats.assists,
                    stats.minutes
                ),

                2
            ),


            'shots_per90': round(

                per90(
                    stats.shots,
                    stats.minutes
                ),

                2
            ),


            'shots_on_target_per90': round(

                per90(
                    stats.shots_on_target,
                    stats.minutes
                ),

                2
            ),


            'key_passes_per90': round(

                per90(
                    stats.key_passes,
                    stats.minutes
                ),

                2
            ),


            'pass_rate': round(

                success_rate(
                    stats.pass_success,
                    stats.pass_attempt
                ),

                1
            ),


            'dribble_per90': round(

                per90(
                    stats.dribble_success,
                    stats.minutes
                ),

                2
            ),


            'interceptions_per90': round(

                per90(
                    stats.interceptions,
                    stats.minutes
                ),

                2
            ),


            'clearances_per90': round(

                per90(
                    stats.clearances,
                    stats.minutes
                ),

                2
            ),


            'recoveries_per90': round(

                per90(
                    stats.recoveries,
                    stats.minutes
                ),

                2
            ),
        }
    }

# =========================================================
# =========================================================
#
# 구단별 BEST11 + 포메이션 선택 기능
#
# =========================================================
# =========================================================


# =========================================================
# 사용할 포메이션
#
# 현재 DB 포지션이
# FW / MF / DF / GK까지만 구분되어 있기 때문에
# 세부 포지션(ST, CAM, CDM 등)은 아직 구분하지 않는다.
# =========================================================

FORMATIONS = {

    # -----------------------------------------------------
    # 4-3-3
    #
    # FW 3
    # MF 3
    # DF 4
    # GK 1
    # -----------------------------------------------------
    '4-3-3': {

        'FW': 3,
        'MF': 3,
        'DF': 4,
        'GK': 1,
    },


    # -----------------------------------------------------
    # 4-4-2
    # -----------------------------------------------------
    '4-4-2': {

        'FW': 2,
        'MF': 4,
        'DF': 4,
        'GK': 1,
    },


    # -----------------------------------------------------
    # 4-2-3-1
    #
    # 현재 DB에서는
    # MF를 CAM / CDM으로 나누지 않기 때문에
    # MF 5명으로 계산
    # -----------------------------------------------------
    '4-2-3-1': {

        'FW': 1,
        'MF': 5,
        'DF': 4,
        'GK': 1,
    },


    # -----------------------------------------------------
    # 3-4-3
    # -----------------------------------------------------
    '3-4-3': {

        'FW': 3,
        'MF': 4,
        'DF': 3,
        'GK': 1,
    },


    # -----------------------------------------------------
    # 3-5-2
    # -----------------------------------------------------
    '3-5-2': {

        'FW': 2,
        'MF': 5,
        'DF': 3,
        'GK': 1,
    },


    # -----------------------------------------------------
    # 5-3-2
    # -----------------------------------------------------
    '5-3-2': {

        'FW': 2,
        'MF': 3,
        'DF': 5,
        'GK': 1,
    },
}


# =========================================================
# 포메이션 목록 가져오기
# =========================================================

def get_formations():

    return FORMATIONS


# =========================================================
# 구단 + 포메이션 BEST11 계산
#
# team_id
#     None 또는 '' → 전체 K리그
#     숫자          → 해당 구단
#
# formation
#     4-3-3
#     4-4-2
#     4-2-3-1
#     3-4-3
#     3-5-2
#     5-3-2
# =========================================================

def get_filtered_best11(
    team_id=None,
    formation='4-3-3'
):

    # =====================================================
    # 1. 잘못된 포메이션이면 기본 4-3-3
    # =====================================================

    if formation not in FORMATIONS:
        formation = '4-3-3'

    formation_count = FORMATIONS[formation]


    # =====================================================
    # 2. 포메이션 후보
    #
    # 450분 이상 선수를 가져온다.
    # =====================================================

    formation_candidates = (
        get_formation_candidates()
    )


    # =====================================================
    # 3. 점수 계산 기준
    #
    # 중요:
    # 팀을 먼저 필터링하지 않는다.
    #
    # K리그 전체 450분 이상 후보를 기준으로
    # 포지션별 최고값을 구해 점수를 계산한다.
    #
    # 따라서 같은 선수의 점수는
    # FC서울을 선택하든 다른 포메이션을 선택하든
    # 바뀌지 않는다.
    # =====================================================

    fw_all = []
    mf_all = []
    df_all = []
    gk_all = []

    for stats in formation_candidates:

        position = (
            stats.player.position
            or ''
        ).strip().upper()

        if position == 'FW':
            fw_all.append(stats)

        elif position == 'MF':
            mf_all.append(stats)

        elif position == 'DF':
            df_all.append(stats)

        elif position == 'GK':
            gk_all.append(stats)


    fw_ranking_all = calculate_position_scores(
        fw_all,
        get_fw_metrics,
        position_weights('FW')
    )

    mf_ranking_all = calculate_position_scores(
        mf_all,
        get_mf_metrics,
        position_weights('MF')
    )

    df_ranking_all = calculate_position_scores(
        df_all,
        get_df_metrics,
        position_weights('DF')
    )

    gk_ranking_all = calculate_position_scores(
        gk_all,
        get_gk_metrics,
        position_weights('GK')
    )


    # =====================================================
    # 4. team_id 숫자 변환
    # =====================================================

    if team_id:

        try:
            team_id = int(team_id)

        except (
            TypeError,
            ValueError
        ):
            team_id = None


    # =====================================================
    # 5. 점수 계산이 끝난 뒤 구단 필터링
    #
    # 핵심:
    # 점수는 리그 전체 기준으로 이미 계산되어 있다.
    # 여기서는 선택한 구단 선수만 남긴다.
    # 점수를 다시 계산하지 않는다.
    # =====================================================

    def filter_team(ranking):

        if not team_id:
            return ranking

        return [
            row
            for row in ranking
            if row['player'].team_id == team_id
        ]


    fw_ranking = filter_team(
        fw_ranking_all
    )

    mf_ranking = filter_team(
        mf_ranking_all
    )

    df_ranking = filter_team(
        df_ranking_all
    )

    gk_ranking = filter_team(
        gk_ranking_all
    )


    # =====================================================
    # 6. 선택된 구단의 실제 후보 목록
    # =====================================================

    if team_id:

        candidates = [
            stats
            for stats in formation_candidates
            if stats.player.team_id == team_id
        ]

    else:

        candidates = formation_candidates


    fw_list = []
    mf_list = []
    df_list = []
    gk_list = []

    for stats in candidates:

        position = (
            stats.player.position
            or ''
        ).strip().upper()

        if position == 'FW':
            fw_list.append(stats)

        elif position == 'MF':
            mf_list.append(stats)

        elif position == 'DF':
            df_list.append(stats)

        elif position == 'GK':
            gk_list.append(stats)


    # =====================================================
    # 7. 선택 포메이션만큼 선수 선택
    # =====================================================

    best11 = {

        'FW':
            fw_ranking[
                :
                formation_count['FW']
            ],

        'MF':
            mf_ranking[
                :
                formation_count['MF']
            ],

        'DF':
            df_ranking[
                :
                formation_count['DF']
            ],

        'GK':
            gk_ranking[
                :
                formation_count['GK']
            ],
    }


    # =====================================================
    # 8. 포지션별 순위
    #
    # 주의:
    # 이 rankings는 포메이션용 450분 후보 순위다.
    # 공식 BEST11/TOP10 600분 순위는 get_best11()이 담당한다.
    # =====================================================

    rankings = {

        'FW':
            fw_ranking,

        'MF':
            mf_ranking,

        'DF':
            df_ranking,

        'GK':
            gk_ranking,
    }


    # =====================================================
    # 9. 실제 선택된 선수 숫자
    # =====================================================

    selected_count = (
        len(best11['FW'])
        +
        len(best11['MF'])
        +
        len(best11['DF'])
        +
        len(best11['GK'])
    )


    # =====================================================
    # 10. 포메이션 구성 가능 여부
    # =====================================================

    formation_available = (
        len(fw_ranking)
        >= formation_count['FW']

        and

        len(mf_ranking)
        >= formation_count['MF']

        and

        len(df_ranking)
        >= formation_count['DF']

        and

        len(gk_ranking)
        >= formation_count['GK']
    )


    # =====================================================
    # 11. 결과 반환
    # =====================================================

    return {

        'best11':
            best11,

        'rankings':
            rankings,

        'candidate_count':
            len(candidates),

        'position_count': {

            'FW':
                len(fw_list),

            'MF':
                len(mf_list),

            'DF':
                len(df_list),

            'GK':
                len(gk_list),
        },

        'formation':
            formation,

        'formation_count':
            formation_count,

        'team_id':
            team_id,

        'selected_count':
            selected_count,

        'formation_available':
            formation_available,
    }


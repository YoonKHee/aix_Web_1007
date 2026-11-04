"""선수 기록 비교용 데이터.

그래프 표시에만 사용하며 승부 예측 가중치는 변경하지 않습니다.
"""

import math

from player.gk_evaluation import match_record
from player.models import PlayerStats
from player.services import get_formation_candidates


# 항목 ID, 표시 이름, DB 필드, 단위, 계산 방식
AXES = {
    'FW': (
        ('goals', '득점', 'goals', '/90분', 'per90'),
        (
            'shots_on_target',
            '유효슈팅',
            'shots_on_target',
            '/90분',
            'per90',
        ),
        ('shots', '슈팅', 'shots', '/90분', 'per90'),
        ('assists', '도움', 'assists', '/90분', 'per90'),
        ('key_passes', '키패스', 'key_passes', '/90분', 'per90'),
        (
            'dribble',
            '드리블 성공',
            'dribble_success',
            '/90분',
            'per90',
        ),
    ),

    'MF': (
        ('assists', '도움', 'assists', '/90분', 'per90'),
        ('key_passes', '키패스', 'key_passes', '/90분', 'per90'),
        (
            'pass_rate',
            '패스 성공률',
            'pass_success',
            '%',
            'pass_rate',
        ),
        ('recoveries', '볼 회수', 'recoveries', '/90분', 'per90'),
        (
            'interceptions',
            '인터셉트',
            'interceptions',
            '/90분',
            'per90',
        ),
        (
            'dribble',
            '드리블 성공',
            'dribble_success',
            '/90분',
            'per90',
        ),
    ),

    'DF': (
        (
            'clearances',
            '클리어링',
            'clearances',
            '/90분',
            'per90',
        ),
        (
            'interceptions',
            '인터셉트',
            'interceptions',
            '/90분',
            'per90',
        ),
        ('recoveries', '볼 회수', 'recoveries', '/90분', 'per90'),
        ('tackle', '태클 성공', 'tackle_success', '/90분', 'per90'),
        (
            'aerial_duel',
            '공중 경합 성공',
            'aerial_duel_success',
            '/90분',
            'per90',
        ),
        (
            'ground_duel',
            '지상 경합 성공',
            'ground_duel_success',
            '/90분',
            'per90',
        ),
    ),

    'GK': (
        ('rating', '평균 평점', 'average_rating', '점', 'rating'),
        (
            'pass_rate',
            '패스 성공률',
            'pass_success',
            '%',
            'pass_rate',
        ),
        (
            'long_pass',
            '롱패스 성공',
            'long_pass_success',
            '/90분',
            'per90',
        ),
        (
            'clearances',
            '클리어링',
            'clearances',
            '/90분',
            'per90',
        ),
        (
            'conceded',
            '경기당 실점↓',
            '',
            '골/경기',
            'conceded',
        ),
        (
            'clean_sheet_rate',
            '무실점 경기',
            '',
            '%',
            'clean_sheet_rate',
        ),
    ),
}


def raw_value(stats, axis, snapshot):
    """실제 기록을 반환합니다. 미확인 기록은 None입니다."""

    if stats is None or stats.minutes <= 0:
        return None

    key, label, field, unit, calculation = axis

    if calculation in ('conceded', 'clean_sheet_rate'):
        record = match_record(stats, snapshot)

        if record is None:
            return None

        if calculation == 'conceded':
            return (
                record['goals_conceded']
                / record['games']
            )

        return (
            record['clean_sheets']
            / record['games']
            * 100
        )

    if calculation == 'pass_rate':
        if stats.pass_attempt <= 0:
            return None

        value = (
            stats.pass_success
            / stats.pass_attempt
            * 100
        )

    else:
        value = getattr(stats, field, None)

        if value is None:
            return None

        if calculation == 'rating' and value <= 0:
            return None

        if calculation == 'per90':
            value = value / stats.minutes * 90

    if not math.isfinite(value) or value < 0:
        return None

    return float(value)


def comparable_value(value, key):
    """그래프에서 바깥쪽일수록 높은 평가가 되도록 변환합니다."""

    if value is None:
        return None

    # 실점은 적을수록 좋습니다.
    # 실제 실점 수치는 raw 값으로 별도 표시합니다.
    if key == 'conceded':
        return 1 / (1 + value)

    return value


def attach_comparisons(context, official_id, roster):
    """선수 명단에 자리별 비교 데이터를 추가한 사본을 반환합니다."""

    candidates = get_formation_candidates()

    maxima = {}
    reference_counts = {}

    # 같은 자리의 리그 450분 이상 후보를 공통 비교 기준으로 사용합니다.
    for role, axes in AXES.items():
        group = [
            stats
            for stats in candidates
            if (
                stats.player.position or ''
            ).strip().upper() == role
        ]

        maxima[role] = {}
        reference_counts[role] = len(group)

        for axis in axes:
            key = axis[0]

            values = [
                comparable_value(
                    raw_value(stats, axis, context.snapshot),
                    key,
                )
                for stats in group
            ]

            available = [
                value
                for value in values
                if value is not None
            ]

            maxima[role][key] = max(
                available,
                default=None,
            )

    records = list(
        PlayerStats.objects.filter(
            season=2026,
            player__team=context.db_teams[official_id],
        ).select_related(
            'player',
            'player__team',
        )
    )

    by_id = {}
    duplicates = set()

    for stats in records:
        if stats.player_id in by_id:
            duplicates.add(stats.player_id)

        by_id[stats.player_id] = stats

    result = []

    for player in roster:
        if player['id'] in duplicates:
            stats = None
        else:
            stats = by_id.get(player['id'])

        comparisons = {}

        for role in player['scores']:
            axes = []

            for axis in AXES[role]:
                key, label, field, unit, calculation = axis

                raw = raw_value(
                    stats,
                    axis,
                    context.snapshot,
                )

                value = comparable_value(raw, key)
                maximum = maxima[role][key]

                score = None

                # 미확인 자료나 비교 기준 부재를 0점으로 바꾸지 않습니다.
                if (
                    value is not None
                    and maximum is not None
                    and maximum > 0
                ):
                    score = min(
                        100.0,
                        max(
                            0.0,
                            value / maximum * 100,
                        ),
                    )

                axes.append({
                    'key': key,
                    'label': label,
                    'unit': unit,
                    'raw': (
                        round(raw, 4)
                        if raw is not None
                        else None
                    ),
                    'score': (
                        round(score, 2)
                        if score is not None
                        else None
                    ),
                    'lower_is_better': key == 'conceded',
                })

            if stats is None or stats.minutes <= 0:
                note = '시즌 기록 없음 또는 출전시간 없음'

            elif stats.minutes < 600:
                note = (
                    '600분 미만: 적은 출전시간으로 '
                    '기록 변동이 클 수 있습니다.'
                )

            else:
                note = ''

            comparisons[role] = {
                'axes': axes,
                'reference_count': reference_counts[role],
                'note': note,
            }

        result.append({
            **player,
            'comparison': comparisons,
        })

    return result
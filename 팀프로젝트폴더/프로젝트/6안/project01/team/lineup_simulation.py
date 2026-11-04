"""선수 구성과 컨디션에 따른 가상 경기 시뮬레이션."""

from collections import Counter
from datetime import date
import math

from player.gk_evaluation import (
    TEAM_NAMES,
    load_snapshot,
    match_record,
    official_metrics,
)
from player.models import Player, PlayerStats
from player.services import (
    FORMATIONS,
    FW_WEIGHTS,
    MF_WEIGHTS,
    DF_WEIGHTS,
    GK_WEIGHTS,
    get_formation_candidates,
    calculate_position_scores,
    get_fw_metrics,
    get_mf_metrics,
    get_df_metrics,
    get_gk_metrics,
    get_filtered_best11,
)
from team.models import Team
from team.match_prediction import (
    PredictionUnavailable,
    load_matches,
    load_bundle,
    team_options,
    forecast,
    features_for,
    predict_probabilities,
)


ROLE_ORDER = ('GK', 'DF', 'MF', 'FW')

ROLE_NAMES = {
    'FW': '공격',
    'MF': '중원',
    'DF': '수비',
    'GK': '골키퍼',
}

CONDITIONS = {
    'bad': 0.9,
    'normal': 1.0,
    'good': 1.1,
}

CONDITION_NAMES = {
    'bad': '안 좋음',
    'normal': '보통',
    'good': '좋음',
}

# 실제 경기에서 학습한 값이 아닌 시뮬레이션 규칙입니다.
PART_WEIGHTS = {
    'FW': 0.30,
    'MF': 0.25,
    'DF': 0.30,
    'GK': 0.15,
}

MAX_PROBABILITY_CHANGE = 0.08

METHODS = {
    'FW': (get_fw_metrics, FW_WEIGHTS),
    'MF': (get_mf_metrics, MF_WEIGHTS),
    'DF': (get_df_metrics, DF_WEIGHTS),
    'GK': (get_gk_metrics, GK_WEIGHTS),
}


def slots(formation):
    if formation not in FORMATIONS:
        raise PredictionUnavailable(
            '지원하는 포메이션을 선택하세요.'
        )

    return [
        role
        for role in ROLE_ORDER
        for _ in range(FORMATIONS[formation][role])
    ]


class SimulationContext:
    def __init__(self):
        self.matches, digest = load_matches()
        self.bundle = load_bundle(digest)
        self.teams = team_options(self.matches)
        self.snapshot = load_snapshot()

        self.references = {}
        candidates = get_formation_candidates()

        for role, (function, weights) in METHODS.items():
            group = [
                stats
                for stats in candidates
                if (stats.player.position or '').strip().upper() == role
            ]

            rows = calculate_position_scores(
                group,
                function,
                weights,
            )

            maxima = {}

            if rows:
                maxima = {
                    key: max(
                        row['metrics'][key]
                        for row in rows
                    )
                    for key in rows[0]['metrics']
                }

            self.references[role] = {
                'maxima': maxima,
                'weights': weights,
                'official_gk': (
                    bool(rows)
                    and 'conceding' in rows[0]['metrics']
                ),
            }

        # 공식 구단명과 기존 DB 구단을 명시적 대응표로 연결합니다.
        by_name = {}

        for team in Team.objects.all():
            name = TEAM_NAMES.get(team.team_name)

            if name in by_name:
                raise PredictionUnavailable(
                    '중복 구단 연결을 확인해야 합니다.'
                )

            if name:
                by_name[name] = team

        self.db_teams = {
            team['id']: by_name[team['name']]
            for team in self.teams
            if team['name'] in by_name
        }

        self._rosters = {}

    def ability(self, stats, role):
        if stats is None or stats.minutes <= 0:
            return 50.0, '기록 없음: 중립 지수 50 사용'

        reference = self.references[role]
        maxima = reference['maxima']

        if not maxima:
            return 50.0, '비교 기록 없음: 중립 지수 50 사용'

        if role == 'GK' and reference['official_gk']:
            record = match_record(
                stats,
                self.snapshot,
            )

            if not record:
                return (
                    50.0,
                    'GK 공식 기록 미일치: 중립 지수 50 사용',
                )

            values = official_metrics(
                stats,
                record,
            )

            weights = {
                'conceding': 40,
                'clean_sheet_rate': 40,
                'rating': 20,
            }

        else:
            function, weights = METHODS[role]
            values = function(stats)

        raw = sum(
            (
                values[key] / maxima[key]
                if maxima[key] > 0
                else 0
            ) * weight
            for key, weight in weights.items()
        )

        raw = max(0.0, min(100.0, raw))

        # 짧은 출전시간의 기록은 중립값 쪽으로 보정합니다.
        confidence = min(
            1.0,
            stats.minutes / 600,
        )

        score = 50 + confidence * (raw - 50)

        note = (
            '600분 미만: 기록 지수를 중립값 쪽으로 보정'
            if confidence < 1
            else ''
        )

        return round(score, 3), note

    def roster(self, official_id):
        if official_id in self._rosters:
            return self._rosters[official_id]

        if official_id not in self.db_teams:
            raise PredictionUnavailable(
                '선택한 팀의 선수 명단을 찾을 수 없습니다.'
            )

        team = self.db_teams[official_id]

        players = list(
            Player.objects
            .filter(team=team)
            .order_by(
                'position',
                'number',
                'id',
            )
        )

        records = list(
            PlayerStats.objects
            .filter(
                season=2026,
                player__team=team,
            )
            .select_related(
                'player',
                'player__team',
            )
        )

        counts = Counter(
            stats.player_id
            for stats in records
        )

        by_id = {
            stats.player_id: stats
            for stats in records
            if counts[stats.player_id] == 1
        }

        result = []

        for player in players:
            position = (
                player.position or ''
            ).strip().upper()

            if position not in ROLE_ORDER:
                continue

            stats = by_id.get(player.id)

            abilities = {
                role: self.ability(stats, role)
                for role in ROLE_ORDER
                if (role == 'GK') == (position == 'GK')
            }

            result.append({
                'id': player.id,
                'name': player.name,
                'number': player.number,
                'position': position,
                'photo': (
                    player.photo.url
                    if player.photo
                    else ''
                ),
                'minutes': (
                    stats.minutes
                    if stats
                    else 0
                ),
                'scores': {
                    role: value[0]
                    for role, value in abilities.items()
                },
                'notes': {
                    role: value[1]
                    for role, value in abilities.items()
                },
            })

        self._rosters[official_id] = result

        return result

    def recommended(self, official_id, formation):
        roster = self.roster(official_id)

        existing = get_filtered_best11(
            self.db_teams[official_id].id,
            formation,
        )['best11']

        preferred = {
            role: [
                row['player'].id
                for row in existing[role]
            ]
            for role in ROLE_ORDER
        }

        chosen = []
        used = set()

        # 기존 BEST11 선발 결과를 우선 사용합니다.
        # 부족한 자리는 같은 구단의 선수로 채웁니다.
        for role in slots(formation):
            eligible = [
                player
                for player in roster
                if player['id'] not in used
                and role in player['scores']
            ]

            eligible.sort(
                key=lambda player: (
                    player['id'] in preferred[role],
                    (
                        -preferred[role].index(player['id'])
                        if player['id'] in preferred[role]
                        else 0
                    ),
                    player['position'] == role,
                    player['minutes'] >= 450,
                    player['scores'][role],
                    -player['id'],
                ),
                reverse=True,
            )

            if not eligible:
                raise PredictionUnavailable(
                    '이 팀은 포메이션을 구성할 선수 명단이 부족합니다.'
                )

            player = eligible[0]

            chosen.append({
                'id': player['id'],
                'condition': 'normal',
            })

            used.add(player['id'])

        return {
            'formation': formation,
            'players': chosen,
        }

    def validate_lineup(self, official_id, specification):
        if not isinstance(specification, dict):
            raise PredictionUnavailable(
                '선수 구성을 확인하세요.'
            )

        formation = specification.get('formation')

        if not isinstance(formation, str):
            raise PredictionUnavailable(
                '포메이션을 확인하세요.'
            )

        roles = slots(formation)
        selected = specification.get('players')

        if not isinstance(selected, list) or len(selected) != 11:
            raise PredictionUnavailable(
                '선발 선수는 정확히 11명이어야 합니다.'
            )

        roster = {
            player['id']: player
            for player in self.roster(official_id)
        }

        used = set()
        lineup = []

        for role, item in zip(roles, selected):
            if (
                not isinstance(item, dict)
                or type(item.get('id')) is not int
            ):
                raise PredictionUnavailable(
                    '선수 ID를 확인하세요.'
                )

            player_id = item['id']
            condition = item.get('condition')

            if player_id not in roster:
                raise PredictionUnavailable(
                    '선택한 구단 소속 선수만 사용할 수 있습니다.'
                )

            if player_id in used:
                raise PredictionUnavailable(
                    '같은 선수를 중복 선택할 수 없습니다.'
                )

            if (
                not isinstance(condition, str)
                or condition not in CONDITIONS
            ):
                raise PredictionUnavailable(
                    '컨디션은 안 좋음·보통·좋음 중에서 선택하세요.'
                )

            player = roster[player_id]

            if role not in player['scores']:
                raise PredictionUnavailable(
                    '골키퍼는 GK 자리에, 필드 선수는 필드 자리에 배치하세요.'
                )

            used.add(player_id)

            score = player['scores'][role]

            lineup.append({
                **player,
                'role': role,
                'condition': condition,
                'condition_label': CONDITION_NAMES[condition],
                'base_score': score,
                'effective_score': round(
                    min(
                        100.0,
                        score * CONDITIONS[condition],
                    ),
                    3,
                ),
                'note': player['notes'].get(role, ''),
            })

        return lineup


def department_scores(lineup):
    return {
        role: (
            sum(
                player['effective_score']
                for player in lineup
                if player['role'] == role
            )
            / sum(
                player['role'] == role
                for player in lineup
            )
        )
        for role in ROLE_ORDER
    }


def adjust_probabilities(prior, home_change, away_change):
    tilt = max(
        -0.35,
        min(
            0.35,
            1.5 * (home_change - away_change),
        ),
    )

    weighted = {
        'H': prior['H'] * math.exp(tilt),
        'D': prior['D'],
        'A': prior['A'] * math.exp(-tilt),
    }

    total = sum(weighted.values())

    adjusted = {
        key: value / total
        for key, value in weighted.items()
    }

    gap = max(
        abs(adjusted[key] - prior[key])
        for key in prior
    )

    factor = (
        min(
            1.0,
            MAX_PROBABILITY_CHANGE / gap,
        )
        if gap
        else 1.0
    )

    return {
        key: (
            prior[key]
            + factor * (adjusted[key] - prior[key])
        )
        for key in prior
    }


def percent_rows(probabilities):
    keys = ('H', 'D', 'A')

    values = {
        key: int(probabilities[key] * 1000)
        for key in keys
    }

    remaining = 1000 - sum(values.values())

    order = sorted(
        keys,
        key=lambda key: (
            probabilities[key] * 1000 - values[key]
        ),
        reverse=True,
    )

    for key in order[:remaining]:
        values[key] += 1

    return {
        key: values[key] / 10
        for key in keys
    }


def bounded_display(prior, adjusted):
    """반올림 후에도 결과별 최대 8%포인트 변화를 지킵니다."""

    before = percent_rows(prior)

    units = {
        key: round(value * 10)
        for key, value in percent_rows(adjusted).items()
    }

    lower = {
        key: max(
            0,
            round(before[key] * 10) - 80,
        )
        for key in before
    }

    upper = {
        key: min(
            1000,
            round(before[key] * 10) + 80,
        )
        for key in before
    }

    units = {
        key: max(
            lower[key],
            min(upper[key], value),
        )
        for key, value in units.items()
    }

    while sum(units.values()) != 1000:
        direction = (
            1
            if sum(units.values()) < 1000
            else -1
        )

        eligible = [
            key
            for key in units
            if (
                units[key] < upper[key]
                if direction > 0
                else units[key] > lower[key]
            )
        ]

        key = max(
            eligible,
            key=lambda item: (
                direction
                * (
                    adjusted[item] * 1000
                    - units[item]
                )
            ),
        )

        units[key] += direction

    return before, {
        key: value / 10
        for key, value in units.items()
    }


def simulate(context, payload):
    if not isinstance(payload, dict):
        raise PredictionUnavailable(
            '설정 형식을 확인하세요.'
        )

    home_id = payload.get('home_team')
    away_id = payload.get('away_team')

    if (
        not isinstance(home_id, str)
        or not isinstance(away_id, str)
    ):
        raise PredictionUnavailable(
            '홈팀과 원정팀을 선택하세요.'
        )

    try:
        target = date.fromisoformat(
            payload.get('date', '')
        )

    except (TypeError, ValueError) as exc:
        raise PredictionUnavailable(
            '경기 날짜를 확인하세요.'
        ) from exc

    base = forecast(
        context.matches,
        context.bundle,
        home_id,
        away_id,
        target,
    )

    features, _ = features_for(
        context.matches,
        home_id,
        away_id,
        target,
    )

    prior = predict_probabilities(
        context.bundle,
        features,
    )

    teams = []

    for side, team_id in [
        ('home', home_id),
        ('away', away_id),
    ]:
        normal = context.validate_lineup(
            team_id,
            context.recommended(
                team_id,
                '4-3-3',
            ),
        )

        edited = context.validate_lineup(
            team_id,
            payload.get(side),
        )

        original = department_scores(normal)
        current = department_scores(edited)

        parts = [
            {
                'role': role,
                'label': ROLE_NAMES[role],
                'weight': PART_WEIGHTS[role] * 100,
                'before': round(original[role], 2),
                'after': round(current[role], 2),
                'change': round(
                    current[role] - original[role],
                    2,
                ),
                'contribution': round(
                    (
                        current[role]
                        - original[role]
                    ) * PART_WEIGHTS[role],
                    3,
                ),
            }
            for role in ROLE_ORDER
        ]

        change = sum(
            (
                current[role]
                - original[role]
            ) / 100 * PART_WEIGHTS[role]
            for role in ROLE_ORDER
        )

        changes = []

        normal_by_id = {
            player['id']: player
            for player in normal
        }

        for player in edited:
            previous = normal_by_id.get(
                player['id']
            )

            if (
                previous is None
                or previous['role'] != player['role']
                or player['condition'] != 'normal'
            ):
                reason = (
                    '선발 변경'
                    if previous is None
                    else '배치 변경'
                    if previous['role'] != player['role']
                    else '컨디션 변경'
                )

                changes.append({
                    'name': player['name'],
                    'role': player['role'],
                    'condition': player['condition_label'],
                    'reason': reason,
                })

        teams.append({
            'formation': payload[side]['formation'],
            'parts': parts,
            'change': change,
            'lineup': edited,
            'changes': changes,
            'baseline_lineup': [
                {
                    'id': player['id'],
                    'name': player['name'],
                    'role': player['role'],
                }
                for player in normal
            ],
            'low_evidence_count': sum(
                bool(player['note'])
                for player in edited
            ),
        })

    adjusted = adjust_probabilities(
        prior,
        teams[0]['change'],
        teams[1]['change'],
    )

    before_percent, after_percent = bounded_display(
        prior,
        adjusted,
    )

    evaluation = context.bundle['evaluation']

    return {
        'home_name': base['home_name'],
        'away_name': base['away_name'],
        'date': base['date'],
        'long_gap': base['long_gap'],
        'stale_days': base['stale_days'],
        'probabilities': [
            {
                'label': label,
                'code': key,
                'before': before_percent[key],
                'after': after_percent[key],
                'change': round(
                    after_percent[key]
                    - before_percent[key],
                    1,
                ),
            }
            for key, label in [
                ('H', '홈승'),
                ('D', '무승부'),
                ('A', '원정승'),
            ]
        ],
        'home': teams[0],
        'away': teams[1],
        'baseline_accuracy': round(
            evaluation['model']['accuracy'] * 100,
            1,
        ),
        'test_count': evaluation['test_count'],
    }
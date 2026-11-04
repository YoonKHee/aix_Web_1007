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
    get_filtered_best11,
    number,
    per90,
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
    poisson_probabilities,
)
from team.sim_detail import DetailIndex
from team import virtual_stats


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


def get_gk_metrics(stats):
    """모의 경기 전용 GK 지표 (5안 방식 그대로: MOM·베스트11은 90분당).

    BEST11 화면(player/services.py)은 GK를 시즌 누적 횟수로 평가하도록 바뀌었지만,
    모의 경기는 BEST11과 별개로 5안의 계산 방식을 유지한다.
    """
    return {
        'rating': number(stats.average_rating),
        'mom': per90(stats.mom, stats.minutes),
        'best11': per90(stats.best11_count, stats.minutes),
        'minutes': number(stats.minutes),
    }

METHODS = {
    'FW': (get_fw_metrics, FW_WEIGHTS),
    'MF': (get_mf_metrics, MF_WEIGHTS),
    'DF': (get_df_metrics, DF_WEIGHTS),
    'GK': (get_gk_metrics, GK_WEIGHTS),
}


def simulation_methods():
    """모의 경기에서 쓸 (지표 함수, 가중치). 가중치는 관리자 > 점수 기준에서 저장한 값을 쓴다.

    관리자 점수 기준은 모의 경기(승부예측)에만 적용되고 BEST11 화면과 감독 연구실은 영향을 받지 않는다.
    저장한 값이 없거나 읽기에 실패하면 기본 가중치(player/services.py)를 그대로 쓴다.
    """
    try:
        from manager import config
        return {
            role: (function, config.weights_for(role, weights))
            for role, (function, weights) in METHODS.items()
        }
    except Exception:
        return dict(METHODS)


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
        self.detail = DetailIndex()          # 포지션별 추가 컬럼 점수 (실제 기록 + 가상 데이터)

        self.references = {}
        candidates = get_formation_candidates()
        self.methods = simulation_methods()

        for role, (function, weights) in self.methods.items():
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
            function, weights = self.methods[role]
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
        extra_w = extra_weight()

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
                'detail': self.detail.player(stats),
                # 화면에 보여 줄 '종합 점수' = 기존 역할 지수 (100-비중)% + 추가 지표 점수 비중%
                # (계산은 기존 방식 그대로: 기존 점수 → 선수 구성 보정, 추가 지표 → 추가 요소 확률)
                'total_scores': {
                    role: round((1 - extra_w) * value[0] + extra_w * self.detail.player(stats)['score'], 1)
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


# ---------------------------------------------------------------- 추가 컬럼 (승부예측 정밀화)
# 포지션별 추가 컬럼 점수로 따로 계산한 승·무·패 확률을 최종 확률에 이 비중만큼 섞는다.
EXTRA_WEIGHT = 0.30          # 기본값. 관리자 > 점수 기준에서 0~50% 로 바꿀 수 있다
EXTRA_FACTOR_RANGE = (0.7, 1.4)     # 예상 득점을 늘리거나 줄이는 최대 범위
FORM_FACTOR_RANGE = 0.15            # 내 BEST11 가상 최근 5경기 흐름으로 예상 득점을 ±15%까지


def extra_weight():
    """관리자 > 점수 기준에 저장한 '추가 요소 비중'(0~50%). 없으면 EXTRA_WEIGHT."""
    try:
        from manager import config
        return config.extra_weight(EXTRA_WEIGHT * 100) / 100
    except Exception:
        return EXTRA_WEIGHT


def _mean(values, default=50.0):
    values = list(values)
    return sum(values) / len(values) if values else default


def team_extra(lineup):
    """라인업의 추가 컬럼 공격·수비 지수 (50 = 리그 주전급 평균). 컨디션도 반영한다."""
    def score(p):
        return min(100.0, p['detail']['score'] * CONDITIONS[p['condition']])

    attack = _mean(score(p) for p in lineup if p['role'] in ('FW', 'MF'))
    df = _mean(score(p) for p in lineup if p['role'] == 'DF')
    gk = _mean(score(p) for p in lineup if p['role'] == 'GK')
    return {'attack': round(attack, 1), 'defense': round(0.6 * df + 0.4 * gk, 1)}


def extra_probabilities(base_home, base_away, home, away, home_form=1.0):
    """기본 예상 득점을 추가 컬럼 지수로 조정한 뒤 포아송으로 승·무·패 확률을 낸다."""
    lo, hi = EXTRA_FACTOR_RANGE
    fh = max(lo, min(hi, (home['attack'] / 50) / max(1.0, away['defense']) * 50)) * home_form
    fa = max(lo, min(hi, (away['attack'] / 50) / max(1.0, home['defense']) * 50))
    goals_home = max(0.05, min(4.5, base_home * fh))
    goals_away = max(0.05, min(4.5, base_away * fa))
    return poisson_probabilities(goals_home, goals_away), {
        'home_goals': round(goals_home, 2), 'away_goals': round(goals_away, 2),
        'home_factor': round(fh, 3), 'away_factor': round(fa, 3)}


def best11_recent(lineup, home_name, opponents):
    """내 BEST11의 '가상' 최근 5경기. 같은 11명이면 항상 같은 결과가 나온다(선수 ID가 씨앗).
    라인업 능력이 높을수록 이길 확률이 조금 높게 만든다. 실제 경기 결과가 아니다."""
    import random

    ids = sorted(p['id'] for p in lineup)
    rng = random.Random('best11-' + ','.join(map(str, ids)))
    strength = _mean(p['effective_score'] for p in lineup)
    win = max(0.15, min(0.65, 0.38 + (strength - 50) / 100 * 0.8))
    draw = 0.27
    games = []
    for _ in range(5):
        r = rng.random()
        result = '승' if r < win else '무' if r < win + draw else '패'
        a = rng.choice([0, 1, 1, 2, 2, 3])
        if result == '승':
            b = rng.randint(0, max(0, a - 1)) if a else 0
            a = max(a, b + 1)
        elif result == '무':
            b = a
        else:
            b = a + rng.choice([1, 1, 2])
        games.append({'opponent': rng.choice(opponents) if opponents else '상대', 'score': f'{a}:{b}', 'result': result})
    points = sum(3 if g['result'] == '승' else 1 if g['result'] == '무' else 0 for g in games) / 5
    form = 1 + FORM_FACTOR_RANGE * max(-1.0, min(1.0, (points - 1.4) / 1.6))
    return {'team': home_name, 'games': games, 'points_per_game': round(points, 2), 'form_factor': round(form, 3),
            'note': '가상 데이터: 내 BEST11이 치른 것으로 가정한 재미용 최근 5경기입니다. 실제 경기 결과가 아닙니다.'}


def best11_weighted(context, home_id, normal, edited, settings, prior, away_change, extra_after, weight):
    """내 BEST11 가중치(감독 연구실 설정)로 홈팀 선수를 평가했을 때의 확률.
    BEST11 화면과 같은 엔진(player.lab)으로 선수 점수(능력 + 케미)를 다시 계산해 선수 구성 보정에 쓴다.
    기본 비교 대상(기본 추천 라인업)도 같은 가중치로 평가해서 공정하게 비교한다."""
    from player.lab import chemistry as CH
    from player.lab import service as LAB

    team = context.db_teams.get(home_id)
    c = LAB.Ctx({'team': str(team.pk) if team else '', 'preset': settings.get('preset', 'default'),
                 'mult': settings.get('mult') or {}, 'chem_scale': settings.get('chem', 1.0),
                 'exp_scale': settings.get('exp', 1.5)})

    def scores(lineup):
        profiles = c.lineup_profiles([p['id'] for p in lineup])
        chem = c.score_lineup(profiles)[1] if profiles else {'players': {}}
        out = {}
        for p in lineup:
            pid = p['id']
            if pid in chem['players']:
                value = CH.final_score(c.adj(pid), chem['players'][pid]['bonus'])
            else:
                value = c.ability.get(pid, p['base_score'])
            out[pid] = min(100.0, value * CONDITIONS[p['condition']])
        return out

    def parts(lineup, sc):
        return {role: _mean(sc[p['id']] for p in lineup if p['role'] == role) for role in ROLE_ORDER}

    before, after = parts(normal, scores(normal)), parts(edited, scores(edited))
    change = sum((after[r] - before[r]) / 100 * PART_WEIGHTS[r] for r in ROLE_ORDER)
    adjusted = adjust_probabilities(prior, change, away_change)
    final = {k: (1 - weight) * adjusted[k] + weight * extra_after[k] for k in prior}
    return final, {'change': round(change * 100, 2),
                   'parts': [{'role': r, 'label': ROLE_NAMES[r], 'before': round(before[r], 1), 'after': round(after[r], 1)}
                             for r in ROLE_ORDER]}


def extra_players(lineup):
    return [{'name': p['name'], 'role': p['role'], 'score': p['detail']['score'], 'note': p['detail'].get('note', ''),
             'metrics': p['detail']['metrics']} for p in lineup]


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
            '_normal': normal,
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

    # 추가 컬럼 확률 (10%) — 기본 라인업(비교 기준)과 지금 라인업 각각 계산
    base_home, base_away = features[-2], features[-1]
    normal_h, normal_a = team_extra(teams[0]['_normal']), team_extra(teams[1]['_normal'])
    now_h, now_a = team_extra(teams[0]['lineup']), team_extra(teams[1]['lineup'])
    recent = None
    if payload.get('home_best11'):
        opponents = [t['name'] for t in context.teams if t['id'] not in (home_id,)]
        recent = best11_recent(teams[0]['lineup'], base['home_name'], opponents)
    extra_before, _ = extra_probabilities(base_home, base_away, normal_h, normal_a)
    extra_after, goals = extra_probabilities(base_home, base_away, now_h, now_a,
                                             recent['form_factor'] if recent else 1.0)
    w = extra_weight()
    final_before = {k: (1 - w) * prior[k] + w * extra_before[k] for k in prior}
    final_after = {k: (1 - w) * adjusted[k] + w * extra_after[k] for k in prior}

    # 내 BEST11 가중치 반영 확률 (BEST11 화면에서 넘어온 내 라인업일 때만)
    mine = None
    settings = payload.get('home_best11_settings')
    if payload.get('home_best11') and isinstance(settings, dict):
        mine_final, mine_info = best11_weighted(context, home_id, teams[0]['_normal'], teams[0]['lineup'], settings,
                                                prior, teams[1]['change'], extra_after, w)
        _, mine_percent = bounded_display(final_before, mine_final)
        mine = {**mine_info, 'probabilities': mine_percent}

    for t in teams:
        t.pop('_normal', None)

    before_percent, after_percent = bounded_display(
        final_before,
        final_after,
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
        'extra': {
            'weight': round(w * 100),
            'base_goals': {'home': round(base_home, 2), 'away': round(base_away, 2)},
            'goals': goals,
            'home': now_h,
            'away': now_a,
            'probabilities': {k: round(v * 100, 1) for k, v in extra_after.items()},
            'players': {'home': extra_players(teams[0]['lineup']), 'away': extra_players(teams[1]['lineup'])},
            'virtual_note': virtual_stats.NOTE,
        },
        'best11_recent': recent,
        'best11_weighted': mine,
        'baseline_accuracy': round(
            evaluation['model']['accuracy'] * 100,
            1,
        ),
        'test_count': evaluation['test_count'],
    }
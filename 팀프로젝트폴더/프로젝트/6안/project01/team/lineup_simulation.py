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


OUT_OF_POSITION = 0.9     # 원래 포지션이 아닌 자리에 세우면 점수 ×0.9


def player_score_context(settings=None):
    """감독 연구실 엔진. settings 가 없으면 기본 설정 = BEST11 화면에 보이는 점수와 같다."""
    from player.lab import service as LAB
    s = settings or {}
    return LAB.Ctx({'preset': s.get('preset', 'default'), 'mult': s.get('mult') or {},
                    'chem_scale': s.get('chem', 1.0), 'exp_scale': s.get('exp', 1.5)})


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

        # 통합 선수 점수: BEST11 화면(감독 연구실 기본 설정)과 같은 값
        self.lab = player_score_context()
        self._reference = None
        finished = [m for m in self.matches if m.get('home_goals') is not None]
        self.league_goals = {
            'home': _mean((m['home_goals'] for m in finished), 1.4),
            'away': _mean((m['away_goals'] for m in finished), 1.1),
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

    def lineup_reference(self, ability=None):
        """기준(=1.0배): 12개 구단 기본 선발 라인업(4-3-3) 공격·수비 지수의 평균.
        ability 를 주면(내 BEST11 가중치) 같은 라인업을 그 점수로 평가한 평균."""
        if ability is None and self._reference:
            return self._reference
        rows = []
        for official_id in self.db_teams:
            try:
                lineup = self.validate_lineup(official_id, self.recommended(official_id, '4-3-3'))
            except PredictionUnavailable:
                continue
            rows.append(team_strength(lineup, ability))
        ref = {'attack': _mean(r['attack'] for r in rows), 'defense': _mean(r['defense'] for r in rows)}
        if ability is None:
            self._reference = ref
        return ref

    def ability(self, stats, role):
        """선수 점수 = BEST11 화면과 같은 통합 점수. 원래 포지션이 아닌 자리는 ×0.9."""
        if stats is None or stats.minutes <= 0:
            return 50.0, '기록 없음: 중립 점수 50 사용'
        base = self.lab.ability.get(stats.player_id)
        if base is None:
            return 50.0, '비교 기록 없음: 중립 점수 50 사용'
        position = (stats.player.position or '').strip().upper()
        notes = []
        score = base
        if role != position:
            score = base * OUT_OF_POSITION
            notes.append(f'원래 포지션({position})이 아니라 ×{OUT_OF_POSITION}')
        if stats.minutes < 450:
            notes.append('450분 미만: 평균 쪽으로 보정')
        return round(score, 3), ' · '.join(notes)

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


# ---------------------------------------------------------------- 추가 컬럼 (승부예측 정밀화)
# 포지션별 추가 컬럼 점수로 따로 계산한 승·무·패 확률을 최종 확률에 이 비중만큼 섞는다.
PLAYER_WEIGHT = 0.30                # 기본: 팀 기록 70% + 선수 능력치 30%. 관리자 > 점수 기준에서 0~60%
PLAYER_FACTOR_RANGE = (0.5, 2.0)    # 선수 능력치로 리그 평균 득점을 늘리거나 줄이는 최대 범위
FORM_FACTOR_RANGE = 0.15            # 내 BEST11 가상 최근 5경기 흐름으로 예상 득점을 ±15%까지


def player_weight():
    """승부예측에서 '선수 능력치' 부분의 비중. 관리자 > 점수 기준의 값(없으면 30%)."""
    try:
        from manager import config
        return config.player_weight(PLAYER_WEIGHT * 100) / 100
    except Exception:
        return PLAYER_WEIGHT


def _mean(values, default=50.0):
    values = list(values)
    return sum(values) / len(values) if values else default


def team_strength(lineup, scores=None):
    """라인업의 공격·수비 지수. 공격 = 공격수·미드필더 평균, 수비 = 수비수 60% + 골키퍼 40%.
    scores 를 주면(내 BEST11 가중치) 그 점수로, 아니면 통합 점수(effective_score)로 계산한다."""
    def score(p):
        if scores is None:
            return p['effective_score']
        base = scores.get(p['id'], p['base_score'])
        if p['role'] != p['position']:
            base *= OUT_OF_POSITION
        return min(100.0, base * CONDITIONS[p['condition']])

    attack = _mean(score(p) for p in lineup if p['role'] in ('FW', 'MF'))
    df = _mean(score(p) for p in lineup if p['role'] == 'DF')
    gk = _mean(score(p) for p in lineup if p['role'] == 'GK')
    return {'attack': round(attack, 1), 'defense': round(0.6 * df + 0.4 * gk, 1)}


def player_probabilities(base_home, base_away, home, away, reference, home_form=1.0):
    """선수 능력치만으로 본 확률 (팀 기록과 독립).
    리그 평균 홈·원정 득점(base)에서 출발해, 공격 지수 ÷ 상대 수비 지수 (기본 선발 라인업 평균 대비)로
    예상 득점을 조정한 뒤 포아송으로 승·무·패를 낸다."""
    lo, hi = PLAYER_FACTOR_RANGE

    def factor(att, opp_def):
        ratio = (att / max(1.0, reference['attack'])) / max(0.05, opp_def / max(1.0, reference['defense']))
        return max(lo, min(hi, ratio))

    fh = factor(home['attack'], away['defense']) * home_form
    fa = factor(away['attack'], home['defense'])
    goals_home = max(0.2, min(4.0, base_home * fh))
    goals_away = max(0.2, min(4.0, base_away * fa))
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

    # 최종 확률 = 팀 기록(최근 5경기·홈/원정·시즌 → 포아송) (1-w) + 선수 능력치 w
    w = player_weight()
    base_home, base_away = context.league_goals['home'], context.league_goals['away']
    ref = context.lineup_reference()
    normal_h, normal_a = team_strength(teams[0]['_normal']), team_strength(teams[1]['_normal'])
    now_h, now_a = team_strength(teams[0]['lineup']), team_strength(teams[1]['lineup'])
    recent = None
    if payload.get('home_best11'):
        opponents = [t['name'] for t in context.teams if t['id'] != home_id]
        recent = best11_recent(teams[0]['lineup'], base['home_name'], opponents)
    form = recent['form_factor'] if recent else 1.0
    player_before, _ = player_probabilities(base_home, base_away, normal_h, normal_a, ref)
    player_after, goals = player_probabilities(base_home, base_away, now_h, now_a, ref, form)
    final_before = {k: (1 - w) * prior[k] + w * player_before[k] for k in prior}
    final_after = {k: (1 - w) * prior[k] + w * player_after[k] for k in prior}

    # 내 BEST11 가중치 반영 확률 (BEST11 화면에서 넘어온 내 라인업일 때만)
    mine = None
    settings = payload.get('home_best11_settings')
    if payload.get('home_best11') and isinstance(settings, dict):
        mine_ctx = player_score_context(settings)
        mine_ref = context.lineup_reference(mine_ctx.ability)   # 같은 가중치로 본 기본 선발 라인업 평균
        mine_h = team_strength(teams[0]['lineup'], mine_ctx.ability)
        # 원정팀은 기본 점수 그대로이므로, 홈 지수만 '내 가중치 리그 평균 대비'로 바꿔 같은 기준에 맞춘다
        scaled_h = {'attack': mine_h['attack'] / max(1.0, mine_ref['attack']) * ref['attack'],
                    'defense': mine_h['defense'] / max(1.0, mine_ref['defense']) * ref['defense']}
        mine_player, mine_goals = player_probabilities(base_home, base_away, scaled_h, now_a, ref, form)
        mine_final = {k: (1 - w) * prior[k] + w * mine_player[k] for k in prior}
        mine = {'probabilities': percent_rows(mine_final), 'home': mine_h, 'goals': mine_goals,
                'change': round(scaled_h['attack'] - now_h['attack'], 1)}

    for t in teams:
        t.pop('_normal', None)

    before_percent, after_percent = percent_rows(final_before), percent_rows(final_after)

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
        'player_part': {
            'weight': round(w * 100),
            'base_goals': {'home': round(base_home, 2), 'away': round(base_away, 2)},
            'goals': goals,
            'home': now_h,
            'away': now_a,
            'reference': {k: round(v, 1) for k, v in ref.items()},
            'probabilities': {k: round(v * 100, 1) for k, v in player_after.items()},
            'team_probabilities': {k: round(v * 100, 1) for k, v in prior.items()},
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
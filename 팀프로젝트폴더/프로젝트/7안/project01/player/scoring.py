"""BEST11 · 감독 연구실 · 승부예측이 함께 쓰는 '통합 선수 점수'의 컬럼과 범주.

- 포지션마다 컬럼(기존 기록 + 추가 컬럼)을 큰 범주 4~6개로 묶는다.
- 범주 비율(가중치)은 관리자 > 점수 기준에서 기본값을, BEST11 화면의 감독 연구실에서 내 설정을 바꿀 수 있다.
- 범주 안의 컬럼은 같은 비중이다 (범주 비율 ÷ 컬럼 수).
- 점수 계산(정규화): 같은 포지션 비교 대상 안에서 (값 - 최저) ÷ (최고 - 최저) → 0~1.
  '적을수록 좋은' 컬럼(실점·오프사이드·경고 등)은 1에서 뺀다. 값이 없는 선수는 비교 대상 평균을 쓴다.
- '가상' 표시 컬럼은 team/virtual_stats.py 의 가상 데이터다 (실제 기록 아님).
"""

import math

PER90 = 'per90'
RATE = 'rate'
VALUE = 'value'


def _p90(value, minutes):
    return (value / minutes * 90) if minutes and minutes > 0 else None


def _rate(success, attempt, minimum):
    return (success / attempt) if attempt and attempt >= minimum else None


def _full_match_rate(s):
    games = s.games or 0
    return min(1.0, s.minutes / (games * 90)) if games else None


def _age_fit(s):
    """전성기 나이(26~30세)에 가까울수록 높다. 범위 안이면 0, 벗어난 만큼 마이너스."""
    from team.virtual_stats import player_age
    age = player_age(s.player)
    return -max(0, abs(age - 28) - 2) if age else None


def _cards_90(s):
    return _p90(s.yellow_cards + 2 * s.red_cards, s.minutes)


def _v(key):
    return lambda s, v: v.get(key)


# 키: (이름, 계산(stats, 가상데이터) -> 값, 높을수록 좋음?, 단위, 시즌 합계 필드, 가상?)
METRIC_DEFS = {
    'goals90': ('득점', lambda s, v: _p90(s.goals, s.minutes), True, PER90, 'goals', False),
    'sot90': ('유효슈팅', lambda s, v: _p90(s.shots_on_target, s.minutes), True, PER90, 'shots_on_target', False),
    'shots90': ('슈팅', lambda s, v: _p90(s.shots, s.minutes), True, PER90, 'shots', False),
    'shot_acc': ('슈팅 정확도', lambda s, v: _rate(s.shots_on_target, s.shots, 5), True, RATE, None, False),
    'conv': ('득점 전환율', lambda s, v: _rate(s.goals, s.shots, 5), True, RATE, None, False),
    'box': ('박스 안 슈팅 비율', lambda s, v: _rate(s.shots_inside_box, s.shots, 5), True, RATE, None, False),
    'ast90': ('도움', lambda s, v: _p90(s.assists, s.minutes), True, PER90, 'assists', False),
    'kp90': ('키패스', lambda s, v: _p90(s.key_passes, s.minutes), True, PER90, 'key_passes', False),
    'drb90': ('드리블 성공', lambda s, v: _p90(s.dribble_success, s.minutes), True, PER90, 'dribble_success', False),
    'drb_rate': ('드리블 성공률', lambda s, v: _rate(s.dribble_success, s.dribble_attempt, 5), True, RATE, None, False),
    'fw90': ('피파울', lambda s, v: _p90(s.fouls_won, s.minutes), True, PER90, 'fouls_won', False),
    'aer_rate': ('공중볼 성공률', lambda s, v: _rate(s.aerial_duel_success, s.aerial_duel_attempt, 5), True, RATE, None, False),
    'aer90': ('공중볼 성공', lambda s, v: _p90(s.aerial_duel_success, s.minutes), True, PER90, 'aerial_duel_success', False),
    'gnd90': ('지상볼 성공', lambda s, v: _p90(s.ground_duel_success, s.minutes), True, PER90, 'ground_duel_success', False),
    'gnd_rate': ('지상볼 성공률', lambda s, v: _rate(s.ground_duel_success, s.ground_duel_attempt, 5), True, RATE, None, False),
    'tkl90': ('태클 성공', lambda s, v: _p90(s.tackle_success, s.minutes), True, PER90, 'tackle_success', False),
    'tkl_rate': ('태클 성공률', lambda s, v: _rate(s.tackle_success, s.tackle_attempt, 5), True, RATE, None, False),
    'dist': ('활동량 km(가상)', _v('distance_km_90'), True, PER90, None, True),
    'spr': ('스프린트(가상)', _v('sprints_90'), True, PER90, None, True),
    'full': ('풀타임 소화율', lambda s, v: _full_match_rate(s), True, RATE, None, False),
    'height': ('키', lambda s, v: s.player.height or None, True, VALUE, None, False),
    'weight': ('몸무게', lambda s, v: s.player.weight or None, True, VALUE, None, False),
    'off90': ('오프사이드', lambda s, v: _p90(s.offsides, s.minutes), False, PER90, 'offsides', False),
    'cards90': ('경고·퇴장', lambda s, v: _cards_90(s), False, PER90, 'yellow_cards', False),
    'disc90': ('파울·경고', lambda s, v: _p90(s.fouls + 3 * s.yellow_cards + 6 * s.red_cards, s.minutes), False, PER90, 'fouls', False),
    'age': ('나이(전성기 26~30세)', lambda s, v: _age_fit(s), True, VALUE, None, False),
    'pass_rate': ('패스 정확도', lambda s, v: _rate(s.pass_success, s.pass_attempt, 30), True, RATE, None, False),
    'fwd_rate': ('전진 패스 성공률', lambda s, v: _rate(s.forward_pass_success, s.forward_pass_attempt, 15), True, RATE, None, False),
    'att3_rate': ('공격 진영 패스 성공률', lambda s, v: _rate(s.attacking_third_pass_success, s.attacking_third_pass_attempt, 15), True, RATE, None, False),
    'long_rate': ('롱패스 성공률', lambda s, v: _rate(s.long_pass_success, s.long_pass_attempt, 10), True, RATE, None, False),
    'cross_rate': ('크로스 성공률', lambda s, v: _rate(s.cross_success, s.cross_attempt, 5), True, RATE, None, False),
    'def3_rate': ('수비 진영 패스 성공률', lambda s, v: _rate(s.defensive_third_pass_success, s.defensive_third_pass_attempt, 15), True, RATE, None, False),
    'rec90': ('볼 회수', lambda s, v: _p90(s.recoveries, s.minutes), True, PER90, 'recoveries', False),
    'int90': ('인터셉트', lambda s, v: _p90(s.interceptions, s.minutes), True, PER90, 'interceptions', False),
    'clr90': ('클리어링', lambda s, v: _p90(s.clearances, s.minutes), True, PER90, 'clearances', False),
    'dblk90': ('수비 차단', lambda s, v: _p90(s.defensive_blocks, s.minutes), True, PER90, 'defensive_blocks', False),
    'blk90': ('블록', lambda s, v: _p90(s.blocks, s.minutes), True, PER90, 'blocks', False),
    'miss90': ('볼 미스', lambda s, v: _p90(s.ball_misses, s.minutes), False, PER90, 'ball_misses', False),
    'rating': ('평균 평점', lambda s, v: s.average_rating or None, True, VALUE, None, False),
    'best11': ('베스트11 선정(누적)', lambda s, v: float(s.best11_count or 0), True, VALUE, 'best11_count', False),
    'mom': ('MOM(누적)', lambda s, v: float(s.mom or 0), True, VALUE, 'mom', False),
    'minutes': ('출전시간', lambda s, v: float(s.minutes or 0), True, VALUE, None, False),
    'save_rate': ('선방률(가상)', _v('save_rate'), True, RATE, None, True),
    'saves90': ('선방(가상)', _v('saves_90'), True, PER90, None, True),
    'conc90': ('실점(가상)', _v('conceded_90'), False, PER90, None, True),
    'cs_rate': ('무실점 비율(가상)', _v('clean_sheet_rate'), True, RATE, None, True),
    'claims': ('펀칭+캐칭(가상)', lambda s, v: (v['punches_90'] + v['catches_90']) if 'punches_90' in v else None, True, PER90, None, True),
}

# 포지션별 범주: (범주 키, 이름, 기본 비율, [컬럼 키])
GROUPS = {
    'FW': [
        ('finishing', '득점력', 45, ['goals90', 'sot90', 'shots90', 'shot_acc', 'conv', 'box']),
        ('creation', '찬스 창출', 22, ['ast90', 'kp90']),
        ('dribbling', '개인기·돌파', 13, ['drb90', 'drb_rate', 'fw90']),
        ('physical', '피지컬·체력', 12, ['aer_rate', 'dist', 'spr', 'full', 'height', 'weight']),
        ('discipline', '규율·경험', 8, ['off90', 'cards90', 'age']),
    ],
    'MF': [
        ('attack', '공격·찬스 창출', 38, ['ast90', 'kp90', 'goals90']),
        ('passing', '패스·빌드업', 18, ['pass_rate', 'fwd_rate', 'att3_rate', 'long_rate', 'cross_rate']),
        ('defending', '수비 가담', 18, ['rec90', 'int90', 'tkl_rate']),
        ('dribbling', '개인기', 8, ['drb90', 'drb_rate', 'miss90']),
        ('physical', '피지컬·체력', 12, ['dist', 'spr', 'full', 'height', 'weight']),
        ('discipline', '규율·경험', 6, ['cards90', 'age']),
    ],
    'DF': [
        ('actions', '수비 액션', 45, ['clr90', 'int90', 'rec90', 'dblk90', 'blk90']),
        ('duels', '경합·태클', 28, ['tkl90', 'tkl_rate', 'aer90', 'aer_rate', 'gnd90', 'gnd_rate']),
        ('buildup', '빌드업', 9, ['def3_rate', 'long_rate']),
        ('physical', '피지컬·체력', 12, ['dist', 'spr', 'full', 'height', 'weight']),
        ('discipline', '규율·경험', 6, ['disc90', 'age']),
    ],
    'GK': [
        ('rating', '경기 평가', 55, ['rating', 'best11', 'mom']),
        ('shotstop', '선방·실점', 20, ['save_rate', 'saves90', 'conc90', 'cs_rate']),
        ('claims', '공중볼 처리', 5, ['claims']),
        ('buildup', '빌드업', 8, ['pass_rate', 'long_rate']),
        ('fitness', '출전·피지컬', 12, ['minutes', 'full', 'height', 'weight', 'age']),
    ],
}
POSITIONS = ('FW', 'MF', 'DF', 'GK')

# 예전 지표 이름 → 새 컬럼 (감독 연구실 프리셋·상대 맞춤이 예전 이름을 쓴다)
OLD_KEYS = {
    'goals': ['goals90'], 'assists': ['ast90'], 'shots_on_target': ['sot90'], 'shots': ['shots90'],
    'key_passes': ['kp90'], 'dribble': ['drb90', 'drb_rate'], 'pass_rate': ['pass_rate', 'fwd_rate', 'att3_rate'],
    'recoveries': ['rec90'], 'interceptions': ['int90'], 'clearances': ['clr90'], 'tackle': ['tkl90', 'tkl_rate'],
    'aerial_duel': ['aer90', 'aer_rate'], 'ground_duel': ['gnd90', 'gnd_rate'], 'defensive_blocks': ['dblk90'],
    'blocks': ['blk90'], 'rating': ['rating'], 'mom': ['mom'], 'best11': ['best11'], 'minutes': ['minutes'],
}

LOWER_BETTER = {k for k, d in METRIC_DEFS.items() if not d[2]}
# 소표본 보정(출전 적은 선수를 평균 쪽으로)에서 빼는 컬럼: 신체·나이·출전 관련
NO_SHRINK = {'minutes', 'height', 'weight', 'age', 'full', 'best11', 'mom'}


def label(key):
    return METRIC_DEFS[key][0] if key in METRIC_DEFS else key


def metric_keys(pos):
    return [k for _g, _l, _w, ks in GROUPS[pos] for k in ks]


def group_of(pos):
    return {k: g for g, _l, _w, ks in GROUPS[pos] for k in ks}


def default_group_weights(pos):
    return {g: float(w) for g, _l, w, _ks in GROUPS[pos]}


def group_weights(pos):
    """범주 비율: 관리자 > 점수 기준에 저장한 값이 있으면 그것, 없으면 기본값."""
    base = default_group_weights(pos)
    try:
        from manager import config
        return config.group_weights_for(pos, base)
    except Exception:
        return base


def metric_weights(pos, groups=None):
    """범주 비율 합을 100으로 환산한 뒤 컬럼별로 나눕니다."""
    groups = group_weights(pos) if groups is None else groups
    values = {g: float(groups.get(g, 0.0)) for g, *_ in GROUPS[pos]}

    if any(not math.isfinite(v) or v < 0 for v in values.values()):
        raise ValueError('범주 비율은 유한한 0 이상의 숫자여야 합니다.')

    total = sum(values.values())

    if not math.isfinite(total) or total <= 0:
        raise ValueError('범주 비율 합은 유한한 양수여야 합니다.')

    return {
        k: values[g] / total * 100 / len(keys)
        for g, label, weight, keys in GROUPS[pos]
        for k in keys
    }


def metric_values(stats, pos):
    from team.virtual_stats import for_player
    v = for_player(stats.player_id)
    out = {}
    for k in metric_keys(pos):
        try:
            out[k] = METRIC_DEFS[k][1](stats, v)
        except (TypeError, ZeroDivisionError):
            out[k] = None
    return out


class Normalizer:
    """비교 대상(같은 포지션) 값 분포로 0~1 점수를 만든다."""

    def __init__(self, values_list, keys):
        self.lo, self.hi, self.mean = {}, {}, {}
        for k in keys:
            xs = [vals[k] for vals in values_list if vals.get(k) is not None]
            if xs:
                self.lo[k], self.hi[k], self.mean[k] = min(xs), max(xs), sum(xs) / len(xs)

    def fill(self, k, x):
        return x if x is not None else self.mean.get(k)

    def unit(self, k, x):
        x = self.fill(k, x)
        if x is None or k not in self.lo:
            return 0.5
        lo, hi = self.lo[k], self.hi[k]
        n = 0.5 if hi == lo else max(0.0, min(1.0, (x - lo) / (hi - lo)))
        return 1 - n if k in LOWER_BETTER else n

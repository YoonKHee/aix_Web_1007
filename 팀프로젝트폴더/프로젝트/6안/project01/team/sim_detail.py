"""승부예측(모의 경기)용 포지션별 '추가 컬럼' 점수.

- 실제 기록(PlayerStats)에서 계산하는 지표(source='real')와
  가상 데이터(team/virtual_stats.py)에서 오는 지표(source='virtual')를 함께 쓴다.
- 각 지표는 같은 포지션 주전급(450분 이상) 선수들 사이의 백분위(0~100)로 바꾸고, 그 평균이 선수의 '추가 지표 점수'다.
- 출전시간이 600분보다 적으면 점수를 50(중립) 쪽으로 당긴다 (모의 경기 기존 규칙과 같음).
- BEST11 화면·감독 연구실은 이 파일을 쓰지 않는다 (승부예측 전용).
"""

from player.models import PlayerStats
from team import virtual_stats

REFERENCE_MINUTES = 450
FULL_CONFIDENCE_MINUTES = 600


def _rate(success, attempt, minimum):
    return (success / attempt) if attempt and attempt >= minimum else None


def _p90(value, minutes):
    return (value / minutes * 90) if minutes and minutes > 0 else None


def _full_match_rate(s):
    games = s.games or 0
    return min(1.0, s.minutes / (games * 90)) if games else None


def _v(key):
    return lambda s, v: v.get(key)


def _age_fit(s):
    """전성기 나이(26~30세)에 가까울수록 높다. 범위 안이면 0, 벗어난 만큼 마이너스."""
    age = virtual_stats.player_age(s.player)
    if not age:
        return None
    return -max(0, abs(age - 28) - 2)


def _positive(value):
    return value if value else None


def _cards_90(s):
    return _p90(s.yellow_cards + 2 * s.red_cards, s.minutes)


# 모든 포지션에 공통으로 붙는 피지컬·나이 컬럼
COMMON = [
    ('age_fit', '나이 (전성기 26~30세에 가까울수록)', lambda s, v: _age_fit(s), True, 'real'),
    ('height', '피지컬: 키', lambda s, v: _positive(s.player.height), True, 'real'),
    ('weight', '피지컬: 몸무게', lambda s, v: _positive(s.player.weight), True, 'real'),
]
CARDS = ('cards_90', '경고·퇴장 (90분당, 적을수록 좋음)', lambda s, v: _cards_90(s), False, 'real')


# (키, 이름, 계산, 높을수록 좋음?, 출처)
METRICS = {
    'FW': [
        ('shot_accuracy', '슈팅 정확도', lambda s, v: _rate(s.shots_on_target, s.shots, 5), True, 'real'),
        ('conversion', '득점 전환율', lambda s, v: _rate(s.goals, s.shots, 5), True, 'real'),
        ('box_shot_ratio', '박스 안 슈팅 비율', lambda s, v: _rate(s.shots_inside_box, s.shots, 5), True, 'real'),
        ('dribble_rate', '개인기 (드리블 성공률)', lambda s, v: _rate(s.dribble_success, s.dribble_attempt, 5), True, 'real'),
        ('aerial_rate', '공중볼 경합 성공률', lambda s, v: _rate(s.aerial_duel_success, s.aerial_duel_attempt, 5), True, 'real'),
        ('fouls_won_90', '피파울 (90분당)', lambda s, v: _p90(s.fouls_won, s.minutes), True, 'real'),
        ('offsides_90', '오프사이드 (90분당, 적을수록 좋음)', lambda s, v: _p90(s.offsides, s.minutes), False, 'real'),
        ('distance', '체력: 활동량 (km/90분)', _v('distance_km_90'), True, 'virtual'),
        ('sprints', '체력: 스프린트 (90분당)', _v('sprints_90'), True, 'virtual'),
        ('full_match', '체력: 풀타임 소화율', lambda s, v: _full_match_rate(s), True, 'real'),
        CARDS,
    ] + COMMON,
    'MF': [
        ('pass_rate', '패스 정확도', lambda s, v: _rate(s.pass_success, s.pass_attempt, 30), True, 'real'),
        ('forward_pass_rate', '전진 패스 성공률', lambda s, v: _rate(s.forward_pass_success, s.forward_pass_attempt, 15), True, 'real'),
        ('att_third_pass_rate', '공격 진영 패스 성공률', lambda s, v: _rate(s.attacking_third_pass_success, s.attacking_third_pass_attempt, 15), True, 'real'),
        ('long_pass_rate', '롱패스 성공률', lambda s, v: _rate(s.long_pass_success, s.long_pass_attempt, 10), True, 'real'),
        ('cross_rate', '크로스 성공률', lambda s, v: _rate(s.cross_success, s.cross_attempt, 5), True, 'real'),
        ('ball_win_90', '볼 회수 + 인터셉트 (90분당)', lambda s, v: _p90(s.recoveries + s.interceptions, s.minutes), True, 'real'),
        ('tackle_rate', '태클 성공률', lambda s, v: _rate(s.tackle_success, s.tackle_attempt, 5), True, 'real'),
        ('dribble_rate', '개인기 (드리블 성공률)', lambda s, v: _rate(s.dribble_success, s.dribble_attempt, 5), True, 'real'),
        ('ball_miss_90', '볼 미스 (90분당, 적을수록 좋음)', lambda s, v: _p90(s.ball_misses, s.minutes), False, 'real'),
        ('distance', '체력: 활동량 (km/90분)', _v('distance_km_90'), True, 'virtual'),
        ('sprints', '체력: 스프린트 (90분당)', _v('sprints_90'), True, 'virtual'),
        ('full_match', '체력: 풀타임 소화율', lambda s, v: _full_match_rate(s), True, 'real'),
        CARDS,
    ] + COMMON,
    'DF': [
        ('tackle_rate', '태클 성공률', lambda s, v: _rate(s.tackle_success, s.tackle_attempt, 5), True, 'real'),
        ('aerial_rate', '공중볼 경합 성공률', lambda s, v: _rate(s.aerial_duel_success, s.aerial_duel_attempt, 5), True, 'real'),
        ('ground_rate', '지상볼 경합 성공률', lambda s, v: _rate(s.ground_duel_success, s.ground_duel_attempt, 5), True, 'real'),
        ('defend_90', '클리어링·차단·블록 (90분당)', lambda s, v: _p90(s.clearances + s.defensive_blocks + s.blocks, s.minutes), True, 'real'),
        ('def_third_pass_rate', '수비 진영 패스 성공률 (빌드업)', lambda s, v: _rate(s.defensive_third_pass_success, s.defensive_third_pass_attempt, 15), True, 'real'),
        ('long_pass_rate', '롱패스 성공률', lambda s, v: _rate(s.long_pass_success, s.long_pass_attempt, 10), True, 'real'),
        ('discipline_90', '파울·경고 (90분당, 적을수록 좋음)', lambda s, v: _p90(s.fouls + 3 * s.yellow_cards + 6 * s.red_cards, s.minutes), False, 'real'),
        ('distance', '체력: 활동량 (km/90분)', _v('distance_km_90'), True, 'virtual'),
        ('sprints', '체력: 스프린트 (90분당)', _v('sprints_90'), True, 'virtual'),
        ('full_match', '체력: 풀타임 소화율', lambda s, v: _full_match_rate(s), True, 'real'),
    ] + COMMON,
    'GK': [
        ('save_rate', '선방률', _v('save_rate'), True, 'virtual'),
        ('saves_90', '선방 (90분당)', _v('saves_90'), True, 'virtual'),
        ('conceded_90', '실점 (90분당, 적을수록 좋음)', _v('conceded_90'), False, 'virtual'),
        ('clean_sheet_rate', '무실점 경기 비율', _v('clean_sheet_rate'), True, 'virtual'),
        ('claims_90', '공중볼 처리: 펀칭+캐칭 (90분당)', lambda s, v: (v['punches_90'] + v['catches_90']) if 'punches_90' in v else None, True, 'virtual'),
        ('rating', '평균 평점', lambda s, v: s.average_rating or None, True, 'real'),
        ('pass_rate', '패스 정확도 (빌드업)', lambda s, v: _rate(s.pass_success, s.pass_attempt, 20), True, 'real'),
        ('long_pass_rate', '롱패스 성공률', lambda s, v: _rate(s.long_pass_success, s.long_pass_attempt, 10), True, 'real'),
        ('full_match', '체력: 풀타임 소화율', lambda s, v: _full_match_rate(s), True, 'real'),
        CARDS,
    ] + COMMON,
}


def _values(stats, pos):
    v = virtual_stats.for_player(stats.player_id)
    return {key: fn(stats, v) for key, _label, fn, _hi, _src in METRICS[pos]}


class DetailIndex:
    """포지션별 기준 분포를 한 번 만들어 두고 선수 점수를 계산한다."""

    def __init__(self):
        rows = PlayerStats.objects.filter(season=2026, minutes__gte=REFERENCE_MINUTES).select_related('player')
        self.pool = {pos: {key: [] for key, *_ in METRICS[pos]} for pos in METRICS}
        for s in rows:
            pos = (s.player.position or '').strip().upper()
            if pos not in METRICS:
                continue
            for key, value in _values(s, pos).items():
                if value is not None:
                    self.pool[pos][key].append(value)
        for pos in self.pool:
            for key in self.pool[pos]:
                self.pool[pos][key].sort()
        self._cache = {}

    def _pct(self, pos, key, value, higher):
        ref = self.pool[pos][key]
        if value is None or not ref:
            return None
        below = sum(1 for x in ref if x < value)
        same = sum(1 for x in ref if x == value)
        p = (below + 0.5 * same) / len(ref) * 100
        return p if higher else 100 - p

    def player(self, stats):
        """{'score': 0~100, 'metrics': [...]} — 기록이 없으면 중립 50."""
        if stats is None or stats.minutes <= 0:
            return {'score': 50.0, 'metrics': [], 'note': '기록 없음: 중립 50'}
        if stats.pk in self._cache:
            return self._cache[stats.pk]
        pos = (stats.player.position or '').strip().upper()
        if pos not in METRICS:
            return {'score': 50.0, 'metrics': [], 'note': ''}
        vals = _values(stats, pos)
        metrics, pcts = [], []
        for key, label, _fn, higher, src in METRICS[pos]:
            pct = self._pct(pos, key, vals[key], higher)
            if pct is not None:
                pcts.append(pct)
            metrics.append({'key': key, 'label': label, 'source': src,
                            'value': None if vals[key] is None else round(vals[key], 3),
                            'percentile': None if pct is None else round(pct)})
        raw = sum(pcts) / len(pcts) if pcts else 50.0
        conf = min(1.0, stats.minutes / FULL_CONFIDENCE_MINUTES)
        out = {'score': round(50 + conf * (raw - 50), 1), 'metrics': metrics,
               'note': '' if conf >= 1 else f'{FULL_CONFIDENCE_MINUTES}분 미만: 중립 쪽으로 보정'}
        self._cache[stats.pk] = out
        return out

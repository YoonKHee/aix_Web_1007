"""
감독 모드 엔진: 피로도 · 경고 누적 · 일정

- '실제 감독이 된다면' 콘셉트. 라운드마다 라인업을 짜면 선수들의 피로도와 경고가 누적된다.
- Django/ORM 에 의존하지 않는 순수 파이썬이다. 상태(state)는 dict 라서 브라우저(localStorage)나 세션에 그대로 저장할 수 있다.
- 숫자는 전부 맨 위 상수다. (연속 출전 규칙: 30 → 연속이면 35, 출장정지는 쓰지 않는다) 아래 값들은 '게임 규칙'이며 공식 규정이나 의학적 사실이 아니다.
- 선수 개인의 부상·건강에 대한 판단은 하지 않는다. 피로도는 출전 부하를 단순 계산한 게임 수치일 뿐이다.
"""

import json
import math
from datetime import date, datetime

# =========================================================
# 조정 가능한 상수 (게임 규칙)
# =========================================================

# 연속 출전 규칙: 한 경기 풀타임의 피로도는 연속으로 뛸수록 커진다.
#   첫 경기(직전 라운드를 쉬었음) = 30, 2경기 연속 이후 = 35  (리스트의 마지막 값이 계속 적용된다)
#   예) 4경기 연속 출전이면 30, 35, 35, 35
STREAK_COSTS = [30.0, 35.0]
STREAK_MIN_MINUTES = 45           # 이 시간 이상 뛰어야 '출전'으로 보고 연속 횟수에 포함
GK_LOAD_FACTOR = 0.5              # 골키퍼는 소모를 절반으로
HALFTIME_RECOVERY = 3.0           # 하프타임 휴식으로 조금 회복. 전반(45분)을 넘겨 뛴 경기에만 적용 (풀타임 30 -> 순소모 27)
HALFTIME_MINUTES = 45             # 이 시간을 넘겨 뛰어야 하프타임을 겪은 것으로 본다

# 하루 회복량. 정규 리그는 보통 7일 간격이라 '30 소모 / 7일 회복' 이 거의 균형이 되도록 4 로 둔다.
RECOVERY_PER_DAY = 4.0
RECOVERY_PER_DAY_30PLUS = 3.5     # 30세 이상은 조금 느리게

BASELINE_MAX = 15.0               # 시즌 내내 풀타임으로 뛴 선수의 시작 피로도

# 피로도 구간별 능력 점수 배율 (이상, 배율, 표시)
FATIGUE_TIERS = [
    (86, 0.80, '휴식 필요'),
    (71, 0.88, '기용 비권장'),
    (51, 0.93, '피곤'),
    (31, 0.97, '약간 피곤'),
    (0, 1.00, '정상'),
]

# 경고: 출장정지는 쓰지 않는다. 대신 (1) 다음 경기 경고 위험도를 보여 주고
#       (2) 경고가 많이 쌓인 선수는 신중하게 뛴다고 보고 능력 점수를 소폭 낮춘다. (게임 규칙)
# 누적 경고 장수(이상) -> 능력 배율
CAUTION_TIERS = [
    (8, 0.98),
    (5, 0.99),
    (0, 1.00),
]
# 다음 경기 경고 확률(%) 표시 기준 (이상)
CARD_RISK_HIGH = 25.0
CARD_RISK_WARN = 15.0


# =========================================================
# 보조
# =========================================================

def _num(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def age_on(birth_date, on):
    """birth_date: 'YYYY-MM-DD' 또는 date. on: date. 모르면 None."""
    if not birth_date:
        return None
    try:
        b = birth_date if isinstance(birth_date, date) else datetime.strptime(str(birth_date)[:10], '%Y-%m-%d').date()
    except ValueError:
        return None
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


# =========================================================
# 1. 일정
# =========================================================

def load_schedule(path, league_id=1):
    """
    공식 경기 JSON(official_source_*.json)에서 정규 리그 일정을 읽는다.
    반환: {'rounds': {라운드: {'date','played'}}, 'team_dates': {팀명: [(라운드, date)]}, 'fixtures': {팀명: [{'round','date','opponent','home','played'}]}}
    주의: 'played' 는 파일을 받은 시점 기준이다 (endYn). 파일이 오래되면 실제와 다를 수 있다.
    """
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    games = []
    for v in d['months'].values():
        data = v['data']
        games += data.get('scheduleList', []) if isinstance(data, dict) else data
    games = [g for g in games if g.get('leagueId') == league_id]

    rounds, team_dates, fixtures = {}, {}, {}
    for g in games:
        gd = datetime.strptime(g['gameDate'], '%Y.%m.%d').date()
        r = g['roundId']
        info = rounds.setdefault(r, {'date': gd, 'played': True})
        info['date'] = min(info['date'], gd)
        info['played'] = info['played'] and g.get('endYn') == 'Y'
        for t, opp, is_home in ((g['homeTeamName'], g['awayTeamName'], True),
                                (g['awayTeamName'], g['homeTeamName'], False)):
            team_dates.setdefault(t, []).append((r, gd))
            fixtures.setdefault(t, []).append({'round': r, 'date': gd, 'opponent': opp, 'home': is_home,
                                               'played': g.get('endYn') == 'Y'})
    for t in team_dates:
        team_dates[t].sort()
        fixtures[t].sort(key=lambda x: (x['round'], x['date']))
    return {'rounds': rounds, 'team_dates': team_dates, 'fixtures': fixtures}


def first_unplayed_round(schedule, today=None):
    """
    시작 라운드: 아직 열리지 않은 첫 라운드.
    파일의 'played' 표시와 오늘 날짜를 둘 다 본다. (파일이 오래돼서 이미 치른 라운드가 '미종료'로 남아 있을 수 있어서)
    """
    today = today or date.today()
    for r in sorted(schedule['rounds']):
        info = schedule['rounds'][r]
        if info['date'] > today:
            return r
    return None


def days_between_rounds(schedule, team, round_a, round_b):
    """팀 기준으로 두 라운드 경기 사이의 일수."""
    dates = dict(schedule['team_dates'].get(team, []))
    if round_a in dates and round_b in dates:
        return (dates[round_b] - dates[round_a]).days
    ra, rb = schedule['rounds'].get(round_a), schedule['rounds'].get(round_b)
    if ra and rb:
        return (rb['date'] - ra['date']).days
    return 7


# =========================================================
# 2. 피로도
# =========================================================

def baseline_fatigue(minutes, games):
    """시즌 평균 출전시간으로 구한 시작 피로도. 항상 풀타임이면 BASELINE_MAX."""
    games = _num(games)
    if games <= 0:
        return 0.0
    avg = _num(minutes) / games
    return round(min(BASELINE_MAX, avg / 90.0 * BASELINE_MAX), 1)


def streak_cost(streak):
    """streak: 이번 경기까지 포함한 연속 출전 횟수(1 = 직전 라운드를 쉬었음)."""
    i = max(1, int(streak)) - 1
    return STREAK_COSTS[min(i, len(STREAK_COSTS) - 1)]


def match_fatigue(minutes_played, position, streak=1):
    """한 경기로 쌓이는 피로도. 출전 시간에 비례하고, 연속 출전 횟수에 따라 풀타임 기준값이 커진다."""
    m = min(max(0.0, _num(minutes_played)), 90.0)
    base = m / 90.0 * streak_cost(streak)
    if m > HALFTIME_MINUTES:
        base -= HALFTIME_RECOVERY * (m - HALFTIME_MINUTES) / (90.0 - HALFTIME_MINUTES)   # 후반을 오래 뛸수록 하프타임 회복 효과가 온전히 반영
    if (position or '').upper() == 'GK':
        base *= GK_LOAD_FACTOR
    return max(0.0, base)


def recovery(days, age=None):
    rate = RECOVERY_PER_DAY_30PLUS if (age is not None and age >= 30) else RECOVERY_PER_DAY
    return max(0, days) * rate


def fatigue_tier(fatigue):
    for low, mult, label in FATIGUE_TIERS:
        if fatigue >= low:
            return {'multiplier': mult, 'label': label}
    return {'multiplier': 1.0, 'label': '정상'}


def adjusted_ability(ability, fatigue):
    """피로도를 반영한 능력 점수."""
    return ability * fatigue_tier(fatigue)['multiplier']


# =========================================================
# 3. 경고 (위험도 표시 + 신중 플레이 효과)
# =========================================================

def card_probability(season_yellow, season_red, season_minutes, minutes_this_match=90):
    """
    다음 경기에서 경고를 받을 확률(%): 시즌 경고 비율(90분당)을 이 경기 출전 시간으로 환산해 포아송으로 계산.
    선수 개인의 '성향'이 아니라 올 시즌 기록의 단순 환산이다.
    """
    minutes = _num(season_minutes)
    if minutes <= 0:
        return 0.0
    lam = _num(season_yellow) / minutes * max(0.0, minutes_this_match)
    return round((1 - math.exp(-lam)) * 100, 1)


def card_risk_label(probability):
    if probability >= CARD_RISK_HIGH:
        return '경고 위험 높음'
    if probability >= CARD_RISK_WARN:
        return '경고 주의'
    return ''


def caution_multiplier(yellow_acc):
    """누적 경고가 많을수록 신중하게 뛰어 능력이 소폭 낮아지는 효과 (게임 규칙)."""
    n = _num(yellow_acc)
    for low, mult in CAUTION_TIERS:
        if n >= low:
            return mult
    return 1.0


def adjusted_ability(ability, fatigue, yellow_acc=0):
    """피로도와 신중 플레이 효과를 모두 반영한 능력 점수."""
    return ability * fatigue_tier(fatigue)['multiplier'] * caution_multiplier(yellow_acc)


def availability(player_state, risk_percent=0.0):
    """배지 목록. 정지 규칙이 없으므로 항상 기용 가능하다."""
    badges = []
    tier = fatigue_tier(player_state.get('fatigue', 0))
    if tier['label'] != '정상':
        badges.append(tier['label'])
    risk = card_risk_label(risk_percent)
    if risk:
        badges.append(risk)
    if caution_multiplier(player_state.get('yellow_acc', 0)) < 1.0:
        badges.append('신중 플레이')
    return {'available': True, 'badges': badges,
            'multiplier': tier['multiplier'] * caution_multiplier(player_state.get('yellow_acc', 0))}


# =========================================================
# 4. 상태 만들기 / 라운드 진행
# =========================================================

def initial_state(players, today=None):
    """
    players: [{'id','position','birth_date','minutes','games','yellow_cards'}]
    반환: {player_id(str): {'fatigue','yellow_acc','streak'}}
    누적 경고(yellow_acc)의 시작값은 올 시즌 실제 경고 수다.
    """
    state = {}
    for p in players:
        state[str(p['id'])] = {
            'fatigue': baseline_fatigue(p.get('minutes'), p.get('games')),
            'yellow_acc': int(_num(p.get('yellow_cards'))),
            'streak': 0,
        }
    return state


def pre_match_fatigue(st, days, age=None):
    """다음 경기 직전의 피로도 (직전 경기 후 휴식일만큼 회복한 값)."""
    return max(0.0, st.get('fatigue', 0.0) - recovery(days, age))


def advance_round(state, played, meta, days_since_last, rng=None):
    """
    라운드 하나를 진행한다. (state 를 바꾸지 않고 새로 만들어 돌려준다)
    played: {player_id: 출전 분}   meta: {player_id: {'position','age','season_yellow','season_red','season_minutes'}}
    days_since_last: {player_id: 지난 경기 이후 일수}(없으면 7)
    rng: random.Random — 있으면 경고 발생을 추첨하고, None 이면 추첨하지 않는다.
    반환: (새 상태, 이벤트 리스트)
    """
    new, events = {}, []
    for pid, st in state.items():
        st = dict(st)
        m = meta.get(pid, {})
        mins = played.get(pid, 0)

        st['fatigue'] = pre_match_fatigue(st, days_since_last.get(pid, 7), m.get('age'))
        if mins >= STREAK_MIN_MINUTES:
            st['streak'] = st.get('streak', 0) + 1          # 연속 출전 +1
        else:
            st['streak'] = 0                                # 쉬면(또는 짧게 뛰면) 연속 기록이 끊긴다
        if mins > 0:
            st['fatigue'] = min(100.0, st['fatigue'] + match_fatigue(mins, m.get('position'), max(1, st['streak'])))
            if rng is not None:
                p = card_probability(m.get('season_yellow'), m.get('season_red'), m.get('season_minutes'), mins) / 100
                if rng.random() < p:
                    st['yellow_acc'] += 1
                    events.append({'player': pid, 'type': 'yellow'})
        new[pid] = st
    return new, events

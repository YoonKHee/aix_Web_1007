"""
BEST11 케미 계산 엔진

- 선수 기록(2026 시즌)만으로 계산한 "기록 기반 추정"이다. 실제 선수 간 호흡이 아니다.
- 데이터에 '누가 누구에게 패스했는지'와 세부 포지션(LB/CB/WB 등)이 없어서,
  같은 라인 안에서는 '역할 보완', 인접한 라인 사이에서는 '연계', 같은 구단이면 '팀 보너스'를 쓴다.
- 이 파일은 Django/ORM 에 의존하지 않는 순수 파이썬 함수들로 되어 있다. (맨 아래 load_profiles 만 ORM 사용)
- 숫자(비중, 등급 기준, 가산점)는 전부 맨 위 상수에 모아 두었다. 조정할 때는 이 숫자만 바꾼다.
"""

from math import sqrt

try:
    from . import chemistry_styles as S      # Django 안에서
except ImportError:                           # 단독 테스트용
    import chemistry_styles as S

# =========================================================
# 조정 가능한 상수
# =========================================================

SEASON = 2026

REFERENCE_MIN_MINUTES = 450       # 백분위 기준 집단: 이 시간 이상 뛴 선수 (포메이션 후보 기준과 동일)
LOW_MINUTES = 450                 # 이보다 적게 뛴 선수는 케미 가산을 절반만 적용
LOW_MINUTES_FACTOR = 0.5

# 쌍 케미 점수 = 보완 + 연계 + 같은 팀  (합 100).  스타일 궁합은 여기에 가감한다 (chemistry_styles.py)
W_COMPLEMENT = 55
W_LINK = 35
W_TEAM = 10
STYLE_TEAM_CREDIT = 0.5      # 다른 구단이어도 구단 스타일(점유형 등)이 같으면 '같은 구단' 점수(W_TEAM)의 이 비율만큼 받는다

# 등급 기준과 가산점
TIER_STRONG = 70                  # 이상: 강한 케미
TIER_NORMAL = 55                  # 이상: 케미 있음
BONUS_STRONG = 3.0
BONUS_NORMAL = 1.5
PENALTY_OVERLAP = -1.0            # 약점 중복(두 선수가 같은 약점)

PLAYER_BONUS_MAX = 5.0            # 한 선수당 가산 상한
PLAYER_BONUS_MIN = -2.0           # 한 선수당 감점 하한

FINAL_SCORE_CAP = 200             # 능력 점수 + 케미 가산 + (이후 추가될 가산) 의 최종 상한. 여유를 두기 위한 값

STRONG_PCT = 60                   # 이 이상이면 해당 항목이 '강점'
WEAK_PCT = 40                     # 이하이면 '약점'
TRAIT_PCT = 70                    # 이 이상이면 해당 성향 보유
QUALITY_FLOOR = 50                # 두 선수 중 능력 평균이 이보다 낮으면 '보완' 가산을 비례해서 줄임

# 포지션별 항목(카테고리) -> 사용하는 지표
# 각 지표는 같은 포지션 선수들 사이의 백분위(0~100)로 바뀐 뒤, 항목 안에서 평균된다.
CATEGORIES = {
    'FW': {
        'ATK': ['goals', 'shots_on_target', 'shots'],
        'CRE': ['assists', 'key_passes'],
        'WIDE': ['cross', 'dribble'],
    },
    'MF': {
        'ATK': ['goals', 'shots_on_target'],
        'CRE': ['assists', 'key_passes'],
        'BUILD': ['pass_rate', 'pass_volume'],
        'DEF': ['recoveries', 'interceptions', 'tackle'],
        'WIDE': ['cross', 'dribble'],
    },
    'DF': {
        'DEF': ['tackle', 'interceptions', 'recoveries', 'clearances', 'blocks'],
        'PHY': ['aerial_duel', 'ground_duel'],
        'BUILD': ['pass_rate', 'pass_volume'],
        'WIDE': ['cross', 'dribble'],
    },
    'GK': {},
}

CATEGORY_LABEL = {
    'ATK': '득점력',
    'CRE': '찬스 창출',
    'WIDE': '측면 돌파',
    'BUILD': '빌드업',
    'DEF': '수비 가담',
    'PHY': '공중·지상 경합',
}

# 인접한 라인 (연계 점수 계산 대상)
ADJACENT = {('FW', 'MF'), ('MF', 'DF'), ('DF', 'GK')}


# =========================================================
# 보조 함수
# =========================================================

def _num(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _per90(v, minutes):
    minutes = _num(minutes)
    if minutes <= 0:
        return 0.0
    return _num(v) / minutes * 90


def _rate(success, attempt):
    attempt = _num(attempt)
    if attempt <= 0:
        return 0.0
    return _num(success) / attempt * 100


def _percentile(value, sorted_values):
    """sorted_values 중 value 이하인 비율(0~100). 기준 집단이 비면 50."""
    n = len(sorted_values)
    if n == 0:
        return 50.0
    lo, hi = 0, n
    while lo < hi:                       # bisect_right
        mid = (lo + hi) // 2
        if sorted_values[mid] <= value:
            lo = mid + 1
        else:
            hi = mid
    return lo / n * 100


# =========================================================
# 1. 선수 지표 -> 항목(카테고리) 백분위 프로필
# =========================================================

def raw_metrics(s):
    """s: 선수 기록(dict). 90분당/성공률 지표로 변환."""
    m = s.get('minutes')
    return {
        'goals': _per90(s.get('goals'), m),
        'assists': _per90(s.get('assists'), m),
        'shots': _per90(s.get('shots'), m),
        'shots_on_target': _per90(s.get('shots_on_target'), m),
        'key_passes': _per90(s.get('key_passes'), m),
        'dribble': _per90(s.get('dribble_success'), m),
        'cross': _per90(s.get('cross_success'), m),
        'pass_rate': _rate(s.get('pass_success'), s.get('pass_attempt')),
        'pass_volume': _per90(s.get('pass_attempt'), m),
        'recoveries': _per90(s.get('recoveries'), m),
        'interceptions': _per90(s.get('interceptions'), m),
        'tackle': _per90(s.get('tackle_success'), m),
        'clearances': _per90(s.get('clearances'), m),
        'blocks': _per90(s.get('blocks'), m) + _per90(s.get('defensive_blocks'), m),
        'aerial_duel': _per90(s.get('aerial_duel_success'), m),
        'ground_duel': _per90(s.get('ground_duel_success'), m),
        'dribble_attempt': _per90(s.get('dribble_attempt'), m),
        'shot_accuracy': _rate(s.get('shots_on_target'), s.get('shots')),
        'goal_conversion': _rate(s.get('goals'), s.get('shots')),
        'card_rate': _per90(_num(s.get('yellow_cards')) + 2 * _num(s.get('red_cards')), m),
        'rating': _num(s.get('average_rating')),
        'best11_rate': _per90(s.get('best11_count'), m),
        'mom_rate': _per90(s.get('mom'), m),
    }


def _assign_styles(pos, met, ref_pos):
    """플레이 스타일 부여. 출전이 충분한 선수에게만, 최대 S.MAX_STYLES 개."""
    if not S.STYLES_ENABLED:
        return []
    found = []
    for code, st in S.STYLES.items():
        if pos not in st['positions']:
            continue
        hi = [_percentile(met[k], ref_pos.get(k, [])) for k in st['high']]
        score = sum(hi) / len(hi)
        if score < st.get('pct', S.STYLE_PCT):
            continue
        if st['low']:
            lo = [_percentile(met[k], ref_pos.get(k, [])) for k in st['low']]
            if sum(lo) / len(lo) > S.LOW_GATE:
                continue
        found.append({'code': code, 'label': st['label'], 'score': round(score, 1)})
    found.sort(key=lambda x: -x['score'])
    return found[:S.MAX_STYLES]


def build_profiles(rows):
    """
    rows: [{'player_id','name','position','team_id','minutes', ...기록 필드...}]
    반환: {player_id: profile}
      profile = {id,name,position,team_id,minutes,low_minutes, cats:{카테고리:0~100}, traits:[카테고리...]}
    백분위의 기준 집단은 같은 포지션 + 출전 REFERENCE_MIN_MINUTES 이상 선수들이다.
    기준 집단에 없는 선수(출전 적음)도 같은 기준표로 점수를 매긴다.
    """
    prepared = []
    for r in rows:
        pos = (r.get('position') or '').strip().upper()
        if pos not in CATEGORIES:
            continue
        prepared.append((r, pos, raw_metrics(r)))

    # 포지션별 기준 분포
    ref = {}
    for r, pos, met in prepared:
        if _num(r.get('minutes')) < REFERENCE_MIN_MINUTES:
            continue
        for k, v in met.items():
            ref.setdefault(pos, {}).setdefault(k, []).append(v)
    for pos in ref:
        for k in ref[pos]:
            ref[pos][k].sort()

    profiles = {}
    for r, pos, met in prepared:
        cats = {}
        for cat, keys in CATEGORIES[pos].items():
            pcts = [_percentile(met[k], ref.get(pos, {}).get(k, [])) for k in keys]
            cats[cat] = sum(pcts) / len(pcts)
        minutes = _num(r.get('minutes'))
        styles = _assign_styles(pos, met, ref.get(pos, {})) if minutes >= REFERENCE_MIN_MINUTES else []
        profiles[r['player_id']] = {
            'id': r['player_id'],
            'name': r.get('name', ''),
            'position': pos,
            'team_id': r.get('team_id'),
            'minutes': minutes,
            'low_minutes': minutes < LOW_MINUTES,
            'cats': cats,
            'traits': [c for c, v in cats.items() if v >= TRAIT_PCT],
            'styles': styles,
            'club_style': r.get('club_style'),
            'club_style_label': r.get('club_style_label', ''),
        }
    return profiles


# =========================================================
# 2. 쌍 케미
# =========================================================

def _ability(p):
    """선수의 항목 백분위 평균 (케미 계산용 단순 능력 지표)."""
    v = list(p['cats'].values())
    return sum(v) / len(v) if v else 50.0


def _complement(a, b):
    """
    역할 보완 점수(0~100, 중립 50) 와 근거.
    두 선수가 공통으로 가진 항목마다
      한쪽이 약점(<=WEAK_PCT)인데 다른 쪽이 강점(>=STRONG_PCT)이면 +1 (보완)
      둘 다 약점이면 -1 (약점 중복)
    """
    shared = [c for c in a['cats'] if c in b['cats']]
    if not shared:
        return 50.0, [], []
    total = 0
    covered, overlap = [], []
    for c in shared:
        x, y = a['cats'][c], b['cats'][c]
        if (x <= WEAK_PCT and y >= STRONG_PCT) or (y <= WEAK_PCT and x >= STRONG_PCT):
            total += 1
            covered.append(c)
        elif x <= WEAK_PCT and y <= WEAK_PCT:
            total -= 1
            overlap.append(c)
    score = 50 + 50 * total / len(shared)
    # 품질 게이트: 한쪽이 전반적으로 너무 약하면(평균 백분위가 QUALITY_FLOOR 미만) '보완' 가산을 줄인다.
    # (스타 선수 + 부진한 선수 조합이 케미 1위로 나오는 것을 막기 위해)
    if score > 50:
        q = min(1.0, min(_ability(a), _ability(b)) / QUALITY_FLOOR)
        score = 50 + (score - 50) * q
    return score, covered, overlap


def _geo(x, y):
    return sqrt(max(x, 0) * max(y, 0))


def _link(a, b):
    """
    인접 라인 연계 점수(0~100) 와 근거 문구. 인접하지 않으면 (None, '').
    FW<->MF : 미드필더의 찬스 창출 x 공격수의 득점력
    MF<->DF : 수비수의 수비 가담 x 미드필더의 빌드업
    DF<->GK : 수비수의 수비 가담 (골키퍼는 이 지표 하나만 반영)
    """
    pa, pb = a['position'], b['position']
    pair = (pa, pb) if (pa, pb) in ADJACENT else (pb, pa) if (pb, pa) in ADJACENT else None
    if pair is None:
        return None, ''
    first = a if a['position'] == pair[0] else b
    second = b if first is a else a
    if pair == ('FW', 'MF'):
        fw, mf = first, second
        return _geo(mf['cats'].get('CRE', 0), fw['cats'].get('ATK', 0)), '찬스 창출→득점력'
    if pair == ('MF', 'DF'):
        mf, df = first, second
        return _geo(df['cats'].get('DEF', 0), mf['cats'].get('BUILD', 0)), '수비 가담→빌드업'
    df = first                                   # ('DF', 'GK')
    return df['cats'].get('DEF', 0), '수비 라인 안정'


def pair_chemistry(a, b):
    """두 선수 프로필의 케미. 순서를 바꿔도 같은 값(대칭)."""
    if a['id'] == b['id']:
        return None
    comp, covered, overlap = _complement(a, b)
    link, link_text = _link(a, b)
    same_team = (a['team_id'] is not None and a['team_id'] == b['team_id'])

    # GK 는 역할 보완을 계산하지 않는다 (지표 구조가 달라 비교가 어렵다)
    has_gk = a['position'] == 'GK' or b['position'] == 'GK'
    if has_gk:
        comp_w, link_w, team_w = 0, W_LINK + W_COMPLEMENT, W_TEAM
        comp = 0.0
    else:
        comp_w, link_w, team_w = W_COMPLEMENT, W_LINK, W_TEAM

    # 같은 라인이면 연계가 없으므로 그 비중은 보완에 합친다
    if link is None:
        comp_w += link_w if not has_gk else 0
        link_w = 0
        link = 0.0

    same_style = (not same_team and a.get('club_style') and a.get('club_style') != 'balanced'
                  and a.get('club_style') == b.get('club_style'))
    team = 100.0 if same_team else (100.0 * STYLE_TEAM_CREDIT if same_style else 0.0)
    score = (comp * comp_w + link * link_w + team * team_w) / 100.0

    # 스타일 궁합: 두 선수의 스타일 조합마다 가감 (한 쌍 최대 ±S.STYLE_ADJ_CAP)
    adj, style_reasons = 0.0, []
    for sa in a.get('styles', []):
        for sb in b.get('styles', []):
            hit = S.COMPAT.get(frozenset((sa['code'], sb['code'])))
            if hit:
                adj += hit[0]
                style_reasons.append(('+' if hit[0] > 0 else '-') + f" {sa['label']}×{sb['label']}: {hit[1]}")
    adj = max(-S.STYLE_ADJ_CAP, min(S.STYLE_ADJ_CAP, adj))
    score = max(0.0, min(100.0, score + adj))

    if score >= TIER_STRONG:
        tier, bonus = 'strong', BONUS_STRONG
    elif score >= TIER_NORMAL:
        tier, bonus = 'normal', BONUS_NORMAL
    else:
        tier, bonus = 'none', 0.0
    if overlap and not has_gk:
        bonus += PENALTY_OVERLAP

    reasons = []
    if covered:
        reasons.append('보완: ' + ', '.join(CATEGORY_LABEL[c] for c in covered))
    if link_text and link >= 50:
        reasons.append('연계: ' + link_text)
    if same_team:
        reasons.append('같은 구단')
    elif same_style:
        reasons.append('같은 스타일 구단(' + a.get('club_style_label', '') + ')')
    if overlap and not has_gk:
        reasons.append('약점 중복: ' + ', '.join(CATEGORY_LABEL[c] for c in overlap))
    reasons.extend(style_reasons)

    return {
        'a': a['id'], 'b': b['id'],
        'score': round(score, 1),
        'tier': tier,
        'bonus': bonus,
        'overlap': bool(overlap) and not has_gk,
        'style_adj': round(adj, 1),
        'reasons': reasons,
    }


# =========================================================
# 3. 라인업 케미 (11명)
# =========================================================

def _counts_for_lineup(a, b):
    """라인업 안에서 케미를 계산할 쌍인가: 같은 라인 + 인접한 라인."""
    if a['position'] == b['position']:
        return a['position'] != 'GK'          # GK 끼리는 없음
    return ((a['position'], b['position']) in ADJACENT or
            (b['position'], a['position']) in ADJACENT)


def lineup_chemistry(lineup, scale=1.0):
    """
    lineup: 프로필 리스트(11명). scale: '케미 중시' 슬라이더(0=끔, 1=기본, 2=두 배).
    반환:
      players: {player_id: {'bonus':가산점, 'pairs':[케미 있는 상대...]}}
      team_score: 11명 가산점 평균
      pairs: 계산한 모든 쌍
    """
    pairs = []
    per_player = {p['id']: {'sum': 0.0, 'n': 0, 'partners': []} for p in lineup}
    for i in range(len(lineup)):
        for j in range(i + 1, len(lineup)):
            a, b = lineup[i], lineup[j]
            if not _counts_for_lineup(a, b):
                continue
            pc = pair_chemistry(a, b)
            pairs.append(pc)
            for me, other in ((a, b), (b, a)):
                f = LOW_MINUTES_FACTOR if me['low_minutes'] else 1.0
                per_player[me['id']]['sum'] += pc['bonus'] * f
                per_player[me['id']]['n'] += 1
                if pc['tier'] != 'none':
                    per_player[me['id']]['partners'].append(
                        {'id': other['id'], 'name': other['name'],
                         'score': pc['score'], 'tier': pc['tier'], 'reasons': pc['reasons']})

    players = {}
    for p in lineup:
        d = per_player[p['id']]
        # 쌍 가산점의 '평균'을 쓴다. (합산하면 연결된 쌍이 많은 선수가 항상 상한에 걸려 차이가 사라진다)
        # 평균이 BONUS_STRONG(전부 강한 케미)이면 PLAYER_BONUS_MAX 가 되도록 환산한다.
        raw = (d['sum'] / d['n'] * PLAYER_BONUS_MAX / BONUS_STRONG) if d['n'] else 0.0
        bonus = max(PLAYER_BONUS_MIN, min(PLAYER_BONUS_MAX, raw)) * scale
        players[p['id']] = {'bonus': round(bonus, 2), 'raw': round(raw, 2),
                            'partners': sorted(per_player[p['id']]['partners'],
                                               key=lambda x: -x['score'])}
    team_score = (sum(v['bonus'] for v in players.values()) / len(players)) if players else 0.0
    return {'players': players, 'team_score': round(team_score, 2), 'pairs': pairs}


def final_score(ability, chemistry_bonus, extra=0.0):
    """최종 점수 = 능력 + 케미 가산 + 이후 추가될 가산(extra). FINAL_SCORE_CAP 을 넘지 않는다."""
    return min(FINAL_SCORE_CAP, ability + chemistry_bonus + extra)


# =========================================================
# 4. 파트너 추천
# =========================================================

def recommend_partners(player, pool, k=3, min_score=TIER_NORMAL):
    """
    player 와 케미가 좋은 선수를 pool(프로필 리스트)에서 찾는다.
    같은 라인이거나 인접한 라인이고, 케미 점수가 min_score 이상인 선수만 추천한다.
    반환: 케미 점수 높은 순 리스트
    """
    out = []
    for other in pool:
        if other['id'] == player['id'] or not _counts_for_lineup(player, other):
            continue
        pc = pair_chemistry(player, other)
        if pc and pc['score'] >= min_score:
            out.append({'id': other['id'], 'name': other['name'], 'position': other['position'],
                        'team_id': other['team_id'], 'score': pc['score'], 'tier': pc['tier'],
                        'reasons': pc['reasons'], 'low_minutes': other['low_minutes']})
    out.sort(key=lambda x: (-x['score'], x['low_minutes']))
    return out[:k]


# =========================================================
# 5. ORM 어댑터 (여기만 Django 사용)
# =========================================================

STAT_FIELDS = [
    'minutes', 'goals', 'assists', 'shots', 'shots_on_target', 'key_passes',
    'dribble_success', 'cross_success', 'pass_success', 'pass_attempt',
    'recoveries', 'interceptions', 'tackle_success', 'clearances', 'blocks',
    'defensive_blocks', 'aerial_duel_success', 'ground_duel_success',
    'dribble_attempt', 'yellow_cards', 'red_cards', 'average_rating', 'best11_count', 'mom',
]


def load_profiles(season=SEASON, exclude_ids=()):
    """PlayerStats(해당 시즌)에서 프로필을 만든다. 관리자 제외선수는 exclude_ids 로 뺀다."""
    from player.models import PlayerStats          # 순수 함수 테스트 시 Django 없이도 import 되도록 지연 import

    qs = (PlayerStats.objects
          .filter(season=season, minutes__gt=0)
          .exclude(player_id__in=list(exclude_ids))
          .select_related('player'))
    rows = []
    for st in qs:
        row = {f: getattr(st, f, None) for f in STAT_FIELDS}
        row.update(player_id=st.player_id, name=st.player.name,
                   position=st.player.position, team_id=st.player.team_id)
        rows.append(row)
    return build_profiles(rows)

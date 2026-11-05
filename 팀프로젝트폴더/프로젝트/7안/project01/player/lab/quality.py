"""
선수 기록 데이터 점검 (순수 파이썬)

- 가져온 기록에서 '있을 수 없는 값'(error), '의심스러운 값'(warn), '참고'(info)를 찾아 알려 준다.
- 값을 고치지 않는다. 찾아서 보여 주기만 한다.
"""

POSITIONS = ('GK', 'DF', 'MF', 'FW')

# (이름, 큰 쪽 필드, 작은 쪽 필드): 큰 쪽이 작은 쪽보다 작으면 오류. 예) 성공 수 <= 시도 수
SUBSET_RULES = [
    ('패스 성공이 시도보다 많음', 'pass_attempt', 'pass_success'),
    ('드리블 성공이 시도보다 많음', 'dribble_attempt', 'dribble_success'),
    ('크로스 성공이 시도보다 많음', 'cross_attempt', 'cross_success'),
    ('태클 성공이 시도보다 많음', 'tackle_attempt', 'tackle_success'),
    ('공중볼 성공이 시도보다 많음', 'aerial_duel_attempt', 'aerial_duel_success'),
    ('지상 경합 성공이 시도보다 많음', 'ground_duel_attempt', 'ground_duel_success'),
    ('유효슈팅이 슈팅보다 많음', 'shots', 'shots_on_target'),
    ('베스트11 선정이 출전 경기보다 많음', 'games', 'best11_count'),
    ('MOM이 출전 경기보다 많음', 'games', 'mom'),
]

NONNEG_FIELDS = ['minutes', 'games', 'goals', 'assists', 'shots', 'shots_on_target', 'pass_attempt', 'pass_success',
                 'yellow_cards', 'red_cards', 'clearances', 'interceptions', 'recoveries', 'tackle_success']

OUTLIER_FIELDS = ['goals', 'assists', 'shots', 'key_passes', 'recoveries', 'interceptions', 'clearances', 'tackle_success']
OUTLIER_MIN_MINUTES = 450
OUTLIER_Z = 6.0            # 같은 포지션 90분당 값이 중앙값에서 '튼튼한 표준편차'의 6배 이상 벗어나면 의심
OUTLIER_ABS_MIN = {'goals': 0.8, 'assists': 0.8, 'shots': 5, 'key_passes': 4, 'recoveries': 15,
                   'interceptions': 6, 'clearances': 15, 'tackle_success': 6}   # 90분당 이 값 미만이면 이상치로 보지 않는다
MAX_MINUTES_PER_GAME = 110  # 한 경기 출전시간으로 가능한 최대치 (연장 포함)


def _n(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def check(rows, team_min=18, team_max=45):
    """
    rows: [{'id','name','team_id','team','position','birth_date','minutes','games', ...기록 필드...}]
    반환: {'summary': {'error':n,'warn':n,'info':n,'players':N}, 'issues': [{'severity','code','title','count','examples':[...]}]}
    """
    buckets = {}

    def add(sev, code, title, row, detail=''):
        b = buckets.setdefault(code, {'severity': sev, 'code': code, 'title': title, 'count': 0, 'examples': []})
        b['count'] += 1
        if len(b['examples']) < 8:
            b['examples'].append({'id': row.get('id'), 'name': row.get('name'), 'team': row.get('team') or '', 'detail': detail})

    for r in rows:
        minutes, games = _n(r.get('minutes')), _n(r.get('games'))
        pos = (r.get('position') or '').strip().upper()
        if pos not in POSITIONS:
            add('error', 'bad_position', '포지션이 GK/DF/MF/FW 가 아님', r, repr(r.get('position')))
        if not r.get('team_id'):
            add('error', 'no_team', '소속 구단이 없음', r)
        if not r.get('birth_date'):
            add('info', 'no_birth', '생년월일이 없음', r)
        if games > 0 and minutes > games * MAX_MINUTES_PER_GAME:
            add('error', 'minutes_gt_games', f'출전시간이 경기 수 × {MAX_MINUTES_PER_GAME}분보다 큼 (연장·추가시간 포함 범위를 벗어남)', r, f'{int(minutes)}분 / {int(games)}경기')
        elif games > 0 and minutes > games * 95:
            add('info', 'minutes_over_95', '경기당 95분 초과 (추가시간·연장 포함으로 보임, 참고)', r, f'{minutes / games:.0f}분/경기')
        if games <= 0 and minutes > 0:
            add('error', 'minutes_no_games', '출전시간은 있는데 경기 수가 0', r, f'{int(minutes)}분')
        if games > 0 and minutes <= 0:
            add('warn', 'games_no_minutes', '경기 수는 있는데 출전시간이 0', r, f'{int(games)}경기')
        if games > 0 and 0 < minutes < games:
            add('warn', 'minutes_lt_games', '경기당 1분도 안 뛴 것으로 기록됨', r, f'{int(minutes)}분 / {int(games)}경기')
        for k in NONNEG_FIELDS:
            if _n(r.get(k)) < 0:
                add('error', 'negative', '음수 값이 있음', r, f'{k}={r.get(k)}')
        for title, big, small in SUBSET_RULES:
            if _n(r.get(small)) > _n(r.get(big)) + 1e-9:
                add('error', f'subset_{small}_{big}', title, r, f'{small}={r.get(small)} > {big}={r.get(big)}')
        if _n(r.get('goals')) > _n(r.get('shots_on_target')) and _n(r.get('goals')) > 0:
            add('warn', 'goals_gt_on_target', '득점이 유효슈팅보다 많음 (자책·기록 방식 차이일 수 있음)', r,
                f"득점 {r.get('goals')} / 유효슈팅 {r.get('shots_on_target')}")
        if _n(r.get('red_cards')) > 0 and _n(r.get('red_cards')) > games:
            add('warn', 'red_gt_games', '퇴장이 경기 수보다 많음', r)

    # 같은 구단 안의 같은 이름
    seen = {}
    for r in rows:
        key = (r.get('team_id'), (r.get('name') or '').strip())
        seen.setdefault(key, []).append(r)
    for (team, name), lst in seen.items():
        if team and name and len(lst) > 1:
            add('warn', 'dup_name', '같은 구단에 같은 이름의 선수가 둘 이상', lst[0], f'{len(lst)}명')

    # 구단별 인원
    per_team = {}
    for r in rows:
        per_team.setdefault(r.get('team') or '(소속 없음)', []).append(r)
    for team, lst in per_team.items():
        if len(lst) < team_min or len(lst) > team_max:
            add('info', 'team_size', f'구단 선수 수가 {team_min}~{team_max}명을 벗어남', {'id': None, 'name': team, 'team': team}, f'{len(lst)}명')

    # 90분당 이상치 (같은 포지션 안에서)
    by_pos = {}
    for r in rows:
        if _n(r.get('minutes')) >= OUTLIER_MIN_MINUTES:
            by_pos.setdefault((r.get('position') or '').strip().upper(), []).append(r)
    for pos, lst in by_pos.items():
        if pos == 'GK' or len(lst) < 8:
            continue
        for k in OUTLIER_FIELDS:
            vals = [_n(r.get(k)) / _n(r.get('minutes')) * 90 for r in lst]
            med = _median(vals)
            mad = _median([abs(v - med) for v in vals])
            mean = sum(vals) / len(vals)
            sd = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
            scale = max(1.4826 * mad, 0.5 * sd, 1e-9)      # 중앙값이 0 인 지표에서 기준이 0 으로 무너지지 않게 표준편차로 바닥을 둔다
            for r, v in zip(lst, vals):
                if (v - med) / scale >= OUTLIER_Z and v >= OUTLIER_ABS_MIN.get(k, 0):
                    add('warn', f'outlier_{k}', f'같은 포지션 대비 90분당 {k} 가 비정상적으로 큼', r, f'{pos} 90분당 {v:.2f} (중앙값 {med:.2f})')

    issues = sorted(buckets.values(), key=lambda b: ({'error': 0, 'warn': 1, 'info': 2}[b['severity']], -b['count']))
    summary = {'error': 0, 'warn': 0, 'info': 0, 'players': len(rows)}
    for b in issues:
        summary[b['severity']] += b['count']
    return {'summary': summary, 'issues': issues}

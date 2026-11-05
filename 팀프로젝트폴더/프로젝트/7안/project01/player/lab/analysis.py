"""
감독 분석 엔진: 다음 상대 분석 · 로테이션 플래너 · 대체 불가 지수 · 라인업 진단

- Django/ORM 에 의존하지 않는 순수 파이썬이다. 예측 함수(forecast_fn, poisson_fn)는 밖에서 넣어 준다.
- 능력 점수(ability)는 사이트의 BEST11 점수를 {선수ID: 점수} 로 넘겨받는다. (이 파일은 점수 계산식을 알지 못한다)
- 모든 '라인업 보정', '대체 불가 지수' 는 기록 기반의 단순 계산이며 실제 경기 결과를 보장하지 않는다.
"""

try:
    from . import chemistry as CH
    from . import management as MG
except ImportError:                      # 단독 테스트용
    import chemistry as CH
    import management as MG

# =========================================================
# 조정 가능한 상수
# =========================================================

# 라인업 보정(실험): 라인업 평균 능력이 기준보다 1점 높을 때 내 예상 득점이 늘어나는 비율, 그리고 상한
LINEUP_EFFECT_PER_POINT = 0.005
LINEUP_EFFECT_CAP = 0.10

# 로테이션: 다음 경기 후 피로도가 이 값을 넘을 것 같으면 휴식 후보
REST_LIMIT = 50.0
REST_MAX_PER_ROUND = 3

# 대체 불가 지수: 대체 후보로 검토하는 최대 인원(같은 포지션, 능력 상위)
REPLACEMENT_CANDIDATES = 15
KEY_PLAYER_COUNT = 3
EASY_REPLACE_RATIO = 0.25          # 최대 지수의 이 비율 미만이면 '대체 용이'

FULL_TO_SHORT = {
    'FC서울': '서울', '울산HD': '울산', '전북현대': '전북', '강원FC': '강원', '광주FC': '광주',
    '김천상무': '김천', '대전하나시티즌': '대전', '부천FC1995': '부천', 'FC안양': '안양',
    '인천유나이티드': '인천', '제주SK FC': '제주', '포항스틸러스': '포항',
}


def short_name(team_name):
    return FULL_TO_SHORT.get(team_name, team_name)


# =========================================================
# 공통: 라인업 점수
# =========================================================

def lineup_total(lineup, ability, state, chem_scale=1.0):
    """
    라인업의 총점 = 각 선수의 (피로·경고 반영 능력 점수) + 케미 가산점.
    반환: (총점, lineup_chemistry 결과)
    """
    chem = CH.lineup_chemistry(lineup, scale=chem_scale)
    total = 0.0
    for p in lineup:
        st = state.get(str(p['id']), {})
        base = ability.get(p['id'], 0.0)
        adj = MG.adjusted_ability(base, st.get('fatigue', 0.0), st.get('yellow_acc', 0))
        total += CH.final_score(adj, chem['players'][p['id']]['bonus'])
    return total, chem


# =========================================================
# 1. 다음 상대 분석
# =========================================================

def lineup_strength_factor(lineup_mean, reference_mean):
    """라인업 평균 능력이 기준보다 높으면 1보다 큰 배율(상한 ±LINEUP_EFFECT_CAP)."""
    f = 1 + (lineup_mean - reference_mean) * LINEUP_EFFECT_PER_POINT
    return max(1 - LINEUP_EFFECT_CAP, min(1 + LINEUP_EFFECT_CAP, f))


def opponent_outlook(fixtures, team, forecast_fn, from_round, count=5, factor=1.0, poisson_fn=None):
    """
    team 의 남은 대진과 예상 결과.
    forecast_fn(home_short, away_short, date) -> 팀 예측 모델의 forecast 결과(dict). 예측 불가면 예외.
    factor != 1 이고 poisson_fn 이 있으면 내 예상 득점에 factor 를 곱해 확률을 다시 계산한다(라인업 보정).
    """
    out = []
    for f in fixtures.get(team, []):
        if f['round'] < from_round:
            continue
        if len(out) >= count:
            break
        home_short, away_short = (team, f['opponent']) if f['home'] else (f['opponent'], team)
        row = {'round': f['round'], 'date': f['date'].isoformat(), 'opponent': f['opponent'],
               'home': f['home'], 'available': False}
        try:
            fc = forecast_fn(home_short, away_short, f['date'])
        except Exception as exc:                       # PredictionUnavailable 등
            row['reason'] = str(exc)
            out.append(row)
            continue
        probs = {p['code']: p['percent'] for p in fc['probabilities']}
        mine_code, opp_code = ('H', 'A') if f['home'] else ('A', 'H')
        row.update(available=True, win=probs[mine_code], draw=probs['D'], loss=probs[opp_code],
                   my_goals=fc['expected_home_goals'] if f['home'] else fc['expected_away_goals'],
                   opp_goals=fc['expected_away_goals'] if f['home'] else fc['expected_home_goals'],
                   adjusted=False)
        if poisson_fn and abs(factor - 1.0) > 1e-9:
            my, op = row['my_goals'] * factor, row['opp_goals']
            hr, ar = (my, op) if f['home'] else (op, my)
            try:
                pr = poisson_fn(hr, ar)
                row.update(win=round(pr[mine_code] * 100, 1), draw=round(pr['D'] * 100, 1),
                           loss=round(pr[opp_code] * 100, 1), adjusted=True, factor=round(factor, 3))
            except Exception:
                pass
        out.append(row)
    return out


# =========================================================
# 2. 로테이션 플래너
# =========================================================

def plan_rotation(lineup, bench, state, meta, rounds, ability, prev_round, schedule, rest_limit=REST_LIMIT):
    """
    남은 라운드(rounds) 동안 같은 라인업을 쓰되, 피로가 많이 쌓일 선수는 같은 포지션 후보와 교체하는 계획.
    lineup/bench: 프로필 리스트, state/meta: management 의 상태와 선수 정보,
    meta[pid] = {'position','age','team'(짧은 이름),'season_yellow','season_red','season_minutes'}
    반환: {'rounds':[...], 'peak_without_rotation':, 'peak_with_rotation':}
    """
    def days(pid, ra, rb):
        return MG.days_between_rounds(schedule, meta[str(pid)].get('team'), ra, rb)

    def simulate(rotate):
        cur = [p['id'] for p in lineup]
        by_id = {p['id']: p for p in lineup + bench}
        st = {k: dict(v) for k, v in state.items()}
        prev, plan, peak = prev_round, [], 0.0
        for rd in rounds:
            gap = {k: days(k, prev, rd) for k in st}
            swaps = []
            if rotate:
                pre = {pid: MG.pre_match_fatigue(st[str(pid)], gap[str(pid)], meta[str(pid)].get('age')) for pid in by_id if str(pid) in st}
                risky = []
                for pid in cur:
                    streak = st[str(pid)].get('streak', 0) + 1
                    after = pre[pid] + MG.match_fatigue(90, meta[str(pid)].get('position'), streak)
                    if after > rest_limit:
                        risky.append((after, pid))
                risky.sort(reverse=True)
                for after, pid in risky[:REST_MAX_PER_ROUND]:
                    pos = by_id[pid]['position']
                    best, best_val = None, -1.0
                    for b in bench:
                        if b['id'] in cur or b['position'] != pos or str(b['id']) not in st:
                            continue
                        b_after = pre[b['id']] + MG.match_fatigue(90, pos, st[str(b['id'])].get('streak', 0) + 1)
                        if b_after > rest_limit:
                            continue
                        val = MG.adjusted_ability(ability.get(b['id'], 0.0), pre[b['id']], st[str(b['id'])].get('yellow_acc', 0))
                        if val > best_val:
                            best, best_val = b, val
                    if best is not None:
                        cur[cur.index(pid)] = best['id']
                        swaps.append({'out': pid, 'in': best['id'], 'out_name': by_id[pid]['name'], 'in_name': best['name'],
                                      'out_fatigue_after': round(after), 'reason': '휴식'})
            played = {str(pid): 90 for pid in cur}
            st, _ = MG.advance_round(st, played, meta, gap)
            lineup_fat = [st[str(pid)]['fatigue'] for pid in cur]
            peak = max(peak, max(lineup_fat))
            plan.append({'round': rd, 'lineup': list(cur), 'swaps': swaps,
                         'avg_fatigue': round(sum(lineup_fat) / len(lineup_fat), 1),
                         'max_fatigue': round(max(lineup_fat), 1)})
            prev = rd
        return plan, peak

    plan, peak_rot = simulate(True)
    _, peak_none = simulate(False)
    return {'rounds': plan, 'peak_with_rotation': round(peak_rot, 1), 'peak_without_rotation': round(peak_none, 1)}


# =========================================================
# 3. 대체 불가 지수
# =========================================================

def irreplaceability(lineup, pool, ability, state, chem_scale=1.0):
    """
    각 선수를 같은 포지션의 최선 대체 후보로 바꿨을 때 라인업 총점이 얼마나 떨어지는가.
    지수 = 총점 하락폭(≥0). index100 은 라인업 내 최대 하락폭을 100 으로 환산한 값.
    """
    base_total, _ = lineup_total(lineup, ability, state, chem_scale)
    in_lineup = {p['id'] for p in lineup}
    results = []
    for i, p in enumerate(lineup):
        cands = [c for c in pool if c['position'] == p['position'] and c['id'] not in in_lineup]
        cands.sort(key=lambda c: -ability.get(c['id'], 0.0))
        best_total, best_c = None, None
        for c in cands[:REPLACEMENT_CANDIDATES]:
            trial = list(lineup)
            trial[i] = c
            total, _ = lineup_total(trial, ability, state, chem_scale)
            if best_total is None or total > best_total:
                best_total, best_c = total, c
        drop = max(0.0, base_total - best_total) if best_total is not None else base_total
        results.append({'id': p['id'], 'name': p['name'], 'position': p['position'], 'drop': round(drop, 2),
                        'replacement': best_c['name'] if best_c else None,
                        'replacement_id': best_c['id'] if best_c else None})
    top = max((r['drop'] for r in results), default=0.0) or 1.0
    for r in results:
        r['index100'] = round(r['drop'] / top * 100)
    ranked = sorted(results, key=lambda r: -r['drop'])
    key_ids = {r['id'] for r in ranked[:KEY_PLAYER_COUNT]}
    for r in results:
        if r['id'] in key_ids and r['drop'] > 0:
            r['label'] = '핵심'
        elif r['drop'] < top * EASY_REPLACE_RATIO:
            r['label'] = '대체 용이'
        else:
            r['label'] = '보통'
    return {'total': round(base_total, 1), 'players': results}


# =========================================================
# 4. 라인업 진단 리포트
# =========================================================

LINE_ORDER = ['FW', 'MF', 'DF', 'GK']
LINE_LABEL = {'FW': '공격', 'MF': '미드필더', 'DF': '수비', 'GK': '골키퍼'}


def _percentile_of(value, sorted_vals):
    n = len(sorted_vals)
    if n == 0:
        return 50.0
    return sum(1 for v in sorted_vals if v <= value) / n * 100


def lineup_report(lineup, ability, state, meta, chem, irr, reference_abilities, today=None):
    """
    reference_abilities: {포지션: [리그 기준 선수들의 능력 점수]}  (라인별 위치 계산용)
    chem: lineup_chemistry 결과, irr: irreplaceability 결과
    """
    report = {'lines': [], 'categories': {}, 'facts': {}, 'notes': []}

    # 라인별 평균 위치 (같은 포지션 리그 기준 대비)
    refs = {pos: sorted(vals) for pos, vals in reference_abilities.items()}
    for pos in LINE_ORDER:
        members = [p for p in lineup if p['position'] == pos]
        if not members:
            continue
        pct = sum(_percentile_of(ability.get(p['id'], 0.0), refs.get(pos, [])) for p in members) / len(members)
        report['lines'].append({'position': pos, 'label': LINE_LABEL[pos], 'count': len(members), 'percentile': round(pct)})

    # 항목(카테고리) 평균: 해당 항목을 가진 선수들의 백분위 평균
    sums, cnt = {}, {}
    for p in lineup:
        for cat, v in p['cats'].items():
            sums[cat] = sums.get(cat, 0.0) + v
            cnt[cat] = cnt.get(cat, 0) + 1
    cats = {c: sums[c] / cnt[c] for c in sums}
    report['categories'] = {CH.CATEGORY_LABEL[c]: round(v) for c, v in cats.items()}
    ranked = sorted(cats.items(), key=lambda kv: -kv[1])
    strong, weak = ranked[:2], ranked[-2:]

    # 사실 지표
    team_count = {}
    for p in lineup:
        team_count[p['team_id']] = team_count.get(p['team_id'], 0) + 1
    top_team_id, top_team_n = max(team_count.items(), key=lambda kv: kv[1])
    ages = [meta[str(p['id'])].get('age') for p in lineup if meta.get(str(p['id']), {}).get('age') is not None]
    fat = [state.get(str(p['id']), {}).get('fatigue', 0.0) for p in lineup]
    exp_yellow = sum(MG.card_probability(meta[str(p['id'])].get('season_yellow'), meta[str(p['id'])].get('season_red'),
                                         meta[str(p['id'])].get('season_minutes')) for p in lineup) / 100.0
    report['facts'] = {
        'same_team_max': top_team_n,
        'same_team_name': meta[str(next(p['id'] for p in lineup if p['team_id'] == top_team_id))].get('team'),
        'avg_age': round(sum(ages) / len(ages), 1) if ages else None,
        'avg_fatigue': round(sum(fat) / len(fat), 1),
        'expected_yellow': round(exp_yellow, 2),
        'chemistry_team_score': chem['team_score'],
        'low_minutes_count': sum(1 for p in lineup if p['low_minutes']),
    }

    # 문장
    best_line = max(report['lines'], key=lambda x: x['percentile'])
    worst_line = min(report['lines'], key=lambda x: x['percentile'])
    notes = [f"{best_line['label']} 라인이 가장 강합니다 (같은 포지션 선수 중 상위 {max(1, 100 - best_line['percentile'])}% 수준)."]
    if worst_line['position'] != best_line['position']:
        notes.append(f"{worst_line['label']} 라인이 상대적으로 약합니다 (상위 {max(1, 100 - worst_line['percentile'])}% 수준).")
    notes.append(f"강점 항목: {', '.join(CH.CATEGORY_LABEL[c] for c, _ in strong)} / "
                 f"보완이 필요한 항목: {', '.join(CH.CATEGORY_LABEL[c] for c, _ in weak)}.")
    if 5 <= top_team_n < len(lineup):
        notes.append(f"{report['facts']['same_team_name']} 선수가 {top_team_n}명이라 팀 호흡 면에서 유리합니다.")
    if report['facts']['avg_age'] is not None:
        if report['facts']['avg_age'] >= 30:
            notes.append(f"평균 나이가 {report['facts']['avg_age']}세로 경험이 풍부한 구성입니다.")
        elif report['facts']['avg_age'] <= 24:
            notes.append(f"평균 나이가 {report['facts']['avg_age']}세로 젊은 구성입니다.")
    if report['facts']['low_minutes_count']:
        notes.append(f"출전 시간이 적어 기록이 불안정한 선수가 {report['facts']['low_minutes_count']}명 포함돼 있습니다.")
    keys = [r['name'] for r in irr['players'] if r['label'] == '핵심']
    if keys:
        notes.append(f"빠지면 타격이 큰 핵심 선수: {', '.join(keys)}.")
    report['notes'] = notes
    return report

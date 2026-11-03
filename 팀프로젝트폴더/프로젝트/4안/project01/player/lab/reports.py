"""선수별 분석 보고서(리그 전체). 라인업과 상관없이 선수 한 명 기준으로, 모든 문장에 근거 숫자(기록·주전급 평균·순위)를 붙인다.

- 기본 설정(기본 가중치, 케미 1×, 경험 보정 기본값)으로 계산해서 JSON 한 파일로 만든다. 팝업은 이 파일을 읽기만 한다.
- 선수 기록이 바뀌면 `python manage.py build_player_reports` 로 다시 만든다.
- 모든 수치는 올 시즌 기록 기반 추정이며 실제 경기 결과를 보장하지 않는다.
"""

from datetime import date

from . import chemistry as CH
from . import service as SVC

TEAMMATE_PARTNERS = 3
SIMILAR_COUNT = 3


def _verdict(pct, minutes):
    if minutes < SVC.SHRINK_FULL_MINUTES:
        return '표본 부족'
    if pct >= 85 and minutes >= 900:
        return '강력 추천'
    if pct >= 65:
        return '추천'
    if pct >= 35:
        return '무난'
    return '대안 검토'


def build_one(c, pid, peers_by_pos, teammates_by_key):
    i = c.info[pid]
    st = c.data['stats'][pid]
    pr = c.profiles[pid]
    pos = pr['position']
    ability = c.ability.get(pid, 0.0)
    bd = SVC._breakdown(c, pid)
    n = bd['ref_count']
    ev = lambda r: SVC._evidence(r).replace('{N}', str(n))

    peers = peers_by_pos[pos]                                   # 내림차순 능력 점수 (주전급)
    rank = sum(1 for v in peers if v > ability) + 1
    pct = round(sum(1 for v in peers if v < ability) / len(peers) * 100) if peers else 0
    top = max(1, 100 - pct)
    avg = sum(peers) / len(peers) if peers else 0.0
    ranked = i['minutes'] >= CH.REFERENCE_MIN_MINUTES            # 450분 미만이면 순위는 참고용

    strengths = sorted([r for r in bd['rows'] if r['pct'] >= 70 and r['weight'] >= 5], key=lambda r: -r['points'])[:3]
    weak = sorted([r for r in bd['rows'] if r['pct'] <= 30 and r['weight'] >= 8], key=lambda r: -r['weight'])[:2]

    # 같은 구단 같은 포지션 안에서의 위치
    mates = [q for q in teammates_by_key.get((i['team_id'], pos), []) if q['minutes'] >= CH.REFERENCE_MIN_MINUTES]
    mates_sorted = sorted(mates, key=lambda q: -c.ability.get(q['id'], 0.0))
    in_team = (mates_sorted.index(next(q for q in mates_sorted if q['id'] == pid)) + 1) if any(q['id'] == pid for q in mates_sorted) else None

    # 케미: 같은 구단 동료 중 잘 맞는 선수
    team_pool = [q for q in c.profiles.values() if q['team_id'] == i['team_id']]
    partners = [{'name': p['name'], 'position': p['position'], 'score': p['score'], 'reasons': p['reasons'][:2]}
                for p in CH.recommend_partners(pr, team_pool, k=TEAMMATE_PARTNERS)]

    # 같은 포지션에서 능력이 더 높은 비교 선수 (주전급)
    higher = sorted([q for q in c.profiles.values() if q['position'] == pos and q['id'] != pid and q['minutes'] >= CH.REFERENCE_MIN_MINUTES
                     and c.ability.get(q['id'], 0.0) > ability], key=lambda q: c.ability.get(q['id'], 0.0))[:SIMILAR_COUNT]
    similar = [{'name': q['name'], 'team': c.info[q['id']]['team'], 'ability': round(c.ability[q['id']], 1), 'minutes': q['minutes']} for q in higher]

    basis = f"올 시즌 {i['games']}경기 {i['minutes']}분 출전"
    for k, lab in (('goals', '골'), ('assists', '도움')):
        v = getattr(st, k, None)
        if v and pos != 'GK':
            basis += f" · {v}{lab}"
    conf = '높음' if i['minutes'] >= 1800 else ('보통' if i['minutes'] >= SVC.SHRINK_FULL_MINUTES else '낮음')
    risk = SVC.MG.card_probability(i['yellow'], i['red'], i['minutes'])
    risk_label = SVC.MG.card_risk_label(risk)
    club = c.data['club'].get(i['team_id'])

    low = i['minutes'] < SVC.SHRINK_FULL_MINUTES          # 표본 부족: 강점·위험 수치를 '근거'로 쓰지 않는다
    why = []
    if ranked:
        why.append(f"{pos} 리그 주전급(450분 이상) {len(peers)}명 중 능력 {rank}위, 상위 {top}% — 주전급 평균 {avg:.1f}점 대비 {ability - avg:+.1f}점.")
    else:
        why.append(f"출전 {i['minutes']}분으로 주전급(450분 이상) 기준에 못 미쳐 순위는 참고용입니다 (능력 {ability:.1f}점, 주전급 평균 {avg:.1f}점).")
    for r in strengths:
        why.append(f"[{'참고' if low else '강점'}] {ev(r)} → 능력 점수에 +{r['points']}점 (이 지표 비중 {r['weight']}%).")
    for r in weak:
        why.append(f"[약점] {ev(r)} → 비중 {r['weight']}% 지표라 점수를 깎습니다 (기여 {r['points']}점).")
    if bd['shrink'] is not None:
        why.append(f"[보정] 출전 {i['minutes']}분(450분 미만)이라 기록을 리그 평균 쪽으로 {round((1 - bd['shrink']) * 100)}% 끌어당겨 계산했습니다.")
    if bd['experience'] < 0.995:
        why.append(f"[보정] 경험: 출전 {i['minutes']}분 / 기준 {SVC.EXPERIENCE_FULL}분 → 점수에 ×{bd['experience']:.2f}.")

    hire = []
    if low:
        note = ', '.join(f"{x['label']}" for x in strengths[:2])
        hire.append(f"출전 {i['minutes']}분({i['games']}경기)뿐이라 '쓰는 이유'를 확정할 근거가 부족합니다." + (f" 기록상 {SVC.J(note, '이')} 눈에 띄지만 표본이 작아 우연일 수 있습니다." if note else ''))
    if not low and ranked and pct >= 70:
        hire.append(f"실력: 같은 포지션 {len(peers)}명 중 {rank}위(상위 {top}%)로, 주전급 평균보다 {ability - avg:+.1f}점 높습니다.")
    for r in ([] if low else strengths[:2]):
        hire.append(f"강점: {ev(r)}.")
    if not low and in_team and in_team <= 2 and len(mates_sorted) >= 2:
        hire.append(f"팀 내 위치: {i['team']}의 같은 포지션 주전급 {len(mates_sorted)}명 중 능력 {in_team}위입니다.")
    if partners and not low:
        hire.append(f"조합: 같은 구단의 {SVC.J(', '.join(p['name'] for p in partners), '와')} 케미가 맞습니다 ({'; '.join(partners[0]['reasons'][:1])} 등).")
    if i['minutes'] >= 1800:
        hire.append(f"검증: {basis} — 표본이 충분해 점수의 신뢰도가 높습니다.")
    if not hire:
        hire.append(f"뚜렷하게 내세울 강점은 없습니다 (능력 {ability:.1f}점, 주전급 평균 {avg:.1f}점).")

    cautions = []
    if i['minutes'] < SVC.SHRINK_FULL_MINUTES:
        cautions.append(f"기록 신뢰도 낮음: 출전 {i['minutes']}분({i['games']}경기)뿐이라 점수가 실제보다 높거나 낮을 수 있습니다.")
    elif i['minutes'] < 900:
        cautions.append(f"경험 부족: 출전 {i['minutes']}분({i['games']}경기)으로 검증이 충분하지 않습니다.")
    for r in ([] if low else weak[:1]):
        cautions.append(f"약점: {ev(r)}.")
    if low:
        pass                                              # 표본이 작아 경고 위험은 산정하지 않는다
    elif risk_label:
        cautions.append(f"{risk_label}: 올 시즌 경고 {i['yellow']}회 → 한 경기에서 경고를 받을 확률 약 {risk:.0f}%.")
    if similar and rank > 3 and ranked:
        s0 = similar[-1]
        cautions.append(f"비교: 같은 포지션에 능력이 더 높은 선수가 {rank - 1}명 있습니다 (바로 위 {s0['team']} {s0['name']} {s0['ability']}점).")

    verdict = _verdict(pct, i['minutes'])
    rule = '판단 기준: 출전 450분 미만 = 표본 부족 / 같은 포지션 상위 15% 이내(+900분 이상) = 강력 추천 / 상위 35% 이내 = 추천 / 상위 65% 이내 = 무난 / 그 아래 = 대안 검토.'
    conclusion = (f"{i['team']} {pos} {i['name']}: 능력 {ability:.1f}점" + (f"(리그 {rank}위/{len(peers)}명, 상위 {top}%)" if ranked else '(순위는 참고용)')
                  + f" — {verdict}.")
    return {'id': pid, 'name': i['name'], 'team': i['team'], 'position': pos, 'verdict': verdict, 'conclusion': conclusion, 'rule': rule,
            'basis': basis, 'confidence': conf, 'ability': round(ability, 1), 'rank': rank, 'rank_total': len(peers), 'top_pct': top, 'ranked': ranked,
            'team_rank': in_team, 'team_rank_total': len(mates_sorted), 'club_style': club['label'] if club else None,
            'rows': bd['rows'], 'why': why, 'hire': hire, 'cautions': cautions, 'partners': partners, 'similar': similar}


def build_all():
    """리그 전체 선수의 보고서. 기본 설정(가중치 기본, 케미 1×, 경험 보정 기본값)."""
    c = SVC.Ctx({})
    peers_by_pos = {}
    for pos in ('FW', 'MF', 'DF', 'GK'):
        peers_by_pos[pos] = sorted([c.ability[q['id']] for q in c.profiles.values() if q['position'] == pos and q['minutes'] >= CH.REFERENCE_MIN_MINUTES], reverse=True)
    tm = {}
    for q in c.profiles.values():
        tm.setdefault((q['team_id'], q['position']), []).append(q)
    players = {}
    for pid in c.profiles:
        if pid in c.data['stats'] and pid in c.info:
            players[str(pid)] = build_one(c, pid, peers_by_pos, tm)
    return {'meta': {'generated': date.today().isoformat(), 'season': SVC.SEASON, 'count': len(players),
                     'settings': '기본 가중치 · 케미 1× · 경험 보정 기본값', 'note': '올 시즌 기록 기반 추정이며 실제 경기 결과를 보장하지 않습니다. "주전급"은 같은 포지션에서 450분 이상 뛴 선수입니다.'},
            'players': players}

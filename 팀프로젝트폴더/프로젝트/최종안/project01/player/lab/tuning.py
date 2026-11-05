"""
상대 맞춤 가중치 (순수 파이썬)

- 다음 상대의 구단 스타일과 득실점 경향을 보고, 선수 점수의 지표별 가중치를 조금 조정한다.
- 규칙은 아래 표가 전부다. (설명 가능한 단순 규칙, 실제 전술 분석이 아니다)
- 규칙 배율에 TUNING_STRENGTH 제곱을 해서 강하게 만들고, 한 지표의 배율은 MULT_MIN ~ MULT_MAX 로 제한한다.
"""

# 기본 규칙 배율(1.2 등)에 TUNING_STRENGTH 제곱을 해서 효과를 키운다. 1.0 이면 은은한 조정, 2.5 이면 상대에 따라 선수 1명 정도가 바뀐다.
TUNING_STRENGTH = 2.5
MULT_MIN, MULT_MAX = 0.6, 1.8
TOP_FRACTION = 1 / 3        # 득점/실점이 상위 3분의 1 구단이면 '많음'

STYLE_RULES = {
    'possession': ({'recoveries': 1.2, 'interceptions': 1.2, 'tackle': 1.15},
                   '점유형 상대: 볼 회수·인터셉트·태클 비중을 높입니다'),
    'direct': ({'interceptions': 1.15, 'clearances': 1.15, 'aerial_duel': 1.15, 'pass_rate': 1.1},
               '직선형 상대: 인터셉트·클리어링·공중볼과 패스 안정성 비중을 높입니다'),
    'wing': ({'aerial_duel': 1.2, 'clearances': 1.2, 'blocks': 1.15},
             '측면형 상대: 공중볼·클리어링·블록 비중을 높입니다'),
    'press': ({'pass_rate': 1.2, 'dribble': 1.15},
              '압박형 상대: 패스 성공률·드리블(공 간수) 비중을 높입니다'),
}
MANY_CONCEDED = ({'goals': 1.15, 'shots_on_target': 1.15, 'key_passes': 1.1},
                 '실점이 많은 상대: 득점·유효슈팅·키패스 비중을 높입니다')
MANY_SCORED = ({'clearances': 1.1, 'interceptions': 1.1, 'tackle': 1.1, 'blocks': 1.1},
               '득점이 많은 상대: 수비 지표 비중을 높입니다')


def _is_top(team, table, key):
    vals = sorted((v[key] for v in table.values()), reverse=True)
    if not vals or team not in table:
        return False
    n = max(1, round(len(vals) * TOP_FRACTION))
    return table[team][key] >= vals[n - 1] and table[team][key] > sum(vals) / len(vals)


def opponent_multipliers(opp, club, goals=None):
    """
    opp: 상대 구단 id, club: club_profile.classify 결과, goals: {구단 id: {'gf','ga'}} (경기당, 없으면 생략)
    반환: (지표별 배율 dict, 이유 문장 리스트)
    """
    mult, reasons = {}, []

    def apply(rule):
        for k, v in rule[0].items():
            mult[k] = mult.get(k, 1.0) * v
        reasons.append(rule[1])

    info = club.get(opp)
    if info and info['style'] in STYLE_RULES:
        apply(STYLE_RULES[info['style']])
    if goals and opp in goals:
        if _is_top(opp, goals, 'ga'):
            apply(MANY_CONCEDED)
        if _is_top(opp, goals, 'gf'):
            apply(MANY_SCORED)
    for k in mult:
        mult[k] = round(max(MULT_MIN, min(MULT_MAX, mult[k] ** TUNING_STRENGTH)), 3)
    return mult, reasons

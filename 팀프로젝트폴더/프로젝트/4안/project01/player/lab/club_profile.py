"""
구단 스타일 프로필 (순수 파이썬)

- 구단 소속 선수들의 올 시즌 기록을 합쳐서 구단별 '경기당' 지표를 만들고, 12개 구단끼리 비교(z점수)해서 스타일을 정한다.
- 스타일은 기록으로 본 경향이며 실제 감독의 전술 선언이 아니다. 팀이 12개뿐이라 기준값이 조금만 달라져도 분류가 바뀔 수 있다.
- 한 구단 = 스타일 1개 (뚜렷하지 않으면 '균형형').
"""

STYLE_LABELS = {
    'possession': '점유형',
    'direct': '직선형',
    'wing': '측면형',
    'press': '압박형',
    'balanced': '균형형',
}

STYLE_THRESHOLD = 0.5      # 스타일 점수(z 평균)가 이 값 이상이어야 그 스타일. 아니면 균형형

AGG_FIELDS = ['minutes', 'pass_attempt', 'pass_success', 'long_pass_attempt', 'forward_pass_attempt',
              'cross_attempt', 'shots', 'recoveries', 'interceptions', 'tackle_attempt']


def _num(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def team_metrics(rows):
    """rows: [{'team_id', AGG_FIELDS...}] -> {team_id: {지표...}}  (경기당 = 총 출전시간 / 990)"""
    sums = {}
    for r in rows:
        t = r.get('team_id')
        if t is None:
            continue
        d = sums.setdefault(t, {k: 0.0 for k in AGG_FIELDS})
        for k in AGG_FIELDS:
            d[k] += _num(r.get(k))
    out = {}
    for t, d in sums.items():
        m = d['minutes'] / 990.0
        if m <= 0 or d['pass_attempt'] <= 0:
            continue
        out[t] = {
            'pass_volume': d['pass_attempt'] / m,
            'pass_rate': d['pass_success'] / d['pass_attempt'] * 100,
            'long_share': d['long_pass_attempt'] / d['pass_attempt'] * 100,
            'forward_share': d['forward_pass_attempt'] / d['pass_attempt'] * 100,
            'cross': d['cross_attempt'] / m,
            'shots': d['shots'] / m,
            'recoveries': d['recoveries'] / m,
            'interceptions': d['interceptions'] / m,
            'tackles': d['tackle_attempt'] / m,
        }
    return out


def _z(values):
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5 or 1.0
    return [(v - mean) / sd for v in values]


# 스타일 점수 = (+지표 z 들의 평균) - (-지표 z 들의 평균)
STYLE_FORMULA = {
    'possession': (['pass_volume', 'pass_rate'], ['long_share']),
    'direct': (['long_share', 'forward_share'], ['pass_volume']),
    'wing': (['cross'], []),
    'press': (['recoveries', 'interceptions', 'tackles'], []),
}


def classify(metrics, threshold=STYLE_THRESHOLD):
    """metrics: team_metrics 결과 -> {team_id: {'style','label','scores':{스타일:점수},'metrics'}}"""
    ids = list(metrics)
    if len(ids) < 4:
        return {t: {'style': 'balanced', 'label': STYLE_LABELS['balanced'], 'scores': {}, 'metrics': metrics[t]} for t in ids}
    keys = list(metrics[ids[0]])
    z = {k: dict(zip(ids, _z([metrics[t][k] for t in ids]))) for k in keys}
    out = {}
    for t in ids:
        scores = {}
        for style, (plus, minus) in STYLE_FORMULA.items():
            val = sum(z[k][t] for k in plus) / len(plus)
            if minus:
                val -= sum(z[k][t] for k in minus) / len(minus)
                val /= 2          # 두 묶음 차이이므로 크기를 맞춘다
            scores[style] = round(val, 2)
        best = max(scores, key=scores.get)
        style = best if scores[best] >= threshold else 'balanced'
        out[t] = {'style': style, 'label': STYLE_LABELS[style], 'scores': scores,
                  'metrics': {k: round(v, 1) for k, v in metrics[t].items()}}
    return out

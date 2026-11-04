"""
감독 연구실 서비스 계층 (Django 사용 부분)

- 기록·일정·예측은 여기서 읽고, 계산은 chemistry / management / analysis (순수 파이썬)에 맡긴다.
- 화면은 선수 ID 목록만 보낸다. 서버가 DB에서 점수를 다시 계산하므로 브라우저에서 점수를 바꿔 보낼 수 없다.
- 피로도·경고 누적은 '모의 경기'에서 쌓이는 기록(브라우저가 보내는 mock_log)을 처음부터 다시 계산(replay)해서 얻는다. 서버에는 저장하지 않는다.
  (베스트11 화면은 그 결과를 읽어서 보여 주기만 하고, 피로를 쌓지는 않는다)
- 모든 수치는 올 시즌 기록 기반의 추정이며 '게임 규칙'을 포함한다. 실제 경기 결과를 보장하지 않는다.
"""

import glob
import os
import time
from datetime import date, timedelta

from django.conf import settings

from player.models import PlayerStats
from player import services as SV

from . import chemistry as CH
from . import management as MG
from . import analysis as AN
from . import club_profile as CP
from . import tuning as TU
from . import quality as QL

SEASON = 2026
CACHE_SECONDS = 300
# 소표본 보정: 출전 450분 미만 선수의 90분당 기록은 리그 평균 쪽으로 끌어당긴다. (450분 이상은 그대로)
#   보정값 = w × 본인 기록 + (1-w) × SHRINK_TARGET × 같은 포지션 평균,  w = 출전시간 / 450
SHRINK_ENABLED = True
SHRINK_FULL_MINUTES = 450
SHRINK_TARGET = 0.85          # 정보가 부족하면 평균보다 조금 낮게 본다
NO_SHRINK_METRICS = {'minutes'}
# 경험(출전시간) 보정: 출전시간이 EXPERIENCE_FULL 분에 못 미치면 능력 점수에 1 미만의 배율을 곱한다.
#   배율 = 1 - 감점폭 × (1 - 출전시간/EXPERIENCE_FULL),  감점폭 = (1 - EXPERIENCE_FLOOR) × 화면의 '경험 중시' 배율(0~2, 기본 1)
#   (경기 수는 출전시간과 거의 같이 움직이고, 교체로 잠깐 뛴 경기는 시간으로 걸러지므로 출전시간 하나로 본다)
EXPERIENCE_FULL = 1800        # 시즌의 약 60%: 이 이상 뛰면 감점 없음
EXPERIENCE_DEFAULT = 1.5      # '경험 중시' 기본 배율 (감점폭 0.30 × 1.5 = 최대 45% 감점, 출전 0분일 때)
EXPERIENCE_FLOOR = 0.70       # 출전시간 0분일 때의 배율(기본 설정)
CANDIDATE_LIMIT = 40
CONDITION_BAD_FATIGUE = 71            # 이 이상이면 모의 경기 컨디션을 '안 좋음' 으로 제안한다 (management 의 '기용 비권장' 구간)

METRIC_FUNCS = {'FW': SV.get_fw_metrics, 'MF': SV.get_mf_metrics, 'DF': SV.get_df_metrics, 'GK': SV.get_gk_metrics}
BASE_WEIGHTS = {'FW': SV.FW_WEIGHTS, 'MF': SV.MF_WEIGHTS, 'DF': SV.DF_WEIGHTS, 'GK': SV.GK_WEIGHTS}

METRIC_LABELS = {
    'goals': '득점', 'assists': '도움', 'shots_on_target': '유효슈팅', 'shots': '슈팅', 'key_passes': '키패스',
    'dribble': '드리블', 'pass_rate': '패스 성공률', 'recoveries': '볼 회수', 'interceptions': '인터셉트',
    'clearances': '클리어링', 'tackle': '태클', 'aerial_duel': '공중볼 경합', 'ground_duel': '지상 경합',
    'defensive_blocks': '수비 차단', 'blocks': '블록', 'rating': '평점', 'mom': 'MOM', 'best11': '베스트11 선정',
    'minutes': '출전시간',
}

# 프리셋 = 지표별 배율(없으면 1). 포지션 안에서 합계 100 으로 다시 맞춘다.
PRESETS = {
    'default': {'label': '기본', 'mult': {}},
    'attack': {'label': '공격 중시', 'mult': {'goals': 1.5, 'assists': 1.3, 'shots_on_target': 1.3, 'key_passes': 1.3, 'dribble': 1.3,
                                              'clearances': 0.7, 'blocks': 0.7, 'defensive_blocks': 0.7}},
    'defense': {'label': '수비 중시', 'mult': {'clearances': 1.4, 'interceptions': 1.4, 'tackle': 1.4, 'recoveries': 1.3,
                                              'aerial_duel': 1.3, 'ground_duel': 1.3, 'blocks': 1.3, 'defensive_blocks': 1.3,
                                              'goals': 0.7, 'shots': 0.7}},
    'build': {'label': '빌드업·점유', 'mult': {'pass_rate': 1.7, 'key_passes': 1.3, 'assists': 1.2, 'dribble': 0.8}},
    'press': {'label': '압박·볼 회수', 'mult': {'recoveries': 1.7, 'interceptions': 1.4, 'tackle': 1.4, 'ground_duel': 1.3, 'goals': 0.8}},
}

_cache = {'t': 0, 'data': None}


# ---------------------------------------------------------------- 데이터 로드

def _load():
    now = time.time()
    if _cache['data'] is not None and now - _cache['t'] < CACHE_SECONDS:
        return _cache['data']
    qs = (PlayerStats.objects.filter(season=SEASON, minutes__gt=0)
          .exclude(player_id__in=SV.EXCLUDED_PLAYER_IDS)
          .select_related('player', 'player__team'))
    rows, stats_by_id = [], {}
    for st in qs:
        pos = (st.player.position or '').strip().upper()
        if pos not in METRIC_FUNCS:
            continue
        row = {f: getattr(st, f, None) for f in CH.STAT_FIELDS}
        row.update(player_id=st.player_id, name=st.player.name, position=pos, team_id=st.player.team_id)
        rows.append(row)
        stats_by_id[st.player_id] = st
    club = CP.classify(CP.team_metrics([
        dict({k: getattr(st, k, 0) for k in CP.AGG_FIELDS}, team_id=st.player.team_id) for st in stats_by_id.values()]))
    for row in rows:
        ci = club.get(row['team_id'])
        row['club_style'] = ci['style'] if ci else None
        row['club_style_label'] = ci['label'] if ci else ''
    profiles = CH.build_profiles(rows)
    info = {}
    for pid, st in stats_by_id.items():
        pl = st.player
        photo = ''
        try:
            photo = pl.photo.url if pl.photo else ''
        except Exception:
            photo = ''
        logo = ''
        try:
            logo = pl.team.logo.url if pl.team_id and pl.team.logo else ''
        except Exception:
            logo = ''
        info[pid] = {'id': pid, 'team_logo': logo, 'name': pl.name, 'position': (pl.position or '').strip().upper(),
                     'team_id': pl.team_id, 'team': pl.team.team_name if pl.team_id else '',
                     'team_short': AN.short_name(pl.team.team_name) if pl.team_id else '',
                     'number': pl.number, 'photo': photo, 'birth_date': pl.birth_date,
                     'minutes': st.minutes, 'games': st.games, 'yellow': st.yellow_cards, 'red': st.red_cards}
    data = {'profiles': profiles, 'stats': stats_by_id, 'info': info, 'club': club}
    _cache.update(t=now, data=data)
    return data


def clear_cache():
    _cache.update(t=0, data=None)


# ---------------------------------------------------------------- 가중치와 능력 점수

def build_weights(preset='default', mult=None, extra=None):
    """지표 배율(프리셋 + 사용자가 조정한 값)을 적용한 포지션별 가중치(합계 100).

    사용자 배율 키는 'FW:goals' 처럼 포지션별로 받는다(공격수 득점을 바꿔도 미드필더 득점은 그대로).
    예전 형식('goals')도 읽는다 — 그 경우 그 지표가 있는 모든 포지션에 적용된다.
    """
    pm = dict(PRESETS.get(preset, PRESETS['default'])['mult'])
    per_pos = {}
    for k, v in (mult or {}).items():
        try:
            val = max(0.0, min(20.0, float(v)))   # 화면에서 가중치 점수 0~100 입력 → 기본 5점 지표도 100까지(100/5=20배)
        except (TypeError, ValueError):
            continue
        if ':' in str(k):
            per_pos[str(k)] = val
        else:
            pm[k] = val
    extra = extra or {}                           # 상대 맞춤 배율은 프리셋·사용자 조정 위에 곱한다
    out = {}
    for pos, base in BASE_WEIGHTS.items():
        raw = {m: w * per_pos.get(f'{pos}:{m}', pm.get(m, 1.0)) * extra.get(m, 1.0) for m, w in base.items()}
        total = sum(raw.values()) or 1.0
        out[pos] = {m: v / total * 100 for m, v in raw.items()}
    return out


def ability_scores(weights, shrink=None, exp_scale=None):
    exp_scale = EXPERIENCE_DEFAULT if exp_scale is None else exp_scale
    """{선수ID: 능력 점수}. 최고값 기준은 450분 이상 선수(사이트 BEST11 과 같은 기준)이다."""
    shrink = SHRINK_ENABLED if shrink is None else shrink
    data = _load()
    by_pos = {}
    for pid, st in data['stats'].items():
        by_pos.setdefault(st.player.position.strip().upper(), []).append((pid, st))
    ability = {}
    for pos, items in by_pos.items():
        fn, w = METRIC_FUNCS[pos], weights[pos]
        mets = {pid: fn(st) for pid, st in items}
        ref = [pid for pid, st in items if st.minutes >= SV.FORMATION_MIN_MINUTES] or [pid for pid, _ in items]
        maxes = {m: max((mets[pid][m] for pid in ref), default=0) for m in w}
        means = {m: sum(mets[pid][m] for pid in ref) / len(ref) for m in w}
        for pid, st in items:
            vals = mets[pid]
            if shrink and st.minutes < SHRINK_FULL_MINUTES:
                f = max(0.0, st.minutes) / SHRINK_FULL_MINUTES
                vals = {m: (vals[m] if m in NO_SHRINK_METRICS else f * vals[m] + (1 - f) * SHRINK_TARGET * means[m]) for m in vals}
            score = sum(SV.normalize_score(vals[m], maxes[m]) * w[m] / 100 for m in w)
            if exp_scale > 0 and st.minutes < EXPERIENCE_FULL:
                score *= max(0.0, 1 - (1 - EXPERIENCE_FLOOR) * exp_scale * (1 - max(0, st.minutes) / EXPERIENCE_FULL))
            ability[pid] = round(min(100.0, score), 2)
    return ability


# ---------------------------------------------------------------- 일정·예측

_sched = {'key': None, 'data': None}
_pred = {'obj': None, 'err': None}


def schedule():
    folder = os.path.join(str(settings.BASE_DIR), 'data', 'matches', '2026', 'official_verified')
    files = sorted(glob.glob(os.path.join(folder, 'official_source_*.json')))
    if not files:
        return None
    key = (files[-1], os.path.getmtime(files[-1]))
    if _sched['key'] != key:
        _sched.update(key=key, data=MG.load_schedule(files[-1]))
    return _sched['data']


def _forecast_tools():
    """팀원이 만든 team.match_prediction 을 그대로 사용한다. 못 불러오면 (None, 이유)."""
    if _pred['obj'] is None and _pred['err'] is None:
        try:
            from team import match_prediction as MP
            matches, sha = MP.load_matches()
            bundle = MP.load_bundle(sha)
            ids = {r['name']: r['id'] for r in MP.team_options(matches)}
            _pred['obj'] = (MP, matches, bundle, ids)
        except Exception as exc:
            _pred['err'] = str(exc)
    return _pred['obj'], _pred['err']


def _meta(info, today):
    return {str(pid): {'position': i['position'], 'age': MG.age_on(i['birth_date'], today), 'team': i['team_short'],
                       'season_yellow': i['yellow'], 'season_red': i['red'], 'season_minutes': i['minutes']}
            for pid, i in info.items()}


def _parse_date(v, default=None):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return default


def clean_log(raw):
    """브라우저가 보낸 모의 경기 기록을 정리한다. 형식: [{'date':'YYYY-MM-DD','ids':[선수ID...]}] (최대 60건)"""
    out = []
    for e in (raw or [])[:60]:
        if not isinstance(e, dict):
            continue
        d = _parse_date(e.get('date'))
        ids = []
        for x in (e.get('ids') or [])[:60]:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                pass
        if d and ids:
            out.append((d, ids))
    out.sort(key=lambda t: t[0])
    return out


def replay_mock(info, meta, log, target_date):
    """
    모의 경기 기록(log)을 날짜순으로 다시 계산해서 target_date 킥오프 직전의 상태를 돌려준다.
    - 경기에 나온 선수는 90분 출전(피로 누적, 연속 출전 횟수 +1).
    - 같은 경기에 나온 구단의 나머지 선수는 '쉬었음'으로 보고 연속 출전이 끊긴다.
    - 그 경기와 상관없는 구단 선수는 아무것도 바뀌지 않고, 시간이 지난 만큼만 회복한다.
    - target_date 이후(같은 날 포함)의 기록은 반영하지 않는다.
    """
    st_rows = [{'id': pid, 'position': i['position'], 'birth_date': i['birth_date'], 'minutes': i['minutes'],
                'games': i['games'], 'yellow_cards': i['yellow']} for pid, i in info.items()]
    state = MG.initial_state(st_rows)
    last = {}
    for d, ids in log:
        if d >= target_date:
            continue
        teams = {info[i]['team_id'] for i in ids if i in info}
        sub = {str(pid): state[str(pid)] for pid, i in info.items() if i['team_id'] in teams}
        days = {k: max(0, (d - last.get(k, d - timedelta(days=7))).days) for k in sub}
        played = {str(i): 90 for i in ids if str(i) in sub}
        new, _ = MG.advance_round(sub, played, meta, days)
        state.update(new)
        for k in sub:
            last[k] = d
    out = {}
    for k, v in state.items():
        gap = max(0, (target_date - last.get(k, target_date - timedelta(days=7))).days)
        out[k] = dict(v, fatigue=MG.pre_match_fatigue(v, gap, meta[k]['age']))
    return out


def goal_table(info):
    """{구단 DB id: {'gf': 경기당 득점, 'ga': 경기당 실점}} — 팀원의 경기 결과 파일에서. 못 읽으면 빈 dict."""
    pred, _err = _forecast_tools()
    if pred is None:
        return {}
    matches = pred[1]
    short_to_id = {}
    for i in info.values():
        if i['team_id']:
            short_to_id[i['team_short']] = i['team_id']
    acc = {}
    for m in matches:
        hg, ag = m.get('home_goals'), m.get('away_goals')
        if hg is None or ag is None:
            continue
        for team, gf, ga in ((m['home_team'], hg, ag), (m['away_team'], ag, hg)):
            tid = short_to_id.get(team)
            if tid:
                d = acc.setdefault(tid, {'gf': 0, 'ga': 0, 'n': 0})
                d['gf'] += gf
                d['ga'] += ga
                d['n'] += 1
    return {t: {'gf': d['gf'] / d['n'], 'ga': d['ga'] / d['n']} for t, d in acc.items() if d['n']}


# ---------------------------------------------------------------- 컨텍스트 (요청 하나의 계산 환경)

class Ctx:
    def __init__(self, body):
        self.data = _load()
        self.today = date.today()
        self.preset = body.get('preset', 'default')
        self.opponent = None
        extra, self.opp_reasons = {}, []
        try:
            opp = int(body.get('opponent')) if body.get('opponent') else None
        except (TypeError, ValueError):
            opp = None
        if opp and any(i['team_id'] == opp for i in self.data['info'].values()):
            self.opponent = opp
            extra, self.opp_reasons = TU.opponent_multipliers(opp, self.data['club'], goal_table(self.data['info']))
        self.opp_mult = extra
        self.weights = build_weights(self.preset, body.get('mult'), extra)
        try:
            self.exp_scale = max(0.0, min(2.0, float(body.get('exp_scale', EXPERIENCE_DEFAULT))))
        except (TypeError, ValueError):
            self.exp_scale = EXPERIENCE_DEFAULT
        self.ability = ability_scores(self.weights, exp_scale=self.exp_scale)
        try:
            self.chem_scale = max(0.0, min(2.0, float(body.get('chem_scale', 1.0))))
        except (TypeError, ValueError):
            self.chem_scale = 1.0
        team = body.get('team') or None
        try:
            self.team_id = int(team) if team else None
        except (TypeError, ValueError):
            self.team_id = None
        self.formation = body.get('formation') if body.get('formation') in SV.FORMATIONS else '4-3-3'
        self.profiles, self.info = self.data['profiles'], self.data['info']
        self.meta = _meta(self.info, self.today)
        self.sch = schedule()
        # 피로도·경고 누적은 '모의 경기' 에서 쌓인 기록만 반영한다. (베스트11 화면은 읽기만 한다)
        self.managed = bool(body.get('use_fatigue'))
        self.target = _parse_date(body.get('date'), self.today)
        # 남은 정규 라운드 = 기준일 당일 이후에 열리는 라운드
        self.first = MG.first_unplayed_round(self.sch, self.target - timedelta(days=1)) if self.sch else None
        self.log = clean_log(body.get('mock_log'))
        if self.managed:
            self.state = replay_mock(self.info, self.meta, self.log, self.target)
        else:
            self.state = {str(pid): {'fatigue': 0.0, 'yellow_acc': 0, 'streak': 0} for pid in self.info}

    # 대상 선수 풀 (구단 선택 시 그 구단, 아니면 리그 전체)
    def pool(self):
        return [p for p in self.profiles.values() if self.team_id is None or p['team_id'] == self.team_id]

    def adj(self, pid):
        """감독 모드일 때만 피로도·신중 플레이 효과를 반영한 능력."""
        base = self.ability.get(pid, 0.0)
        if not self.managed:
            return base
        s = self.state.get(str(pid), {})
        return MG.adjusted_ability(base, s.get('fatigue', 0.0), s.get('yellow_acc', 0))

    def lineup_profiles(self, ids):
        return [self.profiles[i] for i in ids if i in self.profiles]

    def score_lineup(self, lineup):
        chem = CH.lineup_chemistry(lineup, scale=self.chem_scale)
        total = sum(CH.final_score(self.adj(p['id']), chem['players'][p['id']]['bonus']) for p in lineup)
        return total, chem

    def badges(self, pid):
        i = self.info[pid]
        s = self.state.get(str(pid), {})
        risk = MG.card_probability(i['yellow'], i['red'], i['minutes'])
        out = {'risk': risk, 'risk_label': MG.card_risk_label(risk), 'badges': []}
        if self.managed:
            out['badges'] = MG.availability(s, risk)['badges']
            out['fatigue'] = round(s.get('fatigue', 0.0))
            out['yellow_acc'] = s.get('yellow_acc', 0)
        if self.profiles[pid]['low_minutes']:
            out['badges'].append('출전 적음')
        gp = i['minutes'] / i['games'] if i['games'] else 0
        out['avg_minutes'] = round(gp)
        return out

    def brief(self, pid):
        i = self.info[pid]
        p = self.profiles[pid]
        return {'id': pid, 'name': i['name'], 'position': i['position'], 'team': i['team'], 'team_id': i['team_id'],
                'number': i['number'], 'photo': i['photo'], 'team_logo': i['team_logo'], 'minutes': i['minutes'], 'low_minutes': p['low_minutes'],
                'ability': round(self.ability.get(pid, 0.0), 1), 'adjusted': round(self.adj(pid), 1)}


# ---------------------------------------------------------------- API 로직

def api_init(body):
    c = Ctx(body)
    teams = sorted({(i['team_id'], i['team']) for i in c.info.values() if i['team_id']}, key=lambda x: x[1])
    pred, err = _forecast_tools()
    club = c.data['club']
    return {
        'teams': [{'id': t, 'name': n, 'style': club[t]['label'] if t in club else ''} for t, n in teams],
        'club_styles': [{'id': t, 'name': n, 'style': club[t]['label'], 'scores': club[t]['scores'], 'metrics': club[t]['metrics']}
                        for t, n in teams if t in club],
        'formations': SV.FORMATIONS,
        'presets': {k: v['label'] for k, v in PRESETS.items()},
        'metrics': {pos: [{'key': m, 'label': METRIC_LABELS.get(m, m), 'weight': round(w, 1)} for m, w in BASE_WEIGHTS[pos].items()]
                    for pos in BASE_WEIGHTS},
        'today': c.today.isoformat(),
        'prediction': {'available': pred is not None, 'trained_through': pred[2]['trained_through'] if pred else None, 'error': err},
        'schedule_note': '일정 파일 기준일은 파일을 받은 시점입니다. 오늘 날짜 이후 경기만 남은 라운드로 봅니다.',
    }


def _default_lineup(c):
    cnt = SV.FORMATIONS[c.formation]
    pool = c.pool()
    ids = []
    for pos in ('GK', 'DF', 'MF', 'FW'):
        cands = [p for p in pool if p['position'] == pos]
        cands.sort(key=lambda p: -(c.adj(p['id']) * (0.85 if p['low_minutes'] else 1.0)))
        ids += [p['id'] for p in cands[:cnt[pos]]]
    return ids


def api_lineup(body):
    """기본 라인업(능력 순) 또는 케미까지 반영해 다듬은 라인업(optimize=true)."""
    c = Ctx(body)
    ids = _default_lineup(c)
    if body.get('optimize'):
        lineup = c.lineup_profiles(ids)
        pool = c.pool()
        for _ in range(2):
            changed = False
            for idx in range(len(lineup)):
                cur_total, _chem = c.score_lineup(lineup)
                taken = {p['id'] for p in lineup}
                cands = [p for p in pool if p['position'] == lineup[idx]['position'] and p['id'] not in taken]
                cands.sort(key=lambda p: -c.adj(p['id']))
                best, best_total = None, cur_total
                for cand in cands[:8]:
                    trial = list(lineup)
                    trial[idx] = cand
                    t, _chem = c.score_lineup(trial)
                    if t > best_total + 1e-6:
                        best, best_total = cand, t
                if best:
                    lineup[idx] = best
                    changed = True
            if not changed:
                break
        ids = [p['id'] for p in lineup]
    return {'lineup': ids}


def _validate_lineup(c, body):
    ids = []
    for x in body.get('lineup') or []:
        try:
            x = int(x)
        except (TypeError, ValueError):
            continue
        if x in c.profiles and x not in ids:
            ids.append(x)
    return ids


def api_evaluate(body):
    c = Ctx(body)
    ids = _validate_lineup(c, body)
    lineup = c.lineup_profiles(ids)
    if len(lineup) != 11:
        return {'error': '선수 11명이 필요합니다.'}
    total, chem = c.score_lineup(lineup)
    players = []
    for p in lineup:
        pid = p['id']
        cp = chem['players'][pid]
        d = c.brief(pid)
        d.update(c.badges(pid))
        d['chem_bonus'] = cp['bonus']
        d['final'] = round(CH.final_score(c.adj(pid), cp['bonus']), 1)
        d['partners'] = [{'id': q['id'], 'name': q['name'], 'score': q['score'], 'tier': q['tier'], 'reasons': q['reasons']}
                         for q in cp['partners'][:3]]
        d['chem_reason'] = _chem_reason(p, lineup, cp)
        players.append(d)

    # 추천: 이 라인업 밖에서 라인업 선수와 케미가 좋은 선수
    taken = set(ids)
    recs = []
    for p in lineup:
        found = CH.recommend_partners(p, [q for q in c.pool() if q['id'] not in taken], k=1)
        if found:
            f = found[0]
            recs.append({'for_id': p['id'], 'for_name': p['name'], 'id': f['id'], 'name': f['name'], 'position': f['position'],
                         'score': f['score'], 'reasons': f['reasons'], 'low_minutes': f['low_minutes']})
    recs.sort(key=lambda r: -r['score'])

    # 분석
    ability_adj = {pid: c.adj(pid) for pid in c.profiles}
    irr_pool = c.pool()
    irr = AN.irreplaceability(lineup, irr_pool, ability_adj, {}, c.chem_scale)
    refs = {}
    for pos in ('FW', 'MF', 'DF', 'GK'):
        refs[pos] = [c.ability[q['id']] for q in c.profiles.values() if q['position'] == pos and q['minutes'] >= CH.REFERENCE_MIN_MINUTES]
    ability_for_report = {pid: c.ability.get(pid, 0.0) for pid in c.profiles}
    report = AN.lineup_report(lineup, ability_for_report, c.state, c.meta, chem, irr, refs, c.today)

    opp_name = next((i['team'] for i in c.info.values() if i['team_id'] == c.opponent), None) if c.opponent else None
    out = {'players': players, 'total': round(total, 1), 'chem_team': chem['team_score'], 'recommend': recs[:5],
           'irreplaceability': irr['players'], 'report': report, 'managed': c.managed,
           'opponent': {'name': opp_name, 'reasons': c.opp_reasons, 'mult': c.opp_mult} if c.opponent else None}
    return out          # 경기·일정·피로와 관련된 분석(다음 상대, 로테이션)은 모의 경기 화면의 api_schedule 이 맡는다


def _outlook(c, lineup):
    if not c.team_id:
        return {'available': False, 'reason': '구단을 선택하면 그 구단의 다음 상대를 분석합니다.'}
    pred, err = _forecast_tools()
    if pred is None or not c.sch:
        return {'available': False, 'reason': err or '일정/예측 데이터를 불러오지 못했습니다.'}
    if not c.first:
        return {'available': False, 'reason': '기준일 이후에 남은 정규 라운드가 없습니다.'}
    MP, matches, bundle, ids = pred
    team_short = next((i['team_short'] for i in c.info.values() if i['team_id'] == c.team_id), None)
    if team_short not in ids:
        return {'available': False, 'reason': '예측 모델에 없는 구단입니다.'}

    def fc(h, a, d):
        return MP.forecast(matches, bundle, ids[h], ids[a], d)

    ref_pool = [q for q in c.profiles.values() if q['minutes'] >= CH.REFERENCE_MIN_MINUTES]
    ref = sum(c.ability[q['id']] for q in ref_pool) / max(1, len(ref_pool))
    mean = sum(c.adj(p['id']) for p in lineup) / len(lineup)
    factor = AN.lineup_strength_factor(mean, ref)
    rows = AN.opponent_outlook(c.sch['fixtures'], team_short, fc, c.first, 5, factor, MP.poisson_probabilities)
    return {'available': True, 'rows': rows, 'factor': round(factor, 3), 'trained_through': bundle['trained_through'],
            'note': '예측 모델은 학습 마지막 날짜 이후 경기만 계산합니다. 라인업 보정은 실험 기능이며 최대 ±10% 입니다.'}


def _rotation(c, lineup):
    """남은 정규 라운드 로테이션 계획. 지금까지 모의 경기로 쌓인 피로(target 날짜 기준)에서 출발한다."""
    if not c.sch or not c.first:
        return None
    team = [p for p in c.profiles.values() if p['team_id'] == c.team_id]
    bench = [p for p in team if p['id'] not in {x['id'] for x in lineup}]
    rounds = [r for r in sorted(c.sch['rounds']) if r >= c.first]
    ability_adj = {pid: c.ability.get(pid, 0.0) for pid in c.profiles}
    team_short = next((i['team_short'] for i in c.info.values() if i['team_id'] == c.team_id), None)
    # prev_round = first 이므로 첫 라운드 앞의 회복일은 0일 (이미 target 날짜까지 회복한 상태에서 시작)
    res = AN.plan_rotation(lineup, bench, c.state, c.meta, rounds, ability_adj, c.first, c.sch)
    names = {pid: c.info[pid]['name'] for pid in c.info}
    for r in res['rounds']:
        r['lineup_names'] = [names[i] for i in r['lineup']]
    res['team'] = team_short
    return res


def api_condition(body):
    """
    모의 경기 화면용: 이 날짜에 이 선수들의 피로 상태. 피로가 많으면 '안 좋음' 컨디션을 제안한다.
    body: {mock_log:[{date,ids}], date:'YYYY-MM-DD', ids:[선수ID...]}
    """
    info = _load()['info']
    target = _parse_date(body.get('date'), date.today())
    meta = _meta(info, target)
    state = replay_mock(info, meta, clean_log(body.get('mock_log')), target)
    players = {}
    for x in (body.get('ids') or [])[:40]:
        try:
            pid = int(x)
        except (TypeError, ValueError):
            continue
        if pid not in info:
            continue
        s = state[str(pid)]
        risk = MG.card_probability(info[pid]['yellow'], info[pid]['red'], info[pid]['minutes'])
        tier = MG.fatigue_tier(s['fatigue'])
        players[pid] = {'fatigue': round(s['fatigue']), 'label': tier['label'], 'streak': s['streak'],
                        'badges': MG.availability(s, risk)['badges'],
                        'suggest_bad': s['fatigue'] >= CONDITION_BAD_FATIGUE}
    return {'players': players, 'date': target.isoformat(), 'records': len(clean_log(body.get('mock_log'))),
            'bad_from': CONDITION_BAD_FATIGUE}


def api_schedule(body):
    """
    모의 경기 화면용: 한 팀 선발 11명 기준으로 남은 정규 일정 예상(다음 상대)과 로테이션 계획.
    body: {mock_log:[{date,ids}], date:'YYYY-MM-DD', ids:[선수ID 11명]}
    피로는 모의 경기 기록을 기준으로 하고, 팀은 선수들의 소속으로 정한다.
    """
    b = dict(body, use_fatigue=True)
    probe = _load()
    ids = []
    for x in (body.get('ids') or [])[:20]:
        try:
            x = int(x)
        except (TypeError, ValueError):
            continue
        if x in probe['profiles'] and x not in ids:
            ids.append(x)
    if len(ids) != 11:
        return {'error': '선수 11명이 필요합니다.'}
    teams = [probe['info'][i]['team_id'] for i in ids]
    team_id = max(set(teams), key=teams.count)
    b['team'] = team_id
    c = Ctx(b)
    lineup = c.lineup_profiles(ids)
    return {'team': c.info[ids[0]]['team'] if teams.count(team_id) == len(teams) else '여러 구단 혼합',
            'mixed': teams.count(team_id) != len(teams),
            'outlook': _outlook(c, lineup), 'rotation': _rotation(c, lineup), 'date': c.target.isoformat()}


def api_candidates(body):
    """교체 후보: out_id 자리에 넣었을 때 라인업 총점이 높은 순. 맨 위가 '추천'이다."""
    c = Ctx(body)
    ids = _validate_lineup(c, body)
    try:
        out_id = int(body.get('out_id'))
    except (TypeError, ValueError):
        return {'error': 'out_id 가 필요합니다.'}
    if out_id not in ids:
        return {'error': '라인업에 없는 선수입니다.'}
    lineup = c.lineup_profiles(ids)
    idx = ids.index(out_id)
    pos = lineup[idx]['position']
    base_total, _chem = c.score_lineup(lineup)
    taken = set(ids)
    cands = [p for p in c.pool() if p['position'] == pos and p['id'] not in taken]
    cands.sort(key=lambda p: -c.adj(p['id']))
    rows = []
    for cand in cands[:CANDIDATE_LIMIT * 2]:
        trial = list(lineup)
        trial[idx] = cand
        t, chem = c.score_lineup(trial)
        cp = chem['players'][cand['id']]
        d = c.brief(cand['id'])
        d.update(c.badges(cand['id']))
        d.update(chem_bonus=cp['bonus'], delta=round(t - base_total, 1), final=round(CH.final_score(c.adj(cand['id']), cp['bonus']), 1),
                 partners=[{'id': q['id'], 'name': q['name'], 'score': q['score']} for q in cp['partners'][:2]])
        rows.append(d)
    rows.sort(key=lambda d: -d['delta'])
    rows = rows[:CANDIDATE_LIMIT]
    for k, d in enumerate(rows):
        d['recommended'] = k < 3 and d['delta'] > 0
    return {'candidates': rows, 'position': pos}



def api_formations(body):
    """포메이션별 점수. 같은 설정(가중치·케미·구단)에서 6개 포메이션의 자동 선발 라인업을 만들어 점수로 비교한다.
    - 점수 = 선수별 최종 점수(능력 + 케미, 상한 200점)의 합.
    - 포메이션마다 포지션 인원이 달라 합계만 보면 인원이 많은 쪽이 유리하므로,
      '리그 같은 포지션 주전급(450분 이상) 평균 대비 +몇 점'(vs_avg)을 순위 기준으로 쓴다. 백분위는 쓰지 않는다."""
    c = Ctx(body)
    ref = {}
    for pos in ('FW', 'MF', 'DF', 'GK'):
        vals = [c.ability[q['id']] for q in c.profiles.values() if q['position'] == pos and q['minutes'] >= CH.REFERENCE_MIN_MINUTES]
        ref[pos] = sum(vals) / len(vals) if vals else 0.0
    rows = []
    for f in SV.FORMATIONS:
        c.formation = f
        ids = _default_lineup(c)
        lineup = c.lineup_profiles(ids)
        if len(lineup) != 11:
            continue
        total, chem = c.score_lineup(lineup)
        vs_avg = sum(CH.final_score(c.adj(p['id']), chem['players'][p['id']]['bonus']) - ref[p['position']] for p in lineup)
        by_pos = {}
        for p in lineup:
            d = by_pos.setdefault(p['position'], {'n': 0, 'vs': 0.0})
            d['n'] += 1
            d['vs'] += CH.final_score(c.adj(p['id']), chem['players'][p['id']]['bonus']) - ref[p['position']]
        by_pos = {k: {'n': v['n'], 'vs': round(v['vs'], 1)} for k, v in by_pos.items()}
        rows.append({'formation': f, 'total': round(total, 1), 'avg': round(total / 11, 1), 'vs_avg': round(vs_avg, 1),
                     'chem_team': chem['team_score'], 'cap': CH.FINAL_SCORE_CAP, 'by_pos': by_pos})
    rows.sort(key=lambda r: -r['vs_avg'])
    for k, r in enumerate(rows):
        r['rank'] = k + 1
    return {'formations': rows, 'best': rows[0]['formation'] if rows else None}



def _short_reason(reasons):
    """케미 이유를 짧게: '보완: 찬스 창출' -> '찬스 창출 보완', '연계: 찬스 창출→득점력' -> '연계', '같은 구단' 은 마지막에."""
    out = []
    for r in reasons:
        if r.startswith('보완:'):
            out.append('보완')
        elif r.startswith('연계:'):
            out.append('연계')
        elif r.startswith('약점 중복:'):
            out.append('약점 중복')
        elif r.startswith('같은 구단') or r.startswith('같은 스타일'):
            out.append('같은 구단' if r.startswith('같은 구단') else '같은 스타일')
    seen = []
    for t in out:
        if t not in seen:
            seen.append(t)
    return '·'.join(seen[:2])


def _chem_reason(me, lineup, cp):
    """카드 옆에 작게 적는 케미 이유 한 줄. 가장 잘 맞는 상대, 가산이 없거나 감점이면 그 이유."""
    if cp['bonus'] > 0 and cp['partners']:
        q = cp['partners'][0]
        txt = _short_reason(q['reasons'])
        return J(q['name'], '와') + ' ' + txt if txt else q['name'] + '와 케미'
    worst = None
    for q in lineup:
        if q['id'] == me['id'] or not CH._counts_for_lineup(me, q):
            continue
        pc = CH.pair_chemistry(me, q)
        if pc['overlap'] and (worst is None or pc['score'] < worst[0]):
            worst = (pc['score'], q, pc)
    if worst and cp['bonus'] <= 0:
        return J(worst[1]['name'], '와') + ' ' + _short_reason(worst[2]['reasons'])
    return '뚜렷한 케미 근거 없음'


def api_chem_partners(body):
    """선수 한 명의 케미 파트너. 현재 라인업 안의 상대별 케미 점수·등급·이유, 그리고 라인업 밖(리그 전체)에서 케미가 좋은 후보."""
    c = Ctx(body)
    ids = _validate_lineup(c, body)
    try:
        pid = int(body.get('player_id'))
    except (TypeError, ValueError):
        return {'error': 'player_id 가 필요합니다.'}
    me = c.profiles.get(pid)
    if not me:
        return {'error': '이 선수의 기록이 없습니다.'}
    lineup = c.lineup_profiles(ids)
    inside = []
    for q in lineup:
        if q['id'] == pid or not CH._counts_for_lineup(me, q):
            continue
        pc = CH.pair_chemistry(me, q)
        inside.append({'id': q['id'], 'name': q['name'], 'position': q['position'], 'team': c.info[q['id']]['team'],
                       'score': pc['score'], 'tier': pc['tier'], 'bonus': pc['bonus'], 'overlap': pc['overlap'], 'reasons': pc['reasons']})
    inside.sort(key=lambda x: -x['score'])
    taken = set(ids)
    outside = []
    for r in CH.recommend_partners(me, [q for q in c.profiles.values() if q['id'] not in taken], k=5):
        r = dict(r)
        r['team'] = c.info[r['id']]['team']
        outside.append(r)
    cp = None
    if len(lineup) == 11 and pid in ids:
        _, chem = c.score_lineup(lineup)
        cp = chem['players'][pid]['bonus']
    return {'player': {'id': pid, 'name': me['name'], 'position': me['position'], 'team': c.info[pid]['team'],
                       'club_style': me.get('club_style_label', ''), 'low_minutes': me['low_minutes']},
            'chem_bonus': cp, 'inside': inside, 'outside': outside,
            'rule': '쌍 케미 = 역할 보완 55 + 인접 라인 연계 35 + 같은 구단 10 (같은 스타일 구단은 5). 70점 이상 강한 케미(+3), 55점 이상 케미 있음(+1.5), 약점이 겹치면 -1.'}


def _jong(word):
    """마지막 글자의 받침 번호(없으면 0, 한글이 아니면 0)."""
    w = (word or '').rstrip(')] ')
    ch = w[-1] if w else ''
    return (ord(ch) - 0xAC00) % 28 if '가' <= ch <= '힣' else 0


def J(word, kind):
    """조사 붙이기: 을/를, 이/가, 와/과, 으로/로 (이름이 받침으로 끝나는지에 따라)."""
    j = _jong(word)
    if kind == '을':
        return word + ('을' if j else '를')
    if kind == '이':
        return word + ('이' if j else '가')
    if kind == '와':
        return word + ('과' if j else '와')
    if kind == '로':
        return word + ('로' if j in (0, 8) else '으로')
    return word


NON_PER90 = {'rating', 'pass_rate', 'minutes'}
TOTAL_FIELD = {'goals': 'goals', 'assists': 'assists', 'shots_on_target': 'shots_on_target', 'shots': 'shots', 'key_passes': 'key_passes',
               'dribble': 'dribble_success', 'recoveries': 'recoveries', 'interceptions': 'interceptions', 'clearances': 'clearances',
               'blocks': 'blocks', 'defensive_blocks': 'defensive_blocks', 'mom': 'mom', 'best11': 'best11_count'}


def _evidence(r):
    """지표 한 줄 근거: 기록 · 주전급 평균 대비 · 순위."""
    if r['unit'] == 'rate':
        val = f"{r['label']} {r['value']:g}"
    else:
        tot = f"시즌 {r['total']:g}개, " if r['total'] not in (None, 0) else ''
        val = f"{r['label']} {tot}90분당 {r['value']:g}"
    cmp_ = f"주전급 평균 {r['mean']:g}" + (f"의 {r['ratio']:g}배" if r['ratio'] and r['ratio'] >= 1.3 else '')
    return f"{val} ({cmp_}, {{N}}명 중 {r['rank']}위)"


def _breakdown(c, pid):
    """선수 한 명의 능력 점수를 지표별로 쪼갠다. ability_scores 와 같은 식이라 합계가 능력 점수와 일치한다(보정 전 합계 × 경험 배율)."""
    data = c.data
    st = data['stats'][pid]
    pos = st.player.position.strip().upper()
    fn, w = METRIC_FUNCS[pos], c.weights[pos]
    items = [(q, s2) for q, s2 in data['stats'].items() if s2.player.position.strip().upper() == pos]
    mets = {q: fn(s2) for q, s2 in items}
    ref = [q for q, s2 in items if s2.minutes >= SV.FORMATION_MIN_MINUTES] or [q for q, _ in items]
    maxes = {m: max((mets[q][m] for q in ref), default=0) for m in w}
    means = {m: sum(mets[q][m] for q in ref) / len(ref) for m in w}
    raw = mets[pid]
    vals = raw
    f = 1.0
    if SHRINK_ENABLED and st.minutes < SHRINK_FULL_MINUTES:
        f = max(0.0, st.minutes) / SHRINK_FULL_MINUTES
        vals = {m: (raw[m] if m in NO_SHRINK_METRICS else f * raw[m] + (1 - f) * SHRINK_TARGET * means[m]) for m in raw}
    rows = []
    for m in w:
        lower = sum(1 for q in ref if mets[q][m] < raw[m])
        same = sum(1 for q in ref if mets[q][m] == raw[m] and q != pid)
        pct = round((lower + 0.5 * same) / len(ref) * 100)          # 같은 값(동률)은 절반만 아래로 본다
        got = SV.normalize_score(vals[m], maxes[m]) * w[m] / 100
        rank_m = sum(1 for q in ref if mets[q][m] > raw[m]) + 1
        total_field = TOTAL_FIELD.get(m)
        total_v = getattr(st, total_field, None) if total_field else None
        rows.append({'key': m, 'label': METRIC_LABELS.get(m, m), 'value': round(raw[m], 2), 'mean': round(means[m], 2), 'max': round(maxes[m], 2),
                     'pct': pct, 'rank': rank_m, 'ratio': round(raw[m] / means[m], 1) if means[m] > 0 else None,
                     'unit': 'rate' if m in NON_PER90 else 'per90', 'total': total_v, 'weight': round(w[m], 1), 'points': round(got, 1)})
    rows.sort(key=lambda r: -r['points'])
    exp = 1.0
    if c.exp_scale > 0 and st.minutes < EXPERIENCE_FULL:
        exp = max(0.0, 1 - (1 - EXPERIENCE_FLOOR) * c.exp_scale * (1 - max(0, st.minutes) / EXPERIENCE_FULL))
    return {'rows': rows, 'shrink': round(f, 2) if f < 1 else None, 'experience': round(exp, 3), 'ref_count': len(ref)}


def api_player_report(body):
    """BEST11 선수 팝업용 분석 보고서. 모든 문장에 근거 숫자(기록·주전급 평균·순위·점수 차이)를 붙인다.
    - 왜 이 점수인가: 지표별 기여 + 보정(소표본·경험) + 케미
    - 왜 쓰는가: 강점의 근거, 이 자리에서 대체 1순위와의 차이, 빠졌을 때 총점 변화
    - 주의점·대안: 약점·표본·경고 위험, 더 나은 대안"""
    c = Ctx(body)
    ids = _validate_lineup(c, body)
    try:
        pid = int(body.get('player_id'))
    except (TypeError, ValueError):
        return {'error': 'player_id 가 필요합니다.'}
    lineup = c.lineup_profiles(ids)
    if len(lineup) != 11 or pid not in ids:
        return {'error': '현재 라인업에 있는 선수만 분석할 수 있습니다.'}
    i = c.info[pid]
    st = c.data['stats'][pid]
    pr = c.profiles[pid]
    pos = pr['position']
    total, chem = c.score_lineup(lineup)
    cp = chem['players'][pid]
    ability = c.ability.get(pid, 0.0)
    final = CH.final_score(c.adj(pid), cp['bonus'])
    bd = _breakdown(c, pid)
    n = bd['ref_count']
    ev = lambda r: _evidence(r).replace('{N}', str(n))

    peers = sorted([c.ability[q['id']] for q in c.profiles.values() if q['position'] == pos and q['minutes'] >= CH.REFERENCE_MIN_MINUTES], reverse=True)
    rank = sum(1 for v in peers if v > ability) + 1
    pct = round(sum(1 for v in peers if v < ability) / len(peers) * 100) if peers else 0
    avg = sum(peers) / len(peers) if peers else 0.0
    top = max(1, 100 - pct)

    strengths = sorted([r for r in bd['rows'] if r['pct'] >= 70 and r['weight'] >= 5], key=lambda r: -r['points'])[:3]
    weak = sorted([r for r in bd['rows'] if r['pct'] <= 30 and r['weight'] >= 8], key=lambda r: -r['weight'])[:2]

    ability_adj = {q: c.adj(q) for q in c.profiles}
    irr = AN.irreplaceability(lineup, c.pool(), ability_adj, {}, c.chem_scale)
    me = next(r for r in irr['players'] if r['id'] == pid)
    cand = api_candidates(dict(body, out_id=pid))
    alts = [{'id': d['id'], 'name': d['name'], 'team': d['team'], 'ability': d['ability'], 'chem_bonus': d['chem_bonus'], 'delta': d['delta']}
            for d in cand.get('candidates', []) if d['delta'] > 0][:3]
    bg = c.badges(pid)

    # --- 대체 1순위와 지표별 직접 비교
    h2h = None
    if me['replacement_id'] and me['replacement_id'] in c.data['stats']:
        rb = _breakdown(c, me['replacement_id'])
        rmap = {r['key']: r for r in rb['rows']}
        rows = []
        for r in bd['rows']:
            o = rmap.get(r['key'])
            if o:
                rows.append({'label': r['label'], 'me': r['value'], 'other': o['value'], 'unit': r['unit'], 'lead': 'me' if r['value'] > o['value'] else ('other' if r['value'] < o['value'] else 'tie')})
        rinfo = c.info[me['replacement_id']]
        h2h = {'name': rinfo['name'], 'team': rinfo['team'], 'minutes': rinfo['minutes'], 'ability': round(c.ability.get(me['replacement_id'], 0.0), 1),
               'rows': rows, 'me_wins': sum(1 for r in rows if r['lead'] == 'me'), 'other_wins': sum(1 for r in rows if r['lead'] == 'other')}

    # --- 근거 자료 한 줄 (시즌 기록)
    basis = f"올 시즌 {i['games']}경기 {i['minutes']}분 출전"
    for k, lab in (('goals', '골'), ('assists', '도움')):
        v = getattr(st, k, None)
        if v and pos != 'GK':
            basis += f" · {v}{lab}"
    conf = '높음' if i['minutes'] >= 1800 else ('보통' if i['minutes'] >= SHRINK_FULL_MINUTES else '낮음')

    # --- 왜 이 점수인가
    why = [f"{pos} 리그 주전급(450분 이상) {len(peers)}명 중 능력 {rank}위, 상위 {top}% — 주전급 평균 {avg:.1f}점 대비 {ability - avg:+.1f}점."]
    for r in strengths:
        why.append(f"[강점] {ev(r)} → 능력 점수에 +{r['points']}점 (이 지표 비중 {r['weight']}%).")
    for r in weak:
        why.append(f"[약점] {ev(r)} → 비중 {r['weight']}% 지표라 점수를 깎습니다 (기여 {r['points']}점).")
    if bd['shrink'] is not None:
        why.append(f"[보정] 출전 {i['minutes']}분(450분 미만)이라 기록을 리그 평균 쪽으로 {round((1 - bd['shrink']) * 100)}% 끌어당겨 계산했습니다.")
    if bd['experience'] < 0.995:
        why.append(f"[보정] 경험: 출전 {i['minutes']}분 / 기준 {EXPERIENCE_FULL}분 → 점수에 ×{bd['experience']:.2f}.")
    why.append(f"[케미] {cp['bonus']:+.1f}점" + (': ' + ' · '.join(f"{q['name']}({'; '.join(q['reasons'][:1])})" if q.get('reasons') else q['name'] for q in cp['partners'][:3]) if cp['partners'] else ' (이 라인업에는 두드러지는 짝이 없음)') + f" → 최종 {final:.1f}점.")

    # --- 왜 쓰는가 (근거 있는 이유만)
    hire = []
    if pct >= 70:
        hire.append(f"실력: 같은 포지션 {len(peers)}명 중 {rank}위(상위 {top}%)로, 주전급 평균보다 {ability - avg:+.1f}점 높습니다.")
    for r in strengths[:2]:
        hire.append(f"강점: {ev(r)}.")
    if cp['bonus'] >= 1.0:
        hire.append(f"조합: 라인업의 {J(', '.join(q['name'] for q in cp['partners'][:3]), '와')} 케미가 맞아 {cp['bonus']:+.1f}점이 더해집니다.")
    if me['drop'] > 0:
        hire.append(f"대체 비교: 빼고 대체 1순위 {J(me['replacement'] or '-', '을')} 넣으면 라인업 총점이 {me['drop']}점 떨어집니다 ({me['label']}).")
    if h2h and h2h['me_wins']:
        hire.append(f"직접 비교: 대체 1순위 {h2h['name']}보다 {len(h2h['rows'])}개 지표 중 {h2h['me_wins']}개에서 앞섭니다 (능력 {ability:.1f} vs {h2h['ability']}점).")
    if i['minutes'] >= 1800:
        hire.append(f"검증: {basis} — 표본이 충분해 점수의 신뢰도가 높습니다.")
    if not hire:
        hire.append(f"뚜렷한 강점은 없습니다. 능력 {ability:.1f}점으로 주전급 평균({avg:.1f})과 비슷한 무난한 선택입니다.")

    # --- 주의점
    cautions = []
    if i['minutes'] < SHRINK_FULL_MINUTES:
        cautions.append(f"기록 신뢰도 낮음: 출전 {i['minutes']}분({i['games']}경기)뿐이라 점수가 실제보다 높거나 낮을 수 있습니다.")
    elif i['minutes'] < 900:
        cautions.append(f"경험 부족: 출전 {i['minutes']}분({i['games']}경기)으로 검증이 충분하지 않습니다.")
    for r in weak[:1]:
        cautions.append(f"약점: {ev(r)}.")
    if bg.get('risk_label'):
        cautions.append(f"{bg['risk_label']}: 올 시즌 경고 {i['yellow']}회 → 한 경기에서 경고를 받을 확률 약 {bg['risk']:.0f}%.")
    if h2h and h2h['other_wins'] > h2h['me_wins']:
        cautions.append(f"대체 1순위 {J(h2h['name'], '이')} {len(h2h['rows'])}개 지표 중 {h2h['other_wins']}개에서 더 앞섭니다.")
    elif me['label'] == '대체 용이':
        cautions.append(f"대체가 쉬운 자리입니다: {J(me['replacement'] or '대체 선수', '로')} 바꿔도 총점 하락이 {me['drop']}점뿐입니다.")
    if alts:
        cautions.append(f"더 나은 대안: {alts[0]['team']} {alts[0]['name']} 선수를 쓰면 라인업 총점이 {alts[0]['delta']:+.1f}점 오릅니다.")

    # --- 결론 (판단 기준을 그대로 밝힌다)
    if i['minutes'] < SHRINK_FULL_MINUTES:
        verdict = '표본 부족'
    elif pct >= 85 and i['minutes'] >= 900:
        verdict = '강력 추천'
    elif pct >= 65:
        verdict = '추천'
    elif pct >= 35:
        verdict = '무난'
    else:
        verdict = '대안 검토'
    rule = '판단 기준: 출전 450분 미만 = 표본 부족 / 같은 포지션 상위 15% 이내(+900분 이상) = 강력 추천 / 상위 35% 이내 = 추천 / 상위 65% 이내 = 무난 / 그 아래 = 대안 검토.'
    conclusion = (f"{i['team']} {pos} {i['name']}: 능력 {ability:.1f}점(리그 {rank}위/{len(peers)}명) + 케미 {cp['bonus']:+.1f} = 최종 {final:.1f}점."
                  + (f" 빠지면 총점 {me['drop']}점 하락." if me['drop'] > 0 else ' 빠져도 총점 변화가 거의 없습니다.')
                  + (f" 단, {J(alts[0]['name'], '이')} {alts[0]['delta']:+.1f}점 더 높습니다." if alts else ''))
    return {'player': {'id': pid, 'name': i['name'], 'team': i['team'], 'position': pos}, 'verdict': verdict, 'conclusion': conclusion, 'rule': rule,
            'basis': basis, 'confidence': conf, 'h2h': h2h,
            'ability': round(ability, 1), 'chem_bonus': cp['bonus'], 'final': round(final, 1), 'rank': rank, 'rank_total': len(peers), 'top_pct': top,
            'rows': bd['rows'], 'why': why, 'hire': hire, 'cautions': cautions, 'alternatives': alts,
            'irreplaceability': {'label': me['label'], 'drop': me['drop'], 'replacement': me['replacement']},
            'notes': '올 시즌 기록 기반 추정이며 실제 경기 결과를 보장하지 않습니다. 케미 가산점은 이 사이트의 게임 규칙입니다. "주전급"은 같은 포지션에서 450분 이상 뛴 선수입니다.'}


def api_quality(body):
    """선수 기록 데이터 점검 리포트. 관리자 제외선수·테스트 선수를 포함한 DB 전체(2026 시즌, 출전 기록 있는 선수)를 본다."""
    qs = (PlayerStats.objects.filter(season=SEASON).select_related('player', 'player__team'))
    rows = []
    for st in qs:
        d = {f: getattr(st, f, None) for f in set(CH.STAT_FIELDS) | {'games', 'best11_count', 'mom', 'dribble_success', 'cross_attempt',
                                                                       'cross_success', 'tackle_attempt', 'tackle_success',
                                                                       'aerial_duel_attempt', 'aerial_duel_success',
                                                                       'ground_duel_attempt', 'ground_duel_success'}}
        pl = st.player
        d.update(id=pl.id, name=pl.name, team_id=pl.team_id, team=pl.team.team_name if pl.team_id else '',
                 position=pl.position, birth_date=pl.birth_date)
        rows.append(d)
    return QL.check(rows)

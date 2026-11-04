"""승부예측(모의 경기)용 가상 데이터.

⚠ 여기서 만드는 값은 모두 '가상 데이터'다. 실제 선수 기록이 아니다.
  - 공식 기록을 구할 수 없는 항목(골키퍼 선방·실점·무실점·공중볼 처리, 활동량·스프린트)을 게임용으로 만든다.
  - 선수 ID를 씨앗(seed)으로 쓰므로 몇 번을 만들어도 같은 값이 나온다.
  - 실제 기록(PlayerStats)과 섞지 않고 data/virtual/2026_virtual_stats.json 에 따로 저장한다.
  - 골키퍼 실점은 실제 구단 실점(구단성적.json)을 기준으로 흔들어서 만들어, 너무 엉뚱한 값이 나오지 않게 했다.

다시 만들기: python manage.py make_virtual_stats
"""

import json
import math
import random
from datetime import datetime
from pathlib import Path

from django.conf import settings

SEED = '2026-virtual-v1'
NOTE = '가상 데이터: 공식 기록이 없어 게임용으로 만든 값입니다. 실제 선수 기록이 아닙니다.'

# 포지션별 기준값 (90분당). 일반적인 프로축구 수준을 참고한 게임용 기준이다.
DISTANCE_BASE = {'FW': 10.2, 'MF': 11.0, 'DF': 10.1, 'GK': 5.4}      # 뛴 거리 km
SPRINT_BASE = {'FW': 24.0, 'MF': 19.0, 'DF': 15.0, 'GK': 1.5}        # 스프린트 횟수

TEAM_SHORT = {
    '강원FC': '강원', '광주FC': '광주', '김천상무': '김천', '대전하나시티즌': '대전',
    '부천FC1995': '부천', 'FC서울': '서울', 'FC안양': '안양', '울산HD': '울산',
    '인천유나이티드': '인천', '전북현대': '전북', '제주SK FC': '제주', '포항스틸러스': '포항',
}

_cache = {}


def path():
    return Path(settings.BASE_DIR) / 'data' / 'virtual' / '2026_virtual_stats.json'


def player_age(player, on=None):
    """나이. DB의 age 칸이 비어 있어(0) 생년월일로 계산한다. 기준일은 시즌 말(2026-11-01)."""
    from datetime import date
    on = on or date(2026, 11, 1)
    b = player.birth_date
    if b:
        return on.year - b.year - ((on.month, on.day) < (b.month, b.day))
    return player.age or None


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def team_conceded_per_game():
    """실제 구단 실점 / 경기 (구단성적.json). 골키퍼 가상 실점의 기준으로만 쓴다."""
    f = Path(settings.BASE_DIR) / 'data' / 'k_1부 리그' / 'json_data' / '구단성적.json'
    try:
        doc = json.loads(f.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    rows = doc if isinstance(doc, list) else next((v for v in doc.values() if isinstance(v, list)), [])
    out = {}
    for r in rows:
        name = ''.join(ch for ch in str(r.get('순위', '')) if not ch.isdigit()).strip()
        try:
            games, conceded = int(r['경기']), int(r['실점'])
        except (KeyError, TypeError, ValueError):
            continue
        if games > 0:
            out[name] = conceded / games
    return out


def build():
    """선수별 가상 기록을 만든다 (DB는 읽기만 한다)."""
    from player.models import PlayerStats

    conceded = team_conceded_per_game()
    league_ga = (sum(conceded.values()) / len(conceded)) if conceded else 1.2
    players = {}
    rows = PlayerStats.objects.filter(season=2026, minutes__gt=0).select_related('player', 'player__team')
    for s in rows:
        pos = (s.player.position or '').strip().upper()
        if pos not in DISTANCE_BASE:
            continue
        rng = random.Random(f'{SEED}-{s.player_id}')
        age = player_age(s.player) or 27
        age_drop = max(0, age - 30)
        d = {
            'distance_km_90': round(_clamp(DISTANCE_BASE[pos] + rng.gauss(0, 0.45) - 0.06 * age_drop,
                                           DISTANCE_BASE[pos] - 1.6, DISTANCE_BASE[pos] + 1.6), 2),
            'sprints_90': round(max(0.0, SPRINT_BASE[pos] * (1 + rng.gauss(0, 0.15)) - 0.4 * age_drop), 1),
        }
        if pos == 'GK':
            team_ga = conceded.get(TEAM_SHORT.get(s.player.team.team_name, ''), league_ga)
            conceded_90 = _clamp(team_ga * (1 + rng.gauss(0, 0.12)), 0.5, 2.6)
            rating = s.average_rating or 6.6
            save_rate = _clamp(rng.gauss(0.69, 0.035) + (rating - 6.7) * 0.05, 0.58, 0.79)
            saves_90 = _clamp(conceded_90 * save_rate / (1 - save_rate), 1.2, 4.5)   # 리그 일반 수준 90분당 2~4개
            save_rate = saves_90 / (saves_90 + conceded_90)
            clean_rate = _clamp(math.exp(-conceded_90) * (1 + rng.gauss(0, 0.15)), 0.03, 0.6)
            games = max(1, s.games or round(s.minutes / 90))
            d.update({
                'conceded_90': round(conceded_90, 2),
                'saves_90': round(saves_90, 2),
                'save_rate': round(save_rate, 3),
                'clean_sheet_rate': round(clean_rate, 3),
                'punches_90': round(rng.uniform(0.3, 1.2), 2),
                'catches_90': round(rng.uniform(0.8, 2.6), 2),
                # 시즌 합계 (위 90분당 값 × 출전시간)
                'saves': round(saves_90 * s.minutes / 90),
                'conceded': round(conceded_90 * s.minutes / 90),
                'clean_sheets': min(games, round(clean_rate * games)),
            })
        players[str(s.player_id)] = d
    return {'virtual': True, 'note': NOTE, 'seed': SEED, 'season': 2026,
            'generated_at': datetime.now().isoformat(timespec='seconds'), 'players': players}


def save():
    data = build()
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    _cache.clear()
    return p, data


def load():
    """저장된 가상 데이터. 파일이 없으면 같은 규칙으로 바로 만든다(저장은 안 함)."""
    p = path()
    try:
        mtime = p.stat().st_mtime
    except OSError:
        mtime = None
    if _cache.get('mtime') == mtime and 'data' in _cache:
        return _cache['data']
    data = None
    if mtime is not None:
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = None
    if not data or not isinstance(data.get('players'), dict):
        data = build()
    _cache.update(mtime=mtime, data=data)
    return data


def for_player(player_id):
    return load()['players'].get(str(player_id), {})

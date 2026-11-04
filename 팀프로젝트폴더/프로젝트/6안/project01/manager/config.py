"""
점수 기준(가중치·최소 출전시간)과 BEST11 제외 선수를 DB에서 읽는 곳.
player/services.py 가 이 파일을 불러 쓴다 (patch_services 명령으로 연결).
DB에 저장된 값이 없거나 오류가 나면 services.py 의 기존 상수를 그대로 쓴다.
"""
import contextlib
import threading

_local = threading.local()

# 가중치 항목의 한글 이름 (키는 services.py 의 *_WEIGHTS 와 같아야 한다)
METRIC_LABELS = {
    'FW': {'goals': '득점 (90분당)', 'assists': '도움 (90분당)', 'shots_on_target': '유효슈팅 (90분당)',
           'shots': '슈팅 (90분당)', 'key_passes': '키패스 (90분당)', 'dribble': '드리블 성공 (90분당)'},
    'MF': {'assists': '도움 (90분당)', 'key_passes': '키패스 (90분당)', 'pass_rate': '패스 성공률',
           'goals': '득점 (90분당)', 'recoveries': '볼 획득 (90분당)', 'interceptions': '인터셉트 (90분당)',
           'dribble': '드리블 성공 (90분당)'},
    'DF': {'clearances': '클리어링 (90분당)', 'interceptions': '인터셉트 (90분당)', 'recoveries': '볼 획득 (90분당)',
           'tackle': '태클 성공 (90분당)', 'aerial_duel': '공중 경합 성공 (90분당)',
           'ground_duel': '지상 경합 성공 (90분당)', 'defensive_blocks': '차단 (90분당)', 'blocks': '블락 (90분당)'},
    'GK': {'rating': '평균평점', 'mom': 'MOM (90분당)', 'best11': 'BEST11 선정 (90분당)', 'minutes': '출전시간'},
}
POSITIONS = ('FW', 'MF', 'DF', 'GK')


def load_saved():
    """DB에 저장된 설정 (없으면 빈 dict)"""
    from .models import ScoreConfig
    obj = ScoreConfig.objects.first()
    return dict(obj.data) if obj else {}


def _data():
    ov = getattr(_local, 'override', None)
    return ov if ov is not None else load_saved()


@contextlib.contextmanager
def override(data):
    """저장하지 않고 이 안에서만 다른 설정으로 계산해 본다 (미리보기용)"""
    prev = getattr(_local, 'override', None)
    _local.override = data
    try:
        yield
    finally:
        _local.override = prev


def min_minutes(default_best11, default_formation):
    d = _data().get('min', {})
    return {'best11': int(d.get('best11', default_best11)),
            'formation': int(d.get('formation', default_formation))}


def weights_for(position, default):
    w = _data().get('weights', {}).get(position)
    if not w:
        return default
    return {k: float(w.get(k, default[k])) for k in default}


def exclusions_initialized():
    return bool(_data().get('exclusions_initialized'))


def excluded_ids(default_ids):
    d = _data()
    if 'exclusions' in d:                      # 미리보기용 임시 목록
        return list(d['exclusions'])
    if d.get('exclusions_initialized'):
        from .models import BestExclusion
        return list(BestExclusion.objects.values_list('player_id', flat=True))
    return list(default_ids)

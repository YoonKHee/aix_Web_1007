"""player/services.py 가 manager 의 설정(가중치·최소 출전시간·제외 선수)을 읽도록 연결한다.

    python manage.py patch_services           # 패치 적용
    python manage.py patch_services --check   # 바뀔 내용만 확인
    python manage.py patch_services --undo    # 백업(.bak)으로 되돌리기

원본은 player/services.py.bak 으로 먼저 저장하고, 예상한 위치가 정확히 맞을 때만 수정한다.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

MARK = '# [manager-patch]'

HELPERS = '''
{mark} 관리자 페이지(manager)에서 설정한 값을 읽는다. 오류가 나면 위의 기존 상수를 그대로 쓴다.
def get_min_minutes():
    try:
        from manager.config import min_minutes
        return min_minutes(BEST11_MIN_MINUTES, FORMATION_MIN_MINUTES)
    except Exception:
        return {{'best11': BEST11_MIN_MINUTES, 'formation': FORMATION_MIN_MINUTES}}


def get_weights(position):
    defaults = {{
        'FW': FW_WEIGHTS,
        'MF': MF_WEIGHTS,
        'DF': DF_WEIGHTS,
        'GK': GK_WEIGHTS,
    }}
    try:
        from manager.config import weights_for
        return weights_for(position, defaults[position])
    except Exception:
        return defaults[position]


def get_excluded_ids():
    try:
        from manager.config import excluded_ids
        return excluded_ids(EXCLUDED_PLAYER_IDS)
    except Exception:
        return list(EXCLUDED_PLAYER_IDS)

'''.format(mark=MARK)

ANCHOR = "GK_WEIGHTS = {\n\n    'rating': 50,\n    'mom': 15,\n    'best11': 25,\n    'minutes': 10,\n}\n"

SIMPLE = [
    ("minutes__gte=BEST11_MIN_MINUTES", "minutes__gte=get_min_minutes()['best11']", 1),
    ("minutes__gte=FORMATION_MIN_MINUTES", "minutes__gte=get_min_minutes()['formation']", 1),
    ("player_id__in=EXCLUDED_PLAYER_IDS", "player_id__in=get_excluded_ids()", 2),
    ("if row['stats'].minutes >= BEST11_MIN_MINUTES", "if row['stats'].minutes >= get_min_minutes()['best11']", 1),
]
for _p in ('FW', 'MF', 'DF', 'GK'):
    SIMPLE.append((f"get_{_p.lower()}_metrics,\n        {_p}_WEIGHTS\n    )",
                   f"get_{_p.lower()}_metrics,\n        get_weights('{_p}')\n    )", 2))


def patched_text(text):
    """text(\\n 줄바꿈) -> (새 text, 바뀐 곳 설명 목록)"""
    if MARK in text:
        raise CommandError('이미 패치되어 있습니다.')
    notes = []
    if text.count(ANCHOR) != 1:
        raise CommandError('GK_WEIGHTS 위치를 찾지 못했습니다 (services.py 가 예상과 다릅니다). 아무것도 바꾸지 않았습니다.')
    text = text.replace(ANCHOR, ANCHOR + HELPERS, 1)
    notes.append('GK_WEIGHTS 아래에 get_min_minutes / get_weights / get_excluded_ids 함수 3개 추가')
    for old, new, count in SIMPLE:
        found = text.count(old)
        if found != count:
            raise CommandError(f'예상한 위치를 찾지 못했습니다: {old!r} (예상 {count}곳, 실제 {found}곳). 아무것도 바꾸지 않았습니다.')
        text = text.replace(old, new)
        notes.append(f'{count}곳: {old.splitlines()[0]}  →  {new.splitlines()[0]}')
    return text, notes


class Command(BaseCommand):
    help = 'player/services.py 를 manager 설정과 연결합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true')
        parser.add_argument('--undo', action='store_true')

    def handle(self, *args, **opts):
        path = Path(settings.BASE_DIR) / 'player' / 'services.py'
        bak = path.with_name('services.py.bak')
        if opts['undo']:
            if not bak.exists():
                raise CommandError('services.py.bak 이 없습니다.')
            path.write_bytes(bak.read_bytes())
            self.stdout.write(self.style.SUCCESS('services.py 를 패치 전 상태로 되돌렸습니다.'))
            return
        raw = path.read_bytes()
        crlf = b'\r\n' in raw
        text = raw.decode('utf-8').replace('\r\n', '\n')
        new, notes = patched_text(text)
        for n in notes:
            self.stdout.write(' - ' + n)
        if opts['check']:
            self.stdout.write('(확인만 했습니다. 파일은 바꾸지 않았습니다.)')
            return
        bak.write_bytes(raw)
        if crlf:
            new = new.replace('\n', '\r\n')
        path.write_bytes(new.encode('utf-8'))
        self.stdout.write(self.style.SUCCESS(f'패치 완료. 원본은 {bak.name} 에 저장했습니다.'))

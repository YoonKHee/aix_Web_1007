"""SQLite 자동 백업·복원. 백업 정보는 DB가 아니라 파일(.json)에 적어서, DB를 복원해도 목록이 사라지지 않는다."""
import json
import re
import sqlite3
import time
from pathlib import Path

NAME_RE = re.compile(r'^db_\d{8}_\d{6}(_\d+)?\.sqlite3$')
KEEP = 40


def make_backup(db_path, folder, reason, batch_id=None, user=''):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S')
    path = folder / f'db_{stamp}.sqlite3'
    n = 1
    while path.exists():
        n += 1
        path = folder / f'db_{stamp}_{n}.sqlite3'
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(path))
    try:
        src.backup(dst)                      # 서버가 켜져 있어도 안전하게 복사
    finally:
        dst.close()
        src.close()
    meta = dict(reason=reason, batch=batch_id, user=user, created=time.strftime('%Y-%m-%d %H:%M:%S'),
                size=path.stat().st_size)
    path.with_suffix('.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
    _prune(folder)
    return path.name


def list_backups(folder):
    folder = Path(folder)
    if not folder.exists():
        return []
    out = []
    for p in sorted(folder.glob('db_*.sqlite3'), reverse=True):
        if not NAME_RE.match(p.name):
            continue
        meta = {}
        mp = p.with_suffix('.json')
        if mp.exists():
            try:
                meta = json.loads(mp.read_text(encoding='utf-8'))
            except ValueError:
                pass
        out.append(dict(name=p.name, size=p.stat().st_size, **{k: meta.get(k) for k in ('reason', 'batch', 'user', 'created')}))
    return out


def get_backup(folder, name):
    if not NAME_RE.match(name or ''):
        return None
    for b in list_backups(folder):
        if b['name'] == name:
            return b
    return None


def restore_backup(db_path, folder, name, user=''):
    """name 시점으로 DB 복원. 복원 직전 상태를 먼저 자동 백업한다."""
    if get_backup(folder, name) is None:
        raise ValueError('백업 파일을 찾을 수 없습니다.')
    safety = make_backup(db_path, folder, f'복원 직전 자동 백업 ({name} 으로 복원하기 전)', user=user)
    bk = sqlite3.connect(str(Path(folder) / name))
    live = sqlite3.connect(str(db_path), timeout=20)
    try:
        bk.backup(live)
    finally:
        live.close()
        bk.close()
    return safety


def _prune(folder):
    files = sorted(p for p in Path(folder).glob('db_*.sqlite3') if NAME_RE.match(p.name))
    for p in files[:-KEEP]:
        p.unlink(missing_ok=True)
        p.with_suffix('.json').unlink(missing_ok=True)

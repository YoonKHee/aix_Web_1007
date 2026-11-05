"""
파일 읽기 → 오타 수정 → 표 분류 → 값 정리 → 선수 매칭(팀+이름+나이) → 변경 전/후 비교
→ 사진 매칭 → 새 컬럼 제안 → 반영 계획(plan) 생성.

build_plan() 까지는 Django 없이 동작합니다 (테스트 가능).
DB 저장은 apply_plan() 에서만 합니다.
"""
import hashlib
import io
import json
import re
import zipfile
import datetime as dt

import pandas as pd


# =========================================================
# 1. 컬럼 이름 사전
# =========================================================

def norm(text):
    return re.sub(r'[\s_\-\(\)（）\[\]/·.]', '', str(text)).lower()


PLAYER_ALIASES = {
    'name': ['성명', '선수명', '선수', '이름', 'name', 'player', 'playername'],
    'team': ['소속클럽', '소속팀', '소속', '팀', '구단', '클럽', '팀명', 'team', 'club'],
    'number': ['등번', '등번호', '번호', '백넘버', 'number', 'no'],
    'position': ['포지션', '포자션', '포지숀', 'position', 'pos'],
    'height': ['키', '신장', 'height'],
    'weight': ['몸무게', '체중', 'weight'],
    'birth_date': ['생년월일', '생일', 'birth', 'birthdate', 'dob', 'dateofbirth'],
    'age': ['나이', '연령', 'age'],
    'season': ['년도', '연도', '시즌', 'season', 'year'],
}

STAT_ALIASES = {
    'minutes': ['출전시간', '출전시간분', 'minutes', 'min'],
    'goals': ['득점', '골', 'goals'],
    'assists': ['도움', '어시스트', 'assists'],
    'games': ['경기', '경기수', '출전경기', 'games'],
    'attack_points': ['공격포인트'],
    'pk_goals': ['pk골'],
    'mom': ['mom'],
    'average_rating': ['평균평점', '평점', 'rating'],
    'best11_count': ['best11'],
    'pk_attempts': ['pk'],
    'shots': ['슈팅'],
    'shots_on_target': ['유효슈팅'],
    'shots_blocked': ['차단된슈팅'],
    'shots_off_target': ['벗어난슈팅'],
    'shots_inside_box': ['pa내슈팅'],
    'shots_outside_box': ['pa외슈팅'],
    'offsides': ['오프사이드'],
    'free_kicks': ['프리킥'],
    'corner_kicks': ['코너킥'],
    'throw_ins': ['스로인'],
    'dribble_attempt': ['드리블시도'],
    'dribble_success': ['드리블성공'],
    'pass_attempt': ['패스시도'],
    'pass_success': ['패스성공'],
    'key_passes': ['키패스'],
    'cross_attempt': ['크로스시도'],
    'cross_success': ['크로스성공'],
    'escape_pressure': ['탈압박'],
    'ground_duel_attempt': ['경합지상시도'],
    'ground_duel_success': ['경합지상성공'],
    'aerial_duel_attempt': ['경합공중시도'],
    'aerial_duel_success': ['경합공중성공'],
    'tackle_attempt': ['태클시도'],
    'tackle_success': ['태클성공'],
    'clearances': ['클리어링'],
    'interceptions': ['인터셉트'],
    'defensive_blocks': ['차단'],
    'recoveries': ['획득'],
    'blocks': ['블락'],
    'ball_misses': ['볼미스'],
    'fouls': ['파울'],
    'fouls_won': ['피파울'],
    'yellow_cards': ['경고'],
    'red_cards': ['퇴장'],
}
for _key, _label in {
    'forward': '전방패스', 'backward': '후방패스', 'lateral': '횡패스',
    'attacking_third': '공격지역패스', 'defensive_third': '수비지역패스',
    'middle_third': '중앙지역패스', 'long': '롱패스', 'medium': '중거리패스',
    'short': '숏패스',
}.items():
    STAT_ALIASES[f'{_key}_pass_attempt'] = [_label + '시도']
    STAT_ALIASES[f'{_key}_pass_success'] = [_label + '성공']

FLOAT_FIELDS = {'average_rating'}
PLAYER_FIELDS = ['number', 'position', 'height', 'weight', 'birth_date', 'age']
STAT_FIELDS = list(STAT_ALIASES)
NOT_CUMULATIVE = {'average_rating'}      # 시즌 중 줄어들 수 있는 값

LABEL = {f: al[0] for f, al in {**PLAYER_ALIASES, **STAT_ALIASES}.items()}
LABEL.update(minutes='출전시간', pk_goals='PK골', pk_attempts='PK', best11_count='BEST11',
             shots_inside_box='PA내 슈팅', shots_outside_box='PA외 슈팅', birth_date='생년월일',
             season='시즌', team='팀', name='이름')

PLAYER_LOOKUP = {norm(a): f for f, al in PLAYER_ALIASES.items() for a in al}
STAT_LOOKUP = {norm(a): f for f, al in STAT_ALIASES.items() for a in al}
ALL_LOOKUP = {**PLAYER_LOOKUP, **{k: v for k, v in STAT_LOOKUP.items()}}
TYPO_HEADERS = {norm('포자션'): '포지션', norm('포지숀'): '포지션'}   # 사전에 넣어 둔 흔한 오타

TOTAL_WORDS = {'합계', '총계', '소계', '전체', 'total', 'sum', 'nan', 'none', ''}

POSITION_MAP = {
    'GK': 'GK', '골키퍼': 'GK', 'G': 'GK',
    'DF': 'DF', '수비수': 'DF', '수비': 'DF', 'D': 'DF',
    'MF': 'MF', '미드필더': 'MF', '미드': 'MF', 'M': 'MF',
    'FW': 'FW', '공격수': 'FW', '공격': 'FW', 'F': 'FW',
}

TEAM_SHORT = {
    '강원': '강원FC', '광주': '광주FC', '김천': '김천상무', '대전': '대전하나시티즌',
    '부천': '부천FC1995', '서울': 'FC서울', '안양': 'FC안양', '울산': '울산HD',
    '인천': '인천유나이티드', '전북': '전북현대', '제주': '제주SK FC', '포항': '포항스틸러스',
}
SHORT_OF = {v: k for k, v in TEAM_SHORT.items()}

IMAGE_EXT = {'png': '.png', 'jpg': '.jpg', 'gif': '.gif', 'webp': '.webp'}


def lev1(a, b):
    """두 문자열이 글자 하나(바꿈/빠짐/끼움)만 다른가"""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def sub1(a, b):
    """길이가 같고 글자 하나만 다른가 (오타 판정용 — 글자가 빠지거나 늘어난 건 다른 항목으로 본다)"""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


# =========================================================
# 2. 팀 이름 해석
# =========================================================

class TeamResolver:
    def __init__(self, team_names):
        self.names = list(team_names)
        self.tokens = {}
        for full in self.names:
            self.tokens[norm(full)] = full
        for short, full in TEAM_SHORT.items():
            if full in self.names:
                self.tokens[norm(short)] = full
        for short in TEAM_SHORT:
            hits = [n for n in self.names if short in n]
            if len(hits) == 1:
                self.tokens.setdefault(norm(short), hits[0])
        self.raw_tokens = sorted(set(self.names) | {s for s, f in TEAM_SHORT.items() if f in self.names},
                                 key=len, reverse=True)

    def resolve(self, text):
        """-> (정식 팀명 또는 None, 방식: exact/alias/fuzzy)"""
        key = norm(text)
        if not key:
            return None, None
        if key in self.tokens:
            return self.tokens[key], ('exact' if self.tokens[key] == str(text).strip() else 'alias')
        hits = {full for tok, full in self.tokens.items() if len(tok) >= 2 and (tok in key or key in tok)}
        if len(hits) == 1:
            return hits.pop(), 'fuzzy'
        hits = {full for tok, full in self.tokens.items() if len(tok) >= 3 and lev1(tok, key)}
        if len(hits) == 1:
            return hits.pop(), 'fuzzy'
        return None, None

    def find_in_text(self, text):
        key = norm(text)
        found = {full for tok, full in self.tokens.items() if len(tok) >= 2 and tok in key}
        return found.pop() if len(found) == 1 else None

    def strip_suffix(self, text):
        text = text.strip()
        for rt in self.raw_tokens:
            if text.endswith(rt) and len(text) > len(rt):
                return text[:-len(rt)].strip(), self.resolve(rt)[0]
        return text, None


# =========================================================
# 3. 파일 읽기 (확장자가 아니라 내용으로 판별)
# =========================================================

class ReadError(Exception):
    pass


def _decode(data):
    for enc in ('utf-8-sig', 'cp949', 'euc-kr', 'utf-16'):
        try:
            return data.decode(enc), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ReadError('글자 인코딩을 알 수 없습니다 (utf-8, cp949, utf-16 모두 실패).')


def _image_kind(head):
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if head[:3] == b'\xff\xd8\xff':
        return 'jpg'
    if head[:4] in (b'GIF8',):
        return 'gif'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'webp'
    return None


def sniff_format(filename, data):
    head = data[:16]
    low = filename.lower()
    img = _image_kind(head)
    if img:
        return 'image'
    if head[:4] == b'PK\x03\x04':
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return 'unknown'
        if '[Content_Types].xml' in names and any(n.startswith('xl/') for n in names):
            return 'xlsx'
        if any(n.startswith('word/') or n.startswith('ppt/') for n in names):
            return 'office'
        return 'zip'
    if head[:4] == b'\xd0\xcf\x11\xe0':
        return 'xls'
    if head[:5] == b'%PDF-':
        return 'pdf'
    text_head = data[:2000].lstrip(b'\xef\xbb\xbf \r\n\t')
    if low.endswith('.json') or (text_head[:1] in (b'[', b'{') and low.endswith('.txt')):
        return 'json'
    if text_head[:1] == b'<':
        return 'html'
    if low.endswith(('.csv', '.tsv', '.txt')):
        return 'csv'
    return 'unknown'


def _zip_name(info):
    name = info.filename
    if not (info.flag_bits & 0x800):
        try:
            name = name.encode('cp437').decode('cp949')   # 윈도우에서 만든 한글 파일명 복구
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
    return name


def expand_inputs(files, notes):
    """zip 묶음을 풀어서 [(경로, bytes)] 로 펼침. 엑셀(xlsx)은 풀지 않음."""
    out = []
    for fname, data in files:
        if sniff_format(fname, data) == 'zip':
            try:
                zf = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                out.append((fname, data))
                continue
            n = 0
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = _zip_name(info)
                base = name.rsplit('/', 1)[-1]
                if name.startswith('__MACOSX') or base.startswith('.') or base.lower() == 'thumbs.db':
                    continue
                out.append((f'{fname}/{name}', zf.read(info)))
                n += 1
            notes.append(f'{fname}: 압축 파일에서 {n}개 파일을 꺼냈습니다.')
        else:
            out.append((fname, data))
    return out


def _flatten_columns(cols):
    out = []
    for c in cols:
        if isinstance(c, tuple):
            parts = []
            for p in c:
                p = str(p).strip()
                if p and not p.lower().startswith('unnamed') and p not in parts:
                    parts.append(p)
            out.append(' '.join(parts))
        else:
            out.append(str(c).strip())
    return out


def _known(v):
    k = norm(v)
    if k in ALL_LOOKUP or k in TYPO_HEADERS:
        return True
    return len(k) >= 3 and any(sub1(k, a) for a in ALL_LOOKUP if len(a) >= 3)


def _find_header_row(raw):
    best, best_hits = None, 0
    for i in range(min(10, len(raw))):
        hits = sum(1 for v in raw.iloc[i].tolist() if isinstance(v, str) and _known(v))
        if hits > best_hits:
            best, best_hits = i, hits
    return best if best_hits >= 2 else None


def _from_raw(raw):
    raw = raw.dropna(how='all').dropna(how='all', axis=1).reset_index(drop=True)
    h = _find_header_row(raw)
    if h is None:
        df = raw.copy()
        df.columns = [f'열{i + 1}' for i in range(df.shape[1])]
        return df, False, 0
    df = raw.iloc[h + 1:].reset_index(drop=True)
    df.columns = [str(v).strip() for v in raw.iloc[h].tolist()]
    return df, True, h


def _rows_to_table(rows):
    width = max(len(r) for r in rows)
    return pd.DataFrame([r + [None] * (width - len(r)) for r in rows]).astype(object)


def _read_pdf(data, notes):
    try:
        import pdfplumber
    except ImportError:
        raise ReadError('PDF를 읽으려면 pdfplumber 패키지가 필요합니다. 터미널에서 pip install pdfplumber 를 실행해주세요.')
    tables = []
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as e:
        raise ReadError(f'PDF를 열 수 없습니다 (암호가 걸렸거나 손상): {e}')
    with pdf:
        total_text = 0
        for pno, page in enumerate(pdf.pages, 1):
            found = page.extract_tables()
            text = page.extract_text() or ''
            total_text += len(text.strip())
            used = False
            for tno, tb in enumerate(found, 1):
                rows = [[(c or '').replace('\n', ' ').strip() for c in r] for r in tb if r]
                if len(rows) >= 2:
                    raw = pd.DataFrame(rows).replace('', pd.NA).astype(object)
                    df, ok, _ = _from_raw(raw)
                    tables.append((f'{pno}쪽 표 {tno}', df, ok))
                    used = True
            if not used and text.strip():
                rows = [re.split(r'\s+', ln.strip()) for ln in text.splitlines() if ln.strip()]
                df, ok, _ = _from_raw(_rows_to_table(rows))
                tables.append((f'{pno}쪽 (표 선이 없어 글자 줄로 읽음)', df, ok))
        if total_text == 0:
            try:
                import pytesseract
                rows = []
                for page in pdf.pages:
                    img = page.to_image(resolution=200).original
                    txt = pytesseract.image_to_string(img, lang='kor+eng')
                    rows += [re.split(r'\s+', ln.strip()) for ln in txt.splitlines() if ln.strip()]
                if not rows:
                    raise ValueError('빈 결과')
                df, ok, _ = _from_raw(_rows_to_table(rows))
                tables.append(('스캔본(OCR)', df, ok))
                notes.append('스캔된 PDF라서 글자 인식(OCR)으로 읽었습니다. 인식 오류가 있을 수 있어 점검 결과를 꼭 확인해주세요.')
            except Exception as e:
                raise ReadError('글자가 없는 스캔 PDF입니다. 글자 인식(OCR)에는 tesseract 프로그램(한국어 언어팩)과 '
                                f'pytesseract 패키지가 필요합니다. ({type(e).__name__})')
    if not tables:
        raise ReadError('PDF에서 표나 글자를 찾지 못했습니다.')
    return tables


def read_tables(filename, data):
    """-> (표 목록 [(이름, DataFrame, 머리글 찾음)], 알림 목록)"""
    fmt = sniff_format(filename, data)
    notes, tables = [], []

    if fmt == 'office':
        raise ReadError('워드/파워포인트 파일은 읽지 못합니다. 표를 엑셀이나 PDF로 저장해서 올려주세요.')
    if fmt in ('unknown', 'image', 'zip'):
        raise ReadError('파일 형식을 알 수 없습니다 (xlsx, xls, csv, tsv, txt, json, html, pdf, 사진, zip 지원).')

    if fmt in ('xlsx', 'xls'):
        try:
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=object,
                                   engine=None if fmt == 'xlsx' else 'xlrd')
        except ImportError:
            raise ReadError('옛 .xls 형식은 xlrd 패키지가 필요합니다. 터미널에서 pip install xlrd 후 다시 올려주세요.')
        except Exception as e:
            raise ReadError(f'엑셀 파일을 열 수 없습니다: {e}')
        for sname, raw in sheets.items():
            df, ok, _ = _from_raw(raw)
            tables.append((f'시트 "{sname}"', df, ok))

    elif fmt == 'html':
        text, _ = _decode(data)
        try:
            found = pd.read_html(io.StringIO(text))
        except Exception as e:
            raise ReadError(f'HTML 표를 찾지 못했습니다: {e}')
        for i, t in enumerate(found, 1):
            t.columns = _flatten_columns(t.columns)
            if sum(1 for c in t.columns if _known(c)) >= 2:
                tables.append((f'표 {i}', t, True))
            else:
                df, ok, _ = _from_raw(t.astype(object))
                tables.append((f'표 {i}', df, ok))
        notes.append('HTML 형태의 표 파일입니다 (확장자가 xls여도 내용은 HTML일 수 있음).')

    elif fmt == 'json':
        text, _ = _decode(data)
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ReadError(f'JSON 문법 오류: {e.msg} (줄 {e.lineno}, 칸 {e.colno})')
        if isinstance(obj, dict):
            lists = {k: v for k, v in obj.items() if isinstance(v, list) and v and isinstance(v[0], dict)}
            if lists:
                for k, v in lists.items():
                    tables.append((f'항목 "{k}"', pd.DataFrame(v), True))
            elif obj and all(isinstance(v, dict) for v in obj.values()):
                tables.append(('JSON', pd.DataFrame(list(obj.values())), True))
            else:
                tables.append(('JSON', pd.DataFrame([obj]), True))
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            tables.append(('JSON', pd.DataFrame(obj), True))
        else:
            raise ReadError('JSON 안에서 "이름: 값" 형태의 목록을 찾지 못했습니다.')

    elif fmt == 'pdf':
        tables = _read_pdf(data, notes)

    else:   # csv / tsv / txt
        text, enc = _decode(data)
        sep = max([',', '\t', ';', '|'], key=lambda s: text[:3000].count(s))
        try:
            raw = pd.read_csv(io.StringIO(text), sep=sep, header=None, dtype=object,
                              engine='python', on_bad_lines='skip')
        except Exception as e:
            raise ReadError(f'CSV를 읽을 수 없습니다: {e}')
        df, ok, _ = _from_raw(raw)
        tables.append(('CSV', df, ok))
        notes.append(f'인코딩 {enc}, 구분자 {sep!r}')
    return tables, notes


# =========================================================
# 4. 값 정리 (오타 수정 포함)
# =========================================================

_TYPO = str.maketrans({'O': '0', 'o': '0', 'I': '1', 'l': '1'})


def to_number(value, as_float=False):
    """-> (숫자 또는 None, 고친 경우 '원래값 → 고친값'). 실패하면 ValueError"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None
    s = str(value).strip()
    if s.lower() in ('', 'nan', 'none', '-', '–', '<na>'):
        return None, None
    fixed = None
    if re.fullmatch(r'(?i)[0-9OoIl,.\s]*[0-9][0-9OoIl,.\s]*(cm|kg|%|분)?', s) and re.search(r'[OoIl]', s):
        unit = re.search(r'(?i)(cm|kg|%|분)$', s)
        body = s[:unit.start()] if unit else s
        s2 = body.translate(_TYPO) + (unit.group(0) if unit else '')
        fixed = f'{s} → {s2}'
        s = s2
    s = re.sub(r'(?i)(cm|kg|%|분|회|명|원|세)$', '', s.replace(',', '')).strip()
    n = float(s)
    if not as_float and n != int(n):
        fixed = f'소수 {s}을(를) 정수 {int(round(n))}(으)로 반올림 — 천 단위 점이라면 {int(round(n * 1000)) if re.fullmatch(r"\d+\.\d{3}", s) else "확인 필요"}'
    return (n if as_float else int(round(n))), fixed


def to_date(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (dt.datetime, pd.Timestamp)):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()
    if s.lower() in ('', 'nan', 'none', 'nat', '-'):
        return None
    m = re.match(r'^(\d{4})\D?(\d{1,2})\D?(\d{1,2})', s)
    if not m:
        raise ValueError(s)
    return dt.date(int(m[1]), int(m[2]), int(m[3]))


def clean_text(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    return re.sub(r'\s+', ' ', str(v)).strip()


def add_issue(issues, level, where, column, value, message, action):
    issues.append(dict(level=level, where=where, column=column, value=str(value), message=message, action=action))


# =========================================================
# 5. 표 1개 분석
# =========================================================

def map_columns(df, registered, where, issues):
    """컬럼 → (종류, 필드). 오타는 고치고, 모르는 컬럼은 원래 이름 그대로 유지"""
    reg = {norm(r): r for r in registered}
    result, used = {}, set()
    for col in df.columns:
        k = norm(col)
        orig = str(col).strip()
        kind = field = None
        if k in PLAYER_LOOKUP:
            kind, field = 'player', PLAYER_LOOKUP[k]
        elif k in STAT_LOOKUP:
            kind, field = 'stat', STAT_LOOKUP[k]
        elif len(k) >= 3:
            cands = {ALL_LOOKUP[a] for a in ALL_LOOKUP if len(a) >= 3 and sub1(k, a)}
            if len(cands) == 1:
                field = cands.pop()
                kind = 'player' if field in PLAYER_ALIASES else 'stat'
                add_issue(issues, 'fix', where, orig, orig,
                          f'컬럼 이름 "{orig}"은(는) "{LABEL[field]}"의 오타로 보입니다.',
                          f'"{LABEL[field]}"(으)로 고쳐서 처리했습니다.')
        elif len(k) == 2:
            cands = {ALL_LOOKUP[a] for a in ALL_LOOKUP if len(a) == 2 and sub1(k, a)}
            if len(cands) == 1:        # 두 글자는 한 글자만 달라도 다른 항목일 수 있어(득점/실점) 제안만 한다
                f2 = next(iter(cands))
                add_issue(issues, 'warn', where, orig, orig,
                          f'컬럼 "{orig}"은(는) "{LABEL[f2]}"의 오타일 수 있습니다. 하지만 두 글자 항목은 다른 항목(예: 득점/실점)일 수 있어 자동으로 고치지 않았습니다.',
                          f'원래 이름 "{orig}" 그대로 새 컬럼으로 두었습니다. "{LABEL[f2]}"이(가) 맞다면 파일의 컬럼 이름을 고쳐서 다시 올려주세요.')
        if kind is None:
            if k in reg:
                kind, field = 'extra', reg[k]
                if reg[k] != orig:
                    add_issue(issues, 'fix', where, orig, orig, f'컬럼 "{orig}"은(는) 이미 등록된 "{reg[k]}"과(와) 같은 항목입니다.',
                              f'"{reg[k]}"(으)로 합쳐서 처리했습니다.')
            elif k.startswith('unnamed') or re.fullmatch(r'열\d+', orig) or not k:
                kind, field = 'skip', ''
            else:
                kind, field = 'extra', orig
        elif k in TYPO_HEADERS:
            add_issue(issues, 'fix', where, orig, orig, f'컬럼 이름 "{orig}"은(는) "{TYPO_HEADERS[k]}"의 오타입니다.',
                      f'"{TYPO_HEADERS[k]}"(으)로 고쳐서 처리했습니다.')
        if kind in ('player', 'stat') and (kind, field) in used:
            kind, field = 'extra', orig          # 같은 항목이 두 번 나오면 뒤쪽은 원래 이름으로 유지
        used.add((kind, field))
        result[col] = (kind, field)
    return result


def infer_name_column(df, colmap, where, issues):
    """'성면'처럼 이름 컬럼의 머리글이 틀렸을 때, 값의 모양(한글 이름)으로 추정"""
    best, best_score = None, 0.0
    for c, (k, f) in colmap.items():
        if k != 'extra':
            continue
        vals = [clean_text(v) for v in df[c].tolist() if clean_text(v)]
        if len(vals) < 2:
            continue
        ok = [v for v in vals if re.fullmatch(r"[가-힣A-Za-z][가-힣A-Za-z0-9·\. ]{1,14}", v) and not re.fullmatch(r'(?i)(gk|df|mf|fw)', v)]
        score = len(ok) / len(vals) * (len(set(vals)) / len(vals))
        if score > 0.85 and score > best_score:
            best, best_score = c, score
    if best is not None:
        colmap[best] = ('player', 'name')
        issues[:] = [i for i in issues if not (i['where'] == where and i['column'] == str(best) and i['level'] == 'warn')]
        add_issue(issues, 'fix', where, str(best), str(best),
                  f'이름 컬럼을 찾지 못해, 값이 선수 이름처럼 보이는 "{best}" 컬럼을 이름 컬럼으로 추정했습니다.',
                  '추정한 컬럼으로 처리했습니다. 틀렸다면 컬럼 이름을 "이름"으로 고쳐 다시 올려주세요.')
    return best


def classify(colmap, has_fused_rank):
    fields = {f for kind, f in colmap.values() if kind == 'player'}
    stats = {f for kind, f in colmap.values() if kind == 'stat'}
    has_name = 'name' in fields or has_fused_rank
    info_cols = fields & {'position', 'birth_date', 'height', 'weight', 'number', 'age'}
    if has_name and stats and info_cols:
        return '선수정보+기록'
    if has_name and stats:
        return '선수 기록'
    if has_name and info_cols:
        return '선수정보'
    if not has_name and 'team' in fields and stats:
        return '구단 기록 (선수 단위가 아님)'
    return '알 수 없음'


def analyze_table(label, df, header_ok, filename, resolver, season_default, registered, issues, rep, unmatched):
    where = f'{filename} · {label}'
    if not header_ok:
        if len(df) <= 3:
            add_issue(issues, 'info', where, '', '', f'{len(df)}줄짜리 작은 표입니다 (제목·요약 조각으로 보임).',
                      '선수 표가 아니라서 무시했습니다.')
            rep['tables'].append(dict(label=label, kind='조각 표(무시)', rows=len(df), mapped=[], extra=[]))
        else:
            add_issue(issues, 'error', where, '', '', '머리글(컬럼 이름 줄)을 찾지 못했습니다. 첫 10줄 안에 이름·팀·득점 같은 항목명이 있어야 합니다.',
                      '이 표는 건너뛰었습니다.')
            rep['tables'].append(dict(label=label, kind='머리글 없음', rows=len(df), mapped=[], extra=[]))
        return []
    file_team = resolver.find_in_text(filename)
    fused = next((c for c in df.columns if norm(c) in ('순위', 'rank')), None)
    colmap = map_columns(df, registered, where, issues)
    has_name_col = any(k == 'player' and f == 'name' for k, f in colmap.values())
    use_fused = bool(fused) and not has_name_col and \
        df[fused].astype(str).str.match(r'^\d+\D').mean() > 0.8
    if use_fused:
        colmap[fused] = ('skip', '')
    elif not has_name_col:
        if infer_name_column(df, colmap, where, issues) is not None:
            has_name_col = True
    kind = classify(colmap, use_fused)
    mapped = [(c, k, f) for c, (k, f) in colmap.items() if k in ('player', 'stat')]
    extra_cols = [c for c, (k, f) in colmap.items() if k == 'extra']
    rep['tables'].append(dict(
        label=label, kind=kind, rows=len(df),
        mapped=[f'{c} → {LABEL.get(f, f)}' for c, k, f in mapped],
        extra=[colmap[c][1] for c in extra_cols]))
    if extra_cols:
        add_issue(issues, 'info', where, ', '.join(colmap[c][1] for c in extra_cols), '',
                  f'DB에 정해진 칸이 없는 컬럼 {len(extra_cols)}개를 찾았습니다 (원래 이름 그대로 유지).',
                  '아래 "새 컬럼 제안"에서 변경 전/후를 확인하고 승인하면 저장됩니다.')
    if kind in ('알 수 없음', '구단 기록 (선수 단위가 아님)'):
        add_issue(issues, 'error', where, '', '',
                  f'선수 이름 컬럼을 찾지 못했거나 종류를 알 수 없는 표입니다 (분류: {kind}). 인식한 컬럼: {[c for c, _, _ in mapped] or "없음"}',
                  '이 표는 건너뛰었습니다. 이름 컬럼이 "성명/선수명/이름" 중 하나인지 확인해주세요.')
        return []

    rows_out = []
    for idx, row in df.iterrows():
        line = idx + 2
        rec = dict(src=where, line=line, player={}, stats={}, extra={})
        raw_name, team_text = '', ''
        if use_fused:
            m = re.match(r'^(\d+)(.*)$', clean_text(row[fused]))
            body = m[2] if m else clean_text(row[fused])
            raw_name, team_hit = resolver.strip_suffix(body)
            team_text = team_hit or ''
            if m:
                rec['extra']['순위'] = int(m[1])
        for col, kind_, field in mapped:
            if kind_ == 'player' and field == 'name' and not use_fused:
                raw_name = clean_text(row[col])
            elif kind_ == 'player' and field == 'team':
                team_text = clean_text(row[col])
        name = raw_name
        if name.lower() in TOTAL_WORDS or name.endswith('합계'):
            if name.lower() not in ('', 'nan', 'none'):
                add_issue(issues, 'info', where, '', name, f'{line}행: 합계/요약 행입니다.', '선수가 아니므로 제외했습니다.')
            continue

        if team_text:
            team_full, how = resolver.resolve(team_text)
            if team_full and how == 'fuzzy':
                add_issue(issues, 'fix', where, '팀', team_text, f'팀 이름 "{team_text}"을(를) "{team_full}"(으)로 인식했습니다 (이 표 전체에 적용).',
                          '자동으로 고쳐서 처리했습니다. 틀렸다면 파일을 고쳐 다시 올려주세요.')
        else:
            team_full = file_team
        if team_full is None:
            msg = (f'"{team_text}"는 DB의 어떤 구단과도 맞지 않습니다.' if team_text
                   else '팀 컬럼도 없고 파일 이름에서도 팀을 찾지 못했습니다.')
            add_issue(issues, 'error', where, '팀', team_text or '(비어 있음)', f'{line}행 "{name}": 소속 팀을 정할 수 없습니다. {msg}',
                      f'이 행을 건너뛰었습니다. 팀 컬럼을 추가하거나 파일 이름에 팀 이름을 넣어주세요 (DB 구단: {", ".join(resolver.names)}).')
            unmatched.append(dict(kind='선수', label=name, reason=f'팀을 알 수 없음 ({where} {line}행)'))
            continue
        if re.search(r'\D\d+$', name):
            add_issue(issues, 'warn', where, '이름', name, f'{line}행: 이름 끝에 숫자가 붙어 있습니다 (동명이인 구분 표기로 보임).',
                      '이름을 바꾸지 않고 그대로 사용합니다. DB 이름과 다르면 새 선수로 인식되니 확인해주세요.')
        rec['team'], rec['name'] = team_full, name
        season = season_default

        for col, kind_, field in mapped:
            v = row[col]
            try:
                if kind_ == 'player':
                    if field in ('name', 'team'):
                        continue
                    if field == 'position':
                        p = clean_text(v)
                        if not p or p.lower() == 'nan':
                            continue
                        pos = POSITION_MAP.get(p.upper().replace(' ', '')) or POSITION_MAP.get(p.replace(' ', ''))
                        if pos is None:
                            add_issue(issues, 'error', where, str(col), p, f'{line}행 "{name}": 포지션 "{p}"을(를) 알 수 없습니다.',
                                      '포지션 값만 비우고 나머지는 반영합니다. GK/DF/MF/FW 중 하나로 고쳐주세요.')
                            continue
                        rec['player']['position'] = pos
                    elif field == 'birth_date':
                        d = to_date(v)
                        if d:
                            rec['player']['birth_date'] = d.isoformat()
                    else:
                        n, fx = to_number(v)
                        if fx:
                            add_issue(issues, 'fix', where, str(col), clean_text(v), f'{line}행 "{name}": {col} 값의 오타를 고쳤습니다 ({fx}).',
                                      '고친 값으로 처리했습니다.')
                        if n is None:
                            continue
                        if field == 'season':
                            season = n
                            continue
                        if field in ('height', 'weight') and not (30 <= n <= 230):
                            add_issue(issues, 'warn', where, str(col), clean_text(v), f'{line}행 "{name}": {col} 값 {n}이(가) 정상 범위(30~230)를 벗어났습니다.',
                                      '그대로 저장합니다. 확인해주세요.')
                        if field == 'age' and not (14 <= n <= 60):
                            add_issue(issues, 'warn', where, str(col), clean_text(v), f'{line}행 "{name}": 나이 {n}이(가) 정상 범위(14~60)를 벗어났습니다.',
                                      '그대로 저장합니다. 확인해주세요.')
                        rec['player'][field] = n
                else:
                    n, fx = to_number(v, as_float=field in FLOAT_FIELDS)
                    if fx:
                        add_issue(issues, 'warn' if fx.startswith('소수') else 'fix', where, str(col), clean_text(v),
                                  f'{line}행 "{name}": {col} 값을 자동으로 바꿨습니다 ({fx}).',
                                  '바꾼 값으로 처리했습니다. 맞는지 확인해주세요.')
                    if n is None:
                        continue
                    if n < 0:
                        add_issue(issues, 'warn', where, str(col), clean_text(v), f'{line}행 "{name}": {col} 값이 음수({n})입니다.',
                                  '그대로 저장합니다. 확인해주세요.')
                    rec['stats'][field] = n
            except ValueError:
                what = '날짜' if field == 'birth_date' else '숫자'
                add_issue(issues, 'error', where, str(col), clean_text(v),
                          f'{line}행 "{name}": {col} 값 "{clean_text(v)}"을(를) {what}로 바꿀 수 없습니다.',
                          '이 칸만 비우고 나머지는 반영합니다.')
        for c in extra_cols:
            f = colmap[c][1]
            try:
                n, _ = to_number(row[c], as_float=True)
                val = (int(n) if n == int(n) else n) if n is not None else (clean_text(row[c]) or None)
            except ValueError:
                val = clean_text(row[c]) or None
            if val is not None:
                rec['extra'][f] = val
        rec['season'] = season
        rows_out.append(rec)
    return rows_out


# =========================================================
# 6. 선수 매칭 (팀 + 이름 + 나이/생년월일)
# =========================================================

def age_consistent(ex, birth, age, season):
    """DB 선수와 파일 값이 같은 사람인가? True / False / None(판단 근거 없음)"""
    if birth and ex.get('birth_date'):
        return birth == ex['birth_date']
    ex_birth = ex.get('birth_date')
    if age is not None and ex_birth:
        return abs(age - (season - int(ex_birth[:4]))) <= 1
    if birth and ex.get('age'):
        return abs((season - int(birth[:4])) - ex['age']) <= 1
    if age is not None and ex.get('age'):
        return abs(age - ex['age']) <= 1
    return None


def diff_changes(cur, new_player, cur_stats, new_stats, season):
    out = []
    for f in PLAYER_FIELDS:
        if f not in new_player:
            continue
        old = cur.get(f)
        if old in (None, '', 0):
            out.append(dict(section='선수정보', field=LABEL.get(f, f), old=None, new=new_player[f], flag=''))
        elif old != new_player[f]:
            out.append(dict(section='선수정보', field=LABEL.get(f, f), old=old, new=new_player[f], flag=''))
    for f, v in new_stats.items():
        old = (cur_stats or {}).get(f)
        if old is None:
            out.append(dict(section=f'{season} 기록', field=LABEL.get(f, f), old=None, new=v, flag=''))
        elif old != v:
            flag = '감소' if (f not in NOT_CUMULATIVE and v < old) else ''
            out.append(dict(section=f'{season} 기록', field=LABEL.get(f, f), old=old, new=v, flag=flag))
    return out


# =========================================================
# 7. 사진 매칭
# =========================================================

def parse_photo_name(path, resolver, name_index):
    parts = [p for p in re.split(r'[\\/]', path) if p]
    stem = parts[-1].rsplit('.', 1)[0]
    team = None
    for part in reversed(parts[:-1]):
        team = resolver.find_in_text(part)
        if team:
            break
    if team is None:
        team = resolver.find_in_text(stem)
    raw = stem
    for tok in resolver.raw_tokens:
        raw = raw.replace(tok, ' ')
    age_hint = None
    m = re.search(r'((?:19|20)\d{2})', raw)
    if m:
        age_hint = ('year', int(m[1]))
        raw = raw.replace(m[1], ' ')
    m = re.search(r'(\d{1,2})\s*세', raw)
    if m:
        age_hint = ('age', int(m[1]))
        raw = raw.replace(m[0], ' ')
    pieces = [x for x in re.split(r'[\s_\-\(\)\[\]]+', raw) if x]
    tries = [' '.join(pieces), ''.join(pieces)] + pieces
    for t in tries:
        if t in name_index:
            return team, t, age_hint
    return team, (' '.join(pieces) or stem), age_hint


def match_photos(photo_files, resolver, people, season, issues, unmatched):
    """people: [{'team','name','birth_date','age','id','has_photo'}] (기존 + 이번에 새로 등록될 선수)"""
    name_index = {}
    for p in people:
        name_index.setdefault(p['name'], []).append(p)
    out, blobs, by_sha = [], {}, {}
    for path, data in photo_files:
        kind = _image_kind(data[:16])
        try:
            from PIL import Image
            Image.open(io.BytesIO(data)).verify()
        except ImportError:
            pass
        except Exception:
            add_issue(issues, 'error', path, '', '', '사진 파일이 손상되었거나 열 수 없습니다.', '건너뛰었습니다.')
            unmatched.append(dict(kind='사진', label=path, reason='손상된 이미지'))
            continue
        team, name, hint = parse_photo_name(path, resolver, name_index)
        cands = list(name_index.get(name, []))
        note = ''
        if team:
            in_team = [c for c in cands if c['team'] == team]
            if in_team:
                cands = in_team
            elif cands:
                note = f'"{team}"에는 없고 다른 팀({", ".join(sorted({c["team"] for c in cands}))})에 같은 이름이 있습니다.'
                cands = []
        if hint and len(cands) > 1:
            f = []
            for c in cands:
                if hint[0] == 'year' and c.get('birth_date') and int(c['birth_date'][:4]) == hint[1]:
                    f.append(c)
                elif hint[0] == 'age' and age_consistent(c, None, hint[1], season):
                    f.append(c)
            cands = f or cands
        sha = hashlib.sha1(data).hexdigest()[:16]
        ent = dict(file=path, team=team or '', name=name, sha=sha, ext=IMAGE_EXT.get(kind, '.png'),
                   key=sha, player_id=None, player_team='', status='', note=note, candidates=[])
        if len(cands) == 1:
            c = cands[0]
            ent.update(status='matched', player_id=c.get('id'), player_team=c['team'], name=c['name'])
            if c.get('has_photo'):
                ent['note'] = '기존 사진을 교체합니다.'
        elif len(cands) > 1:
            ent.update(status='ambiguous',
                       candidates=[f'{c["team"]} {c["name"]} ({c.get("birth_date") or "생년월일 없음"})' for c in cands],
                       note='같은 이름이 여러 명이라 사진 이름이나 폴더에 팀·출생연도가 필요합니다.')
            unmatched.append(dict(kind='사진', label=path, reason='동명이인 후보 ' + ', '.join(ent['candidates'])))
            add_issue(issues, 'error', path, '', name, f'사진 "{path}": 같은 이름의 선수가 {len(cands)}명입니다 ({", ".join(ent["candidates"])}).',
                      '연결하지 않았습니다. 폴더를 팀 이름으로 나누거나 파일 이름에 출생연도를 넣어주세요 (예: 강원/김정훈_2004.png).')
        else:
            ent.update(status='unmatched', note=note or 'DB에서 이 이름의 선수를 찾지 못했습니다.')
            unmatched.append(dict(kind='사진', label=path, reason=ent['note']))
            add_issue(issues, 'error', path, '', name, f'사진 "{path}": 일치하는 선수를 찾지 못했습니다. {ent["note"]}',
                      '연결하지 않았습니다. 파일 이름을 "선수이름.png"로, 폴더를 팀 이름으로 맞춰주세요.')
        out.append(ent)
        blobs[ent['key']] = data
        if ent['status'] == 'matched':
            by_sha.setdefault(sha, []).append(ent)
    for sha, ents in by_sha.items():          # 같은 사진이 여러 선수에게 → 기본 이미지일 가능성
        targets = {(e['player_team'], e['name']) for e in ents}
        if len(targets) > 1:
            for e in ents:
                e['status'] = 'duplicate'
                e['note'] = f'같은 사진이 {len(targets)}명에게 쓰였습니다 (기본 이미지일 가능성).'
                unmatched.append(dict(kind='사진', label=e['file'], reason='같은 사진이 여러 선수에게 쓰임'))
            add_issue(issues, 'warn', ', '.join(e['file'] for e in ents[:3]), '', sha,
                      f'똑같은 사진 파일이 {len(targets)}명에게 연결되려 합니다: {", ".join(f"{t} {n}" for t, n in sorted(targets))}.',
                      '기본 이미지로 보고 연결하지 않았습니다.')
    return out, blobs


# =========================================================
# 8. 새 컬럼 제안 (변경 전/후 + 데이터 점검)
# =========================================================

def propose_columns(players, registered):
    reg = {norm(r) for r in registered}
    cols = {}
    for p in players:
        for season, vals in p['extra'].items():
            for name, v in vals.items():
                if name == '순위':
                    continue
                cols.setdefault(name, []).append((p['team'], p['name'], v))
    total = len(players)
    out = []
    for name, items in cols.items():
        if norm(name) in reg:
            continue
        values = [v for _, _, v in items]
        nums = [v for v in values if isinstance(v, (int, float))]
        texts = [v for v in values if isinstance(v, str)]
        kind = 'text' if texts and len(texts) >= len(nums) else ('float' if any(isinstance(v, float) for v in nums) else 'int')
        problems = []
        if texts and nums:
            problems.append(f'숫자 {len(nums)}개와 글자 {len(texts)}개가 섞여 있습니다 (예: {texts[0]!r}).')
        lo = hi = None
        if nums:
            lo, hi = min(nums), max(nums)
            if lo < 0:
                problems.append(f'음수 값이 있습니다 (최소 {lo}).')
            if name.strip().endswith('%') and hi > 100:
                problems.append(f'비율(%) 컬럼인데 100을 넘는 값이 있습니다 (최대 {hi}). 원본 계산 오류일 수 있습니다.')
            if len(set(nums)) == 1 and len(nums) > 5:
                problems.append(f'모든 값이 {nums[0]}로 같습니다.')
        if len(items) < total * 0.5:
            problems.append(f'전체 {total}명 중 {len(items)}명만 값이 있습니다.')
        out.append(dict(name=name, kind=kind, filled=len(items), total=total, min=lo, max=hi,
                        sample=[f'{t} {n}: {v}' for t, n, v in items[:3]], problems=problems))
    return out


# =========================================================
# 9. 전체 계획 만들기
# =========================================================

def build_plan(files, team_names, existing_players, default_season=2026, registered_columns=()):
    """
    files            : [(파일이름, bytes)]
    existing_players : [{'id','team','name','birth_date','age','has_photo','cur':{...},'stats':{'2026':{...}}}]
    registered_columns : 이미 승인된 추가 컬럼 이름들
    반환: (plan, blobs)   blobs = {사진 key: bytes}  (plan 은 JSON 으로 저장 가능)
    """
    resolver = TeamResolver(team_names)
    issues, report, unmatched, notes = [], [], [], []
    inputs = expand_inputs(files, notes)
    all_rows, photo_files = [], []

    for fname, data in inputs:
        if sniff_format(fname, data) == 'image':
            photo_files.append((fname, data))
            continue
        rep = dict(file=fname, tables=[], notes=[])
        try:
            tables, fnotes = read_tables(fname, data)
        except ReadError as e:
            add_issue(issues, 'error', fname, '', '', str(e), '이 파일은 반영하지 않았습니다.')
            rep['notes'] = [str(e)]
            report.append(rep)
            continue
        rep['notes'] = fnotes
        for label, df, ok in tables:
            all_rows += analyze_table(label, df, ok, fname, resolver, default_season,
                                      registered_columns, issues, rep, unmatched)
        report.append(rep)
    if notes:
        report.insert(0, dict(file='(압축 파일)', tables=[], notes=notes))

    merged = {}
    for r in all_rows:
        key = (r['team'], r['name'])
        m = merged.setdefault(key, dict(team=r['team'], name=r['name'], player={}, seasons={}, extra={}, sources=[]))
        for k, v in r['player'].items():
            if k in m['player'] and m['player'][k] != v:
                add_issue(issues, 'warn', r['src'], LABEL.get(k, k), v,
                          f'{r["line"]}행 "{r["name"]}": 같은 선수의 {LABEL.get(k, k)} 값이 파일마다 다릅니다 ({m["player"][k]} ↔ {v}).',
                          f'나중에 읽은 값 {v}을(를) 사용합니다.')
            m['player'][k] = v
        s = m['seasons'].setdefault(r['season'], {})
        for k, v in r['stats'].items():
            if k in s and s[k] != v:
                add_issue(issues, 'warn', r['src'], LABEL.get(k, k), v,
                          f'{r["line"]}행 "{r["name"]}": {r["season"]}시즌 {LABEL.get(k, k)} 값이 파일마다 다릅니다 ({s[k]} ↔ {v}).',
                          f'나중에 읽은 값 {v}을(를) 사용합니다.')
            s[k] = v
        if r['extra']:
            m['extra'].setdefault(str(r['season']), {}).update(r['extra'])
        m['sources'].append(f'{r["src"]} {r["line"]}행')

    by_key, by_name = {}, {}
    for p in existing_players:
        by_key.setdefault((p['team'], p['name']), []).append(p)
        by_name.setdefault(p['name'], []).append(p)

    plan_players = []
    counts = dict(update=0, create=0, skipped=0, transfer=0, unchanged=0)
    for key, m in merged.items():
        birth, age = m['player'].get('birth_date'), m['player'].get('age')
        season0 = next(iter(m['seasons']), default_season)
        src = ', '.join(m['sources'][:2])
        action, pid, note, ex = None, None, '', None
        hit = by_key.get(key)
        if hit:
            ok = [h for h in hit if age_consistent(h, birth, age, season0) is not False]
            if not ok:
                h = hit[0]
                add_issue(issues, 'error', src, '생년월일/나이', birth or age,
                          f'"{m["team"]} {m["name"]}": 이름·팀은 DB와 같지만 생년월일/나이가 맞지 않습니다 '
                          f'(파일 {birth or str(age) + "세"} / DB {h.get("birth_date") or str(h.get("age")) + "세"}). 동명이인일 수 있습니다.',
                          '안전을 위해 이 선수는 반영하지 않았습니다. 같은 사람이면 DB 값을 고치고, 다른 사람이면 이름을 구분해 다시 올려주세요.')
                unmatched.append(dict(kind='선수', label=f'{m["team"]} {m["name"]}', reason='이름·팀은 같지만 나이/생년월일이 다름'))
                counts['skipped'] += 1
                continue
            ex = ok[0]
            action, pid = 'update', ex['id']
        else:
            cand = [p for p in by_name.get(m['name'], []) if p['team'] != m['team']]
            strong = [p for p in cand if birth and p.get('birth_date') == birth]
            weak = [p for p in cand if not strong and age_consistent(p, birth, age, season0) is True]
            if strong or len(weak) == 1:
                p = (strong or weak)[0]
                ex = p
                action, pid = 'transfer', p['id']
                basis = '생년월일이 같은' if strong else '나이가 비슷한'
                note = f'DB에는 "{p["team"]}" 소속'
                add_issue(issues, 'warn', src, '팀', m['team'],
                          f'"{m["name"]}": {basis} 선수가 DB의 "{p["team"]}"에 있습니다. 이적으로 보입니다.',
                          '"이적 반영"을 체크해야 팀이 바뀝니다. 체크하지 않으면 이 선수는 건너뜁니다.')
                counts['transfer'] += 1
            else:
                if cand:
                    add_issue(issues, 'info', src, '이름', m['name'],
                              f'"{m["team"]} {m["name"]}": 같은 이름의 선수가 다른 팀({", ".join(sorted({c["team"] for c in cand}))})에 있지만 같은 사람이라는 근거(생년월일/나이)가 없습니다.',
                              '다른 사람(동명이인)으로 보고 새 선수로 등록합니다.')
                if not m['player'].get('position'):
                    add_issue(issues, 'error', src, '포지션', '',
                              f'"{m["team"]} {m["name"]}": DB에 없는 새 선수인데 포지션 정보가 없어 등록할 수 없습니다.'
                              + (' 기록 파일만 올린 것 같습니다.' if not m['player'] else ''),
                              '건너뛰었습니다. 포지션이 있는 선수정보 파일을 함께 올리면 등록됩니다.')
                    unmatched.append(dict(kind='선수', label=f'{m["team"]} {m["name"]}', reason='DB에 없는 새 선수인데 포지션 정보가 없음'))
                    counts['skipped'] += 1
                    continue
                action = 'create'
        if action != 'transfer':
            counts[action] += 1

        changes, decreased = [], []
        if action == 'create':
            for f, v in m['player'].items():
                changes.append(dict(section='선수정보', field=LABEL.get(f, f), old=None, new=v, flag=''))
            for s, vals in m['seasons'].items():
                for f, v in vals.items():
                    changes.append(dict(section=f'{s} 기록', field=LABEL.get(f, f), old=None, new=v, flag=''))
        else:
            first = True
            for s, vals in m['seasons'].items():
                cs = (ex.get('stats') or {}).get(str(s)) or {}
                changes += diff_changes(ex.get('cur') or {}, m['player'] if first else {}, cs, vals, s)
                first = False
            if not m['seasons']:
                changes += diff_changes(ex.get('cur') or {}, m['player'], {}, {}, season0)
            decreased = [c for c in changes if c['flag'] == '감소']
        if decreased:
            add_issue(issues, 'warn', src, '누적 기록', m['name'],
                      f'"{m["team"]} {m["name"]}": 기존보다 줄어든 누적 기록이 있습니다 — ' +
                      ', '.join(f'{c["field"]} {c["old"]}→{c["new"]}' for c in decreased[:6]),
                      '그대로 반영합니다. 어느 쪽이 최신 파일인지 확인해주세요.')
        if action == 'update' and not changes and not m['extra']:
            counts['unchanged'] += 1
        plan_players.append(dict(
            action=action, id=pid, team=m['team'], name=m['name'], note=note,
            player=m['player'], seasons={str(k): v for k, v in m['seasons'].items()},
            extra=m['extra'], changes=changes, anomaly=bool(decreased), sources=m['sources'][:3]))

    people = [dict(p) for p in existing_players] + \
             [dict(team=p['team'], name=p['name'], birth_date=p['player'].get('birth_date'),
                   age=p['player'].get('age'), id=None, has_photo=False)
              for p in plan_players if p['action'] == 'create']
    photos, blobs = match_photos(photo_files, resolver, people, default_season, issues, unmatched)
    proposals = propose_columns(plan_players, registered_columns)

    uniq = {}
    for i in issues:                     # 똑같은 안내는 한 번만 보여주고 횟수를 적는다
        k = (i['level'], i['where'], i['column'], i['value'], i['message'], i['action'])
        if k in uniq:
            uniq[k]['count'] += 1
        else:
            uniq[k] = dict(i, count=1)
    issues = list(uniq.values())
    order = {'error': 0, 'warn': 1, 'fix': 2, 'info': 3}
    issues.sort(key=lambda i: order[i['level']])
    plan = dict(
        files=report, issues=issues, players=plan_players, photos=photos, unmatched=unmatched,
        proposals=proposals, registered=list(registered_columns),
        summary=dict(counts, rows=len(all_rows), players=len(plan_players),
                     photos=len(photos), photos_ok=sum(1 for p in photos if p['status'] == 'matched'),
                     errors=sum(1 for i in issues if i['level'] == 'error'),
                     warns=sum(1 for i in issues if i['level'] == 'warn'),
                     fixes=sum(1 for i in issues if i['level'] == 'fix'),
                     infos=sum(1 for i in issues if i['level'] == 'info'),
                     unmatched=len(unmatched), anomalies=sum(1 for p in plan_players if p['anomaly'])))
    return plan, blobs


# =========================================================
# 10. DB 저장 (Django 필요)
# =========================================================

def apply_plan(plan, allow_transfer=False, approved_columns=(), registered_columns=(), read_blob=None):
    from django.core.files.base import ContentFile
    from django.db import transaction
    from team.models import Team
    from player.models import Player, PlayerStats
    from .models import ExtraStat

    allowed = {norm(c) for c in list(approved_columns) + list(registered_columns)}
    teams = {t.team_name: t for t in Team.objects.all()}
    res = dict(created=0, updated=0, transferred=0, skipped_transfer=0, stats_rows=0, extra_rows=0,
               photos_linked=0, photos_skipped=0)
    with transaction.atomic():
        done = {}
        for p in plan['players']:
            team = teams.get(p['team'])
            if team is None:
                continue
            fields = dict(p['player'])
            if 'birth_date' in fields:
                fields['birth_date'] = dt.date.fromisoformat(fields['birth_date'])
            if p['action'] == 'create':
                player = Player.objects.create(team=team, name=p['name'], **fields)
                res['created'] += 1
            elif p['action'] == 'transfer':
                if not allow_transfer:
                    res['skipped_transfer'] += 1
                    continue
                player = Player.objects.get(id=p['id'])
                player.team = team
                for k, v in fields.items():
                    setattr(player, k, v)
                player.save()
                res['transferred'] += 1
            else:
                player = Player.objects.get(id=p['id'])
                for k, v in fields.items():
                    setattr(player, k, v)
                player.save()
                res['updated'] += 1
            done[(p['team'], p['name'])] = player
            for season, values in p['seasons'].items():
                if not values:
                    continue
                stats, _ = PlayerStats.objects.get_or_create(player=player, season=int(season))
                for k, v in values.items():
                    setattr(stats, k, v)
                stats.save()
                res['stats_rows'] += 1
            for season, values in p['extra'].items():
                keep = {k: v for k, v in values.items() if norm(k) in allowed or k == '순위'}
                if not keep:
                    continue
                obj, _ = ExtraStat.objects.get_or_create(player=player, season=int(season))
                obj.data = {**obj.data, **keep}
                obj.save()
                res['extra_rows'] += 1

        for ph in plan.get('photos', []):
            if ph['status'] != 'matched' or read_blob is None:
                res['photos_skipped'] += 1
                continue
            player = done.get((ph['player_team'], ph['name']))
            if player is None and ph.get('player_id'):
                player = Player.objects.filter(id=ph['player_id']).first()
            if player is None:
                player = Player.objects.filter(team__team_name=ph['player_team'], name=ph['name']).first()
            blob = read_blob(ph['key'])
            if player is None or blob is None:
                res['photos_skipped'] += 1
                continue
            folder = SHORT_OF.get(ph['player_team'], ph['player_team'])
            player.photo.save(f'{folder}/{ph["name"]}{ph["ext"]}', ContentFile(blob), save=True)
            res['photos_linked'] += 1
    return res

"""금칙어 검사.
- 공백·특수문자·대소문자를 무시하고 비교합니다 ("씨 발", "씨.발" 도 걸림).
- 같은 글자를 반복해서 늘린 것도 하나로 합쳐 비교합니다.
- 오탐(예: '시발점')은 ALLOWED 로 빼고, 관리자 화면에서 금칙어/허용어를 더 추가할 수 있습니다.
- 축구 응원글에 흔한 '미친 활약' 같은 표현은 막지 않도록 '사람을 향한' 욕설·비하 표현 위주로 넣었습니다.
"""
import re
import unicodedata

DEFAULT_BANNED = [
    # 욕설
    '시발', '씨발', '씨팔', '시팔', '씨바', '쉬발', '병신', '븅신', '지랄', '좆', '조까', '존나', '개새끼', '개새', '개소리',
    '미친놈', '미친년', '미친새끼', '또라이', '염병', '엠창', '엿먹', '닥쳐', '꺼져', '아가리', '쌍놈', '쌍년', '씹새', '씹년', '씹놈',
    'ㅅㅂ', 'ㅆㅂ', 'ㅂㅅ', 'ㅈㄹ', 'ㅄ', '10새', '시부럴',
    # 죽음·폭력 위협
    '뒤져', '뒈져', '디져', '죽어버려', '죽여버', '죽여라',
    # 패드립
    '느금', '니애미', '니미', '애미뒤', '애비뒤',
    # 혐오·비하
    '한남충', '김치녀', '맘충', '틀딱', '급식충', '찐따', '장애인새끼', '창녀', '걸레년', '호로', '짱깨', '쪽발이', '쪽바리', '똥남아',
    # 영어
    'fuck', 'shit', 'bitch', 'asshole', 'bastard', 'cunt', 'motherfucker',
]

# 금칙어가 들어 있지만 정상적인 낱말 (검사에서 제외)
DEFAULT_ALLOWED = ['시발점', '시발역', '시발택시', '시발지', '시발자', '시발선', '시발석', '개소리쳤', '니미나']


def normalize(text):
    # 전각 문자 등은 풀어주되, 자음(ㅅㅂ)은 NFKC 가 다른 글자로 바꾸므로 그대로 둔다
    t = ''.join(c if 'ㄱ' <= c <= 'ㅣ' else unicodedata.normalize('NFKC', c) for c in (text or '')).lower()
    t = re.sub(r'[^0-9a-z가-힣ㄱ-ㅎㅏ-ㅣ]', '', t)       # 공백·특수문자 제거
    t = re.sub(r'(.)\1+', r'\1', t)                      # 같은 글자 반복 → 1개
    return t


class Matcher:
    def __init__(self, extra_banned=(), extra_allowed=()):
        self.banned = {}
        for w in list(DEFAULT_BANNED) + list(extra_banned):
            n = normalize(w)
            if n:
                self.banned.setdefault(n, w)
        self.allowed = sorted({normalize(w) for w in list(DEFAULT_ALLOWED) + list(extra_allowed) if normalize(w)},
                              key=len, reverse=True)

    def find(self, text):
        """걸린 금칙어를 돌려줌 (없으면 None)"""
        t = normalize(text)
        for a in self.allowed:
            t = t.replace(a, ' ')
        for n, original in self.banned.items():
            if n in t:
                return original
        return None


def get_matcher():
    from .models import BannedWord
    rows = list(BannedWord.objects.values_list('word', 'allow'))
    return Matcher([w for w, a in rows if not a], [w for w, a in rows if a])


def scan_all():
    """이미 올라온 글·댓글을 모두 검사해서 위반이면 숨김 처리. (글 수, 댓글 수) 반환"""
    from .models import Comment, Post
    m = get_matcher()
    n_post = n_comment = 0
    for p in Post.objects.filter(status=Post.OK):
        w = m.find(p.title) or m.find(p.content)
        if w:
            p.soft_delete(f'금칙어 포함: {w}')
            n_post += 1
    for c in Comment.objects.filter(status=Comment.OK):
        w = m.find(c.content)
        if w:
            c.soft_delete(f'금칙어 포함: {w}')
            n_comment += 1
    return n_post, n_comment

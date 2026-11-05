"""
플레이 스타일 목록과 스타일끼리의 궁합표 (chemistry.py 가 사용)

- 스타일은 선수의 '기록'에서 나온 성향이다. 실제 선수의 성격이나 능력에 대한 평가가 아니다.
- 부상 이력은 데이터에 없어서 '유리몸' 같은 스타일은 만들지 않았다.
- 한 스타일 = 같은 포지션 선수들 사이에서 high 지표의 평균 백분위가 STYLE_PCT 이상이고,
  low 지표의 평균 백분위가 LOW_GATE 이하일 때 부여한다. (low 가 없으면 high 만 본다)
- 숫자(궁합 점수)는 쌍 케미 점수(0~100)에 더하거나 빼는 값이다.
"""

STYLES_ENABLED = False   # 스타일 기능 사용 여부. 지금은 끔 (선수에게 스타일이 붙지 않고 궁합 가감도 없다)
STYLE_PCT = 75        # 이 이상이면 스타일 보유
LOW_GATE = 50         # low 지표는 이 이하여야 함
MAX_STYLES = 2        # 선수 한 명이 가질 수 있는 스타일 수
STYLE_ADJ_CAP = 15    # 한 쌍에서 스타일 궁합이 더하거나 뺄 수 있는 최대 점수

# pct: 이 스타일만의 기준(없으면 STYLE_PCT). 한 지표만 보는 스타일은 해당 인원이 25%나 되지 않도록 더 높게 둔다.
# code: 코드, label: 화면에 보일 이름, positions: 대상 포지션,
# high/low: raw_metrics 의 지표 이름, pros/cons: 장점/단점 문구
STYLES = {
    # ---------------- FW ----------------
    'selfish_shooter': dict(
        label='이기적인 슈터', positions=('FW',),
        high=['shots', 'shots_on_target'], low=['key_passes', 'assists'],
        pros='슈팅 기회를 스스로 만들어 마무리한다', cons='동료를 살리는 패스가 적다'),
    'link_forward': dict(
        label='연계형 공격수', positions=('FW',),
        high=['key_passes', 'assists'], low=['shots'],
        pros='동료에게 기회를 만들어 준다', cons='직접 마무리하는 횟수가 적다'),
    'finisher': dict(
        pct=80,
        label='마무리 전문가', positions=('FW',),
        high=['goals', 'shot_accuracy', 'goal_conversion'], low=[],
        pros='적은 기회로도 골을 만든다', cons='기회가 오지 않으면 존재감이 줄어든다'),
    'dribbler': dict(
        label='개인기 선호', positions=('FW', 'MF'),
        high=['dribble_attempt', 'dribble'], low=['pass_rate'],
        pros='혼자 수비를 뚫는다', cons='패스 연결이 적고 공을 잃기 쉽다'),
    # ---------------- MF ----------------
    'pass_master': dict(
        label='패스 마스터', positions=('MF',),
        high=['pass_rate', 'pass_volume', 'key_passes'], low=[],
        pros='경기 흐름을 조율하고 기회를 공급한다', cons='직접 득점은 적은 편이다'),
    'destroyer': dict(
        label='볼 회수형', positions=('MF',),
        high=['recoveries', 'interceptions', 'tackle'], low=['key_passes'],
        pros='공을 빼앗아 수비를 안정시킨다', cons='공격 전개 기여가 적다'),
    # ---------------- DF ----------------
    'iron_wall': dict(
        label='철벽 수비', positions=('DF',),
        high=['tackle', 'interceptions', 'clearances', 'blocks', 'recoveries'], low=[],
        pros='상대 공격을 막아내는 능력이 뛰어나다', cons='공격 가담이 적을 수 있다'),
    'aerial_boss': dict(
        pct=88,
        label='공중 지배자', positions=('DF',),
        high=['aerial_duel', 'clearances'], low=[],
        pros='공중볼 경합에서 강하다', cons='지상 플레이가 상대적으로 약할 수 있다'),
    'ball_playing': dict(
        pct=88,
        label='빌드업 수비수', positions=('DF',),
        high=['pass_rate', 'pass_volume'], low=[],
        pros='뒤에서부터 공격을 시작한다', cons='수비 지표가 상대적으로 낮을 수 있다'),
    'overlapper': dict(
        pct=88,
        label='오버래핑형', positions=('DF',),
        high=['cross', 'dribble'], low=[],
        pros='측면에서 공격에 가담한다', cons='수비 뒤 공간을 비울 수 있다'),
    # ---------------- GK ----------------
    'reliable_gk': dict(
        pct=88,
        label='믿음직한 수문장', positions=('GK',),
        high=['rating', 'best11_rate', 'mom_rate'], low=[],
        pros='평점과 수상 기록이 안정적이다', cons='기록 외의 세부 능력은 데이터로 알 수 없다'),
    # ---------------- 공통 ----------------
    'card_collector': dict(
        pct=92,
        label='카드 수집가', positions=('FW', 'MF', 'DF', 'GK'),
        high=['card_rate'], low=[],
        pros='적극적으로 몸싸움에 임한다', cons='경고와 퇴장 위험이 높다'),
}

# 스타일 쌍 궁합 (+: 잘 맞음, -: 충돌). 순서 상관없음.
# (스타일1, 스타일2): (점수, 이유)
_COMPAT = [
    ('pass_master', 'selfish_shooter', 12, '패스 마스터가 슈터에게 기회를 공급'),
    ('pass_master', 'finisher', 10, '패스 마스터가 마무리 전문가에게 기회를 공급'),
    ('pass_master', 'link_forward', 3, '패스 연결이 풍부해짐'),
    ('pass_master', 'dribbler', 6, '돌파와 패스가 번갈아 가능'),
    ('link_forward', 'selfish_shooter', 10, '연계형이 슈터를 살려 줌'),
    ('link_forward', 'finisher', 8, '연계형이 마무리 전문가를 살려 줌'),
    ('selfish_shooter', 'selfish_shooter', -12, '슈팅 기회를 서로 다툼'),
    ('dribbler', 'dribbler', -10, '개인기끼리라 연계가 부족'),
    ('iron_wall', 'ball_playing', 10, '수비 안정과 빌드업의 역할 분담'),
    ('iron_wall', 'pass_master', 8, '수비 안정 위에서 패스 전개'),
    ('ball_playing', 'destroyer', 8, '볼 회수 후 빌드업으로 이어짐'),
    ('ball_playing', 'reliable_gk', 8, '뒤에서의 빌드업이 안정적'),
    ('iron_wall', 'destroyer', -4, '수비형이 겹쳐 공격 전환이 느려짐'),
    ('aerial_boss', 'iron_wall', 6, '공중과 지상 수비를 나눠 맡음'),
    ('overlapper', 'dribbler', -4, '측면 공간이 겹침'),
    ('card_collector', 'card_collector', -12, '퇴장 위험이 겹침'),
]

COMPAT = {}
for _a, _b, _pts, _why in _COMPAT:
    COMPAT[frozenset((_a, _b))] = (_pts, _why)

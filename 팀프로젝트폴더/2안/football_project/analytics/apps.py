from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    name = 'analytics'

def get_slot_candidates(scored_df, formation):
# """
# 선택된 포메이션의 각 세부 슬롯별로 상위 3명의 후보(Top 3)를 추출합니다.
# """
    candidates = {}

    if formation == "4-3-3":
        # FW 대분류 중 득점/PA슈팅이 높은 선수를 ST(스트라이커) 후보 Top 3
        candidates['ST'] = scored_df[scored_df['포지션'] == 'FW'].sort_values(by='득점', ascending=False).head(3)
        # 드리블/크로스가 좋은 선수를 윙어(LW, RW) 후보 Top 3
        candidates['LW'] = scored_df[scored_df['포지션'] == 'FW'].sort_values(by='드리블_성공', ascending=False).head(3)
        candidates['RW'] = scored_df[scored_df['포지션'] == 'FW'].sort_values(by='크로스_성공', ascending=False).head(3)
        
        # MF, DF, GK 등도 동일한 방식으로 세부 슬롯 후보 지정 가능
        candidates['MF'] = scored_df[scored_df['포지션'] == 'MF'].sort_values(by='종합_평가점수', ascending=False).head(3)
        candidates['DF'] = scored_df[scored_df['포지션'] == 'DF'].sort_values(by='종합_평가점수', ascending=False).head(3)
        candidates['GK'] = scored_df[scored_df['포지션'] == 'GK'].sort_values(by='종합_평가점수', ascending=False).head(3)
        
    return candidates

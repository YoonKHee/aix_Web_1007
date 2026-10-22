# analytics/utils.py
import pandas as pd
import numpy as np
import glob
import os

def load_all_teams_data(data_dir='data'):
    """
    data/ 폴더에 있는 모든 팀의 엑셀 파일을 읽어와 하나의 데이터프레임으로 통합합니다.
    """
    all_files = glob.glob(os.path.join(data_dir, "*.xls")) + glob.glob(os.path.join(data_dir, "*.xlsx"))
    df_list = []
    
    for file_path in all_files:
        try:
            # 파일명에서 구단 이름 추출 (예: "2026 서울.xls" -> "서울")
            filename = os.path.basename(file_path)
            team_name = filename.replace("2026", "").replace(".xls", "").replace(".xlsx", "").strip()
            
            dfs = pd.read_html(file_path)
            df = dfs[0]
            
            # MultiIndex 컬럼 단일화
            if isinstance(df.columns, pd.MultiIndex):
                new_cols = []
                for col in df.columns:
                    c0 = str(col[0]).strip()
                    c1 = str(col[1]).strip()
                    new_cols.append(c0 if c0 == c1 else f"{c0}_{c1}")
                df.columns = new_cols
                
            df['소속구단'] = team_name
            df_list.append(df)
        except Exception as e:
            print(f"파일 읽기 오류 ({file_path}): {e}")
            
    if not df_list:
        return pd.DataFrame()
        
    return pd.concat(df_list, ignore_index=True)

def process_football_data(target_team="전체 (K리그 통합)", formation="4-3-3", min_minutes=90):
    """
    전체 구단 또는 특정 구단의 데이터를 로드하고 점수를 계산한 뒤 소수점 첫째 자리로 반환합니다.
    """
    df = load_all_teams_data()
    if df.empty:
        return [], []
        
    try:
        def get_col_val(dframe, col_name):
            if col_name in dframe.columns:
                return pd.to_numeric(dframe[col_name], errors='coerce').fillna(0)
            return pd.Series(0, index=dframe.index)

        # 최소 출전시간 미달자 필터링
        df_filtered = df[pd.to_numeric(df['출전시간(분)'], errors='coerce').fillna(0) >= min_minutes].copy()
        minutes = pd.to_numeric(df_filtered['출전시간(분)'], errors='coerce').fillna(1)
        per_90 = 90.0 / minutes
        
        # 1. 세부 가산점 산출 (90분당 환산)
        df_filtered['공격_점수'] = (
            get_col_val(df_filtered, '득점') * 10.0 +
            get_col_val(df_filtered, '도움') * 7.0 +
            get_col_val(df_filtered, '키패스') * 2.0 +
            get_col_val(df_filtered, 'PA내 슈팅') * 1.5 +
            get_col_val(df_filtered, '드리블_성공') * 1.5 +
            get_col_val(df_filtered, '탈압박') * 1.5
        ) * per_90
        
        df_filtered['빌드업_점수'] = (
            get_col_val(df_filtered, '공격지역패스_성공') * 0.5 +
            get_col_val(df_filtered, '전방 패스_성공') * 0.3 +
            get_col_val(df_filtered, '롱패스_성공') * 0.8 +
            get_col_val(df_filtered, '크로스_성공') * 1.0
        ) * per_90
        
        df_filtered['수비_점수'] = (
            get_col_val(df_filtered, '태클_성공') * 1.5 +
            get_col_val(df_filtered, '인터셉트') * 1.2 +
            get_col_val(df_filtered, '차단') * 1.0 +
            get_col_val(df_filtered, '획득') * 0.8 +
            get_col_val(df_filtered, '클리어링') * 0.8
        ) * per_90
        
        df_filtered['감점'] = (
            get_col_val(df_filtered, '볼미스') * 1.0 +
            get_col_val(df_filtered, '파울') * 0.5 +
            get_col_val(df_filtered, '경고') * 2.0 +
            get_col_val(df_filtered, '퇴장') * 5.0
        ) * per_90
        
        # 2. 포지션별 가중치 적용 종합 점수 계산 (소수점 첫째 자리 반올림)
        def calc_total(row):
            pos = str(row['포지션']).upper()
            if 'FW' in pos:
                base = row['공격_점수'] * 1.5 + row['빌드업_점수'] * 0.8 + row['수비_점수'] * 0.7
            elif 'MF' in pos:
                base = row['공격_점수'] * 1.1 + row['빌드업_점수'] * 1.2 + row['수비_점수'] * 1.0
            elif 'DF' in pos:
                base = row['공격_점수'] * 0.5 + row['빌드업_점수'] * 1.0 + row['수비_점수'] * 1.5
            elif 'GK' in pos:
                base = row['빌드업_점수'] * 1.0 + row['수비_점수'] * 1.2
            else:
                base = row['공격_점수'] + row['빌드업_점수'] + row['수비_점수']
            return round(max(base - row['감점'], 0), 1)

        df_filtered['종합_평가점수'] = df_filtered.apply(calc_total, axis=1)
        
        # 점수 및 소수점 자리 포맷팅 정리
        df_filtered['공격_점수'] = df_filtered['공격_점수'].round(1)
        df_filtered['빌드업_점수'] = df_filtered['빌드업_점수'].round(1)
        df_filtered['수비_점수'] = df_filtered['수비_점수'].round(1)
        df_filtered['감점'] = df_filtered['감점'].round(1)

        # 특정 구단만 필터링할 경우
        if target_team != "전체 (K리그 통합)":
            df_filtered = df_filtered[df_filtered['소속구단'] == target_team]

        df_sorted = df_filtered.sort_values(by='종합_평가점수', ascending=False)
        
        # 3. 포메이션별 베스트 11 자동 선출 (전체 선수 비교 혹은 해당 구단 내 비교)
        formation_map = {
            "4-3-3": {"FW": 3, "MF": 3, "DF": 4, "GK": 1},
            "4-4-2": {"FW": 2, "MF": 4, "DF": 4, "GK": 1},
            "3-5-2": {"FW": 2, "MF": 5, "DF": 3, "GK": 1},
            "4-2-3-1": {"FW": 1, "MF": 5, "DF": 4, "GK": 1}
        }
        reqs = formation_map.get(formation, formation_map["4-3-3"])
        
        b11_dfs = []
        for pos, count in reqs.items():
            subset = df_sorted[df_sorted['포지션'] == pos].head(count)
            b11_dfs.append(subset)
            
        best_11_df = pd.concat(b11_dfs).sort_values(by=['포지션', '종합_평가점수'], ascending=[False, False]) if b11_dfs else pd.DataFrame()
        
        return df_sorted.to_dict('records'), best_11_df.to_dict('records')
    except Exception as e:
        print(f"데이터 처리 오류: {e}")
        return [], []
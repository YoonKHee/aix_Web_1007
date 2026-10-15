# analytics/views.py 에 있는 team_battle_view 함수
# analytics/views.py
import json
import os
import glob
import pandas as pd
from django.shortcuts import render






# 유틸리티 함수 안전 임포트 (없을 경우 기본 함수 대체)
try:
    from .utils import process_football_data, load_all_teams_data
except ImportError:
    def process_football_data(target_team="전체 (K리그 통합)", formation="4-3-3", min_minutes=90):
        return [], []
    def load_all_teams_data():
        return pd.DataFrame()


# analytics/views.py 의 dashboard_view 함수 부분 수정
import math

def calculate_hexagon_points(ratios, cx=90, cy=90, max_r=55):
    # 6개 축 기준 (공격, 빌드업, 수비, 득점, 도움, 종합)
    points = []
    for i, val in enumerate(ratios):
        angle_deg = -90 + (i * 60)
        angle_rad = math.radians(angle_deg)
        r = max_r * float(val)
        x = cx + r * math.cos(angle_rad)
        y = cy + r * math.sin(angle_rad)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def dashboard_view(request):
    team = request.GET.get('team', '전체 (K리그 통합)')
    formation = request.GET.get('formation', '4-3-3')
    min_mins = int(request.GET.get('min_mins', 90))
    
    all_files = glob.glob(os.path.join('data', "*.xls")) + glob.glob(os.path.join('data', "*.xlsx"))
    teams_list = ["전체 (K리그 통합)"]
    for f in all_files:
        name = os.path.basename(f).replace("2026", "").replace(".xls", "").replace(".xlsx", "").strip()
        if name not in teams_list:
            teams_list.append(name)
            
    all_players_dict, best_11_dict = process_football_data(team, formation, min_mins)

    slot_candidates = {}
    if all_players_dict:
        df_all = pd.DataFrame(all_players_dict)
        for pos in ['GK', 'DF', 'MF', 'FW']:
            pos_df = df_all[df_all['포지션'] == pos].sort_values(by='종합_평가점수', ascending=False)
            slot_candidates[pos] = pos_df.to_dict('records')
    
    for p in best_11_dict:
        p['이미지유형'] = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
        
        # 육각형 그래프용 능력치 비율 계산 (0.15 ~ 1.0 스케일)
        p['hex_attack'] = round(min(max(float(p.get('공격_점수', 0)) / 20.0, 0.15), 1.0), 2)
        p['hex_buildup'] = round(min(max(float(p.get('빌드업_점수', 0)) / 20.0, 0.15), 1.0), 2)
        p['hex_defense'] = round(min(max(float(p.get('수비_점수', 0)) / 20.0, 0.15), 1.0), 2)
        p['hex_goal'] = round(min(max(float(p.get('득점', 0)) / 4.0, 0.15), 1.0), 2)
        p['hex_assist'] = round(min(max(float(p.get('도움', 0)) / 4.0, 0.15), 1.0), 2)
        p['hex_total'] = round(min(max(float(p.get('종합_평가점수', 0)) / 45.0, 0.15), 1.0), 2)
        
        ratios = [p['hex_attack'], p['hex_buildup'], p['hex_defense'], p['hex_goal'], p['hex_assist'], p['hex_total']]
        p['hex_points'] = calculate_hexagon_points(ratios)

    position_averages = {}
    if all_players_dict:
        df_all = pd.DataFrame(all_players_dict)
        if '포지션' in df_all.columns and '종합_평가점수' in df_all.columns:
            position_averages = df_all.groupby('포지션')['종합_평가점수'].mean().round(1).to_dict()


    context = {
        'best_11': best_11_dict,
        'slot_candidates': slot_candidates,
        'position_averages': position_averages,
        'current_team': team,
        'teams_list': teams_list,
        'current_formation': formation,
        'current_mins': min_mins,
        'formations': ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1"]
    }
    return render(request, 'analytics/dashboard.html', context)


def player_stats_view(request):
    team = request.GET.get('team', '전체 (K리그 통합)')
    min_mins = int(request.GET.get('min_mins', 90))
    
    all_files = glob.glob(os.path.join('data', "*.xls")) + glob.glob(os.path.join('data', "*.xlsx"))
    teams_list = ["전체 (K리그 통합)"]
    for f in all_files:
        name = os.path.basename(f).replace("2026", "").replace(".xls", "").replace(".xlsx", "").strip()
        if name not in teams_list:
            teams_list.append(name)
            
    all_players_dict, _ = process_football_data(target_team=team, formation="4-3-3", min_minutes=min_mins)
    
    context = {
        'all_players': all_players_dict,
        'current_team': team,
        'teams_list': teams_list,
        'current_mins': min_mins,
    }
    return render(request, 'analytics/player_stats.html', context)


def team_battle_view(request):
    all_files = glob.glob(os.path.join('.', "*.csv"))
    teams_data_map = {}
    
    for f in all_files:
        try:
            filename = os.path.basename(f)
            team_name = ""
            
            if "서울" in filename or "Seoul" in filename:
                team_name = "FC 서울"
            elif "울산" in filename or "Ulsan" in filename:
                team_name = "울산 HD"
            elif "포항" in filename or "Pohang" in filename:
                team_name = "포항 스틸러스"
            elif "전북" in filename or "Jeonbuk" in filename:
                team_name = "전북 현대"
            elif "광주" in filename or "Gwangju" in filename:
                team_name = "광주 FC"
            elif "인천" in filename or "Incheon" in filename:
                team_name = "인천 유나이티드"
            elif "제주" in filename or "Jeju" in filename:
                team_name = "제주 유나이티드"
            elif "강원" in filename or "Gangwon" in filename:
                team_name = "강원 FC"
            elif "수원" in filename or "Suwon" in filename:
                team_name = "수원 FC"
            elif "김천" in filename or "Gimcheon" in filename:
                team_name = "김천 상무"
            elif "대구" in filename or "Daegu" in filename:
                team_name = "대구 FC"
            elif "대전" in filename or "Daejeon" in filename:
                team_name = "대전 하나시티즌"
            elif "부천" in filename or "Bucheon" in filename:
                team_name = "부천 FC"
            else:
                continue

            df = pd.read_csv(f, encoding='utf-8-sig')
            if df.empty or '선수명' not in df.columns or '포지션' not in df.columns:
                continue

            if '종합_평가점수' not in df.columns:
                df['종합_평가점수'] = df['점수'] if '점수' in df.columns else 75.0

            if team_name not in teams_data_map:
                teams_data_map[team_name] = []
            
            existing_names = [p['선수명'] for p in teams_data_map[team_name]]
            for _, row in df.iterrows():
                p_name = str(row['선수명']).strip()
                p_pos = str(row['포지션']).strip().upper()
                if p_name and p_name not in existing_names:
                    teams_data_map[team_name].append({
                        '선수명': p_name,
                        '포지션': p_pos if p_pos in ['GK', 'DF', 'MF', 'FW'] else 'MF',
                        '종합_평가점수': float(row.get('종합_평가점수', 75.0)),
                        '이미지유형': "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
                        '소속구단': team_name
                    })
                    existing_names.append(p_name)
        except Exception as e:
            pass

    teams_list = list(teams_data_map.keys())
    if not teams_list:
        teams_list = ["FC 서울", "울산 HD", "포항 스틸러스", "전북 현대"]
        teams_data_map = {t: [] for t in teams_list}

    team_a = request.GET.get('team_a', teams_list[0])
    team_b = request.GET.get('team_b', teams_list[1] if len(teams_list) > 1 else teams_list[0])

    players_a = teams_data_map.get(team_a, [])
    players_b = teams_data_map.get(team_b, [])

    context = {
        'teams_list': teams_list,
        'team_a': team_a,
        'team_b': team_b,
        'players_a_json': json.dumps(players_a, ensure_ascii=False),
        'players_b_json': json.dumps(players_b, ensure_ascii=False),
    }
    return render(request, 'analytics/team_battle.html', context)




def player_stats_view(request):
    # 점수표 페이지에서도 팀을 선택할 수 있도록 파라미터 수신 (기본값: 전체)
    team = request.GET.get('team', '전체 (K리그 통합)')
    min_mins = int(request.GET.get('min_mins', 90))
    
    all_files = glob.glob(os.path.join('data', "*.xls")) + glob.glob(os.path.join('data', "*.xlsx"))
    teams_list = ["전체 (K리그 통합)"]
    for f in all_files:
        name = os.path.basename(f).replace("2026", "").replace(".xls", "").replace(".xlsx", "").strip()
        if name not in teams_list:
            teams_list.append(name)
            
    # 선택된 팀 데이터를 기준으로 점수 산출
    all_players_dict, _ = process_football_data(target_team=team, formation="4-3-3", min_minutes=min_mins)
    
    context = {
        'all_players': all_players_dict,
        'current_team': team,
        'teams_list': teams_list,
        'current_mins': min_mins,
    }
    return render(request, 'analytics/player_stats.html', context)
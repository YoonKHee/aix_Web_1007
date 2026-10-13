# analytics/views.py
from django.shortcuts import render
from .utils import load_all_teams_data, process_football_data
import os
import glob
import pandas as pd

def dashboard_view(request):
    team = request.GET.get('team', '전체 (K리그 통합)')
    formation = request.GET.get('formation', '4-3-3')
    min_mins = int(request.GET.get('min_mins', 90))
    
    # 구단 목록 자동 추출
    all_files = glob.glob(os.path.join('data', "*.xls")) + glob.glob(os.path.join('data', "*.xlsx"))
    teams_list = ["전체 (K리그 통합)"]
    for f in all_files:
        name = os.path.basename(f).replace("2026", "").replace(".xls", "").replace(".xlsx", "").strip()
        if name not in teams_list:
            teams_list.append(name)
            
    all_players_dict, best_11_dict = process_football_data(team, formation, min_mins)
    
    # 포지션별 평균 점수 계산 (전체 선수 기준)
    position_averages = {}
    if all_players_dict:
        df_all = pd.DataFrame(all_players_dict)
        if '포지션' in df_all.columns and '종합_평가점수' in df_all.columns:
            avg_series = df_all.groupby('포지션')['종합_평가점수'].mean().round(1)
            position_averages = avg_series.to_dict()

    context = {
        'all_players': all_players_dict,
        'best_11': best_11_dict,
        'position_averages': position_averages,
        'current_team': team,
        'teams_list': teams_list,
        'current_formation': formation,
        'current_mins': min_mins,
        'formations': ["4-3-3", "4-4-2", "3-5-2", "4-2-3-1"]
    }
    return render(request, 'analytics/dashboard.html', context)
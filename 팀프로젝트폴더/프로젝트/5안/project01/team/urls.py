from django.urls import path

from .prediction_views import predict_match

from .simulation_views import (
    simulation_page,
    simulation_roster,
    simulation_result,
)


app_name = 'team'


urlpatterns = [
    # 기본 승무패 예측 화면
    path(
        'predict/',
        predict_match,
        name='predict_match',
    ),

    # 선수 교체·컨디션 시뮬레이션 화면
    path(
        'simulate/',
        simulation_page,
        name='simulate',
    ),

    # 선택한 구단의 선수 명단
    path(
        'simulation/roster/',
        simulation_roster,
        name='simulation_roster',
    ),

    # 사용자 설정에 따른 시뮬레이션 계산
    path(
        'simulation/result/',
        simulation_result,
        name='simulation_result',
    ),
]
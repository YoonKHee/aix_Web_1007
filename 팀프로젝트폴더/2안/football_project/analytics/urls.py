# analytics/urls.py
from django.urls import path
from .views import dashboard_view, player_stats_view, team_battle_view

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('players/', player_stats_view, name='player_stats'),
    path('battle/', team_battle_view, name='team_battle'),
]
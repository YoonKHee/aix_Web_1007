from django.urls import include, path
from . import views
from .tracking_demo_views import tracking_demo


app_name = 'player'


urlpatterns = [

    # 선수 목록
    path(
        'plist/',
        views.plist,
        name='plist'
    ),

    # 선수 상세페이지
    path(
        'pview/<int:id>/',
        views.pview,
        name='pview'
    ),

    # BEST11
    path(
        'best11/',
        views.best11,
        name='best11'
    ),

    # 선수 팝업용 JSON
    path(
        'info/<int:id>/',
        views.player_info,
        name='player_info'
    ),

    # 감독 연구실 (가중치 · 케미 · 교체 · 진단 · 데이터 점검)
    path(
        'lab/',
        include('player.lab.urls')
    ),

    # 트래킹 데모 (5안)
    path(
        'tracking-demo/',
        tracking_demo,
        name='tracking_demo',
    ),

]
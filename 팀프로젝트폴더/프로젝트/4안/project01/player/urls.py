from django.urls import path
from . import views


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

]
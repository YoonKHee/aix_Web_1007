from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path(
        '',
        include('home.urls'),
    ),

    path(
        'admin/',
        admin.site.urls,
    ),

    path(
        'player/',
        include('player.urls'),
    ),

    path(
        'team/',
        include('team.urls'),
    ),

    path(
        'board/',
        include('board.urls'),
    ),

    path(
        'manager/',
        include('manager.urls'),
    ),

    path(
        'soccer_game/',
        include('soccer_game.urls'),
    ),
]


urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT,
)
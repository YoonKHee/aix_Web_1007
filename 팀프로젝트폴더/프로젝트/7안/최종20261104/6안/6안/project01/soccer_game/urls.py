from django.urls import path
from . import views

app_name = 'soccer_game'

urlpatterns = [
    path('game/', views.game, name='game'),

]

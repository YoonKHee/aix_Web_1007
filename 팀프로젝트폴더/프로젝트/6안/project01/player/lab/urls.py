from django.urls import path

from . import views

urlpatterns = [
    path('init/', views.lab_init, name='lab_init'),
    path('lineup/', views.lab_lineup, name='lab_lineup'),
    path('evaluate/', views.lab_evaluate, name='lab_evaluate'),
    path('candidates/', views.lab_candidates, name='lab_candidates'),
    path('condition/', views.lab_condition, name='lab_condition'),
    path('schedule/', views.lab_schedule, name='lab_schedule'),
    path('formations/', views.lab_formations, name='lab_formations'),
    path('player-report/', views.lab_player_report, name='lab_player_report'),
    path('chem-partners/', views.lab_chem_partners, name='lab_chem_partners'),
    path('quality/', views.lab_quality, name='lab_quality'),
]

from django.urls import path
from . import views

app_name = 'screen'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard2/', views.dashboard2, name='dashboard2'),
]

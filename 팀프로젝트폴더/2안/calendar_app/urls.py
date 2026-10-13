from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),
    path('api/events/', views.api_events_view, name='api_events'),
    path('ics/<str:event_id>/', views.export_ics_view, name='export_ics'),
]
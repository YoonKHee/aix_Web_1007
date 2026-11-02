from . import views
from django.urls import path, include

app_name='event'
urlpatterns = [
    path('event/', views.event, name='event'),
]

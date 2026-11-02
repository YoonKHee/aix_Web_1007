from . import views
from django.urls import path, include

app_name='community'
urlpatterns = [
    path('community/', views.community, name='community'),
]

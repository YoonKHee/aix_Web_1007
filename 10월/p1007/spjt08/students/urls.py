from . import views
from django.urls import path,include

app_name = 'students'
urlpatterns = [
    path('swrite/', views.swrite, name='swrite'),
]
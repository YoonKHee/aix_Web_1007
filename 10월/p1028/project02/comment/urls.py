from django.urls import path,include
from . import views

app_name='comment'
urlpatterns = [
    path('commlist/', views.commlist, name='commlist'),
    path('commwrite/', views.commwrite, name='commwrite'),
]


from . import views
from django.urls import path, include

app_name='students'
urlpatterns = [
    path('slist/', views.slist, name='slist'),
    path('swrite/', views.swrite, name='swrite'),
    path('sview/<str:name>/', views.sview, name='sview'),
    path('supdate/<str:name>/', views.supdate, name='supdate'),
    path('sdelete/<str:name>/', views.sdelete, name='sdelete'),
]

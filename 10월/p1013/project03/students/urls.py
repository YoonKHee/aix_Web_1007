from . import views
from django.urls import path, include

app_name = 'students'
urlpatterns = [
    path('swrite/', views.swrite, name='swrite'),
    path('slist/', views.slist, name='slist'),
    path('sview/<int:no>/', views.sview, name='sview'),
    path('supdate/<int:no>/', views.supdate, name='supdate'),
    path('sdelete/<int:no>/', views.sdelete, name='sdelete'),
]

from . import views
from django.urls import path,include

app_name='student'
urlpatterns = [
    path('swrite/', views.swrite, name='swrite'),
    path('slist/', views.slist, name='slist'),
]

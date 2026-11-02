from . import views
from django.urls import path, include

app_name='students'
urlpatterns = [
    path('slist/',views.slist, name='slist'),
    path('swrite/',views.swrite, name='swrite'),
]
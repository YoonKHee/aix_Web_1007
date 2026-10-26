from django.urls import path,include
from . import views

app_name='customer'
urlpatterns = [
    path('clist/', views.clist, name='clist'),
    path('cview/<int:bno>/', views.cview, name='cview'),
]

from . import views
from django.urls import path,include

app_name = ''
urlpatterns = [
    # url(swrite), views파일에서 swrite함수를 찾음
    # path('swrite/', views.swrite, name='swrite'),
    # path('slist/', views.slist, name='slist'),
    # path('p_list/', views.p_list, name='p_list'),
    path('', views.index, name='index'),
    # path('p_member/', views.p_member, name='p_member'),
    # path('p_stulist/', views.p_stulist, name='p_stulist'),
    # path('p_view/', views.p_view, name='p_view'),
    # path('p_write/', views.p_write, name='p_write'),
]
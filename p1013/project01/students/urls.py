
from . import views
from django.urls import path, include

app_name = 'students'
urlpatterns = [
    path('swrite/', views.swrite, name='swrite'),
    path('slist/', views.slist, name='slist'),
    path('sview/<int:no>', views.sview, name='sview'),
    path('sdelete/<int:no>/', views.sdelete, name='sdelete'),
    path('supdate/<int:no>/', views.supdate, name='supdate'),
]

    #-----------------------------------------------------------------------------------
    # HTML에서 디장고로 값 전달방법 = url path, 파라미터방식
    # path('swrite3/', views.swrite3, name='swrite3'),
    # path('swrite2/<str:name>/', views.swrite2, name='swrite2'),
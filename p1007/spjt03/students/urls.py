from . import views # .은 현재 자기폴더 안을 뜻함
from django.urls import path,include # 추가해서 사용가능
# from django.urls import include


urlpatterns = [
    path('swrite/', views.swrite ,name='swrite'), # students app 안에 urls를 찾아감.
]
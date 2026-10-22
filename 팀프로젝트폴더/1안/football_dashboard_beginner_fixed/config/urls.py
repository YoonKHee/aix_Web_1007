from django.contrib import admin
from django.urls import include, path
from screen import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # 주소창에 http://127.0.0.1:8000/ 만 입력해도 첫 화면 실행
    path('', views.dashboard, name='home'),

    # screen 앱 주소 연결
    path('screen/', include('screen.urls')),
]

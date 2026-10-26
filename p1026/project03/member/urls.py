from django.urls import path,include
from . import views

app_name='member'
urlpatterns = [
    path('step01/', views.step01, name='step01'),
    # 이메일 전송
    path('emailsend/', views.emailsend, name='emailsend'),
    # 이메일 전송후 인증키 확인
    path('email_key/', views.email_key, name='email_key'),
    path('login/', views.login, name='login'),
]

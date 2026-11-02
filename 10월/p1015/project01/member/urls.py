"""
URL configuration for project01 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from . import views
from django.urls import path, include

app_name = 'member'
urlpatterns = [
    # 로그인
    path('login/', views.login,name='login'),
    path('logout/', views.logout,name='logout'),


    # 회원가입
    path('step01/', views.step01,name='step01'),
    path('step02/', views.step02,name='step02'),
    path('step03/', views.step03,name='step03'),
    path('step04/', views.step04,name='step04'),
]

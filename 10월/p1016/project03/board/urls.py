"""
URL configuration for project03 project.

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
from django.urls import path,include

app_name = 'board'
urlpatterns = [
    path('blist/', views.blist,name='blist'),
    path('bwrite/', views.bwrite,name='bwrite'),
]

# # 파일 업로드식 url 구성이 되어 있어야 파일을 업로드 할 수 있다.
# urlpatterns += static(settings.MEDIA_URL,
# document_root = settings.MEDIA_ROOT
# )

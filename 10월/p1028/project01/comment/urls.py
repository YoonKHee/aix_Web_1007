from django.urls import path,include
from . import views

app_name='comment'
urlpatterns = [
    path('commlist/', views.commlist, name='commlist'),
    # ajax 댓글쓰기
    path('commwrite/', views.commwrite, name='commwrite'),
]


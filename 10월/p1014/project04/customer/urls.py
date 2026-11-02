from . import views
from django.urls import path, include

app_name='customer'
urlpatterns = [
    path('customer/', views.customer, name='customer'),
]

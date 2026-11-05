from django.urls import path
from . import views

app_name = 'manager'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('import/', views.import_upload, name='import_upload'),
    path('import/<int:pk>/', views.import_report, name='import_report'),
    path('import/<int:pk>/apply/', views.import_apply, name='import_apply'),
    path('history/', views.history, name='history'),
    path('scoring/', views.scoring, name='scoring'),
    path('exclusions/', views.exclusions, name='exclusions'),
    path('backups/', views.backups, name='backups'),
    path('backups/now/', views.backup_now, name='backup_now'),
    path('backups/<str:name>/restore/', views.backup_restore, name='backup_restore'),
]

from django.contrib import admin
from students.models import Students
# Register your models here.
admin.site.register(Students)
print('Students 관리자 등록 파일 실행됨')
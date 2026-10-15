from django.db import models

# Create your models here.
class Member(models.Model):
    # primary_key:중복값 안되게, null값 안되게
    # ForeignKey 외래키 : 다른 클래스에서 primary_key로 사용된것을 사용할때
    id = models.CharField(max_length=30, primary_key=True)
    pw = models.CharField(max_length=100)
    name = models.CharField(max_length=60)
    nickname = models.CharField(max_length=60)
    tel = models.CharField(max_length=20,default='010-0000-0000')
    gender = models.CharField(max_length=10)
    hobby = models.CharField(max_length=100)
    mdate = models.DateTimeField(auto_now=True, blank=True)

    def __str__(self):
        return f'{self.id},{self.name},{self.nickname},{self.hobby},{self.mdate},'
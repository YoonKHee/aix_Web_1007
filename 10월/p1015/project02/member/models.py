from django.db import models

# Create your models here.
class Member(models.Model):
    id = models.CharField(max_length=30, primary_key=True)
    pw = models.CharField(max_length=30)
    name = models.CharField(max_length=60)
    nickname = models.CharField(max_length=60)
    tel = models.CharField(max_length=20,default='010-0000-0000')
    gender = models.CharField(max_length=10)
    hobby = models.CharField(max_length=60)
    mdate = models.DateTimeField(auto_now=True, blank=True)

    def __str__(self):
        return f'{self.id},{self.name},{self.nickname},{self.hobby},{self.mdate}'
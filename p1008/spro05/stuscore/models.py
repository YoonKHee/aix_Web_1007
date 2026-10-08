from django.db import models

# Create your models here.

class Stuscore(models.Model):
    no = models.IntegerField(default=0)
    name = models.CharField(max_length=100)
    school = models.CharField(max_length=100)
    grade = models.IntegerField(default=0)
    age = models.IntegerField(default=0)
    stature = models.FloatField(default=0)
    kor = models.IntegerField(default=0)
    eng = models.IntegerField(default=0)
    math = models.IntegerField(default=0)
    sw = models.CharField(max_length=100)
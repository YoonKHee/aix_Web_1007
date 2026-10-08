from django.db import models

# Create your models here.
class Stu(models.Model):
    name = models.CharField(max_length=100)
    major = models.CharField(max_length=100)
    grade = models.IntegerField(default=0)
    age = models.IntegerField(default=0)
    gender = models.CharField(max_length=30)

    def __str__(self):
        return f'{self.name},{self.major},{self.grade},{self.age},{self.gender}'
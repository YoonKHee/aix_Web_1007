from django.db import models

# Create your models here.
class Screen1(models.Model):
    sno = models.AutoField(primary_key=True)
    rank = models.IntegerField(default=0)
    title = models.CharField(max_length=1000,blank=True)
    date = models.DateTimeField(null=True,blank=True)
    percent = models.FloatField(default=0)
    revenue = models.IntegerField(default=0)
    crevenue = models.IntegerField(default=0)
    sales = models.IntegerField(default=0)
    csales = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.title},{self.percent},{self.revenue},{self.sales}'
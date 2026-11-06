from django.db import models
from member.models import Member

class Board(models.Model):
    bno = models.AutoField(primary_key=True)
    member = models.ForeignKey(Member,on_delete=models.SET_NULL,blank=True,null=True)
    btitle = models.CharField(max_length=1000)
    bcontent = models.TextField()

    bgroup = models.IntegerField(default=0)
    bstep = models.IntegerField(default=0)
    bindent = models.IntegerField(default=0)
    bhit = models.IntegerField(default=1)
    bdate = models.DateTimeField(auto_now=True,blank=True)
    bfile = models.ImageField(blank=True,upload_to='board')

    def __str__(self):
        return f'{self.bno},{self.btitle},{self.bdate}'

 

from django.db import models

# Create your models here.
class Board(models.Model):
    btitle = models.CharField(max_length=1000)
    # upload 폴더 안에 board 폴더를 생성해서 그 안에 파일저장.
    bfile = models.ImageField(null=True, upload_to='board')

    def __str__(self):
        return f'{self.btitle},{self.bfile}'
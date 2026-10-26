from django.db import models
from member.models import Member

class Event(models.Model):
    eno = models.AutoField(primary_key=True)
    # id = models.CharField(max_length=30)  # member -> primary_key
    member = models.ForeignKey(Member,on_delete=models.SET_NULL,blank=True,null=True)
    etitle = models.CharField(max_length=1000)
    econtent = models.TextField()    # 대용량TextField
    ehit = models.IntegerField(default=1)
    first_date = models.DateTimeField(auto_now=True,blank=True)
    end_date = models.DateTimeField(auto_now=True,blank=True)
    edate = models.DateTimeField(auto_now=True,blank=True)
    efile = models.ImageField(blank=True,upload_to='event') #upload/event폴더를 생성하고 그안에 파일저장
    efile2 = models.ImageField(blank=True,upload_to='event') #upload/event폴더를 생성하고 그안에 파일저장

    def __str__(self):
        return f'{self.eno},{self.etitle},{self.edate}'

    # bno,id,btitle,bcontent,bgroup,bstep,bindent,bhit,bdate,bfile
    # bno : 게시판번호
    # id : 회원아이디
    # btitle:제목, bcontent:내용
    # bgroup-답변달기그룹핑,bstep-그룹핑순서,bindent-들여쓰기 : 답변달기
    # bhit : 조회수
    # bdate : 등록일
    # bfile : 파일첨부

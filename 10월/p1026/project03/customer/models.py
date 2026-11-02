from django.db import models
from member.models import(Member)
# Create your models here.
class Board(models.Model):
    bno = models.AutoField(primary_key=True)                   # 게시판번호
    # 다른테이블에 primary_key 등록이 되어 있는 것을 다른 테이블에서 사용할때
    # Board 데이터가 등록될때 Member에서 id값을 확인해서 있는지 체크
    # member = models.ForeignKey(Member,on_delete=models.DO_NOTHING,blank=True,null=True) # 회원탈퇴해도 게시물은 삭제 안되게
    # member = models.ForeignKey(Member,on_delete=models.CASCADE,blank=True,null=True) # 탈퇴시 게시글도 같이 삭제
    member = models.ForeignKey(Member,on_delete=models.SET_NULL,blank=True,null=True) # 탈퇴시 값이 널로 바뀜
    # id = models.CharField(max_length=30)                       # 회원아이디
    btitle = models.CharField(max_length=1000)                 # 제목
    bcontent = models.TextField()# 대용량텍스트                  # 내용
    # 답변달기
    bgroup = models.IntegerField(default=0)                    # 답변달기 그룹핑
    bstep = models.IntegerField(default=0)                     # 답변달기 그룹순서
    bindent = models.IntegerField(default=0)                   # 답변달기 들여쓰기
    bhit = models.IntegerField(default=1)                      # 조회수
    bdate = models.DateTimeField(auto_now=True, blank=True)    # 등록일
    bfile = models.ImageField(blank=True, upload_to='board')   # 파일첨부 # upload/board폴도를 생성하고 그안에 파일저장   

    def __str__(self):
        return f'{self.bno},{self.btitle},{self.bdate}'




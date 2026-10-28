from django.shortcuts import render
import os
from pathlib import Path
from dotenv import load_dotenv
from django.db.models import F,Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import smtplib
from email.mime.text import MIMEText
import random
import string
from comment.models import Comment
from event.models import Event
from member.models import Member

# ajax 하단 댓글쓰기
def commwrite(request):
    eno = request.POST.get('eno')
    # ForeignKey는 객체 1개 전체를 입력해야함
    e_qs = Event.objects.get(eno=eno)
    m_qs = Member.objects.get(id=request.session['s_id'])
    cpw = request.POST.get('cpw','')
    ccontent = request.POST.get('ccontent')
    # comment 저장 
    qs = Comment.objects.create(event=e_qs,member=m_qs,cpw=cpw,ccontent=ccontent)
    print('확인:',cpw,ccontent,eno,qs.cno,qs.cdate)
    qs_1 = Comment.objects.filter(cno=qs.cno).values()
    qs_1 = list(qs_1)
    context = {'result':'성공','comment':qs_1} #  qs엔 cno,event,member,cpw,ccontent,cdate 모두 포함되어 있음
    return JsonResponse(context)









def commlist(request):
    context = {'result':'성공'}
    return JsonResponse(context)
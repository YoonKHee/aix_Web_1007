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
import json
# Create your views here.




def step02(request):
    return render(request,'step02.html')


def ekey(request):
    ekey = request.POST.get('ekey','')  
    s_ekey = request.session['s_ekey']
    print(f'인증키확인:{ekey},{s_ekey}')
    if ekey==s_ekey:
        context = {'temp':1}
    else:
        context = {'temp':0}
    return JsonResponse(context)



def email(request):
    # 1. 이메일 주소 가져오기 (input 에 입력한 주소)
    email= request.POST.get('email','')
    print('데이터 확인 :',email)

    # 2. 네이버 비밀번호 가져오기 (.env)(.env 파일 불러오기)
    BASE_DIR = Path(__file__).resolve().parent.parent
    ENV_FILE = BASE_DIR / '.env'
    load_dotenv(ENV_FILE) # .env 파일 불러오기
    naver_key = os.getenv('naver_key') # .env 에 저장된 네이버 비밀번호 가져오기
    print('네이버 인증키:',naver_key)

    # 3. 인증키난수생성
    chars = string.digits + string.ascii_lowercase # 0-9 + a-z 를 리스트에 넣기 # 난수 생성용
    ekey = ''.join(random.choices(chars,k=10)) # 소문자영어와 숫자로 구분된 인증키 10자리 생성
    print(ekey)

    # 4. 이메일내용 - 글자로 이메일 발송
    sendEmail = 'qufwja3@naver.com'
    content = f'이메일확인 인증키: {ekey}'
    text = f'''
    <html>
            <body>
                <h2>[ 이메일확인 인증키 ]</h2>
                <p>{ekey}</p>
            </body>
        </html>
        '''

    # 5. 정보 그룹핑
    msg = MIMEText(text,'html') # 이메일 내용 만들기 html로 보내기 여러줄의 이메일
    msg = MIMEText(content) # 이메일 내용 만들기 일반 텍스트
    msg['From'] = sendEmail # 보내는사람
    msg['To'] = email # 받는사람
    msg['Subject'] = '이메일 테스트' # 이메일 내용

    # 6. 그룹핑 정보 전송
    s = smtplib.SMTP('smtp.naver.com',587)  # SMTP 서버
    s.starttls() # 메일서버 접근
    s.login(sendEmail,naver_key) # 메일서버로그인
    s.sendmail(sendEmail,email,msg.as_string()) # 메일발송
    s.close() # 메일 닫기

    request.session['s_ekey'] = ekey
    context = {'ekey':ekey}
    return JsonResponse(context)












def step01(request):
    BASE_DIR = Path(__file__).resolve().parent.parent
    ENV_FILE = BASE_DIR / '.env'
    load_dotenv(ENV_FILE)
    naver_key = os.getenv('naver_key')
    print('네이버인증키: ',naver_key)
    return render(request,'step01.html')
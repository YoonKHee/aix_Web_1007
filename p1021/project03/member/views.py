from django.shortcuts import render
from dotenv import load_dotenv
import os
from pathlib import Path
# Create your views here.
def step01(request):
    BASE_DIR = Path(__file__).resolve().parent.parent
    ENV_FILE = BASE_DIR / '.env'
    load_dotenv(ENV_FILE)
    naver_key = os.getenv('naver_key')
    print('네이버인증키: ',naver_key)
    return render(request,'step01.html')
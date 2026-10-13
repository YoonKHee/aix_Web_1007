from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
# HttpResponse:테스트 하기 좋음 html안만들고 임시로 이름을 지정해서 넣어줌
def index(request):
    return render(request,'index.html')

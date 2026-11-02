from django.shortcuts import render,redirect
from django.db.models import F,Q
from board.models import Board
from django.conf import settings
from django.conf.urls.static import static
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from screen.models import Screen1
# Create your views here.

def map(request):
    return render(request,'map.html')











# 차트그래프
def chart(request):
    # qs = Screen1.objects.filter(Q(csales__gte=1000000)|Q(csales__gte=1000000))
    qs = Screen1.objects.filter(Q(csales__gte=1000000)&Q(sales__gte=10000)).order_by('-revenue')
    # qs = Screen1.objects.all().order_by('-revenue')
    for s in qs:
        print(s)
    print('검색개수',qs.count())


    return render(request,'screen/chart.html')

# 차트 데이터
# ajax 통신
def chart_data(request):
    search_word = request.POST.get('search_word','')
    qs = Screen1.objects.filter(Q(crevenue__gte=1160000000)|Q(title__contains='가')).values()[:6]
    r_qs = list(qs)
    context = {'list':r_qs}
    return JsonResponse(context)
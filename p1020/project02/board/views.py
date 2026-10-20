from django.shortcuts import render,redirect
from board.models import Board
from django.db.models import F,Q
from django.conf import settings
from django.conf.urls.static import static
from member.models import Member
import os
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# 차트 그래프
def chart(request):
    # id_list = ['aaa','bbb','ccc','ddd','eee','fff']
    # qs = Board.objects.all().order_by('bno')[:6]
    # qs_value = list(qs.values())
    # id_list = [1,2,3,4,5,6]
    # bhit_list = [19,20,21,26,40,70]
    # print(qs_value)
    # context ={'id_list':id_list,'bhit_list':bhit_list}
    return render(request, 'chart.html')


# ajax 페이지
def chart_data(request):
    id_list = ['aaa','bbb','ccc','ddd','eee','fff']
    bhit_list = [19,20,21,26,40,70]
    data = {'id_list':id_list,'bhit_list':bhit_list}
    return JsonResponse(data)
    



# 게시글 삭제
def bdelete(request,bno):
    Board.objects.get(bno=bno).delete()
    context = {'temp':0, 'bno':bno}
    return render(request, 'bwrite.html', context)






# 게시글 수정
# GET-수정페이지, POST- 수정저장
def bupdate(request,bno):
    if request.method=='GET':
        qs = Board.objects.get(bno=bno)
        context = {'board':qs}
        return render(request, 'bupdate.html',context)
    elif request.method =='POST':
        btitle = request.POST.get('btitle')
        bcontent = request.POST.get('bcontent')
        bfile = request.POST.get('bfile')
        qs = Board.objects.get(bno=bno)
        qs.btitle = btitle
        qs.bcontent = bcontent
        if bfile:
            qs.bfile = bfile
        qs.save()
        

        context = {'temp':2,'bno':bno}
        return render(request, 'bwrite.html',context)




def bview(request, bno):
    # board 1개검색
    # qs = Board.objects.get(bno=bno)
    # qs.bhit = qs.bhit+1
    # qs.save()

    # 데이터 1개 가져오기
    qs= Board.objects.filter(bno=bno) # .first()면 qs 없으면 qs[0]
    qs.update(bhit = F('bhit')+1) # F: qs에 있는 컬럼값을 가져올때 사용


    context = {'board':qs[0]}
    return render(request, 'bview.html', context)










# 게시글 리스트
def blist(request):
    if request.method =='GET':
        qs =Board.objects.all().order_by('-bgroup','bstep')
        pg = Paginator(qs,7)
        page=int(request.GET.get('page',1))
        qs = pg.get_page(page)
        context = {'list':qs,'page':page}
        return render(request, 'blist.html',context)
    elif request.method =='POST':
        qs =Board.objects.all().order_by('-bgroup','bstep')
        # 검색부분-----------------------------------------
        category = request.POST.get('category')
        search_word = request.POST.get('search_word')
        # # category - btitle
        # if category == 'btitle':
        #     qs = Board.objects.filter(btitle__contains=search_word).order_by('-bgroup','bstep')
        # elif category == 'bcontent':
        #     qs = Board.objects.filter(bcontent__contains=search_word).order_by('-bgroup','bstep')
        # else:
        #     qs = Board.objects.filter(Q(btitle__contains=search_word)|Q(bcontent__contains=search_word)).order_by('-bgroup','bstep')
            
        qs = Board.objects.filter( Q(id__icontains='s')|Q(bhit__gte=50) ).order_by('-bgroup','bstep')
        print('개수 : ',qs.count())

        # 페이징처리----------------------------------------
        pg = Paginator(qs,7)
        page=int(request.GET.get('page',1))
        qs = pg.get_page(page)
        context = {'list':qs,'page':page}
        return render(request, 'blist.html',context)





# 게시글 등록
# GET:페이지 열기,  POST:저장
def bwrite(request):
    if request.method == 'GET':
        return render(request, 'bwrite.html')
    elif request.method == 'POST':
        btitle = request.POST.get('btitle')
        id = request.POST.get('id')
        bcontent = request.POST.get('bcontent')
        bfile = request.FILES.get('bfile')
        print(f'데이터 확인: {btitle},{id},{bcontent},{bfile}')
        #create 방식
        qs = Board.objects.create(btitle=btitle,id=id,bcontent=bcontent,bfile=bfile)
        
        # save() 방식
        # Board(btitle=btitle,id=id,bcontent=bcontent,bfile=bfile).save()
        
        # 답변달기
        qs.bgroup = qs.bno
        qs.save()
        context = {'temp':1}
        return render(request,'bwrite.html',context)
        





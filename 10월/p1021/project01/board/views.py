from django.shortcuts import render,redirect
from django.db.models import F,Q
from board.models import Board
from django.conf import settings
from django.conf.urls.static import static
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# html --> django로 데이터 주는 방법
# 1. form : 회원가입 게시판
# 2. url path : 게시판 bno
# 3. 파라미터 : 하단 넘버링 page/?page=1
# 4. 자바스크립트 (ajax,axis)  :  차트 # 특정 부분만 바꿀때 render 보다 소규모 , render : 다른 페이지에서 사용할때.

# 받는 방법
# 1. context
# 2. 자바스크립트(ajax,axis)
# 3. 파라미터 redirect('/?page=1) // 거의 안씀 그냥 참고만




# 차트 그래프
def chart(request):
    return render(request,'chart.html')

# 차트 데이터
# ajax 통신
def chart_data(request):
    # qs = Board.objects.get(bno=3).values() # 리스트 형식이 아니라 사용 x
    # qs = Board.objects.filter(bno=3).values() # 리스트 형식
    # qs = Board.objects.all().values() # 리스트 형식
    # btitle '사진'글자가 포함되어 있거나 조회수가 70이상인것을 검색
    search = request.POST.get('search',0)
    word = request.POST.get('word',0)
    print('search:',search)
    print('word:',word)
    qs = Board.objects.filter(
    Q(btitle__contains=search) | Q(bhit__gte=int(word))
).values()[:6] # 리스트 형식
    r_qs = list(qs)
    # 객체를 리스트타입으로 변경해서 보내야함.
    context = {'list':r_qs,'data1':[1,2,3,4],'data2':'홍길동'} # 딕셔너리가 json형식
    print(f'{r_qs},{context}')
    return JsonResponse(context)



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
    qs =Board.objects.all().order_by('-bgroup','bstep')
    context = {'list':qs}
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
        





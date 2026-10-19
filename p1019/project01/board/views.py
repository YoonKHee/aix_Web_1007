from django.shortcuts import render,redirect
from board.models import Board
from django.db.models import F,Q




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
        qs.content = bcontent
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
        





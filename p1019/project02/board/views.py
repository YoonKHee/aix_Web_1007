from django.shortcuts import render
from board.models import Board
from django.db.models import F,Q
# Create your views here.
# 게시글 삭제
def bdelete(request,bno):
    Board.objects.get(bno=bno).delete()
    context = {'temp':0,'bno':bno}
    return render(request,'bwrite.html',context)


# 게시글 수정
def bupdate(request, bno):
    if request.method=='GET':
        qs = Board.objects.get(bno=bno)
        context= {'board':qs}
        return render(request,'bupdate.html',context)
    elif request.method =='POST':
        btitle = request.POST.get('btitle')
        bcontent = request.POST.get('bcontent')
        bfile = request.FILES.get('bfile')
        qs = Board.objects.get(bno=bno)
        qs.btitle = btitle
        qs.bcontent = bcontent
        if bfile:
            qs.bfile = bfile
        qs.save()
        context = {'temp':2,'bno':bno}
        return render(request, 'bwrite.html', context)


def bwrite(request):
    if request.method =='GET': 
        return render(request, 'bwrite.html')
    elif request.method =="POST":
        btitle = request.POST.get('btitle')
        id = request.POST.get('id')
        bcontent = request.POST.get('bcontent')
        bfile = request.POST.get('bfile')
        print(f"{bfile}{id}{bcontent}{btitle}")
        qs = Board.objects.create(btitle=btitle,id=id,bcontent=bcontent,bfile=bfile)
        qs.bgroup = qs.bno
        qs.save()
        context = {'temp':1}
        return render(request,'bwrite.html',context)


def blist(request):
    qs = Board.objects.all().order_by('-bgroup','bstep')
    context = {'list':qs}
    return render(request, 'blist.html',context)




def bview(request,bno):
    qs = Board.objects.filter(bno=bno)
    qs.update(bhit = F('bhit')+1)
    context = {'board':qs[0]}
    return render(request, 'bview.html', context)
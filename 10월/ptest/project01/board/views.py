from django.shortcuts import render,redirect
from django.db.models import F,Q
from board.models import Board
from django.conf import settings
from django.conf.urls.static import static
import os
from member.models import Member
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# Create your views here.
def blist(request):
    qs = Board.objects.all().order_by('-bgroup','bstep')
    context = {'list':qs}
    return render(request,'blist.html',context)

def bwrite(request):
    if request.method =='GET':
        return render(request,'bwrite.html')
    elif request.method =='POST':
        btitle = request.POST.get('btitle')
        id = request.session['s_id']
        bcontent = request.POST.get('bcontent')
        bfile = request.POST.get('bfile')
        print(f'데이터확인 : {btitle},{id},{bcontent},{bfile}')
        member = Member.objects.get(id=id)
        qs = Board.objects.create(btitle=btitle,bcontent=bcontent,bfile=bfile,member=member)
        context = {'temp':1}
        return render(request,'bwrite.html',context)


def bview(request,bno):
    qs = Board.objects.filter(bno=bno).first()
    qs.bhit = qs.bhit+1
    qs.save()
    context = {'board':qs}
    return render(request,'bview.html',context)


def bupdate(request,bno):
    if request.method =='GET':
        qs = Board.objects.get(bno=bno)
        context = {'board':qs}
        return render(request, 'bupdate.html',context)
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
        return redirect('board:bview', bno=bno)








def bdelete(request,bno):
    qs = Board.objects.get(bno=bno)
    qs.delete()
    context={'temp':0,'bno':bno}
    return render(request, 'blist.html',context)




def breply(request,bno):    
    if request.method=='GET':
        qs = Board.objects.get(bno=bno)
        context = {'board':qs}
        return render(request,'breply.html',context)
    elif request.method =='POST':
        bgroup = request.POST.get('bgroup')
        bstep = int(request.POST.get('bstep'))
        bindent = int(request.POST.get('bindent'))
        btitle = request.POST.get('bcontent')
        bfile = request.FILES.get('bfile')
        id = request.session['s_id']
        member = Member.objects.get(id=id)

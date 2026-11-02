from django.shortcuts import render
from customer.models import Board

def cview(request,bno):
    qs = Board.objects.filter(bno=bno)[0]
    print('확인:',qs)
    context = {'board':qs} # 1개
    return render(request,'cview.html',context)




def clist(request):
    qs = Board.objects.all().order_by('-bgroup','bstep')
    print('확인:',qs)
    context = {'list':qs} # list는 여러개
    return render(request,'clist.html',context)

from django.shortcuts import render
from board.models import Board
from django.db.models import F,Q
# Create your views here.
def bwrite(request):
    return render(request, 'bwrite.html')



def blist(request):
    qs = Board.objects.all().order_by('-bgroup','bstep')
    context = {'list':qs}
    return render(request, 'blist.html',context)




def bview(request,bno):
    qs = Board.objects.filter(bno=bno)
    qs.update(bhit = F('bhit')+1)

    context = {'board':qs[0]}

    return render(request, 'bview.html', context)
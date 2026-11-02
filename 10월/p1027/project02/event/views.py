from django.shortcuts import render
from event.models import Event
from member.models import Member
from comment.models import Comment

# 이벤트리스트 
def event(request):
    qs = Event.objects.all().order_by('-eno')
    context = {'list':qs}
    return render(request, 'event.html',context)

def eview(request,eno):
    qs = Event.objects.filter(eno=eno)[0]
    qs2 = Comment.objects.filter(event=qs).order_by('-cno')
    context = {'event':qs,'comment':qs2}
    print('확인 : ',eno,qs2)
    return render(request, 'eview.html',context)

from django.shortcuts import render
from member.models import Member
# Create your views here.

def logout(request):
    request.session.clear()
    context = {'temp':2}
    return render(request,'login.html',context)


# get,post
def login(request):
    if request.method == 'GET':
        return render(request, 'login.html')
    elif request.method == 'POST':
        id = request.POST.get('id')
        pw = request.POST.get('pw')
        qs = Member.objects.filter(id=id,pw=pw).first()
        if qs:
            request.session['s_id'] = id
            request.session['s_nickname'] = qs.nickname
            context= {'temp':1}
        else:
            context = {'temp':0}

        print(f'{id}{pw}{context}{qs}')
        return render(request, 'login.html',context)
        
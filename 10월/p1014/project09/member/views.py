from django.shortcuts import render
from member.models import Member
# Create your views here.

def logout(request):
    request.session.clear()
    context = {'temp':2}
    return render(request, 'login.html', context)

def login(request):
    if request.method=='GET':
        return render(request, 'login.html')
    elif request.method == 'POST':
        id =request.POST.get('id')
        pw =request.POST.get('pw')
        print(f'{id},{pw}')
        try:
            qs = Member.objects.get(id=id,pw=pw)
            request.session['s_id'] = qs.id
            request.session['s_nickname'] = qs.nickname
            print('로그인성공')
            context = {'temp':1}
            return render(request, 'login.html',context)
        except Member.DoesNotExist:
            print('로그인 실패')
            context = {'temp':0}
            return render(request, 'login.html',context)

from django.shortcuts import render
from member.models import(Member)

# Create your views here.
# 로그인 페이지 열기:GET , 로그인 확인:POST
def logout(request):
    context = {'temp':2}
    request.session.clear()
    return render(request, 'login.html', context)




def login(request):
    if request.method =="GET":
        return render(request, 'login.html')


    
    elif request.method =="POST":
        id = request.POST.get('id')
        pw = request.POST.get('pw')
        rememberId = request.POST.get('rememberId')

        qs = Member.objects.filter(id=id,pw=pw).first()

        if qs:
            context = {'temp':1}
            request.session['s_id'] = id
            request.session['s_nickname'] = qs.nickname
        else:
            context = {'temp':0}

        print(f'{id}{pw}{rememberId}{context}')

        response
        response = render(request, 'login.html', context)
        return response
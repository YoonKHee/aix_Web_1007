from django.shortcuts import render
from member.models import Member

# Create your views here.
def logout(request):
    request.session.clear()# 세션 모두 삭제
    # del request.session.['s_nickname'] # 세션 1개만 삭제
    context ={'temp':2}
    return render(request,'login.html',context)

def login(request):
    if request.method =='GET':
        context = {}
        if request.COOKIES.get('cookie_id'): # 있으면 넣고 없으면 None이라 그냥 넘어감
            context = {'cookie_id':request.COOKIES.get('cookie_id')} # idsave = 1
        return render(request, 'login.html',context)
    elif request.method =='POST':
        id = request.POST.get('id')
        pw = request.POST.get('pw')
        idsave = request.POST.get('idsave','') #  idsave 값이 있으면 들고오고 없을땐 빈공백처리
        # 회원 확인2
        qs = Member.objects.filter(id=id,pw=pw).first() # qs, None
        if qs:
            request.session['s_id'] = qs.id
            request.session['s_nickname'] = qs.nickname
            context = {'temp':1}
        else:
            context = {'temp':0}

        print(f'로그인정보 : {id},{pw},idsave:{idsave} / 회원확인 : {context}')
        # 쿠키사용을 위해 분리
        response = render(request, 'login.html', context) 
        if idsave != '':
            response.set_cookie('cookie_id',id,max_age=60*60*24*365)
            context
        else:
            response.delete_cookie('cookie_id')
        return response

        

        # 회원 확인 1
        # try:
        #     qs = Member.objects.get(id=id,pw=pw) # db에 id,pw로 회원 확인
        #     request.session['s_id'] = qs.id
        #     request.session['s_nickname'] = qs.nickname
        #     context = {'temp':1}
        #     context = {'temp':0}
        # except Member.DoesNotExist: #DoexNotExist :없을때
        # print(f'로그인정보 : {id},{pw} / 회원확인 : {context}')
        # return render(request, 'login.html', context) 
    # python -> html :context
    # htiml -> python : form,url path,파라미터, 자바스크립트(ajax)


def step01(request):
    return render(request, 'step01.html')
def step02(request):
    return render(request, 'step02.html')
def step03(request):
    return render(request, 'step03.html')
def step04(request):
    return render(request, 'step04.html')
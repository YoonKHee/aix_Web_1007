from django.shortcuts import render,redirect
from member.models import Member

# 세션 모두 삭제
def logout(request):
    request.session.clear()
    context = {'temp':2}
    return render(request, 'login.html',context)



# 로그인페이지 - session : 서버에 저장 # 민감한정보 ,쿠키보다 보안에 우수 단점 사용자가 많아질 경우 서버 메모리를 많이 차지함
# cookie :로컬컴퓨터에 저장(내 컴퓨터에 저장) # 안민감한 정보. 보안이 다소 안좋음 내컴퓨터 해킹 당하면 다 털림
def login(request):
    if request.method == 'GET':
        return render(request,'login.html')
    elif request.method == 'POST':
        id = request.POST.get('id')
        pw = request.POST.get('pw')
        print(f'로그인정보:{id},{pw}')
        try: 
            qs = Member.objects.get(id=id,pw=pw) # id='aaa' and pw = '1111' / 없으면:None
            request.session['session_id'] = qs.id
            request.session['session_nickname'] = qs.nickname
            print('로그인이 되었습니다.') # 세션모두 저장
            context = {'temp':1}
            return render(request,'login.html',context)
        except Member.DoesNotExist: 
            print('아이디 또는 패스워드가 일치하지 않습니다. 다시 로그인하세요.')
            context = {'temp':0}
            return render(request,'login.html',context)
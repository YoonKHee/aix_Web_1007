from django.shortcuts import render, redirect
from member.models import Member
# -------------------------------------------------------------------------------
# 회원 수정페이지
def mupdate(request, id):
    if request.method =='GET':
        print(f'확인 데이터: {id}')
        qs = Member.objects.get(id=id)
        tel = qs.tel.split('-')
        context = {'member':qs,'tel':tel}
        return render(request,'mupdate.html',context)
    elif request.method =='POST':
        # id = request.session.s_id
        pw = request.POST.get('pw')
        name = request.POST.get('name')
        nickname = request.POST.get('nickname')
        tel1 = request.POST.get('tel1')
        tel2 = request.POST.get('tel2')
        tel3 = request.POST.get('tel3')
        tel = f'{tel1}-{tel2}-{tel3}'
        gender = request.POST.get('gender')
        hobby = request.POST.getlist('hobby')
        qs = Member.objects.get(id=id)
        
        # id로 검색
        # qs.pw = pw
        # qs.name = name
        # qs.nickname = nickname
        # qs.tel = tel
        # qs.gender =gender
        # qs.hobby =hobby
        
        # qs.save() 
        # 필터를 이용한 불러오기
        Member.objects.filter(id=id).update(
            name=name,nickname=nickname,tel=tel,gender=gender,hobby=hobby
        )
        # db 수정
        # 1번 save
        # Member(id=id,pw=pw,name=name,nickname=nickname,tel=tel,gender=gender,hobby=hobby).save()
        # 2번 create
        # Member.objects.create(id=id,pw=pw,name=name,nickname=nickname,tel=tel,gender=gender,hobby=hobby)
        print(f'{id},{pw},{name},{nickname},{tel},{gender},{hobby}')
        return redirect('/')
# Create your views here.
# -------------------------------------------------------------------------------
# 회원가입페이지 : GET, 회원가입 추가:POST
def mwrite(request):
    if request.method =='GET':
        return render(request,'mwrite.html')
    elif request.method =='POST':
        id = request.POST.get('id')
        pw = request.POST.get('pw')
        name = request.POST.get('name')
        nickname = request.POST.get('nickname')
        tel1 = request.POST.get('tel1')
        tel2 = request.POST.get('tel2')
        tel3 = request.POST.get('tel3')
        tel = f'{tel1}-{tel2}-{tel3}'
        gender = request.POST.get('gender')
        hobby = request.POST.getlist('hobby')

        # db 저장
        # 1번 save
        Member(id=id,pw=pw,name=name,nickname=nickname,tel=tel,gender=gender,hobby=hobby).save()
        # 2번 create
        # Member.objects.create(id=id,pw=pw,name=name,nickname=nickname,tel=tel,gender=gender,hobby=hobby)
        print(f'{id},{pw},{name},{nickname},{tel},{gender},{hobby}')
        return render(request, 'mwrite.html')

# -------------------------------------------------------------------------------
# 로그아웃
def logout(request):
    context = {'temp':2}
    request.session.clear()
    return render(request, 'login.html',context)
# -------------------------------------------------------------------------------

# 로그인

def login(request):
    if request.method =="GET":
        # 쿠키검색
        cook_id = request.COOKIES.get('cook_id','') # 있으면 쿠키id, 없으면 빈 공백
        if cook_id:
            context ={'cook_id':cook_id}
        else:
            context = {}
        return render(request, 'login.html', context)
    
    elif request.method =="POST":
        id = request.POST.get('id')
        pw = request.POST.get('pw')
        rememberId = request.POST.get('rememberId')
        # DB 확인
        qs = Member.objects.filter(id=id,pw=pw).first()
        if qs:# 로그인 성공
            context = {'temp':1}
            # session 로그인정보 추가
            request.session['s_id'] = qs.id
            request.session['s_nickname'] = qs.nickname
        else: # 로그인 실패
            context = {'temp':0}


        print(f'{id}{pw}{rememberId}{context}')
        response = render(request, 'login.html', context)
        #쿠키 적용
        if rememberId:
            response.set_cookie('cook_id',id,max_age=60*60*24*365)
        else:
            response.delete_cookie('cook_id')
        return response
# -------------------------------------------------------------------------------
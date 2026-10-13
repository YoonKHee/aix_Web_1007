from django.shortcuts import render,redirect
from students.models import Students

# 학생성적삭제
def sdelete(request, no):
    qs = Students.objects.get(no=no).delete()
    return redirect('/students/slist/')





# 학생정보수정
def supdate(request,no):
    if request.method == 'GET':
        qs = Students.objects.get(no=no)
        context = {'stu':qs}
        return render(request, 'supdate.html',context)
    elif request.method == 'POST':
        #수정부분
        qs = Students.objects.get(no=no)
        # 수정을 하면 됨.
        name = request.POST.get('name')
        major = request.POST.get('major')
        grade = request.POST.get('grade')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        hobby = request.POST.getlist('hobby')
        # 수정된 데이터반영
        qs.name=name
        qs.major=major
        qs.grade=grade
        qs.age=age
        qs.gender=gender
        qs.hobby=hobby
        qs.save()
        return redirect('students:slist') # app_name,name방식

# 학생정보 상세보기 - 1개
def sview(request,no):
    qs = Students.objects.get(no=no)
    context = {'stu':qs}
    return render(request,'sview.html',context)


# 학생정보 입력페이지 - 여러개
def swrite(request):
    if request.method=='GET':
        return render(request,'swrite.html')
    elif request.method=='POST': #1. form값 전달
        name = request.POST.get('name')
        major = request.POST.get('major')
        grade = request.POST.get('grade')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        hobby = request.POST.getlist('hobby') # checkbox 값이 여러개라 리스트로 받아야함
        # 저장방법
        # save()저장
        Students(name=name,major=major,grade=grade,age=age,gender=gender,hobby=hobby).save()
        # create()저장
        # Students.objects.create(name=name,major=major,grade=grade,age=age,gender=gender,hobby=hobby)
        print(name,major,grade,age,gender,hobby)
        return redirect('/')

    # 학생정보리스트
def slist(request):
    # 딕셔너리 형태로 데이터를 전달함.
    qs = Students.objects.all().order_by('-no') # 전체가져오기 , 정렬(-역순정렬)
    # qs = Students.objects.get(name='홍길동') # 1개 가져오기
    #__contains:포함, __endswith:끝에 포함
    # qs = Students.objects.filter(name__contains='s') # s가 포함되어있는 학생
    # qs = Students.objects.filter(name__endswith='s') # s가 끝에 포함되어있는 학생
    # gt:크다, gte:크거나같다, lt:작다, lte:작거나같다
    # qs = Students.objects.filter(grade__gte='3') # 3학년이상
    # qs = Students.objects.filter(grade__gt='3') # 3학년초과
    context = {'list':qs}
    return render(request,'slist.html',context)





#---------------------------------------------------------------
# html -> 디장고 데이터 전달방법
# 1. form
# 2. url path
# 3. 파라미터
# 4. 자바스크립트(ajax)

# GPU 병렬방식 : 동시에 실행함 = 비동기식 : ajax
# CPU 직렬방식 : 순차적으로 실행함 = 동기식

# 학생정보입력 - url path : 매개변수로 값 전달
def swrite2(request,name):
    print(f'url path 값전달 :{name}')
    return redirect("/")

# 학생정보입력 - 파라미터 : 매개변수로 값 전달
def swrite3(request):
    name = request.GET.get('name')
    age = request.GET.get('age')
    print(f'파라미터:{name},{age}')
    return redirect("/")
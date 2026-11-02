from django.shortcuts import render,redirect
from students.models import Students

def sdelete(request,name):
    qs = Students.objects.get(name=name).delete()
    return redirect('/students/slist/')



# 학생정보수정
def supdate(request,name):
    if request.method == 'GET':
        print(f'name 수정페이지 : {name}')
        qs = Students.objects.get(name=name) #1개의 정보전송
        context = {'stu':qs}
        return render(request, 'supdate.html',context)
    elif request.method == 'POST':
        print(f'name 수정완료 : {name}')
        qs = Students.objects.get(name=name) # 이전정보 검색
        if qs:
            name = request.POST.get('name')
            major = request.POST.get('major')
            age = request.POST.get('age')
            grade = request.POST.get('grade')
            gender = request.POST.get('gender')
            qs.name= name
            qs.major = major
            qs.age = age
            qs.grade = grade
            qs.gender = gender
            qs.save()
        return redirect('/students/slist/')

# Create your views here.




# 학생정보리스트
def slist(request):
    # db에서 전체 리스트 가져오기
    qs = Students.objects.all() # 전체 가져오기

    # qs = Students.objects.get(name='홍길동') # 1개 가져오기
    # qs = Students.objects.filter(name__contains='홍') # 검색해서 여러개 가져오기
    context = {'list':qs}
    return render(request, 'slist.html',context)



# 학생상세보기
def sview(request,name):
    print(f'name 데이터 :{name}')
    qs = Students.objects.get(name=name) # 1개의 정보전송
    context = {'stu':qs}
    return render(request, 'sview.html',context)







# 학생정보 입력페이지, 저장
def swrite(request):
    if request.method== 'GET':
        return render(request, 'swrite.html')
    elif request.method == "POST":
        name = request.POST.get('name') # get은 데이터가 없어도 에러가 나지 않음.
        major = request.POST['major'] # 데이터가 없을때 에러가 남.
        age = request.POST['age']
        grade = request.POST['grade']
        gender = request.POST['gender'] 
        # 1. save() 1번째 저장방법
        qs = Students(name=name,major=major,age=age,grade=grade,gender=gender).save()
        # qs.save() 위처럼 뒤에 붙여서 한번에 써도됨.
        # 2. create() 2번째 저장방법      
        # Students.objects.create(name=name,major=major,age=age,grade=grade,gender=gender)
        print(f'확인:{name},{major},{age},{grade},{gender}')

        return redirect('/students/slist')



# html에서 파이썬 데이터 전달방법
# 1. form # 가장 많이 사용
# 2. 파라미터
# 3. 자바스크립트
# 받는방법은
# 1. context # 1개뿐
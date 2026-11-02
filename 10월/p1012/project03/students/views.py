from django.shortcuts import render,redirect
from students.models import Students

# 학생정보삭제
def sdelete(request,name):
    qs = Students.objects.get(name=name).delete()
    return redirect('/students/slist/')

# 학생정보수정
def supdate(request,name):
    if request.method=='GET':
        print(f'name 수정페이지 : {name}')
        qs = Students.objects.get(name=name)
        context = {'stu':qs}
        return render(request,'supdate.html',context)
    elif request.method=='POST':
        print(f'name 수정완료:{name}')
        qs = Students.objects.get(name=name)
        if qs:
            name = request.POST.get('name')
            major = request.POST.get('major')
            age = request.POST.get('age')
            grade = request.POST.get('grade')
            gender = request.POST.get('gender')
            qs.name = name
            qs.major = major
            qs.age = age
            qs.grade = grade
            qs.gender = gender
            qs.save()
        return redirect('/students/silst/')
    
# 상세학생보기
def sview(request,name):
    print(f'name 데이터 : {name}')
    qs = Students.objects.get(name=name)
    context = {'stu':qs}
    return render(request,'sview.html',context)

#학생정보리스트
def slist(request):
    qs = Students.objects.all()
    context = {'list':qs}
    return render(request,'slist.html',context)

# 학생정보 입력페이지, 저장
def swrite(request):
    if request.method == "GET":
        return render(request,'swrite.html')
    elif request.method =="POST":
        name = request.POST.get('name')
        major = request.POST.get('major')
        grade = request.POST.get('grade')
        age = request.POST.get('age')
        gender = request.POST.get('gender')

        qs =Students(name=name, major=major, grade=grade, age=age, gender=gender).save()
        print(f"확인:{name}{age}")

        return redirect('/students/slist/')
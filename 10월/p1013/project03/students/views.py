from django.shortcuts import render, redirect
from students.models import Students


def sdelete(request,no):
    qs = Students.objects.get(no=no).delete()
    context = {'stu':qs}
    return redirect("students:slist")


# 학생정보수정
def supdate(request,no):
    if request.method =="GET":
        qs = Students.objects.get(no=no)
        context = {'stu':qs}
        return render(request,'supdate.html',context)
    elif request.method =="POST":
        qs = Students.objects.get(no=no)
        name = request.POST.get('name')
        major = request.POST.get('major')
        grade = request.POST.get('grade')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        hobby = request.POST.getlist('hobby')
        qs.name=name
        qs.major=major
        qs.grade=grade
        qs.age=age
        qs.gender=gender
        qs.hobby=hobby
        qs.save()
        return redirect('students:slist')

# 학생상세정보
def sview(request,no):
    qs = Students.objects.get(no=no)
    context = {'stu':qs}
    return render(request,'sview.html',context)

# 학생성적입력
def swrite(request):
    if request.method=='GET':
        return render(request, 'swrite.html')
    elif request.method == "POST":
        name = request.POST.get('name')
        major = request.POST.get('major')
        grade = request.POST.get('grade')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        hobby = request.POST.getlist('hobby')

        Students(name=name,major=major,grade=grade,age=age,gender=gender,hobby=hobby).save()
        print(name,major,grade,age,gender,hobby)
        return redirect('/')



# 학생리스트
def slist(request):
    qs = Students.objects.all().order_by('-no')
    context = {'list':qs}
    return render(request, 'slist.html', context)
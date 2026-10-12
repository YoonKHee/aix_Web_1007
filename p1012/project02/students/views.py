from django.shortcuts import render, redirect
from students.models import Students

# Create your views here.
# 학생정보리스트
def slist(request):
    qs = Students.objects.all()
    context = {list:qs}
    return render(request,'slist.html',context)




def swrite(request):
    if request.method=='GET':
        return render(request,'swrite.html')
    elif request.method=='POST':
        name = request.POST.get('name')
        major = request.POST.get('major')
        age = request.POST.get('age')
        grade = request.POST.get('grade')
        gender = request.POST.get('gender')
        qs = Students(name=name,major=major,age=age,grade=grade,gender=gender).save()
        print(f'{name},{major},{age},{grade},{gender}')
        return redirect('/students/slist/')
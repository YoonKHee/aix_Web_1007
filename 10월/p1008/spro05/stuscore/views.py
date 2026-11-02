from django.shortcuts import render,redirect
from stuscore.models import Stuscore
# Create your views here.
# def score_write(request):
#     return render(request, 'score_write.html')

def score_write(request):
    if request.method == 'GET':
        print('페이지가 로딩되었습니다.')
        return render(request, 'score_write.html')

    elif request.method == 'POST':
        no = request.POST.get('no')
        name = request.POST.get('name')
        school = request.POST.get('school')
        grade = request.POST.get('grade')
        age = request.POST.get('age')
        stature = request.POST.get('stature')
        kor = request.POST.get('kor')
        eng = request.POST.get('eng')
        math = request.POST.get('math')
        sw = request.POST.get('sw')

        qs = Stuscore(
            no=no,
            name=name,
            school=school,
            grade=grade,
            age=int(age),
            stature=float(stature),
            kor=int(kor),
            eng=int(eng),
            math=int(math),
            sw=sw
        )

        qs.save()

        print(no, name, school, grade, age, stature, kor, eng, math, sw)

        return redirect('/')
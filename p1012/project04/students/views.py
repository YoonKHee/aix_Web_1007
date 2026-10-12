from django.shortcuts import render
from students.models import Students


# Create your views here.
def slist(request):
    qs = Students.objects.all()
    context = {'list':qs}
    return render(request,'slist.html', context)

def swrite(request):
    return render(request,'swrite.html')
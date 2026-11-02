from django.shortcuts import render

# Create your views here.
def clist(request):
    return render(request,'clist.html')
from django.shortcuts import render

# Create your views here.
def slist(request):
    return render(request, 'slist.html')
def swrite(request):
    return render(request, 'swrite.html')
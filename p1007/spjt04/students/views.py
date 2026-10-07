from django.shortcuts import render

# Create your views here.
def swrite(request):
    return render(request, 'swrite.html')
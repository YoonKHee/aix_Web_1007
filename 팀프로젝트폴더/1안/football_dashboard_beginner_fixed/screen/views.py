from django.shortcuts import render

def dashboard(request):
    return render(request, 'screen/dashboard.html')

def dashboard2(request):
    return render(request, 'screen/dashboard2.html')

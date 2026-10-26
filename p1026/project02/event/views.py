from django.shortcuts import render

def event(request):
    return render(request, 'event.html')

def eview(request,eno):
    context = {'eno':eno}
    return render(request, 'eview.html', context)
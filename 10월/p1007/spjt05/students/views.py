from django.shortcuts import render
#
# Create your views here.
# 학생성적입력페이지
def swrite(request):
    return render(request,'swrite.html') # render:html을 호출하겠다
#학생성적출력페이지
def slist(request):
    return render(request,'slist.html')
def p_list(request):
    return render(request,'p_list.html')
def index(request):
    return render(request,'index.html')
def p_member(request):
    return render(request,'p_member.html')
def p_stulist(request):
    return render(request,'p_stulist.html')
def p_view(request):
    return render(request,'p_view.html')
def p_write(request):
    return render(request,'p_write.html')

from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST

from .forms import CommentForm, PostForm, SignupForm
from .matchbot import safe_ensure
from .models import Comment, Post, Report

PER_PAGE = 10
REPORT_LIMIT = 3          # 서로 다른 회원 3명이 신고하면 자동 숨김


def member_required(view):
    """로그인 안 했으면 → 안내(알림) 후 로그인 창으로"""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            q = urlencode({'next': request.get_full_path(), 'need': 1})
            return redirect(f'{reverse("board:login")}?{q}')
        return view(request, *args, **kwargs)
    return wrapper


class BoardLogin(LoginView):
    template_name = 'board/login.html'
    redirect_authenticated_user = True
    next_page = reverse_lazy('board:list')


def signup(request):
    if request.user.is_authenticated:
        return redirect('board:list')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        user = authenticate(request, username=user.get_username(), password=form.cleaned_data['password1'])
        if user:
            login(request, user)
        messages.success(request, '가입이 완료되었습니다. 환영합니다!')
        return redirect('board:list')
    return render(request, 'board/signup.html', {'form': form})


@member_required
def post_list(request):
    safe_ensure()                                      # 곧 열릴 경기가 있으면 "누가 이길까요?" 글을 자동으로 올림
    qs = (Post.objects.filter(status=Post.OK).select_related('author__profile')
          .annotate(n_comments=Count('comments', filter=Q(comments__status=Comment.OK))))
    q = request.GET.get('q', '').strip()
    by = request.GET.get('by', 'all')
    if q:
        if by == 'title':
            qs = qs.filter(title__icontains=q)
        elif by == 'author':
            qs = qs.filter(author__profile__nickname__icontains=q)
        else:
            qs = qs.filter(Q(title__icontains=q) | Q(content__icontains=q))
    paginator = Paginator(qs, PER_PAGE)
    page = paginator.get_page(request.GET.get('page'))
    for i, p in enumerate(page):                       # 목록 번호 (최신 글이 가장 큰 번호)
        p.no = paginator.count - (page.number - 1) * PER_PAGE - i
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'board/list.html', {'page': page, 'q': q, 'by': by, 'qs': params.urlencode(),
                                               'total': paginator.count})


@member_required
def post_detail(request, pk):
    post = get_object_or_404(Post.objects.select_related('author__profile'), pk=pk)
    if post.status == Post.DELETED and not request.user.is_staff:
        return render(request, 'board/gone.html', {'post': post}, status=410)
    viewed = request.session.get('board_viewed', [])
    if pk not in viewed:                               # 새로고침으로 조회수 올리기 방지
        Post.objects.filter(pk=pk).update(views=F('views') + 1)
        post.views += 1
        request.session['board_viewed'] = (viewed + [pk])[-200:]
    comments = post.comments.filter(status=Comment.OK).select_related('author__profile')
    return render(request, 'board/detail.html', {'post': post, 'comments': comments, 'form': CommentForm(),
                                                 'is_owner': post.author_id == request.user.id})


@member_required
def post_create(request):
    form = PostForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        messages.success(request, '글을 등록했습니다.')
        return redirect('board:detail', pk=post.pk)
    return render(request, 'board/form.html', {'form': form, 'mode': '글쓰기'})


@member_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk, status=Post.OK)
    if post.author_id != request.user.id:
        messages.error(request, '본인이 쓴 글만 수정할 수 있습니다.')
        return redirect('board:detail', pk=pk)
    form = PostForm(request.POST or None, instance=post)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, '글을 수정했습니다.')
        return redirect('board:detail', pk=pk)
    return render(request, 'board/form.html', {'form': form, 'mode': '글 수정', 'post': post})


@member_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if post.author_id == request.user.id or request.user.is_staff:
        post.delete()
        messages.success(request, '글을 삭제했습니다.')
        return redirect('board:list')
    messages.error(request, '삭제 권한이 없습니다.')
    return redirect('board:detail', pk=pk)


@member_required
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk, status=Post.OK)
    form = CommentForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.post, c.author = post, request.user
        c.save()
        messages.success(request, '댓글을 등록했습니다.')
    else:
        for errs in form.errors.values():
            for e in errs:
                messages.error(request, e)
    return redirect(f'{reverse("board:detail", args=[pk])}#comments')


@member_required
@require_POST
def comment_delete(request, pk):
    c = get_object_or_404(Comment, pk=pk)
    if c.author_id == request.user.id or request.user.is_staff:
        c.delete()
        messages.success(request, '댓글을 삭제했습니다.')
    else:
        messages.error(request, '삭제 권한이 없습니다.')
    return redirect(f'{reverse("board:detail", args=[c.post_id])}#comments')


def _report(request, obj, kw, back):
    if obj.author_id == request.user.id:
        messages.error(request, '본인 글은 신고할 수 없습니다.')
    elif Report.objects.filter(user=request.user, **kw).exists():
        messages.info(request, '이미 신고한 글입니다.')
    else:
        Report.objects.create(user=request.user, reason=request.POST.get('reason', '')[:100], **kw)
        n = Report.objects.filter(**kw).values('user').distinct().count()
        if n >= REPORT_LIMIT and obj.status == obj.OK:
            obj.soft_delete(f'신고 {n}건 누적')
            messages.success(request, '신고가 접수되어 해당 내용이 숨김 처리되었습니다.')
        else:
            messages.success(request, '신고가 접수되었습니다.')
    return redirect(back)


@member_required
@require_POST
def post_report(request, pk):
    post = get_object_or_404(Post, pk=pk, status=Post.OK)
    return _report(request, post, {'post': post}, reverse('board:detail', args=[pk]))


@member_required
@require_POST
def comment_report(request, pk):
    c = get_object_or_404(Comment, pk=pk, status=Comment.OK)
    return _report(request, c, {'comment': c}, reverse('board:detail', args=[c.post_id]) + '#comments')

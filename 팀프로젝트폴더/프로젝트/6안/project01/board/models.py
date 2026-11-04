from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Profile(models.Model):
    """회원가입 때 받는 별명 (아이디·비밀번호는 Django 기본 User 사용)"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    nickname = models.CharField('별명', max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nickname


class _Moderated(models.Model):
    OK, DELETED = 'ok', 'deleted'
    STATUS = [(OK, '정상'), (DELETED, '삭제됨 (규정 위반)')]
    status = models.CharField('상태', max_length=10, choices=STATUS, default=OK, db_index=True)
    deleted_reason = models.CharField('삭제 사유', max_length=200, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self, reason):
        """규정 위반 글/댓글: 지우지 않고 숨김 처리 (관리자가 확인·복구 가능)"""
        self.status = self.DELETED
        self.deleted_reason = reason[:200]
        self.deleted_at = timezone.now()
        self.save(update_fields=['status', 'deleted_reason', 'deleted_at'])

    def restore(self):
        self.status = self.OK
        self.deleted_reason = ''
        self.deleted_at = None
        self.save(update_fields=['status', 'deleted_reason', 'deleted_at'])


class Post(_Moderated):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_posts')
    title = models.CharField('제목', max_length=100)
    content = models.TextField('내용')
    views = models.PositiveIntegerField('조회수', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title


class Comment(_Moderated):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_comments')
    content = models.CharField('댓글', max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.content[:30]


class Report(models.Model):
    """신고. 서로 다른 회원 N명이 신고하면 자동 숨김 (views.REPORT_LIMIT)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_reports')
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BannedWord(models.Model):
    """관리자가 추가하는 금칙어 / 허용어(오탐 방지). 기본 금칙어는 filters.py 에 들어 있음"""
    word = models.CharField('단어', max_length=50, unique=True)
    allow = models.BooleanField('허용어(체크하면 이 단어는 검사에서 제외)', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return ('[허용] ' if self.allow else '') + self.word


class Match(models.Model):
    """예정된 경기. 경기 하루 이틀 전에 AI 해설위원이 "누가 이길까요?" 글을 자동으로 올림"""
    home = models.ForeignKey('team.Team', on_delete=models.CASCADE, related_name='board_home_matches', verbose_name='홈')
    away = models.ForeignKey('team.Team', on_delete=models.CASCADE, related_name='board_away_matches', verbose_name='원정')
    kickoff = models.DateTimeField('경기 시각')
    post = models.OneToOneField(Post, null=True, blank=True, on_delete=models.SET_NULL, related_name='match',
                                verbose_name='자동 작성된 글')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kickoff']

    def __str__(self):
        return f'{self.kickoff:%m/%d %H:%M} {self.home} vs {self.away}'

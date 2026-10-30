from django.contrib import admin, messages

from .filters import scan_all
from .models import BannedWord, Comment, Match, Post, Profile, Report


@admin.action(description='선택한 글/댓글 숨김 처리')
def hide(modeladmin, request, queryset):
    for o in queryset:
        o.soft_delete(f'관리자 삭제 ({request.user.get_username()})')


@admin.action(description='선택한 글/댓글 복구')
def restore(modeladmin, request, queryset):
    for o in queryset:
        o.restore()


@admin.action(description='금칙어 재검사 (전체 글·댓글)')
def rescan(modeladmin, request, queryset):
    p, c = scan_all()
    messages.info(request, f'검사 완료: 글 {p}개, 댓글 {c}개를 숨김 처리했습니다.')


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'status', 'deleted_reason', 'views', 'created_at')
    list_filter = ('status',)
    search_fields = ('title', 'content', 'author__username')
    actions = [hide, restore, rescan]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'content', 'author', 'post', 'status', 'deleted_reason', 'created_at')
    list_filter = ('status',)
    search_fields = ('content', 'author__username')
    actions = [hide, restore, rescan]


@admin.register(BannedWord)
class BannedWordAdmin(admin.ModelAdmin):
    list_display = ('word', 'allow', 'created_at')
    list_filter = ('allow',)


admin.site.register(Profile)
admin.site.register(Report)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('kickoff', 'home', 'away', 'post')
    list_filter = ('kickoff',)
    date_hierarchy = 'kickoff'

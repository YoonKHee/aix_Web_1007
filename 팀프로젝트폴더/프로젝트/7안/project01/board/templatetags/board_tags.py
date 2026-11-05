"""메인 화면에 붙일 때 쓰는 태그.
    {% load board_tags %}
    {% latest_posts 5 %}
"""
from django import template

from board.models import Post

register = template.Library()


@register.filter
def nick(user):
    try:
        return user.profile.nickname
    except Exception:
        return user.get_username()


@register.filter
def who(user):
    """화면에 보이는 작성자 표기: 별명(abc****)  — 아이디는 앞 3자리만, 나머지는 *"""
    from board.matchbot import BOT_USERNAME
    u = user.get_username()
    try:
        nickname = user.profile.nickname
    except Exception:
        nickname = ''
    if u == BOT_USERNAME:
        return f'🤖 {nickname or "AI 해설위원"}'
    masked = u[:3] + '*' * max(len(u) - 3, 0)
    return f'{nickname}({masked})' if nickname else masked


@register.inclusion_tag('board/_latest.html')
def latest_posts(count=5):
    posts = Post.objects.filter(status=Post.OK).select_related('author__profile')[:count]
    return {'posts': posts}

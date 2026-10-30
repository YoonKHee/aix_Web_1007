"""경기 예측 글 자동 작성 (AI 해설위원).
- 경기(Match)가 등록돼 있고 시작 N일 이내면, 아직 글이 없는 경기에 "누가 이길까요?" 글을 올립니다.
- 게시판 목록을 열 때마다 자동으로 확인하므로 별도 스케줄러 없이 동작합니다.
- 글 내용은 DB의 올 시즌 기록(득점·도움 1위)을 넣어 만든 정해진 양식이며, 외부 AI 서비스는 호출하지 않습니다.
"""
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Match, Post, Profile

log = logging.getLogger(__name__)
BOT_USERNAME = 'ai_bot'
BOT_NICK = 'AI 해설위원'
WEEK = '월화수목금토일'
SEASON = 2026


def get_bot():
    User = get_user_model()
    user, created = User.objects.get_or_create(username=BOT_USERNAME)
    if created:
        user.set_unusable_password()                  # 로그인 불가 계정
        user.save()
    Profile.objects.get_or_create(user=user, defaults={'nickname': BOT_NICK})
    return user


def _leader(team, field):
    from player.models import PlayerStats
    row = (PlayerStats.objects.filter(player__team=team, season=SEASON, **{f'{field}__gt': 0})
           .select_related('player').order_by(f'-{field}').first())
    return (row.player.name, getattr(row, field)) if row else None


def _brief(team):
    g, a = _leader(team, 'goals'), _leader(team, 'assists')
    parts = []
    if g:
        parts.append(f'득점 1위 {g[0]}({g[1]}골)')
    if a:
        parts.append(f'도움 1위 {a[0]}({a[1]}도움)')
    return ' · '.join(parts) if parts else '올 시즌 기록 준비 중'


def build_post(m):
    k = timezone.localtime(m.kickoff) if timezone.is_aware(m.kickoff) else m.kickoff
    when = f'{k.month}월 {k.day}일({WEEK[k.weekday()]}) {k:%H:%M}'
    stadium = f' · 🏟 {m.home.stadium}' if m.home.stadium else ''
    title = f'[AI] {m.home.team_name} vs {m.away.team_name} — 누가 이길까요? 스코어를 맞혀보세요'
    content = (
        f'{m.home.team_name} vs {m.away.team_name}\n'
        f'📅 {when}{stadium}\n\n'
        f'안녕하세요, AI 해설위원입니다. 이번 경기, 어느 팀이 이길까요?\n\n'
        f'🏠 {m.home.team_name}: {_brief(m.home)}\n'
        f'✈️ {m.away.team_name}: {_brief(m.away)}\n\n'
        f'👉 댓글로 예상 스코어를 남겨주세요!\n'
        f'예) {m.home.team_name} 2 : 1 {m.away.team_name}'
    )
    return title[:100], content


def ensure_match_threads(days=2):
    """곧 열릴 경기 중 글이 아직 없는 경기에 글을 올림. 새로 올린 글 수를 돌려줌."""
    now = timezone.now()
    todo = list(Match.objects.filter(post__isnull=True, kickoff__gte=now, kickoff__lte=now + timedelta(days=days))
                .select_related('home', 'away'))
    if not todo:
        return 0
    bot, n = get_bot(), 0
    for m in todo:
        with transaction.atomic():
            title, content = build_post(m)
            post = Post.objects.create(author=bot, title=title, content=content)
            if Match.objects.filter(pk=m.pk, post__isnull=True).update(post=post):
                n += 1
            else:                                      # 동시에 다른 요청이 먼저 올렸으면 중복 글 제거
                post.delete()
    return n


def safe_ensure():
    try:
        return ensure_match_threads()
    except Exception:
        log.exception('경기 예측 글 자동 작성 실패')
        return 0

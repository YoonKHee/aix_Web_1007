import csv
import re
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from board.models import Match
from team.models import Team

FORMATS = ['%Y-%m-%d %H:%M', '%Y.%m.%d %H:%M', '%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M:%S']


def _k(s):
    return re.sub(r'\s|·|fc', '', (s or '').lower())


def resolve(name, teams):
    k = _k(name)
    if not k:
        return None
    for t in teams:
        if _k(t.team_name) == k:
            return t
    cand = [t for t in teams if len(k) >= 2 and (k in _k(t.team_name) or _k(t.team_name) in k)]
    return cand[0] if len(cand) == 1 else None


class Command(BaseCommand):
    help = 'CSV(일시,홈,원정)로 경기 일정을 한꺼번에 등록합니다. 예) 2026-11-01 14:00,울산HD,전북현대'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')

    def handle(self, *args, **o):
        raw = open(o['csv_path'], 'rb').read()
        for enc in ('utf-8-sig', 'cp949'):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise CommandError('파일 인코딩을 읽을 수 없습니다 (UTF-8 또는 CP949로 저장해주세요).')
        teams = list(Team.objects.all())
        added = dup = 0
        bad = []
        for i, row in enumerate(csv.reader(text.splitlines()), 1):
            if len(row) < 3:
                continue
            when = None
            for f in FORMATS:
                try:
                    when = datetime.strptime(row[0].strip(), f)
                    break
                except ValueError:
                    pass
            if when is None:
                if i > 1:
                    bad.append(f'{i}줄: 날짜를 읽을 수 없음 ({row[0]})')
                continue                                   # 첫 줄 제목줄은 건너뜀
            h, a = resolve(row[1], teams), resolve(row[2], teams)
            if not h or not a or h == a:
                bad.append(f'{i}줄: 팀을 찾을 수 없음 ({row[1]} / {row[2]})')
                continue
            if settings.USE_TZ:
                when = timezone.make_aware(when)
            _, created = Match.objects.get_or_create(home=h, away=a, kickoff=when)
            added += created
            dup += not created
        self.stdout.write(f'등록 {added}건, 이미 있음 {dup}건, 문제 {len(bad)}건')
        for b in bad:
            self.stdout.write('  - ' + b)

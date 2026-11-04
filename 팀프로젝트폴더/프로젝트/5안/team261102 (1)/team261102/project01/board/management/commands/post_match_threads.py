from django.core.management.base import BaseCommand

from board.matchbot import ensure_match_threads


class Command(BaseCommand):
    help = '곧 열릴 경기에 대한 "누가 이길까요?" 글을 자동으로 올립니다.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=2, help='며칠 앞까지의 경기를 대상으로 할지 (기본 2일)')

    def handle(self, *args, **o):
        self.stdout.write(f'새 글 {ensure_match_threads(o["days"])}개를 올렸습니다.')

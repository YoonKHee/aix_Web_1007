from django.core.management.base import BaseCommand

from board.filters import scan_all


class Command(BaseCommand):
    help = '이미 올라온 게시글·댓글에서 금칙어를 찾아 자동으로 숨김 처리합니다.'

    def handle(self, *args, **opts):
        p, c = scan_all()
        self.stdout.write(f'글 {p}개, 댓글 {c}개를 숨김 처리했습니다.')

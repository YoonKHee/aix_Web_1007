from django.db.models.signals import post_save
from django.dispatch import receiver

from .filters import scan_all
from .models import BannedWord


@receiver(post_save, sender=BannedWord)
def rescan_after_new_word(sender, instance, **kwargs):
    """금칙어를 추가하면 기존 글·댓글도 바로 다시 검사 (자동 삭제)"""
    if not instance.allow:
        scan_all()

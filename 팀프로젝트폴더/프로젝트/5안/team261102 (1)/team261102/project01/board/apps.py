from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'board'
    verbose_name = '자유게시판'

    def ready(self):
        from . import signals  # noqa: F401  (금칙어를 추가하면 기존 글도 자동 검사)

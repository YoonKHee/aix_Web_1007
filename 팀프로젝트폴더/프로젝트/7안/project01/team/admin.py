from datetime import datetime
import shutil

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.views.decorators.http import require_POST

from team.models import Team, MatchResult
from team.match_prediction import (
    _load_json_matches,
    load_matches,
    load_bundle,
    model_path,
    PredictionUnavailable,
)


admin.site.register(Team)


@admin.register(MatchResult)
class MatchResultAdmin(admin.ModelAdmin):
    change_list_template = 'admin/team/matchresult/change_list.html'

    list_display = [
        'match_date',
        'round',
        'home_team_id',
        'away_team_id',
        'home_goals',
        'away_goals',
        'outcome',
        'updated_at',
    ]

    list_filter = [
        'round',
        'match_date',
        'home_team_id',
        'away_team_id',
    ]

    readonly_fields = ['outcome', 'updated_at']

    fields = [
        'match_date',
        'round',
        'home_team_id',
        'away_team_id',
        'home_goals',
        'away_goals',
        'official_match_id',
        'outcome',
        'updated_at',
    ]

    actions = None

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='결과')
    def outcome(self, obj):
        if obj.home_goals is None or obj.away_goals is None:
            return '점수 입력 후 자동 계산'

        return {
            'H': '홈승',
            'D': '무승부',
            'A': '원정승',
        }[obj.result]

    def get_urls(self):
        return [
            path(
                'import/',
                self.admin_site.admin_view(
                    require_POST(self.import_results)
                ),
                name='team_matchresult_import',
            ),
            path(
                'train/',
                self.admin_site.admin_view(
                    require_POST(self.train)
                ),
                name='team_matchresult_train',
            ),
        ] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        status = '모델 갱신 필요'
        through = None
        count = None

        try:
            matches, digest = load_matches()
            count = len(matches)
            bundle = load_bundle(digest)
            through = bundle['trained_through']
            status = '현재 경기 데이터 반영 완료'
        except PredictionUnavailable:
            pass

        context = {
            **(extra_context or {}),
            'model_status': status,
            'trained_through': through,
            'prediction_count': count,
            'can_import': (
                self.has_add_permission(request)
                and self.has_change_permission(request)
            ),
            'can_train': self.has_change_permission(request),
        }

        return super().changelist_view(request, context)

    def import_results(self, request):
        if not (
            self.has_add_permission(request)
            and self.has_change_permission(request)
        ):
            raise PermissionDenied

        try:
            rows, _ = _load_json_matches()
            created = 0

            with transaction.atomic():
                for row in rows:
                    obj, new = MatchResult.objects.get_or_create(
                        match_date=row['match_date'],
                        home_team_id=row['home_team_id'],
                        away_team_id=row['away_team_id'],
                        defaults={
                            'round': row['round'],
                            'home_goals': row['home_goals'],
                            'away_goals': row['away_goals'],
                            'official_match_id': row['official_match_id'],
                        },
                    )
                    obj.full_clean()
                    created += int(new)

        except (
            OSError,
            ValueError,
            ValidationError,
            IntegrityError,
        ) as exc:
            self.message_user(
                request,
                f'가져오기 실패: {exc}',
                messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f'{created}경기 추가 완료. 기존 입력은 유지했습니다.',
                messages.SUCCESS,
            )

        return HttpResponseRedirect(
            reverse('admin:team_matchresult_changelist')
        )

    def train(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied

        from team.train_prediction import train_model

        try:
            target = model_path()

            if target.exists():
                backup_dir = target.parent / 'backups'
                backup_dir.mkdir(parents=True, exist_ok=True)

                stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')

                shutil.copy2(
                    target,
                    backup_dir / f'model_{stamp}.json',
                )

            bundle = train_model()

            _, digest = load_matches()
            load_bundle(digest)

        except (ImportError, ValueError, OSError) as exc:
            self.message_user(
                request,
                f'모델 갱신 실패: {exc}',
                messages.ERROR,
            )
        else:
            self.message_user(
                request,
                (
                    f"{bundle['training_match_count']}경기 반영 완료. "
                    f"학습 기준일: {bundle['trained_through']}"
                ),
                messages.SUCCESS,
            )

        return HttpResponseRedirect(
            reverse('admin:team_matchresult_changelist')
        )
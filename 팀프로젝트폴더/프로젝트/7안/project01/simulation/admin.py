from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import SimulationRun, SimulationTeamSummary

@admin.register(SimulationRun)
class SimulationRunAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'scenario_name',
        'home_team',
        'away_team',
        'seed',
        'duration_sec',
        'event_count',
        'frame_count',
        'validation_status',
    )

    list_filter = (
        'scenario_code',
        'home_team',
        'away_team',
        'generator_version',
    )

    search_fields = (
        'home_team__team_name',
        'away_team__team_name',
        'scenario_name',
    )

    list_select_related = (
        'home_team',
        'away_team',
    )

    readonly_fields = (
        'id',
        'created_at',
        'home_team',
        'away_team',
        'scenario_code',
        'scenario_name',
        'generator_version',
        'seed',
        'duration_sec',
        'frame_count',
        'event_count',
        'source_sha256',
        'fingerprint',
        'parameters',
        'validation',
        'roster_snapshot',
        'replay_link',
        'download_link',
    )

    fields = readonly_fields

    actions = None

    # 생성 이력을 보호하기 위해 조회만 제공합니다.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description='데이터 검사')
    def validation_status(self, obj):
        if obj.validation.get('passed'):
            return '통과'

        return '확인 필요'

    @admin.display(description='생성 당시 명단')
    def roster_snapshot(self, obj):
        players = obj.document.get('players', [])

        rows = []

        for player in players:
            team = (
                '홈팀'
                if player.get('team_id') == 'HOME'
                else '원정팀'
            )

            rows.append(
                f"{team} / "
                f"{player.get('player_id', '')} / "
                f"{player.get('name', '')} / "
                f"실제 선수 ID: {player.get('real_player_id', '-')} / "
                f"등번호: {player.get('real_number', '-')} / "
                f"가상 역할: {player.get('role', '')}"
            )

        return format_html(
            '<pre style="white-space:pre-wrap; line-height:1.8;">{}</pre>',
            '\n'.join(rows),
        )
    @admin.display(description="저장 경기 재생")
    def replay_link(self, obj):
        url = reverse(
            "simulation:replay",
            args=[obj.pk],
        )

        return format_html(
            '<a href="{}">저장된 경기 재생하기</a>',
            url,
        )

    @admin.display(description='전체 분석 데이터')
    def download_link(self, obj):
        url = reverse(
            'admin:simulation_run_download',
            args=[obj.pk],
        )

        return format_html(
            '<a href="{}">가상 경기 JSON 다운로드</a>',
            url,
        )

    def get_urls(self):
        custom_urls = [
            path(
                '<uuid:object_id>/download/',
                self.admin_site.admin_view(self.download),
                name='simulation_run_download',
            ),
        ]

        return custom_urls + super().get_urls()

    def download(self, request, object_id):
        obj = self.get_object(request, str(object_id))

        if obj is None:
            raise Http404('가상 경기 기록이 없습니다.')

        if not self.has_view_permission(request, obj):
            raise PermissionDenied

        response = JsonResponse(
            obj.document,
            json_dumps_params={
                'ensure_ascii': False,
                'indent': 2,
            },
        )

        response['Content-Disposition'] = (
            f'attachment; filename="simulation_{obj.pk}.json"'
        )

        return response

    from .models import SimulationTeamSummary


@admin.register(SimulationTeamSummary)
class SimulationTeamSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "side",
        "distance_m",
        "pass_attempts",
        "successful_passes",
        "success_rate",
        "interceptions",
        "possession_seconds",
    )

    list_filter = (
        "side",
        "metrics_version",
        "run__scenario_code",
        "run__generator_version",
    )

    list_select_related = (
        "run__home_team",
        "run__away_team",
    )

    actions = None

    @admin.display(description="패스 성공률")
    def success_rate(self, obj):
        rate = obj.pass_success_rate
        return "시도 없음" if rate is None else f"{rate}%"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
from . import tracking_admin    
from . import event_admin
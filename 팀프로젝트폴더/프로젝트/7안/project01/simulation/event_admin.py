from django.contrib import admin

from .event_models import SimulationPlayerEventStats


@admin.register(SimulationPlayerEventStats)
class SimulationPlayerEventStatsAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "slot_id",
        "pass_attempts",
        "successful_passes",
        "failed_passes",
        "success_rate",
        "passes_received",
        "forward_pass_attempts",
        "successful_forward_passes",
        "interceptions",
        "possession_seconds",
    )

    list_filter = (
        "team_side",
        "data_source",
        "run__scenario_code",
    )

    search_fields = ("player__name",)

    list_select_related = (
        "player__team",
        "run",
    )

    actions = None

    @admin.display(description="패스 성공률")
    def success_rate(self, obj):
        rate = obj.pass_success_rate

        return (
            "시도 없음"
            if rate is None
            else f"{rate}%"
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
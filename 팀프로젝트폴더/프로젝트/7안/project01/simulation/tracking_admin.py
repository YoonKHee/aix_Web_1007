from django.contrib import admin

from .tracking_models import SimulationPlayerTracking


@admin.register(SimulationPlayerTracking)
class SimulationPlayerTrackingAdmin(admin.ModelAdmin):
    list_display = (
        "player",
        "slot_id",
        "team_side",
        "total_distance_m",
        "max_speed_kmh",
        "high_speed_distance_m",
        "sprint_count",
        "average_x",
        "average_y",
        "defensive_third_seconds",
        "middle_third_seconds",
        "attacking_third_seconds",
        "opponent_box_entries",
    )

    list_filter = (
        "team_side",
        "data_source",
        "run__scenario_code",
    )

    search_fields = (
        "player__name",
    )

    list_select_related = (
        "player__team",
        "run",
    )

    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from .models import SimulationRun


def make_roster(players, team):
    """저장된 선수 정보로 화면에 표시할 명단을 만듭니다."""
    return [
        {
            "slot_id": player["player_id"],
            "name": player.get("name", ""),
            "number": player.get("real_number"),
            "position": player.get("real_position", ""),
            "demo_role": player.get("role", ""),
        }
        for player in players
        if player.get("team_id") == team
    ]


@staff_member_required
def replay(request, run_id):
    if not request.user.has_perm("simulation.view_simulationrun"):
        raise PermissionDenied

    run = get_object_or_404(
        SimulationRun.objects.select_related("home_team", "away_team"),
        pk=run_id,
    )

    # 저장된 데이터를 그대로 사용합니다.
    data = run.document
    players = data.get("players", [])
    metadata = data.get("simulation", {})

    home_name = (
        metadata.get("home_team", {}).get("name")
        or run.home_team.team_name
    )
    away_name = (
        metadata.get("away_team", {}).get("name")
        or run.away_team.team_name
    )

    return render(
        request,
        "player/tracking_demo.html",
        {
            "demo_data": data,
            "saved_run": run,
            "replay_mode": True,
            "selected_team": {"team_name": home_name},
            "selected_away_team": {"team_name": away_name},
            "real_roster": make_roster(players, "HOME"),
            "away_roster": make_roster(players, "AWAY"),
        },
    )
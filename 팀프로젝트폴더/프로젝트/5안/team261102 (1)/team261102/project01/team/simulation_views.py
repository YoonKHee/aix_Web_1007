from datetime import date, timedelta
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from player.services import FORMATIONS
from team.lineup_simulation import SimulationContext, simulate
from team.match_prediction import PredictionUnavailable
from team.player_comparison import attach_comparisons


@require_GET
def simulation_page(request):
    context = {'unavailable': None}

    try:
        simulation = SimulationContext()

        last_day = date.fromisoformat(
            simulation.bundle['trained_through']
        )

        teams = []

        for team in simulation.teams:
            db_team = simulation.db_teams.get(team['id'])

            logo = (
                db_team.logo.url
                if db_team and db_team.logo
                else ''
            )

            teams.append({
                **team,
                'logo': logo,
            })

        context['bootstrap'] = {
            'teams': teams,
            'formations': list(FORMATIONS),
            'defaultDate': max(
                timezone.localdate(),
                last_day + timedelta(days=1),
            ).isoformat(),
            'minDate': (
                last_day + timedelta(days=1)
            ).isoformat(),
            'trainedThrough': last_day.isoformat(),
        }

    except PredictionUnavailable as exc:
        context['unavailable'] = str(exc)

    return render(
        request,
        'team/lineup_simulation.html',
        context,
    )


@require_GET
def simulation_roster(request):
    try:
        team = request.GET.get('team', '')

        formation = request.GET.get(
            'formation',
            '4-3-3',
        )

        if formation not in FORMATIONS:
            raise PredictionUnavailable(
                '지원하는 포메이션을 선택하세요.'
            )

        context = SimulationContext()

        # 해당 구단의 선수 명단
        roster = context.roster(team)

        # 육각형 그래프에 사용할 비교 데이터 연결
        roster_with_comparisons = attach_comparisons(
            context,
            team,
            roster,
        )

        history = []

        for match in context.matches:
            if team not in (
                match['home_team_id'],
                match['away_team_id'],
            ):
                continue

            home = team == match['home_team_id']

            history.append({
                'date': match['match_date'],
                'home': home,
                'opponent': (
                    match['away_team']
                    if home
                    else match['home_team']
                ),
                'gf': (
                    match['home_goals']
                    if home
                    else match['away_goals']
                ),
                'ga': (
                    match['away_goals']
                    if home
                    else match['home_goals']
                ),
            })

        roles = [
            role
            for role in ('GK', 'DF', 'MF', 'FW')
            for _ in range(FORMATIONS[formation][role])
        ]

        return JsonResponse({
            'history': history,
            'roster': roster_with_comparisons,
            'recommended': context.recommended(
                team,
                formation,
            ),
            'roles': roles,
        })

    except PredictionUnavailable as exc:
        return JsonResponse(
            {'error': str(exc)},
            status=400,
        )


@require_POST
def simulation_result(request):
    try:
        if len(request.body) > 65536:
            raise PredictionUnavailable(
                '설정 데이터가 너무 큽니다.'
            )

        payload = json.loads(request.body)

        return JsonResponse(
            simulate(
                SimulationContext(),
                payload,
            )
        )

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {'error': '설정 데이터를 읽을 수 없습니다.'},
            status=400,
        )

    except PredictionUnavailable as exc:
        return JsonResponse(
            {'error': str(exc)},
            status=400,
        )
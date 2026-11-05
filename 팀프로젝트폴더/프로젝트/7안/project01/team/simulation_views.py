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


def _best11_request(request, simulation):
    """BEST11 화면에서 넘어온 내 라인업. 형식이 틀리면 None (화면은 평소처럼 연다)."""
    team_pk = request.GET.get('b11_team', '')
    formation = request.GET.get('b11_formation', '')
    raw = request.GET.get('b11_lineup', '')
    if not (team_pk.isdigit() and formation in FORMATIONS and raw):
        return None
    try:
        ids = [int(x) for x in raw.split(',')]
    except ValueError:
        return None
    if len(ids) != 11 or len(set(ids)) != 11:
        return None
    official = next((oid for oid, team in simulation.db_teams.items() if team.pk == int(team_pk)), None)
    if not official:
        return None
    return {'team': official, 'formation': formation, 'players': ids, **_best11_settings(request.GET.get('b11_set', ''))}


def _best11_settings(raw):
    """BEST11 화면의 내 가중치 설정(프리셋·지표별 가중치·케미·경험). 형식이 틀리면 기본값."""
    from player.lab.service import PRESETS
    try:
        s = json.loads(raw) if raw else {}
    except ValueError:
        s = {}
    if not isinstance(s, dict):
        s = {}
    preset = s.get('preset') if s.get('preset') in PRESETS else 'default'
    mult = {}
    if isinstance(s.get('mult'), dict):
        for k, v in list(s['mult'].items())[:80]:
            try:
                mult[str(k)[:40]] = max(0.0, min(20.0, float(v)))
            except (TypeError, ValueError):
                pass

    def num(key, default):
        try:
            return max(0.0, min(2.0, float(s.get(key, default))))
        except (TypeError, ValueError):
            return default

    settings = {'preset': preset, 'mult': mult, 'chem': num('chem', 1.0), 'exp': num('exp', 1.5)}
    parts = [f"프리셋 {PRESETS[preset]['label']}"]
    if mult:
        parts.append(f'지표별 가중치 {len(mult)}개 변경')
    if settings['chem'] != 1.0:
        parts.append(f"케미 ×{settings['chem']:g}")
    if settings['exp'] != 1.5:
        parts.append(f"경험 보정 {settings['exp']:g}")
    return {'settings': settings, 'settings_summary': ' · '.join(parts)}


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

        # BEST11 화면의 '이 라인업으로 승부예측' 버튼: ?b11_team=<구단 pk>&b11_formation=4-3-3&b11_lineup=id,id,...
        b11 = _best11_request(request, simulation)
        if b11:
            context['bootstrap']['best11'] = b11

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
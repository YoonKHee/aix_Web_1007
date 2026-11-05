import json

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from team.models import Team
from player.services import get_filtered_best11


def connect_roster(data, team, prefix):
    """기존 BEST11을 가상 슬롯에 연결합니다."""
    result = get_filtered_best11(
        team_id=str(team.pk),
        formation='4-3-3',
    )

    slots = {
        'GK': [1],
        'DF': [2, 3, 4, 5],
        'MF': [6, 7, 8],
        'FW': [9, 10, 11],
    }

    demo_players = {
        player['player_id']: player
        for player in data['players']
    }

    assignments = []

    for position, numbers in slots.items():
        rows = result['best11'][position]

        if len(rows) != len(numbers):
            return [], '기존 BEST11 기준으로 11명을 구성할 수 없습니다.'

        for number, row in zip(numbers, rows):
            slot_id = f'{prefix}{number:02d}'
            player = row['player']

            if (
                player.team_id != team.pk
                or slot_id not in demo_players
            ):
                return [], '선수 소속팀 또는 가상 슬롯을 확인해야 합니다.'

            assignments.append((slot_id, player))

    ids = [player.pk for _, player in assignments]

    if len(assignments) != 11 or len(set(ids)) != 11:
        return [], '11명의 선수 구성을 확인해야 합니다.'

    roster = []

    # 검사를 모두 통과한 뒤에만 명단을 연결합니다.
    for slot_id, player in assignments:
        demo_player = demo_players[slot_id]

        demo_player.update({
            'name': player.name,
            'real_player_id': player.pk,
            'real_number': player.number,
            'real_position': player.position,
            'real_team_name': team.team_name,
            'real_photo_url': (
                player.photo.url if player.photo else ''
            ),
        })

        roster.append({
            'slot_id': slot_id,
            'name': player.name,
            'number': player.number,
            'position': player.position,
            'demo_role': demo_player['role'],
        })

    return roster, ''


def tracking_demo(request):
    target = (
        settings.BASE_DIR
        / 'data'
        / 'demo'
        / 'tracking_demo.json'
    )

    try:
        data = json.loads(target.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise Http404('먼저 더미 데이터 생성 파일을 실행하세요.')

    teams = Team.objects.all().order_by('team_name')

    def find_team(value):
        if not value.isdecimal():
            return None
        return teams.filter(pk=int(value)).first()

    home_value = request.GET.get('team', '')
    away_value = request.GET.get('away', '')

    home_team = find_team(home_value)
    away_team = find_team(away_value)

    home_roster = []
    away_roster = []
    warnings = []

    if home_value and home_team is None:
        warnings.append('홈팀은 목록에 있는 구단을 선택하세요.')

    if away_value and away_team is None:
        warnings.append('원정팀은 목록에 있는 구단을 선택하세요.')

    if home_team and away_team and home_team.pk == away_team.pk:
        warnings.append(
            '같은 구단끼리는 연결하지 않습니다. '
            '다른 원정팀을 선택하세요. 원정팀은 가상 명단을 유지합니다.'
        )
        away_team = None

    if home_team:
        home_roster, warning = connect_roster(data, home_team, 'H')

        if warning:
            warnings.append(f'홈팀: {warning} 가상 명단을 유지합니다.')

    if away_team:
        away_roster, warning = connect_roster(data, away_team, 'A')

        if warning:
            warnings.append(f'원정팀: {warning} 가상 명단을 유지합니다.')

    return render(
        request,
        'player/tracking_demo.html',
        {
            'demo_data': data,
            'teams': teams,

            # 기존 홈팀 HTML과 호환되는 항목입니다.
            'selected_team': home_team,
            'selected_team_id': str(home_team.pk) if home_team else '',
            'real_roster': home_roster,
            'roster_warning': ' '.join(warnings),

            'selected_away_team': away_team,
            'selected_away_team_id': (
                str(away_team.pk) if away_team else ''
            ),
            'away_roster': away_roster,
        },
    )
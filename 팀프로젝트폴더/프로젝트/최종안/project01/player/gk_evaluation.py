"""공식 GK 기록을 기존 DB와 대조하고 평가 지표를 계산합니다."""

import json
from pathlib import Path

from django.conf import settings


TEAM_NAMES = {
    '강원FC': '강원',
    '광주FC': '광주',
    '김천상무': '김천',
    '대전하나시티즌': '대전',
    '부천FC1995': '부천',
    'FC서울': '서울',
    'FC안양': '안양',
    '울산HD': '울산',
    '인천유나이티드': '인천',
    '전북현대': '전북',
    '제주SK FC': '제주',
    '포항스틸러스': '포항',
}

OFFICIAL_GK_WEIGHTS = {
    'conceding': 40,
    'clean_sheet_rate': 40,
    'rating': 20,
}


def load_snapshot():
    path = (
        Path(settings.BASE_DIR)
        / 'data'
        / 'gk'
        / '2026_official.json'
    )

    try:
        snapshot = json.loads(
            path.read_text(encoding='utf-8')
        )

    except (OSError, ValueError):
        return None

    if not isinstance(snapshot, dict):
        return None

    if (
        snapshot.get('season') != 2026
        or snapshot.get('league_id') != 1
    ):
        return None

    records = snapshot.get('records')

    if not isinstance(records, list):
        return None

    if not all(
        isinstance(row, dict)
        for row in records
    ):
        return None

    return snapshot


def match_record(stats, snapshot):
    if (
        not snapshot
        or stats.season != snapshot['season']
    ):
        return None

    team = TEAM_NAMES.get(
        stats.player.team.team_name
    )

    matches = [
        row
        for row in snapshot['records']
        if team is not None
        and row.get('name') == stats.player.name
        and row.get('team') == team
    ]

    if len(matches) != 1:
        return None

    row = matches[0]

    values = [
        row.get(key)
        for key in (
            'games',
            'goals_conceded',
            'clean_sheets',
        )
    ]

    if not all(
        type(value) is int and value >= 0
        for value in values
    ):
        return None

    if (
        row['games'] <= 0
        or row['games'] != stats.games
    ):
        return None

    if row['clean_sheets'] > row['games']:
        return None

    return row


def official_metrics(stats, record):
    return {
        'conceding': (
            1
            / (
                1
                + record['goals_conceded']
                / record['games']
            )
        ),
        'clean_sheet_rate': (
            record['clean_sheets']
            / record['games']
            * 100
        ),
        'rating': float(
            stats.average_rating or 0
        ),
    }


def evaluation_status(stats_list):
    snapshot = load_snapshot()

    available = bool(stats_list) and all(
        match_record(stats, snapshot)
        for stats in stats_list
    )

    return {
        'available': available,
        'retrieved_at': (
            snapshot.get('retrieved_at', '')
            if snapshot
            else ''
        ),
        'source_url': (
            snapshot.get('source_url', '')
            if snapshot
            else ''
        ),
    }
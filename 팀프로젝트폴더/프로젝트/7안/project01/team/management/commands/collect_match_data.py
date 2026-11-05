from collections import Counter
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import json
from pathlib import Path
import shutil
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from team.match_prediction import data_path


SOURCE_URL = (
    'https://www.kleague.com/getScheduleList.do'
)

CLUBS = {
    'K21': '강원',
    'K22': '광주',
    'K35': '김천',
    'K10': '대전',
    'K26': '부천',
    'K09': '서울',
    'K27': '안양',
    'K01': '울산',
    'K18': '인천',
    'K05': '전북',
    'K04': '제주',
    'K03': '포항',
}


def fetch_month(month):
    payload = {
        'leagueId': '1',
        'teamId': None,
        'ticketStatus': None,
        'year': '2026',
        'month': f'{month:02d}',
        'ticketYn': None,
    }

    request = Request(
        SOURCE_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': (
                'application/json; charset=utf-8'
            ),
            'Referer': (
                'https://www.kleague.com/'
                'schedule.do?leagueId=1'
            ),
        },
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:
        document = json.loads(
            response.read()
        )

    if (
        not isinstance(document, dict)
        or str(document.get('resultCode')) != '200'
    ):
        raise ValueError(
            f'{month}월 공식 사이트 응답을 확인해야 합니다.'
        )

    data = document.get('data')

    if (
        not isinstance(data, dict)
        or not isinstance(data.get('scheduleList'), list)
    ):
        raise ValueError(
            f'{month}월 일정 형식이 변경되었습니다.'
        )

    return month, document


def normalize_schedule(documents):
    by_id = {}

    korea = timezone(
        timedelta(hours=9)
    )

    for month in sorted(documents):
        rows = documents[month]['data']['scheduleList']

        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(
                    '경기 자료 형식을 확인해야 합니다.'
                )

            competition = (
                str(row.get('year')),
                str(row.get('leagueId')),
                str(row.get('meetSeq')),
            )

            # 응답에 섞인 다른 대회는 제외합니다.
            if competition != ('2026', '1', '1'):
                continue

            round_number = row.get('roundId')

            if type(round_number) is not int:
                raise ValueError(
                    '라운드 형식을 확인해야 합니다.'
                )

            if not 1 <= round_number <= 33:
                continue

            # 종료된 경기만 사용합니다.
            if (
                row.get('endYn') != 'Y'
                or row.get('gameStatus') != 'FE'
            ):
                continue

            home = row.get('homeTeam')
            away = row.get('awayTeam')

            if (
                home not in CLUBS
                or away not in CLUBS
                or home == away
            ):
                raise ValueError(
                    '경기의 구단 정보를 확인해야 합니다.'
                )

            if (
                row.get('homeTeamName') != CLUBS[home]
                or row.get('awayTeamName') != CLUBS[away]
            ):
                raise ValueError(
                    '공식 구단 ID와 이름이 일치하지 않습니다.'
                )

            home_goals = row.get('homeGoal')
            away_goals = row.get('awayGoal')
            game_id = row.get('gameId')

            values = (
                home_goals,
                away_goals,
                game_id,
            )

            if (
                not all(
                    type(value) is int
                    for value in values
                )
                or min(home_goals, away_goals) < 0
                or game_id <= 0
            ):
                raise ValueError(
                    '득점 또는 경기 ID 형식을 확인해야 합니다.'
                )

            kickoff = datetime.strptime(
                row['gameDate'] + ' ' + row['gameTime'],
                '%Y.%m.%d %H:%M',
            ).replace(
                tzinfo=korea
            )

            if (
                kickoff.year != 2026
                or kickoff > datetime.now(timezone.utc)
            ):
                raise ValueError(
                    '종료 경기의 날짜를 확인해야 합니다.'
                )

            result = (
                'H'
                if home_goals > away_goals
                else 'A'
                if home_goals < away_goals
                else 'D'
            )

            match = {
                'official_match_id': game_id,
                'round': round_number,
                'match_date': kickoff.date().isoformat(),
                'kickoff_at': kickoff.isoformat(),
                'home_team_id': home,
                'home_team': CLUBS[home],
                'away_team_id': away,
                'away_team': CLUBS[away],
                'home_goals': home_goals,
                'away_goals': away_goals,
                'result': result,
                'match_status': 'finished',
            }

            # 같은 기록이 중복 응답되면 하나만 유지합니다.
            # 같은 ID인데 내용이 다르면 저장을 중단합니다.
            if (
                game_id in by_id
                and by_id[game_id] != match
            ):
                raise ValueError(
                    '같은 경기 ID의 기록이 충돌합니다: '
                    f'{game_id}'
                )

            by_id[game_id] = match

    matches = sorted(
        by_id.values(),
        key=lambda match: (
            match['kickoff_at'],
            match['official_match_id'],
        ),
    )

    if len(matches) != 198:
        raise ValueError(
            '1~33라운드 종료 경기는 198개가 필요하지만 '
            f'{len(matches)}개입니다. 저장하지 않았습니다.'
        )

    expected_rounds = Counter({
        round_number: 6
        for round_number in range(1, 34)
    })

    actual_rounds = Counter(
        match['round']
        for match in matches
    )

    if actual_rounds != expected_rounds:
        raise ValueError(
            '라운드별 경기 수가 맞지 않습니다.'
        )

    team_counts = Counter()
    pair_counts = Counter()
    fixtures = set()

    for match in matches:
        home = match['home_team_id']
        away = match['away_team_id']

        team_counts.update([
            home,
            away,
        ])

        pair_counts[
            tuple(sorted((home, away)))
        ] += 1

        key = (
            match['round'],
            home,
            away,
        )

        if key in fixtures:
            raise ValueError(
                '다른 ID로 중복된 경기가 있습니다.'
            )

        fixtures.add(key)

    expected_team_counts = Counter({
        team: 33
        for team in CLUBS
    })

    if (
        team_counts != expected_team_counts
        or any(
            count != 3
            for count in pair_counts.values()
        )
    ):
        raise ValueError(
            '팀별 경기 수 또는 상대팀 연결이 맞지 않습니다.'
        )

    for round_number in range(1, 34):
        teams = [
            team_id
            for match in matches
            if match['round'] == round_number
            for team_id in (
                match['home_team_id'],
                match['away_team_id'],
            )
        ]

        expected = Counter({
            team: 1
            for team in CLUBS
        })

        if Counter(teams) != expected:
            raise ValueError(
                f'{round_number}라운드에서 '
                '같은 팀이 중복되거나 빠졌습니다.'
            )

    return matches


def save_schedule(
    matches,
    documents,
    target,
):
    target = Path(target)

    now = datetime.now(timezone.utc)

    stamp = now.strftime(
        '%Y%m%d_%H%M%S_%f'
    )

    same = False

    if target.exists():
        previous = json.loads(
            target.read_text(
                encoding='utf-8-sig'
            )
        )

        old_matches = previous.get(
            'matches',
            [],
        )

        keys = list(matches[0])

        old_core = [
            {
                key: match.get(key)
                for key in keys
            }
            for match in old_matches
        ]

        same = (
            sorted(
                old_core,
                key=lambda match: (
                    match['official_match_id']
                ),
            )
            ==
            sorted(
                matches,
                key=lambda match: (
                    match['official_match_id']
                ),
            )
        )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 공식 응답도 별도로 보존합니다.
    source = target.parent / (
        f'official_source_{stamp}.json'
    )

    source.write_text(
        json.dumps(
            {
                'source_url': SOURCE_URL,
                'retrieved_at': now.isoformat(),
                'months': documents,
            },
            ensure_ascii=False,
            indent=2,
        ) + '\n',
        encoding='utf-8',
    )

    # 기존 경기 내용이 같으면 파일과 모델 해시를 유지합니다.
    if same:
        return False

    document = {
        'schema_version': 1,
        'season': 2026,
        'league_id': 1,
        'match_count': len(matches),
        'source_url': SOURCE_URL,
        'retrieved_at': now.isoformat(),
        'note': (
            '종료된 1~33라운드의 기본 예측용 경기 정보. '
            '선수 기록은 기존 DB를 사용합니다.'
        ),
        'matches': matches,
    }

    temporary = target.with_suffix('.tmp')

    temporary.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ) + '\n',
        encoding='utf-8',
    )

    # 기존 데이터가 다르면 덮어쓰기 전에 백업합니다.
    if target.exists():
        backup = target.with_name(
            f'{target.stem}_backup_{stamp}.json'
        )

        shutil.copy2(
            target,
            backup,
        )

    temporary.replace(target)

    return True


class Command(BaseCommand):
    help = (
        '2026 K리그1 1~33라운드 종료 경기 198개를 '
        '수집·검증하여 JSON으로 저장합니다.'
    )

    def handle(self, *args, **options):
        documents = {}

        self.stdout.write(
            '공식 경기 일정을 수집합니다…'
        )

        try:
            with ThreadPoolExecutor(
                max_workers=4
            ) as pool:
                futures = [
                    pool.submit(
                        fetch_month,
                        month,
                    )
                    for month in range(1, 13)
                ]

                for future in as_completed(futures):
                    month, document = future.result()

                    documents[month] = document

                    self.stdout.write(
                        f'{month:02d}월 확인 완료'
                    )

            matches = normalize_schedule(
                documents
            )

            changed = save_schedule(
                matches,
                documents,
                data_path(),
            )

        except (
            URLError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            raise CommandError(
                f'수집 중단: {exc}'
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                '12개 팀 · 198경기 검증 완료'
            )
        )

        self.stdout.write(
            f'저장 위치: {data_path()}'
        )

        if changed:
            self.stdout.write(
                '다음 단계에서 모델을 학습해야 합니다.'
            )
        else:
            self.stdout.write(
                '기존 데이터와 동일하여 '
                '원본 파일과 모델 해시를 유지했습니다.'
            )
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from team.management.commands.collect_match_data import (
    CLUBS,
    fetch_month,
)


class Command(BaseCommand):
    help = '공식 사이트의 종료 경기 결과를 조회합니다. DB는 변경하지 않습니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            default=timezone.localdate().month,
            help='조회할 월: 1~12',
        )

    def handle(self, *args, **options):
        month = options['month']

        if not 1 <= month <= 12:
            raise CommandError('월은 1~12 사이로 입력하세요.')

        self.stdout.write(f'2026년 {month}월 경기 결과 조회 중…')

        try:
            _, document = fetch_month(month)
            rows = document['data']['scheduleList']

            matches = []
            seen = set()

            for row in rows:
                # 2026 K리그1 경기만 확인합니다.
                if (
                    str(row.get('year')) != '2026'
                    or str(row.get('leagueId')) != '1'
                    or str(row.get('meetSeq')) != '1'
                ):
                    continue

                # 종료된 경기만 확인합니다.
                if (
                    row.get('endYn') != 'Y'
                    or row.get('gameStatus') != 'FE'
                ):
                    continue

                home = row['homeTeam']
                away = row['awayTeam']
                home_goals = row['homeGoal']
                away_goals = row['awayGoal']
                game_id = row['gameId']
                round_number = row['roundId']

                if (
                    home not in CLUBS
                    or away not in CLUBS
                    or home == away
                ):
                    raise ValueError('구단 정보를 확인해야 합니다.')

                if (
                    type(home_goals) is not int
                    or type(away_goals) is not int
                    or min(home_goals, away_goals) < 0
                    or type(game_id) is not int
                    or game_id <= 0
                    or type(round_number) is not int
                    or not 1 <= round_number <= 38
                ):
                    raise ValueError('점수·경기 ID·라운드를 확인해야 합니다.')

                day = datetime.strptime(
                    row['gameDate'],
                    '%Y.%m.%d',
                ).date()

                if (
                    day.year != 2026
                    or day.month != month
                    or day > timezone.localdate()
                ):
                    raise ValueError('종료 경기 날짜를 확인해야 합니다.')

                if game_id in seen:
                    raise ValueError(f'중복 경기 ID: {game_id}')

                seen.add(game_id)

                matches.append((
                    day,
                    game_id,
                    (
                        f'{day} | {round_number}R | '
                        f'{CLUBS[home]} {home_goals}:{away_goals} '
                        f'{CLUBS[away]} | 공식 ID: {game_id}'
                    ),
                ))

        except Exception as exc:
            raise CommandError(f'조회 실패: {exc}') from exc

        for _, _, text in sorted(matches):
            self.stdout.write(text)

        self.stdout.write(
            self.style.SUCCESS(
                f'종료 경기 {len(matches)}개 조회 완료. '
                'DB와 JSON은 변경하지 않았습니다.'
            )
        )
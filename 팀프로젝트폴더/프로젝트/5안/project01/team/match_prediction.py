"""경기 전 기록 생성과 승무패 확률 계산."""

from datetime import date
from hashlib import sha256
import json
import math
from pathlib import Path

from django.conf import settings


FEATURE_NAMES = [
    'recent_points_diff',
    'recent_goals_for_diff',
    'recent_goals_against_diff',
    'venue_points_diff',
    'venue_goals_for_diff',
    'venue_goals_against_diff',
    'rest_days_diff',
    'season_points_diff',
    'season_goals_for_diff',
    'season_goals_against_diff',
    'smoothed_venue_points_diff',
    'smoothed_venue_goals_for_diff',
    'smoothed_venue_goals_against_diff',
    'expected_home_goals',
    'expected_away_goals',
]

LABELS = {
    'H': '홈승',
    'D': '무승부',
    'A': '원정승',
}

MIN_HISTORY = 5
MODEL_VERSION = 2


class PredictionUnavailable(ValueError):
    pass


def data_path():
    return (
        Path(settings.BASE_DIR)
        / 'data/matches/2026/official_verified'
        / 'K리그1_2026_경기통합.json'
    )


def model_path():
    return (
        Path(settings.BASE_DIR)
        / 'data/prediction/model_2026.json'
    )


def load_matches():
    try:
        raw = data_path().read_bytes()
        document = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise PredictionUnavailable(
            '검증된 경기 자료를 읽을 수 없습니다.'
        ) from exc

    matches = document.get('matches', [])

    if not matches:
        raise PredictionUnavailable('경기 자료가 없습니다.')

    seen = set()

    for match in matches:
        try:
            day = date.fromisoformat(match['match_date'])
            home = match['home_team_id']
            away = match['away_team_id']
            hg = match['home_goals']
            ag = match['away_goals']
            key = match['official_match_id']

            valid = (
                day.year == 2026
                and home != away
                and key is not None
                and key not in seen
                and type(hg) is int
                and type(ag) is int
                and min(hg, ag) >= 0
                and match['result']
                == ('H' if hg > ag else 'A' if hg < ag else 'D')
                and match['match_status'] == 'finished'
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PredictionUnavailable(
                '경기 자료 형식을 확인해야 합니다.'
            ) from exc

        if not valid:
            raise PredictionUnavailable(
                '경기 자료에 중복 또는 잘못된 결과가 있습니다.'
            )

        seen.add(key)

    matches = sorted(
        matches,
        key=lambda match: (
            match['match_date'],
            match['official_match_id'],
        ),
    )

    return matches, sha256(raw).hexdigest()


def team_options(matches):
    teams = {}

    for match in matches:
        teams[match['home_team_id']] = match['home_team']
        teams[match['away_team_id']] = match['away_team']

    return [
        {'id': team_id, 'name': name}
        for team_id, name in sorted(
            teams.items(),
            key=lambda item: item[1],
        )
    ]


def team_history(matches, team_id, before):
    history = []

    for match in matches:
        if date.fromisoformat(match['match_date']) >= before:
            continue

        if team_id not in (
            match['home_team_id'],
            match['away_team_id'],
        ):
            continue

        home = match['home_team_id'] == team_id
        gf = match['home_goals'] if home else match['away_goals']
        ga = match['away_goals'] if home else match['home_goals']

        history.append({
            'date': match['match_date'],
            'home': home,
            'gf': gf,
            'ga': ga,
            'points': 3 if gf > ga else 1 if gf == ga else 0,
        })

    return sorted(history, key=lambda row: row['date'])


def averages(rows):
    return {
        key: sum(row[key] for row in rows) / len(rows)
        for key in ('points', 'gf', 'ga')
    }


def features_for(matches, home_id, away_id, before):
    if home_id == away_id:
        raise PredictionUnavailable(
            '서로 다른 두 팀을 선택하세요.'
        )

    histories = [
        team_history(matches, team_id, before)
        for team_id in (home_id, away_id)
    ]

    if any(len(history) < MIN_HISTORY for history in histories):
        raise PredictionUnavailable(
            '양 팀 모두 이전 경기 기록이 5경기 이상 필요합니다.'
        )

    summaries = []

    for history, home in zip(histories, (True, False)):
        recent = history[-5:]
        venue = [
            row for row in history
            if row['home'] == home
        ][-5:]

        summaries.append({
            'history_count': len(history),
            'recent': averages(recent),
            'venue': averages(venue or recent),
            'venue_count': len(venue),
            'season': averages(history),
            'recent_results': [
                '승'
                if row['points'] == 3
                else '무'
                if row['points'] == 1
                else '패'
                for row in recent
            ],
            'last_match': history[-1]['date'],
            'rest_days': (
                before
                - date.fromisoformat(history[-1]['date'])
            ).days,
        })

    home, away = summaries

    values = [
        home['recent'][key] - away['recent'][key]
        for key in ('points', 'gf', 'ga')
    ]

    values += [
        home['venue'][key] - away['venue'][key]
        for key in ('points', 'gf', 'ga')
    ]

    values.append(
        min(home['rest_days'], 30)
        - min(away['rest_days'], 30)
    )

    blended = []

    for history, summary, is_home in zip(
        histories,
        summaries,
        (True, False),
    ):
        venue = [
            row for row in history
            if row['home'] == is_home
        ]

        summary['smoothed_venue'] = {
            key: (
                sum(row[key] for row in venue)
                + 6 * summary['season'][key]
            ) / (len(venue) + 6)
            for key in ('points', 'gf', 'ga')
        }

        blended.append({
            key: (
                0.5 * summary['season'][key]
                + 0.3 * summary['smoothed_venue'][key]
                + 0.2 * summary['recent'][key]
            )
            for key in ('points', 'gf', 'ga')
        })

    values += [
        home['season'][key] - away['season'][key]
        for key in ('points', 'gf', 'ga')
    ]

    values += [
        home['smoothed_venue'][key]
        - away['smoothed_venue'][key]
        for key in ('points', 'gf', 'ga')
    ]

    prior = [
        match for match in matches
        if date.fromisoformat(match['match_date']) < before
    ]

    league_average = (
        sum(
            match['home_goals'] + match['away_goals']
            for match in prior
        )
        / (2 * len(prior))
    )

    if league_average <= 0:
        raise PredictionUnavailable(
            '예상 득점을 계산할 리그 기록이 부족합니다.'
        )

    home_base = (
        sum(match['home_goals'] for match in prior)
        + 5 * league_average
    ) / (len(prior) + 5)

    away_base = (
        sum(match['away_goals'] for match in prior)
        + 5 * league_average
    ) / (len(prior) + 5)

    expected_home = (
        home_base
        * blended[0]['gf']
        * blended[1]['ga']
        / league_average ** 2
    )

    expected_away = (
        away_base
        * blended[1]['gf']
        * blended[0]['ga']
        / league_average ** 2
    )

    values += [
        max(0.1, min(4.5, expected_home)),
        max(0.1, min(4.5, expected_away)),
    ]

    return values, summaries


def training_rows(matches):
    rows = []

    for match in matches:
        day = date.fromisoformat(match['match_date'])

        try:
            features, _ = features_for(
                matches,
                match['home_team_id'],
                match['away_team_id'],
                day,
            )
        except PredictionUnavailable:
            continue

        rows.append({
            'date': match['match_date'],
            'x': features,
            'y': match['result'],
            'match_id': match['official_match_id'],
        })

    return rows


def chronological_split(rows):
    if len(rows) < 60:
        raise PredictionUnavailable(
            '시간순 학습·평가에 필요한 경기 수가 부족합니다.'
        )

    boundary = rows[int(len(rows) * 0.7)]['date']

    train = [
        row for row in rows
        if row['date'] < boundary
    ]

    test = [
        row for row in rows
        if row['date'] >= boundary
    ]

    if (
        len(train) < 30
        or len(test) < 15
        or set(row['y'] for row in train) != set(LABELS)
    ):
        raise PredictionUnavailable(
            '세 결과를 학습·평가할 경기 수가 부족합니다.'
        )

    return train, test


def poisson_probabilities(home_rate, away_rate):
    if not all(
        math.isfinite(value) and 0 < value <= 4.5
        for value in (home_rate, away_rate)
    ):
        raise PredictionUnavailable(
            '예상 득점 범위를 확인해야 합니다.'
        )

    home = [math.exp(-home_rate)]
    away = [math.exp(-away_rate)]

    for goals in range(1, 26):
        home.append(home[-1] * home_rate / goals)
        away.append(away[-1] * away_rate / goals)

    probabilities = {
        'H': 0.0,
        'D': 0.0,
        'A': 0.0,
    }

    for home_goals, home_probability in enumerate(home):
        for away_goals, away_probability in enumerate(away):
            result = (
                'H'
                if home_goals > away_goals
                else 'A'
                if home_goals < away_goals
                else 'D'
            )

            probabilities[result] += (
                home_probability * away_probability
            )

    total = sum(probabilities.values())

    return {
        key: value / total
        for key, value in probabilities.items()
    }


def predict_probabilities(bundle, features):
    model = bundle['model']

    # 예상 득점 모형에는 mean이나 scale이 필요하지 않습니다.
    # 반드시 일반 분류기 계산보다 먼저 구분합니다.
    if model.get('kind') == 'poisson':
        return poisson_probabilities(
            features[-2],
            features[-1],
        )

    normalized = [
        (value - mean) / scale
        for value, mean, scale in zip(
            features,
            model['mean'],
            model['scale'],
        )
    ]

    logits = [
        bias + sum(
            weight * value
            for weight, value in zip(
                coefficients,
                normalized,
            )
        )
        for coefficients, bias in zip(
            model['coef'],
            model['intercept'],
        )
    ]

    exponentials = [
        math.exp(value - max(logits))
        for value in logits
    ]

    total = sum(exponentials)

    return dict(zip(
        model['classes'],
        (value / total for value in exponentials),
    ))


def load_bundle(dataset_hash):
    try:
        bundle = json.loads(
            model_path().read_text(encoding='utf-8')
        )

        model = bundle['model']

        valid = (
            bundle['version'] == MODEL_VERSION
            and bundle['dataset_sha256'] == dataset_hash
            and bundle['feature_names'] == FEATURE_NAMES
            and set(model['classes']) == set(LABELS)
            and len(model['classes']) == 3
        )

        if model.get('kind') == 'poisson':
            valid = valid and model.get('max_goals') == 25
        else:
            valid = valid and (
                model.get('kind', 'logistic') == 'logistic'
                and len(model['coef']) == 3
                and len(model['intercept']) == 3
                and len(model['mean']) == len(FEATURE_NAMES)
                and len(model['scale']) == len(FEATURE_NAMES)
                and all(
                    len(row) == len(FEATURE_NAMES)
                    for row in model['coef']
                )
            )

            values = (
                model['mean']
                + model['scale']
                + model['intercept']
                + [
                    value
                    for row in model['coef']
                    for value in row
                ]
            )

            valid = (
                valid
                and all(
                    math.isfinite(value)
                    for value in values
                )
                and all(
                    value > 0
                    for value in model['scale']
                )
            )

        date.fromisoformat(bundle['trained_through'])

    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise PredictionUnavailable(
            '예측 모델을 준비해야 합니다.'
        ) from exc

    if not valid:
        raise PredictionUnavailable(
            '경기 자료 또는 계산 방식이 변경되어 '
            '예측 모델을 다시 준비해야 합니다.'
        )

    return bundle


def forecast(
    matches,
    bundle,
    home_id,
    away_id,
    target_date,
):
    teams = {
        row['id']: row['name']
        for row in team_options(matches)
    }

    if home_id not in teams or away_id not in teams:
        raise PredictionUnavailable(
            '목록에 있는 팀을 선택하세요.'
        )

    cutoff = date.fromisoformat(
        bundle['trained_through']
    )

    if target_date <= cutoff:
        raise PredictionUnavailable(
            f'학습에 사용한 마지막 날짜({cutoff}) 이후를 선택하세요.'
        )

    if target_date.year != 2026:
        raise PredictionUnavailable(
            '이 모델은 2026년 경기만 대상으로 합니다.'
        )

    values, summaries = features_for(
        matches,
        home_id,
        away_id,
        target_date,
    )

    probabilities = predict_probabilities(
        bundle,
        values,
    )

    units = {
        key: int(probabilities[key] * 1000)
        for key in LABELS
    }

    remaining = 1000 - sum(units.values())

    order = sorted(
        LABELS,
        key=lambda key: (
            probabilities[key] * 1000 - units[key]
        ),
        reverse=True,
    )

    for key in order[:remaining]:
        units[key] += 1

    best = max(
        probabilities,
        key=probabilities.get,
    )

    return {
        'home_name': teams[home_id],
        'away_name': teams[away_id],
        'date': target_date.isoformat(),
        'probabilities': [
            {
                'code': key,
                'label': LABELS[key],
                'percent': units[key] / 10,
            }
            for key in ('H', 'D', 'A')
        ],
        'best_label': LABELS[best],
        'home': summaries[0],
        'away': summaries[1],
        'stale_days': (target_date - cutoff).days,
        'long_gap': (target_date - cutoff).days > 14,
        'expected_home_goals': values[-2],
        'expected_away_goals': values[-1],
        'model_kind': bundle['model'].get(
            'kind',
            'logistic',
        ),
    }
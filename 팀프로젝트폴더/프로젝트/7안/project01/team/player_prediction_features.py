import math

from player.gk_evaluation import TEAM_NAMES
from player.services import get_filtered_best11
from team.models import Team


FORMATION = "4-3-3"

ROLE_COLUMNS = [
    ("FW", "attack_score_diff", "공격진 점수"),
    ("MF", "midfield_score_diff", "중원 점수"),
    ("DF", "defense_score_diff", "수비진 점수"),
    ("GK", "goalkeeper_score_diff", "골키퍼 점수"),
]

EXPECTED_COUNTS = {
    "FW": 3,
    "MF": 3,
    "DF": 4,
    "GK": 1,
}


def find_team(name):
    """예측 화면의 구단명을 선수 DB의 구단과 연결합니다."""
    matches = [
        team
        for team in Team.objects.all()
        if TEAM_NAMES.get(team.team_name, team.team_name) == name
    ]

    if len(matches) != 1:
        raise ValueError(
            f"{name}: 선수 DB의 구단을 하나로 연결할 수 없습니다."
        )

    return matches[0]


def team_scores(team):
    """BEST11의 포지션별 평균점수를 계산합니다."""
    result = get_filtered_best11(
        team_id=str(team.pk),
        formation=FORMATION,
    )

    lineup = result["best11"]
    scores = {}
    selected = set()

    for role, expected in EXPECTED_COUNTS.items():
        rows = lineup[role]

        if len(rows) != expected:
            raise ValueError(
                f"{team.team_name}: {role} 후보가 부족해 "
                "BEST11을 구성할 수 없습니다."
            )

        values = []

        for row in rows:
            player = row["player"]

            if player.team_id != team.pk or player.pk in selected:
                raise ValueError(
                    "선수 소속팀 또는 중복 선정을 확인해야 합니다."
                )

            score = float(row["score"])

            if not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError(
                    "선수 점수 범위를 확인해야 합니다."
                )

            selected.add(player.pk)
            values.append(score)

        scores[role] = sum(values) / len(values)

    return scores


def build_player_features(home_name, away_name):
    """양 팀 선수 점수와 예측 입력용 차이를 만듭니다."""
    try:
        home = find_team(home_name)
        away = find_team(away_name)

        if home.pk == away.pk:
            raise ValueError(
                "서로 다른 팀을 선택해야 합니다."
            )

        home_scores = team_scores(home)
        away_scores = team_scores(away)

    except ValueError as exc:
        return {
            "available": False,
            "message": str(exc),
        }

    values = {}
    rows = []

    for role, column, label in ROLE_COLUMNS:
        difference = round(
            home_scores[role] - away_scores[role],
            3,
        )

        values[column] = difference

        rows.append({
            "column": column,
            "label": label,
            "home": round(home_scores[role], 3),
            "away": round(away_scores[role], 3),
            "difference": difference,
        })

    return {
        "available": True,
        "formation": FORMATION,
        "home_name": home.team_name,
        "away_name": away.team_name,
        "values": values,
        "rows": rows,
    }
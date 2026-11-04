from django.db.models import Count, Max, Q, Sum

from simulation.generator import VERSION
from simulation.tracking_metrics import TRACKING_VERSION
from simulation.tracking_models import SimulationPlayerTracking
from simulation.event_metrics import EVENT_VERSION
from simulation.event_models import SimulationPlayerEventStats


def ratio(numerator, denominator, multiplier=1):
    if (
        denominator is None
        or denominator <= 0
        or numerator is None
    ):
        return None

    return numerator / denominator * multiplier


def attach_simulation_summaries(players):
    players = list(players)

    if not players:
        return players

    ids = [player.pk for player in players]

    gps_rows = (
        SimulationPlayerTracking.objects
        .filter(
            player_id__in=ids,
            metrics_version=TRACKING_VERSION,
            data_source="synthetic",
            run__generator_version=VERSION,
        )
        .values("player_id")
        .annotate(
            count=Count("pk"),
            distance=Sum("total_distance_m"),
            seconds=Sum("tracked_seconds"),
            high_speed=Sum("high_speed_distance_m"),
            top_speed=Max("max_speed_kmh"),
            attacking=Sum("attacking_third_seconds"),
            spatial_seconds=Sum(
                "tracked_seconds",
                filter=Q(
                    attacking_third_seconds__isnull=False
                ),
            ),
        )
    )

    event_rows = (
        SimulationPlayerEventStats.objects
        .filter(
            player_id__in=ids,
            metrics_version=EVENT_VERSION,
            data_source="synthetic",
            run__generator_version=VERSION,
        )
        .values("player_id")
        .annotate(
            count=Count("pk"),
            attempts=Sum("pass_attempts"),
            successes=Sum("successful_passes"),
            interceptions_total=Sum("interceptions"),
        )
    )

    gps = {
        row["player_id"]: row
        for row in gps_rows
    }

    events = {
        row["player_id"]: row
        for row in event_rows
    }

    for player in players:
        g = gps.get(player.pk, {})
        e = events.get(player.pk, {})

        # 화면 표시용 값이며 선수 기본정보는 변경하지 않습니다.
        player.simulation_summary = {
            "gps_count": g.get("count", 0),
            "event_count": e.get("count", 0),
            "has_data": bool(g or e),
            "cells": [
                ratio(
                    g.get("distance"),
                    g.get("seconds"),
                    60,
                ),
                ratio(
                    g.get("high_speed"),
                    g.get("seconds"),
                    60,
                ),
                g.get("top_speed"),
                ratio(
                    g.get("attacking"),
                    g.get("spatial_seconds"),
                    100,
                ),
                ratio(
                    e.get("successes"),
                    e.get("attempts"),
                    100,
                ),
                ratio(
                    e.get("interceptions_total"),
                    e.get("count"),
                ),
            ],
        }

    return players
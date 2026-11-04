from django.core.paginator import Paginator
from django.db.models import Q

from simulation.models import SimulationRun
from simulation.generator import VERSION
from simulation.tracking_models import SimulationPlayerTracking
from simulation.tracking_metrics import TRACKING_VERSION
from simulation.event_models import SimulationPlayerEventStats
from simulation.event_metrics import EVENT_VERSION


GROUPS = [
    (
        "GPS 이동·속도",
        "gps",
        [
            ("tracked_seconds", "기록 시간(초)"),
            ("total_distance_m", "이동 거리(m)"),
            ("distance_per_minute", "분당 거리(m)"),
            ("avg_speed_kmh", "평균 속도(km/h)"),
            ("max_speed_kmh", "최고 속도(km/h)"),
            ("high_speed_distance_m", "고속 거리(m)"),
            ("sprint_count", "스프린트 횟수"),
            ("sprint_distance_m", "스프린트 거리(m)"),
            ("sprint_seconds", "스프린트 시간(초)"),
        ],
    ),
    (
        "GPS 활동 위치",
        "gps",
        [
            ("average_x", "평균 전진 위치(m)"),
            ("average_y", "평균 측면 위치(m)"),
            ("defensive_third_seconds", "수비 지역(초)"),
            ("middle_third_seconds", "중앙 지역(초)"),
            ("attacking_third_seconds", "공격 지역(초)"),
            ("opponent_box_entries", "상대 박스 진입"),
        ],
    ),
    (
        "패스·수비 이벤트",
        "events",
        [
            ("pass_attempts", "패스 시도"),
            ("successful_passes", "성공 패스"),
            ("failed_passes", "실패 패스"),
            ("pass_success_rate", "성공률(%)"),
            ("passes_received", "패스 수신"),
            ("forward_pass_attempts", "전진 패스 시도"),
            ("successful_forward_passes", "전진 패스 성공"),
            ("interceptions", "가로채기"),
            ("possession_seconds", "공 보유(초)"),
        ],
    ),
]


def get_player_simulation_records(player_id, page_number):
    gps_query = SimulationPlayerTracking.objects.filter(
        player_id=player_id,
        metrics_version=TRACKING_VERSION,
        data_source="synthetic",
    )

    event_query = SimulationPlayerEventStats.objects.filter(
        player_id=player_id,
        metrics_version=EVENT_VERSION,
        data_source="synthetic",
    )

    runs = (
        SimulationRun.objects
        .filter(generator_version=VERSION)
        .filter(
            Q(pk__in=gps_query.values("run_id"))
            | Q(pk__in=event_query.values("run_id"))
        )
        .order_by("-created_at", "-pk")
    )

    # 한 페이지에 가상 경기 10회씩 표시합니다.
    page = Paginator(runs, 10).get_page(page_number)

    run_ids = [
        run.pk
        for run in page.object_list
    ]

    gps = {
        record.run_id: record
        for record in gps_query.filter(run_id__in=run_ids)
    }

    events = {
        record.run_id: record
        for record in event_query.filter(run_id__in=run_ids)
    }

    groups = []

    for title, source, fields in GROUPS:
        rows = []
        records = gps if source == "gps" else events

        for run in page.object_list:
            record = records.get(run.pk)
            snapshot = run.document.get("simulation", {})

            rows.append({
                "run": run,
                "home_name": snapshot.get(
                    "home_team", {}
                ).get("name", ""),
                "away_name": snapshot.get(
                    "away_team", {}
                ).get("name", ""),
                "cells": [
                    getattr(record, key)
                    if record is not None else None
                    for key, label in fields
                ],
            })

        groups.append({
            "title": title,
            "headers": [
                label
                for key, label in fields
            ],
            "rows": rows,
        })

    return {
        "page": page,
        "groups": groups,
    }
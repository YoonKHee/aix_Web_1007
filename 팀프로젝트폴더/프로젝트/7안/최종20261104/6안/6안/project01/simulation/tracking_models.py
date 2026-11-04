from django.db import models


class SimulationPlayerTracking(models.Model):
    run = models.ForeignKey(
        "simulation.SimulationRun",
        on_delete=models.CASCADE,
        related_name="player_tracking",
        verbose_name="가상 경기",
    )

    player = models.ForeignKey(
        "player.Player",
        on_delete=models.PROTECT,
        related_name="simulation_tracking",
        verbose_name="선수",
    )

    slot_id = models.CharField(
        "가상 슬롯",
        max_length=4,
    )

    team_side = models.CharField(
        "홈·원정",
        max_length=4,
        choices=[
            ("HOME", "홈팀"),
            ("AWAY", "원정팀"),
        ],
    )

    data_source = models.CharField(
        "출처",
        max_length=20,
        default="synthetic",
        choices=[
            ("synthetic", "더미데이터"),
        ],
    )

    metrics_version = models.CharField(
        "계산 버전",
        max_length=40,
    )

    parameters = models.JSONField(
        "계산 기준",
        default=dict,
    )

    tracked_seconds = models.FloatField("위치 기록 시간(초)")
    total_distance_m = models.FloatField("총 이동 거리(m)")
    distance_per_minute = models.FloatField("분당 이동 거리(m)")
    avg_speed_kmh = models.FloatField("평균 속도(km/h)")
    max_speed_kmh = models.FloatField("최고 속도(km/h)")
    high_speed_distance_m = models.FloatField("고속 이동 거리(m)")
    sprint_count = models.PositiveIntegerField("스프린트 횟수")
    sprint_distance_m = models.FloatField("스프린트 거리(m)")
    sprint_seconds = models.FloatField("스프린트 시간(초)")



    average_x = models.FloatField(
        "평균 전진 위치(m)",
        null=True,
        blank=True,
    )

    average_y = models.FloatField(
        "평균 측면 위치(m)",
        null=True,
        blank=True,
    )

    defensive_third_seconds = models.FloatField(
        "수비 지역 시간(초)",
        null=True,
        blank=True,
    )

    middle_third_seconds = models.FloatField(
        "중앙 지역 시간(초)",
        null=True,
        blank=True,
    )

    attacking_third_seconds = models.FloatField(
        "공격 지역 시간(초)",
        null=True,
        blank=True,
    )

    opponent_box_entries = models.PositiveIntegerField(
        "상대 페널티지역 진입",
        null=True,
        blank=True,
    )
    class Meta:
        
        verbose_name = "가상 경기 선수 GPS 기록"
        verbose_name_plural = "가상 경기 선수 GPS 기록"

        constraints = [
            models.UniqueConstraint(
                fields=["run", "player", "metrics_version"],
                name="unique_simulation_player_tracking",
            ),
        ]
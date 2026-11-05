from django.db import models


class SimulationPlayerEventStats(models.Model):
    run = models.ForeignKey(
        "simulation.SimulationRun",
        on_delete=models.CASCADE,
        related_name="player_events",
        verbose_name="가상 경기",
    )

    player = models.ForeignKey(
        "player.Player",
        on_delete=models.PROTECT,
        related_name="simulation_events",
        verbose_name="선수",
    )

    slot_id = models.CharField("가상 슬롯", max_length=4)

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
    )

    metrics_version = models.CharField(
        "집계 버전",
        max_length=40,
    )

    parameters = models.JSONField(
        "집계 기준",
        default=dict,
    )

    pass_attempts = models.PositiveIntegerField("패스 시도")
    successful_passes = models.PositiveIntegerField("성공 패스")
    failed_passes = models.PositiveIntegerField("실패 패스")
    passes_received = models.PositiveIntegerField("성공 패스 수신")

    forward_pass_attempts = models.PositiveIntegerField(
        "전진 패스 시도"
    )

    successful_forward_passes = models.PositiveIntegerField(
        "전진 패스 성공"
    )

    interceptions = models.PositiveIntegerField("가로채기")
    possession_seconds = models.FloatField("공 보유 시간(초)")

    class Meta:
        verbose_name = "가상 경기 선수 이벤트 기록"
        verbose_name_plural = "가상 경기 선수 이벤트 기록"

        constraints = [
            models.UniqueConstraint(
                fields=["run", "player", "metrics_version"],
                name="unique_simulation_player_events",
            ),
        ]

    @property
    def pass_success_rate(self):
        if not self.pass_attempts:
            return None

        return round(
            self.successful_passes / self.pass_attempts * 100,
            1,
        )
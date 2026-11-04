import uuid

from django.core.exceptions import ValidationError
from django.db import models


class SimulationRun(models.Model):
    # 가상 경기마다 서로 다른 고유번호를 부여합니다.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    created_at = models.DateTimeField(
        '생성 시각',
        auto_now_add=True,
    )

    # 기존 구단 정보를 연결하되, 과거 가상 경기 기록을 보호합니다.
    home_team = models.ForeignKey(
        'team.Team',
        verbose_name='홈팀',
        on_delete=models.PROTECT,
        related_name='home_simulation_runs',
    )

    away_team = models.ForeignKey(
        'team.Team',
        verbose_name='원정팀',
        on_delete=models.PROTECT,
        related_name='away_simulation_runs',
    )

    scenario_code = models.CharField(
        '시나리오 코드',
        max_length=40,
    )

    scenario_name = models.CharField(
        '시나리오 이름',
        max_length=100,
    )

    generator_version = models.CharField(
        '생성 규칙 버전',
        max_length=40,
    )

    seed = models.PositiveIntegerField(
        '난수 시드',
    )

    duration_sec = models.FloatField(
        '경기 길이(초)',
    )

    frame_count = models.PositiveIntegerField(
        '위치 기록 수',
    )

    event_count = models.PositiveIntegerField(
        '이벤트 수',
    )

    source_sha256 = models.CharField(
        '원본 JSON 해시',
        max_length=64,
    )

    fingerprint = models.CharField(
        '중복 검사 해시',
        max_length=64,
        unique=True,
    )

    # 생성 당시 명단과 좌표를 그대로 보관합니다.
    document = models.JSONField(
        '명단·이벤트·트래킹 스냅샷',
    )

    parameters = models.JSONField(
        '생성 조건',
        default=dict,
    )

    validation = models.JSONField(
        '검사 결과',
        default=dict,
    )

    class Meta:
        verbose_name = '가상 경기'
        verbose_name_plural = '가상 경기'
        ordering = ['-created_at']

        constraints = [
            models.CheckConstraint(
                condition=~models.Q(
                    home_team=models.F('away_team')
                ),
                name='simulation_different_teams',
            ),
        ]

    def clean(self):
        errors = {}

        if (
            self.home_team_id is not None
            and self.home_team_id == self.away_team_id
        ):
            errors['away_team'] = '홈팀과 원정팀은 달라야 합니다.'

        if self.duration_sec is not None and self.duration_sec <= 0:
            errors['duration_sec'] = '경기 길이는 0보다 커야 합니다.'

        if (
            not isinstance(self.document, dict)
            or self.document.get('is_synthetic') is not True
        ):
            errors['document'] = '가상 데이터만 저장할 수 있습니다.'

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return (
            f'{self.home_team} 대 {self.away_team}'
            f' / {self.scenario_name}'
        )

class SimulationTeamSummary(models.Model):
    run = models.ForeignKey(
        SimulationRun,
        on_delete=models.CASCADE,
        related_name="team_summaries",
        verbose_name="가상 경기",
    )

    side = models.CharField(
        "홈·원정",
        max_length=4,
        choices=[
            ("HOME", "홈팀"),
            ("AWAY", "원정팀"),
        ],
    )

    metrics_version = models.CharField(
        "집계 버전",
        max_length=40,
    )

    distance_m = models.FloatField("팀 전체 이동 거리(m)")
    pass_attempts = models.PositiveIntegerField("패스 시도")
    successful_passes = models.PositiveIntegerField("성공 패스")
    interceptions = models.PositiveIntegerField("가로채기")
    possession_seconds = models.FloatField("공 보유 시간(초)")

    updated_at = models.DateTimeField(
        "집계 시각",
        auto_now=True,
    )

    class Meta:
        verbose_name = "가상 경기 팀 통계"
        verbose_name_plural = "가상 경기 팀 통계"

        constraints = [
            models.UniqueConstraint(
                fields=["run", "side", "metrics_version"],
                name="unique_simulation_team_summary",
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
from .tracking_models import SimulationPlayerTracking
from .event_models import SimulationPlayerEventStats
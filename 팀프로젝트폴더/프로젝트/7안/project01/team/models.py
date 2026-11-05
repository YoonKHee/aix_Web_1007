from django.db import models


class Team(models.Model):
    team_name = models.CharField(max_length=100)
    league = models.CharField(max_length=50)
    stadium = models.CharField(max_length=100, blank=True)

    # 구단 로고
    logo = models.ImageField(
        upload_to='team_logos/',
        blank=True
    )

    def __str__(self):
        return self.team_name

class MatchResult(models.Model):
    TEAM_CHOICES = [
        ('K21', '강원'),
        ('K22', '광주'),
        ('K35', '김천'),
        ('K10', '대전'),
        ('K26', '부천'),
        ('K09', '서울'),
        ('K27', '안양'),
        ('K01', '울산'),
        ('K18', '인천'),
        ('K05', '전북'),
        ('K04', '제주'),
        ('K03', '포항'),
    ]

    match_date = models.DateField('경기 날짜')
    round = models.PositiveSmallIntegerField('라운드')

    home_team_id = models.CharField(
        '홈팀', max_length=3, choices=TEAM_CHOICES
    )
    away_team_id = models.CharField(
        '원정팀', max_length=3, choices=TEAM_CHOICES
    )

    home_goals = models.PositiveSmallIntegerField('홈 득점')
    away_goals = models.PositiveSmallIntegerField('원정 득점')

    official_match_id = models.PositiveIntegerField(
        '공식 경기 ID',
        null=True,
        blank=True,
        unique=True,
        help_text='모르면 비워 두세요.',
    )

    updated_at = models.DateTimeField('최종 수정', auto_now=True)

    class Meta:
        verbose_name = '경기 결과'
        verbose_name_plural = '경기 결과'
        ordering = ['-match_date', '-pk']

        constraints = [
            models.UniqueConstraint(
                fields=['match_date', 'home_team_id', 'away_team_id'],
                name='unique_prediction_fixture',
            ),
            models.CheckConstraint(
                condition=~models.Q(
                    home_team_id=models.F('away_team_id')
                ),
                name='different_prediction_teams',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone

        errors = {}

        if self.home_team_id == self.away_team_id:
            errors['away_team_id'] = '홈팀과 원정팀은 달라야 합니다.'

        if self.match_date:
            if (
                self.match_date.year != 2026
                or self.match_date > timezone.localdate()
            ):
                errors['match_date'] = '2026년의 종료된 경기만 입력하세요.'

        if self.round is not None and not 1 <= self.round <= 38:
            errors['round'] = '라운드는 1~38 사이여야 합니다.'

        if errors:
            raise ValidationError(errors)

    @property
    def result(self):
        if self.home_goals > self.away_goals:
            return 'H'
        if self.home_goals < self.away_goals:
            return 'A'
        return 'D'

    def __str__(self):
        return (
            f'{self.match_date} '
            f'{self.get_home_team_id_display()} '
            f'{self.home_goals}:{self.away_goals} '
            f'{self.get_away_team_id_display()}'
        )
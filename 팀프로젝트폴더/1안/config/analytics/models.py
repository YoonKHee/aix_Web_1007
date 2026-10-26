from django.db import models

# 1. 선수 마스터 테이블 (고유 신원 관리)
class Player(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="선수명")
    position = models.CharField(max_length=10, verbose_name="주 포지션")
    
    def __str__(self):
        return f"{self.name} ({self.position})"

# 2. 시즌별·팀별 상세 기록 테이블 (이적 및 연도별 성적 관리)
class PlayerSeason(models.Model):
    # 어떤 선수의 기록인지 연결 (ForeignKey)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="seasons", verbose_name="선수")
    year = models.IntegerField(verbose_name="시즌 연도") # 예: 2026
    team = models.CharField(max_length=50, verbose_name="소속 팀") # 예: 강원
    back_number = models.IntegerField(default=0, verbose_name="등번호")
    minutes_played = models.IntegerField(default=0, verbose_name="출전시간(분)")
    
    # 주요 경기 지표들
    goals = models.IntegerField(default=0, verbose_name="득점")
    assists = models.IntegerField(default=0, verbose_name="도움")
    shots = models.IntegerField(default=0, verbose_name="슈팅")
    shots_on_target = models.IntegerField(default=0, verbose_name="유효 슈팅")
    passes_attempted = models.IntegerField(default=0, verbose_name="패스 시도")
    passes_success = models.IntegerField(default=0, verbose_name="패스 성공")
    key_passes = models.IntegerField(default=0, verbose_name="키패스")
    prog_passes_attempted = models.IntegerField(default=0, verbose_name="전방 패스 시도")
    prog_passes_success = models.IntegerField(default=0, verbose_name="전방 패스 성공")
    tackles_attempted = models.IntegerField(default=0, verbose_name="태클 시도")
    tackles_success = models.IntegerField(default=0, verbose_name="태클 성공")
    aerial_attempted = models.IntegerField(default=0, verbose_name="공중볼 경합 시도")
    aerial_won = models.IntegerField(default=0, verbose_name="공중볼 경합 성공")
    clearances = models.IntegerField(default=0, verbose_name="클리어링")
    interceptions = models.IntegerField(default=0, verbose_name="인터셉트")

    class Meta:
        unique_together = ('player', 'year', 'team')

    def __str__(self):
        return f"[{self.year}] {self.player.name} - {self.team}"
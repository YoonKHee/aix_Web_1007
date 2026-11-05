from django.db import models


class ImportBatch(models.Model):
    """업로드 1회 = 1건. 점검 결과(plan)와 반영 결과를 보관한다."""
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150, blank=True)
    filenames = models.TextField(blank=True)
    season = models.IntegerField(default=2026)
    status = models.CharField(max_length=20, default='검토중')   # 검토중 / 반영됨
    plan = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    schema_file = models.CharField(max_length=300, blank=True)   # 새 컬럼 승인 때 만든 변경 기록 파일

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.status}'


class StatColumn(models.Model):
    """승인된 추가 컬럼 목록 (DB 구조에 없던 새 항목). 한 번 승인되면 다음 업로드부터는 묻지 않고 저장한다."""
    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=10, default='float')     # int / float / text
    approved_at = models.DateTimeField(auto_now_add=True)
    batch = models.ForeignKey(ImportBatch, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class ExtraStat(models.Model):
    """승인된 추가 컬럼 값을 선수·시즌별로 저장"""
    player = models.ForeignKey('player.Player', on_delete=models.CASCADE)
    season = models.IntegerField(default=2026)
    data = models.JSONField(default=dict)

    class Meta:
        unique_together = ('player', 'season')

    def __str__(self):
        return f'{self.player} {self.season}'


class ScoreConfig(models.Model):
    """점수 기준 설정 (1건만 사용): 가중치, 최소 출전시간, 제외 선수 관리 여부"""
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class ScoreConfigLog(models.Model):
    """점수 기준을 바꾼 기록 (누가, 언제, 무엇을)"""
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']


class BestExclusion(models.Model):
    """BEST11 계산에서 제외할 선수"""
    player = models.OneToOneField('player.Player', on_delete=models.CASCADE)
    reason = models.CharField(max_length=200, blank=True)
    snapshot = models.CharField(max_length=200, blank=True)    # 나중에 DB가 바뀌어도 누구였는지 알 수 있게
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.snapshot or str(self.player_id)

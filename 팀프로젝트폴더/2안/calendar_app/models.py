from django.db import models

class ExamEvent(models.Model):
    event_id = models.CharField(max_length=64, unique=True, primary_key=True)
    source = models.CharField(max_length=20)       # 'qnet', 'civil', 'public'
    institution = models.CharField(max_length=100)  # 주관 기관명
    title = models.CharField(max_length=255)        # 시험/공고명
    event_type = models.CharField(max_length=20)    # 'APPLY'(접수), 'EXAM'(시험), 'PASS'(발표)
    start_date = models.DateField()
    end_date = models.DateField()
    official_url = models.URLField(max_length=500)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.event_type}] {self.title} ({self.start_date} ~ {self.end_date})"
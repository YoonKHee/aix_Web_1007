from django.contrib import admin
from .models import ImportBatch, StatColumn, ExtraStat, ScoreConfig, ScoreConfigLog, BestExclusion

admin.site.register(ImportBatch)
admin.site.register(StatColumn)
admin.site.register(ExtraStat)
admin.site.register(ScoreConfig)
admin.site.register(ScoreConfigLog)
admin.site.register(BestExclusion)

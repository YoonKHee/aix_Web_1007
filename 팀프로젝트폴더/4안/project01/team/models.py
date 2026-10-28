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
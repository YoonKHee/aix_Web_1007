from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=50)
    league = models.CharField(max_length=30, default="K리그1")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["league", "name"], name="unique_team_per_league"),
        ]

    def __str__(self):
        return self.name


class Player(models.Model):
    class Position(models.TextChoices):
        GK = "GK", "골키퍼"
        DF = "DF", "수비수"
        MF = "MF", "미드필더"
        FW = "FW", "공격수"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=50)
    position = models.CharField(max_length=2, choices=Position.choices)
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    weight_kg = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    stats = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "name"], name="unique_player_per_team"),
        ]

    def __str__(self):
        return f"{self.name} ({self.team.name}, {self.position})"
from django.db import models
from team.models import Team


# =========================================================
# 선수 기본정보
# =========================================================
class Player(models.Model):

    # 소속팀
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE
    )

    # 선수명
    name = models.CharField(
        max_length=100
    )

    # 등번호
    number = models.IntegerField(
        default=0
    )

    # 포지션
    position = models.CharField(
        max_length=20
    )

    # 기존 필드
    # 기존 DB 보호를 위해 우선 유지
    age = models.IntegerField(
        default=0
    )

    # 키
    height = models.IntegerField(
        default=0
    )

    # 몸무게
    weight = models.IntegerField(
        default=0
    )

    # 생년월일
    birth_date = models.DateField(
        null=True,
        blank=True
    )

    # 선수 사진
    photo = models.ImageField(
        upload_to='players/',
        blank=True
    )

    def __str__(self):
        return f'{self.team},{self.name},{self.number},{self.position}'


# =========================================================
# 선수 시즌별 기록
# =========================================================
class PlayerStats(models.Model):

    # 어떤 선수의 기록인지 연결
    player = models.ForeignKey(Player, on_delete=models.CASCADE)


    # -----------------------------------------------------
    # 1. 시즌
    # 원본 : 년도
    # -----------------------------------------------------
    season = models.IntegerField(default=2026)


    # -----------------------------------------------------
    # 2. 기본 기록
    # -----------------------------------------------------

    # 원본 : 출전시간(분)
    minutes = models.IntegerField(default=0)

    # 원본 : 득점
    goals = models.IntegerField(default=0)

    # 원본 : 도움
    assists = models.IntegerField(default=0)

    # -----------------------------------------------------
    # 새 JSON 선수성적에서 추가되는 기록
    # -----------------------------------------------------

    # 경기 출전 수
    games = models.IntegerField(default=0)

    # 공격포인트
    attack_points = models.IntegerField(default=0)

    # PK 득점
    pk_goals = models.IntegerField(default=0)

    # MOM 선정 횟수
    mom = models.IntegerField(default=0)

    # 평균 평점
    average_rating = models.FloatField(default=0)

    # BEST11 선정 횟수
    best11_count = models.IntegerField(default=0)

    # PK 기록
    pk_attempts = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 3. 슈팅
    # -----------------------------------------------------

    # 원본 : 슈팅
    shots = models.IntegerField(default=0)

    # 원본 : 유효 슈팅
    shots_on_target = models.IntegerField(default=0)

    # 원본 : 차단된슈팅
    shots_blocked = models.IntegerField(default=0)

    # 원본 : 벗어난슈팅
    shots_off_target = models.IntegerField(default=0)

    # 원본 : PA내 슈팅
    shots_inside_box = models.IntegerField(default=0)

    # 원본 : PA외 슈팅
    shots_outside_box = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 4. 공격 기타
    # -----------------------------------------------------

    # 원본 : 오프사이드
    offsides = models.IntegerField(default=0)

    # 원본 : 프리킥
    free_kicks = models.IntegerField(default=0)

    # 원본 : 코너킥
    corner_kicks = models.IntegerField(default=0)

    # 원본 : 스로인
    throw_ins = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 5. 드리블
    # -----------------------------------------------------

    # 원본 : 드리블 - 시도
    dribble_attempt = models.IntegerField(default=0)

    # 원본 : 드리블 - 성공
    dribble_success = models.IntegerField(default=0)

    # 드리블 성공%는 DB에 저장하지 않음
    # 성공 / 시도 * 100 으로 계산


    # -----------------------------------------------------
    # 6. 전체 패스
    # -----------------------------------------------------

    # 원본 : 패스 - 시도
    pass_attempt = models.IntegerField(default=0)

    # 원본 : 패스 - 성공
    pass_success = models.IntegerField(default=0)

    # 원본 : 키패스
    key_passes = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 7. 전방 패스
    # -----------------------------------------------------

    # 원본 : 전방 패스 - 시도
    forward_pass_attempt = models.IntegerField(default=0)

    # 원본 : 전방 패스 - 성공
    forward_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 8. 후방 패스
    # -----------------------------------------------------

    # 원본 : 후방 패스 - 시도
    backward_pass_attempt = models.IntegerField(default=0)

    # 원본 : 후방 패스 - 성공
    backward_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 9. 횡패스
    # -----------------------------------------------------

    # 원본 : 횡패스 - 시도
    lateral_pass_attempt = models.IntegerField(default=0)

    # 원본 : 횡패스 - 성공
    lateral_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 10. 공격지역패스
    # -----------------------------------------------------

    # 원본 : 공격지역패스 - 시도
    attacking_third_pass_attempt = models.IntegerField(default=0)

    # 원본 : 공격지역패스 - 성공
    attacking_third_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 11. 수비지역패스
    # -----------------------------------------------------

    # 원본 : 수비지역패스 - 시도
    defensive_third_pass_attempt = models.IntegerField(default=0)

    # 원본 : 수비지역패스 - 성공
    defensive_third_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 12. 중앙지역패스
    # -----------------------------------------------------

    # 원본 : 중앙지역패스 - 시도
    middle_third_pass_attempt = models.IntegerField(default=0)

    # 원본 : 중앙지역패스 - 성공
    middle_third_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 13. 롱패스
    # -----------------------------------------------------

    # 원본 : 롱패스 - 시도
    long_pass_attempt = models.IntegerField(default=0)

    # 원본 : 롱패스 - 성공
    long_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 14. 중거리패스
    # -----------------------------------------------------

    # 원본 : 중거리패스 - 시도
    medium_pass_attempt = models.IntegerField(default=0)

    # 원본 : 중거리패스 - 성공
    medium_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 15. 숏패스
    # -----------------------------------------------------

    # 원본 : 숏패스 - 시도
    short_pass_attempt = models.IntegerField(default=0)

    # 원본 : 숏패스 - 성공
    short_pass_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 16. 크로스
    # -----------------------------------------------------

    # 원본 : 크로스 - 시도
    cross_attempt = models.IntegerField(default=0)

    # 원본 : 크로스 - 성공
    cross_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 17. 탈압박
    # -----------------------------------------------------

    # 원본에는 탈압박 시도/성공이 따로 없고
    # '탈압박' 하나의 컬럼만 존재
    escape_pressure = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 18. 지상 경합
    # -----------------------------------------------------

    # 원본 : 경합 지상 - 시도
    ground_duel_attempt = models.IntegerField(default=0)

    # 원본 : 경합 지상 - 성공
    ground_duel_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 19. 공중 경합
    # -----------------------------------------------------

    # 원본 : 경합 공중 - 시도
    aerial_duel_attempt = models.IntegerField(default=0)

    # 원본 : 경합 공중 - 성공
    aerial_duel_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 20. 태클
    # -----------------------------------------------------

    # 원본 : 태클 - 시도
    tackle_attempt = models.IntegerField(default=0)

    # 원본 : 태클 - 성공
    tackle_success = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 21. 수비 기록
    # -----------------------------------------------------

    # 원본 : 클리어링
    clearances = models.IntegerField(default=0)

    # 원본 : 인터셉트
    interceptions = models.IntegerField(default=0)

    # 원본 : 차단
    defensive_blocks = models.IntegerField(default=0)

    # 원본 : 획득
    recoveries = models.IntegerField(default=0)

    # 원본 : 블락
    blocks = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 22. 볼미스
    # -----------------------------------------------------

    # 원본 : 볼미스
    ball_misses = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 23. 파울
    # -----------------------------------------------------

    # 원본 : 파울
    fouls = models.IntegerField(default=0)

    # 원본 : 피파울
    fouls_won = models.IntegerField(default=0)


    # -----------------------------------------------------
    # 24. 카드
    # -----------------------------------------------------

    # 원본 : 경고
    yellow_cards = models.IntegerField(default=0)

    # 원본 : 퇴장
    red_cards = models.IntegerField(default=0)
    #----------------------------------------------------------
    
        # 패스 성공률
    def pass_success_rate(self):

        if self.pass_attempt == 0:
            return 0

        return round(
            self.pass_success / self.pass_attempt * 100,
            1
        )


    # 드리블 성공률
    def dribble_success_rate(self):

        if self.dribble_attempt == 0:
            return 0

        return round(
            self.dribble_success / self.dribble_attempt * 100,
            1
        )


    # 크로스 성공률
    def cross_success_rate(self):

        if self.cross_attempt == 0:
            return 0

        return round(
            self.cross_success / self.cross_attempt * 100,
            1
        )


    # 지상 경합 성공률
    def ground_duel_success_rate(self):

        if self.ground_duel_attempt == 0:
            return 0

        return round(
            self.ground_duel_success / self.ground_duel_attempt * 100,
            1
        )


    # 공중 경합 성공률
    def aerial_duel_success_rate(self):

        if self.aerial_duel_attempt == 0:
            return 0

        return round(
            self.aerial_duel_success / self.aerial_duel_attempt * 100,
            1
        )


    # 태클 성공률
    def tackle_success_rate(self):

        if self.tackle_attempt == 0:
            return 0

        return round(
            self.tackle_success / self.tackle_attempt * 100,
            1
        )
    #----------------------------------------------------------
        # ==========================================
    # 90분당 기록 계산
    # ==========================================
    def per90(self, value):

        # 출전시간이 0분이면 계산할 수 없으므로 0 반환
        if self.minutes == 0:
            return 0

        # 기록 ÷ 출전시간 × 90
        return round(
            value / self.minutes * 90,
            2
        )


    # 90분당 득점
    def goals_per90(self):
        return self.per90(self.goals)


    # 90분당 도움
    def assists_per90(self):
        return self.per90(self.assists)


    # 90분당 슈팅
    def shots_per90(self):
        return self.per90(self.shots)


    # 90분당 유효슈팅
    def shots_on_target_per90(self):
        return self.per90(self.shots_on_target)


    # 90분당 키패스
    def key_passes_per90(self):
        return self.per90(self.key_passes)


    # 90분당 드리블 성공
    def dribble_success_per90(self):
        return self.per90(self.dribble_success)


    # 90분당 인터셉트
    def interceptions_per90(self):
        return self.per90(self.interceptions)


    # 90분당 클리어링
    def clearances_per90(self):
        return self.per90(self.clearances)


    # 90분당 획득
    def recoveries_per90(self):
        return self.per90(self.recoveries)


    # 90분당 태클 성공
    def tackle_success_per90(self):
        return self.per90(self.tackle_success)


    # -----------------------------------------------------
    # 관리자 페이지 등에 표시되는 이름
    # -----------------------------------------------------
    def __str__(self):
        return f'{self.player.name} - {self.season}'
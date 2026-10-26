import os
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from analytics.models import Player, PlayerSeason

class Command(BaseCommand):
    help = '공용 data 폴더의 엑셀 파일을 자동으로 읽어와 DB에 적재합니다.'

    def handle(self, *args, **kwargs):
        # 1. 프로젝트 최상위의 공용 data 폴더 경로 찾기
        data_dir = os.path.join(settings.BASE_DIR, 'data')
        
        if not os.path.exists(data_dir):
            self.stdout.write(self.style.ERROR(f"공용 data 폴더를 찾을 수 없습니다: {data_dir}"))
            return

        # 2. data 폴더 안에서 엑셀 파일들만 쏙쏙 골라내기
        excel_files = [f for f in os.listdir(data_dir) if f.endswith('.xls') or f.endswith('.xlsx')]
        
        if not excel_files:
            self.stdout.write(self.style.WARNING("적재할 엑셀 파일이 없습니다."))
            return

        for filename in excel_files:
            file_path = os.path.join(data_dir, filename)
            
            # 3. 파일 이름(예: 2026_강원.xls)에서 연도와 팀명 자동 추출
            parts = filename.split('_')
            try:
                year = int(parts[0])
                team_name = parts[1].split('.')[0]
            except (IndexError, ValueError):
                self.stdout.write(self.style.WARNING(f"파일명 형식 불일치 (예: 2026_강원.xls): {filename}"))
                continue

            # 4. Pandas로 엑셀 파일 읽기 (HTML 테이블 형태 파싱)
            try:
                tables = pd.read_html(file_path)
                df = tables[4] # 선수 상세 기록 테이블
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"파일 읽기 실패 {filename}: {e}"))
                continue

            count = 0
            for idx, row in df.iterrows():
                name = row.get(('선수명', '선수명'))
                position = row.get(('포지션', '포지션'))
                
                if pd.isna(name) or name == '합계':
                    continue

                # 5. 선수 마스터 생성 또는 가져오기 (이적해도 고유 ID 유지)
                player_obj, created = Player.objects.get_or_create(
                    name=name,
                    defaults={'position': position}
                )

                # 6. 시즌별/팀별 기록 생성 또는 갱신 (update_or_create)
                PlayerSeason.objects.update_or_create(
                    player=player_obj,
                    year=year,
                    team=team_name,
                    defaults={
                        'back_number': int(row.get(('등번호', '등번호'), 0) if pd.notna(row.get(('등번호', '등번호'))) else 0),
                        'minutes_played': int(row.get(('출전시간(분)', '출전시간(분)'), 0)),
                        'goals': int(row.get(('득점', '득점'), 0)),
                        'assists': int(row.get(('도움', '도움'), 0)),
                        'shots': int(row.get(('슈팅', '슈팅'), 0)),
                        'shots_on_target': int(row.get(('유효 슈팅', '유효 슈팅'), 0)),
                        'passes_attempted': int(row.get(('패스', '시도'), 0)),
                        'passes_success': int(row.get(('패스', '성공'), 0)),
                        'key_passes': int(row.get(('키패스', '키패스'), 0)),
                        'prog_passes_attempted': int(row.get(('전방 패스', '시도'), 0)),
                        'prog_passes_success': int(row.get(('전방 패스', '성공'), 0)),
                        'tackles_attempted': int(row.get(('태클', '시도'), 0)),
                        'tackles_success': int(row.get(('태클', '성공'), 0)),
                        'aerial_attempted': int(row.get(('경합 공중', '시도'), 0)),
                        'aerial_won': int(row.get(('경합 공중', '성공'), 0)),
                        'clearances': int(row.get(('클리어링', '클리어링'), 0)),
                        'interceptions': int(row.get(('인터셉트', '인터셉트'), 0)),
                    }
                )
                count += 1

            self.stdout.write(self.style.SUCCESS(f"[{filename}] 성공적으로 {count명의 선수 기록 적재 완료!"))